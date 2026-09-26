#!/usr/bin/env node
/* Meridyen bildirim sunucusu.
 *
 * NE YAPAR: Realtime Database'deki `bildirimKuyrugu` düğümünü dinler. Biri
 * mesaj/çağrı gönderdiğinde istemci oraya bir kayıt bırakıyor; bu sunucu o
 * kaydı anında yakalayıp hedefin CİHAZLARINA (Android + web) FCM push'u
 * gönderiyor ve kaydı siliyor.
 *
 * NEDEN GEREKLİ: uygulama tamamen kapalıyken (görev listesinden atılmış ya da
 * hiç açılmamış) tarayıcıda çalışan hiçbir kod kalmıyor; bildirimi yalnız
 * Google'ın push altyapısı teslim edebiliyor. Uygulama AÇIKKEN bildirimler
 * zaten yerelde çiziliyor, bu sunucu ona karışmıyor (yerli taraf öndeyse
 * push'u yok sayıyor, web tarafında da service worker yalnız sayfa kapalı/
 * arka plandayken çalışıyor).
 *
 * ÇALIŞTIRMA: README.md — üç adım (servis hesabı anahtarı, npm install, npm start).
 */
'use strict';

const http = require('http');
const admin = require('firebase-admin');
const B = require('./bildirim');

/* ---- ayarlar ---- */
const VERITABANI = process.env.MERIDYEN_DB ||
  'https://meridyen-830fb-default-rtdb.europe-west1.firebasedatabase.app';
const KUYRUK = process.env.MERIDYEN_KUYRUK || 'bildirimKuyrugu';
const PORT = Number(process.env.PORT || 8080);
/* Sunucu uzun süre kapalı kaldıysa birikmiş ESKİ bildirimleri göndermek
   kullanıcıyı gece yarısı uyandırmaktan başka işe yaramaz: bu yaştan
   büyükleri sessizce siliyoruz. */
const EN_ESKI_DK = Number(process.env.MERIDYEN_EN_ESKI_DK || 30);
const EN_COK_DENEME = 5;
/* TEK SEFER kipi: kuyruk boşalınca çık. Sınama için ve "sunucuyu sürekli
   çalıştıramıyorum, zamanlanmış görevle ara ara boşaltayım" senaryosu için. */
const TEK_SEFER = process.env.MERIDYEN_TEK_SEFER === '1';

/* ---- kimlik ---- */
function kimlikAl() {
  const satir = process.env.MERIDYEN_SERVIS_HESABI;      // JSON'un kendisi
  if (satir) {
    try {
      return admin.credential.cert(JSON.parse(satir));
    } catch (e) {
      cik('MERIDYEN_SERVIS_HESABI okunamadı (geçerli JSON değil): ' + e.message);
    }
  }
  if (process.env.GOOGLE_APPLICATION_CREDENTIALS) {
    return admin.credential.applicationDefault();        // dosya yolu
  }
  cik('Servis hesabı anahtarı yok.\n' +
      'Ya MERIDYEN_SERVIS_HESABI ortam değişkenine anahtarın JSON içeriğini koy,\n' +
      'ya da GOOGLE_APPLICATION_CREDENTIALS ile dosya yolunu ver. (bkz. README.md)');
}

function cik(mesaj) {
  console.error('\n[HATA] ' + mesaj + '\n');
  process.exit(1);
}

function gunluk() {
  const d = new Date().toISOString().replace('T', ' ').slice(0, 19);
  console.log('[' + d + ']', Array.prototype.join.call(arguments, ' '));
}

/* ---- kurulum ---- */
admin.initializeApp({ credential: kimlikAl(), databaseURL: VERITABANI });
const db = admin.database();
const fcm = admin.messaging();

const sayac = { alinan: 0, gonderilen: 0, basarisiz: 0, atilanBelirtec: 0, eski: 0, hatali: 0 };
const denemeler = new Map();          // kayıt anahtarı -> deneme sayısı

/* ---- tek bir kuyruk kaydını işle ---- */
async function kaydiIsle(anahtar, kayit) {
  const ref = db.ref(KUYRUK + '/' + anahtar);

  if (!B.kayitGecerliMi(kayit)) {
    sayac.hatali++;
    gunluk('geçersiz kayıt atıldı:', anahtar);
    await ref.remove();
    return;
  }

  const yas = Date.now() - Number(kayit.ts || 0);
  if (kayit.ts && yas > EN_ESKI_DK * 60 * 1000) {
    sayac.eski++;
    gunluk('eski kayıt atıldı (' + Math.round(yas / 60000) + ' dk):', anahtar);
    await ref.remove();
    return;
  }

  const an = await db.ref('cihazlar/' + kayit.hedef).once('value');
  const cihazlar = an.val() || {};
  const isler = B.mesajlariKur(kayit, cihazlar);
  if (!isler.length) {
    gunluk('hedefin kayıtlı cihazı yok:', kayit.hedef.slice(0, 8));
    await ref.remove();
    return;
  }

  const sonuc = await fcm.sendEach(isler.map((i) => i.mesaj));
  sayac.gonderilen += sonuc.successCount;
  sayac.basarisiz += sonuc.failureCount;

  /* Ölü belirteçleri temizle: yoksa her mesajda aynı hata tekrarlanır ve
     kota boşa gider. */
  const silinecek = [];
  sonuc.responses.forEach((yanit, i) => {
    if (yanit.success) return;
    const hata = yanit.error;
    if (B.belirtecOlduMu(hata)) {
      silinecek.push(isler[i].anahtar);
    } else {
      gunluk('gönderilemedi (' + (hata && hata.code) + '):', isler[i].anahtar);
    }
  });
  for (const a of silinecek) {
    sayac.atilanBelirtec++;
    await db.ref('cihazlar/' + kayit.hedef + '/' + a).remove().catch(() => {});
  }

  gunluk('gönderildi:', kayit.tur || 'mesaj',
         '→', kayit.hedef.slice(0, 8),
         '| cihaz ' + sonuc.successCount + '/' + isler.length +
         (silinecek.length ? ' | ölü belirteç ' + silinecek.length : ''));
  await ref.remove();
}

/* Sıraya alarak işle: aynı anda onlarca kayıt gelse bile FCM'i ve
   veritabanını boğmayalım, sıra korunsun. */
let zincir = Promise.resolve();
function sirayaAl(anahtar, kayit) {
  sayac.alinan++;
  zincir = zincir.then(() => kaydiIsle(anahtar, kayit)).catch(async (hata) => {
    const sayi = (denemeler.get(anahtar) || 0) + 1;
    denemeler.set(anahtar, sayi);
    if (B.geciciHataMi(hata) && sayi < EN_COK_DENEME) {
      const bekle = Math.min(30000, 1000 * Math.pow(2, sayi));
      gunluk('geçici hata, ' + Math.round(bekle / 1000) + ' sn sonra yeniden (' +
             sayi + '/' + EN_COK_DENEME + '):', hata.message);
      await new Promise((r) => setTimeout(r, bekle));
      sirayaAl(anahtar, kayit);
      return;
    }
    gunluk('KAYIT İŞLENEMEDİ, atılıyor:', anahtar, '|', hata && hata.message);
    sayac.hatali++;
    denemeler.delete(anahtar);
    await db.ref(KUYRUK + '/' + anahtar).remove().catch(() => {});
  }).then(() => { denemeler.delete(anahtar); });
  return zincir;
}

/* ---- dinleme ----
   child_added, sunucu açıldığında MEVCUT kayıtlar için de tetikleniyor:
   kapalıyken biriken (ve çok eski olmayan) bildirimler böyle teslim ediliyor. */
db.ref(KUYRUK).on('child_added', (an) => sirayaAl(an.key, an.val()),
  (hata) => {
    cik('Kuyruk dinlenemedi: ' + hata.message +
        '\nServis hesabı doğru projeye mi ait? Veritabanı adresi doğru mu?\n' + VERITABANI);
  });

db.ref('.info/connected').on('value', (an) => {
  gunluk(an.val() ? 'veritabanına bağlandı' : 'veritabanı bağlantısı koptu (kendiliğinden denenecek)');
});

/* ---- sağlık ucu ----
   Ücretsiz barındırma sağlayıcılarının çoğu açık bir port istiyor; ayrıca
   tarayıcıdan bakıp "çalışıyor mu" sorusunu yanıtlamayı kolaylaştırıyor. */
http.createServer((istek, yanit) => {
  yanit.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
  yanit.end(JSON.stringify({
    durum: 'çalışıyor',
    veritabani: VERITABANI,
    kuyruk: KUYRUK,
    calismaSuresiSn: Math.round(process.uptime()),
    sayac: sayac
  }, null, 1));
}).listen(PORT, () => gunluk('sağlık ucu: http://localhost:' + PORT));

gunluk('Meridyen bildirim sunucusu başladı. Kuyruk:', KUYRUK,
       TEK_SEFER ? '(tek sefer kipi)' : '');

/* Tek sefer kipi: kuyruk boşalıp iş bitince düzgünce çık. */
if (TEK_SEFER) {
  const BOSTA_MS = Number(process.env.MERIDYEN_BOSTA_MS || 1500);
  let sonIs = Date.now();
  const eskiSiraya = sirayaAl;
  const bekce = setInterval(() => {
    if (sayac.alinan !== bekce.sonAlinan) { bekce.sonAlinan = sayac.alinan; sonIs = Date.now(); return; }
    if (Date.now() - sonIs < BOSTA_MS) return;
    zincir.then(() => {
      gunluk('kuyruk boş, çıkılıyor. sayaç:', JSON.stringify(sayac));
      clearInterval(bekce);
      db.ref(KUYRUK).off();
      admin.app().delete().catch(() => {}).then(() => process.exit(0));
      setTimeout(() => process.exit(0), 2000).unref();
    });
  }, 250);
  bekce.sonAlinan = 0;
}

/* ---- düzgün kapanma ---- */
['SIGINT', 'SIGTERM'].forEach((sinyal) => {
  process.on(sinyal, () => {
    gunluk('kapanıyor (' + sinyal + ')…');
    db.ref(KUYRUK).off();
    admin.app().delete().catch(() => {}).then(() => process.exit(0));
    setTimeout(() => process.exit(0), 3000).unref();
  });
});
process.on('unhandledRejection', (e) => gunluk('yakalanmamış söz hatası:', e && e.message));
