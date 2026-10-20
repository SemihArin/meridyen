#!/usr/bin/env node
/* Meridyen bildirim sunucusu — sınamalar.
   Ağ yok, gerçek anahtar yok: saf mantık doğrudan, sunucunun tamamı ise
   sahte bir firebase-admin ile GERÇEK index.js çalıştırılarak sınanıyor. */
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const B = require('./bildirim');

const T = []; const ok = (ad, kosul) => T.push([ad, !!kosul]);

/* ================= 1. SAF MANTIK ================= */
const kayitMesaj = { hedef: 'HEDEF', gonderen: 'GONDEREN', gonderenAd: 'Semih',
                     tur: 'mesaj', baslik: 'Semih', metin: 'merhaba dünya', ts: Date.now() };
const cihazAcik = { belirtec: 'BELIRTEC_' + 'x'.repeat(30), icerikGoster: true };
const cihazKapali = { belirtec: 'BELIRTEC_' + 'y'.repeat(30), icerikGoster: false };

{
  const m = B.mesajKur(kayitMesaj, cihazAcik);
  ok('notification bloğu YOK (data-only)', m.notification === undefined);
  ok('android yüksek öncelikli', m.android.priority === 'high');
  ok('mesaj ömrü 24 saat', m.android.ttl === B.OMUR_MESAJ_SN * 1000);
  ok('webpush aciliyeti yüksek', m.webpush.headers.Urgency === 'high');
  ok('yerli taraf anahtarları var', m.data.baslik === 'Semih' && m.data.metin === 'merhaba dünya');
  ok('web taraf anahtarları var', m.data.title === 'Semih' && m.data.body === 'merhaba dünya');
  ok('gönderen taşınıyor', m.data.gonderen === 'GONDEREN');
  ok('etiket iki tarafta aynı', m.data.etiket === 'meridyen-GONDEREN' && m.data.tag === m.data.etiket);
  ok('bütün data değerleri metin', Object.values(m.data).every((v) => typeof v === 'string'));
}

{
  const m = B.mesajKur(kayitMesaj, cihazKapali);
  ok('içerik kapalıyken metin GİTMİYOR',
     !JSON.stringify(m).includes('merhaba dünya'));
  ok('içerik kapalıyken genel metin', m.data.body === 'Yeni bir mesajın var.');
  ok('içerik kapalıyken gönderen adı da gizli', m.data.title === 'Meridyen');
}

{
  const cagri = { hedef: 'H', gonderen: 'G', tur: 'arama', baslik: 'Semih',
                  metin: 'Görüntülü arıyor', aramaTuru: 'goruntu', sid: 'S1', ts: Date.now() };
  const m = B.mesajKur(cagri, cihazAcik);
  ok('çağrı türü tur=arama', m.data.tur === 'arama');
  ok('çağrı türü taşınıyor', m.data.aramaTuru === 'goruntu');
  ok('çağrı ömrü kısa', m.android.ttl === B.OMUR_CAGRI_SN * 1000);
  ok('çağrıda arayan adı gizlenmiyor', m.data.baslik === 'Semih');
  ok('sid taşınıyor', m.data.sid === 'S1');

  const eksik = { hedef: 'H', gonderen: 'G', tur: 'arama', metin: 'Sesli arıyor', ts: Date.now() };
  ok('aramaTuru yoksa metinden çıkarılıyor', B.aramaTuru(eksik) === 'ses');
  ok('görüntülü metinden çıkarılıyor',
     B.aramaTuru({ tur: 'arama', metin: 'Görüntülü arıyor' }) === 'goruntu');
  const kapaliCagri = B.mesajKur(cagri, cihazKapali);
  ok('içerik kapalıyken çağrıda da metin yok', kapaliCagri.data.metin === 'Arıyor');
}

{
  const cihazlar = {
    a: cihazAcik, b: cihazKapali,
    c: { belirtec: 'kisa' },                 // geçersiz
    d: { ts: 1 },                            // belirteç yok
    e: null
  };
  const liste = B.mesajlariKur(kayitMesaj, cihazlar);
  ok('bozuk cihaz kayıtları atlanıyor', liste.length === 2);
  ok('cihaz anahtarı taşınıyor', liste[0].anahtar === 'a' && liste[1].anahtar === 'b');
}

{
  ok('geçersiz kayıt eleniyor',
     !B.kayitGecerliMi(null) && !B.kayitGecerliMi({}) && !B.kayitGecerliMi({ hedef: 'x' }));
  ok('geçerli kayıt kabul', B.kayitGecerliMi(kayitMesaj));
  ok('ölü belirteç tanınıyor',
     B.belirtecOlduMu({ code: 'messaging/registration-token-not-registered' }) &&
     B.belirtecOlduMu({ code: 'messaging/invalid-registration-token' }));
  ok('geçici hata ölü sayılmıyor', !B.belirtecOlduMu({ code: 'messaging/server-unavailable' }));

  /* ---- BELİRTEÇ SİLMEDE AŞIRI CÖMERTLİK TEHLİKESİ ----
     Yanlış servis hesabıyla kurulumda HER gönderim hata veriyor; o hatada
     belirteç silinirse veritabanındaki bütün cihaz kayıtları tek seferde
     uçuyor ve anahtar düzeltilse bile kimse bildirim alamıyor. */
  ok('kurulum hatası belirteci ÖLDÜ saymıyor',
     !B.belirtecOlduMu({ code: 'messaging/mismatched-credential' }));
  ok('kurulum hatası ayrıca tanınıyor',
     B.kurulumHatasiMi({ code: 'messaging/mismatched-credential' }) &&
     B.kurulumHatasiMi({ errorInfo: { code: 'app/invalid-credential' } }));
  ok('kurulum hatası geçici sayılmıyor',
     !B.geciciHataMi({ code: 'messaging/mismatched-credential' }));

  /* invalid-argument hem bozuk belirteç hem bozuk YÜK için dönüyor:
     yalnız metin belirteci işaret ediyorsa silinmeli. */
  ok('invalid-argument + belirteç metni → ölü',
     B.belirtecOlduMu({ code: 'messaging/invalid-argument',
                        message: 'The registration token is not a valid FCM registration token' }));
  ok('invalid-argument + YÜK hatası → ölü DEĞİL',
     !B.belirtecOlduMu({ code: 'messaging/invalid-argument',
                         message: 'Invalid value at data.ttl (TYPE_STRING)' }));
  ok('invalid-argument metinsiz → ölü DEĞİL (emniyetli taraf)',
     !B.belirtecOlduMu({ code: 'messaging/invalid-argument' }));
  ok('errorInfo içindeki metin de okunuyor',
     B.belirtecOlduMu({ errorInfo: { code: 'messaging/invalid-argument',
                                     message: 'not a valid FCM registration token' } }));
  ok('geçici hata tanınıyor',
     B.geciciHataMi({ code: 'messaging/server-unavailable' }) &&
     B.geciciHataMi({ message: 'socket hang up' }));
}

/* ================= 2. UÇTAN UCA (gerçek index.js, sahte admin) ================= */
const SINAMA = path.join(__dirname, 'sinama');
const veriYolu = path.join(SINAMA, 'veri.json');
const kayitYolu = path.join(SINAMA, 'kayit.json');

const veri = {
  bildirimKuyrugu: {
    k1: { hedef: 'AYSE', gonderen: 'SEMIH', gonderenAd: 'Semih', tur: 'mesaj',
          baslik: 'Semih', metin: 'gizli metin', ts: Date.now() },
    k2: { hedef: 'AYSE', gonderen: 'SEMIH', tur: 'arama', baslik: 'Semih',
          metin: 'Sesli arıyor', aramaTuru: 'ses', ts: Date.now() },
    kEski: { hedef: 'AYSE', gonderen: 'SEMIH', tur: 'mesaj', baslik: 'Semih',
             metin: 'dünkü mesaj', ts: Date.now() - 6 * 60 * 60 * 1000 },
    kBozuk: { gonderen: 'SEMIH', tur: 'mesaj' },
    kCihazsiz: { hedef: 'KIMSE', gonderen: 'SEMIH', tur: 'mesaj', ts: Date.now() },
    /* Hedefin belirteci sendEach'i FIRLATTIRIYOR: kalıcı geçici hata.
       Sunucu en çok EN_COK_DENEME kez denemeli, sonra kaydı atmalı. */
    kPatla: { hedef: 'PATLAYAN', gonderen: 'SEMIH', tur: 'mesaj', ts: Date.now() }
  },
  cihazlar: {
    AYSE: {
      telefon: { belirtec: 'TELEFON_' + 'a'.repeat(30), icerikGoster: true },
      masaustu: { belirtec: 'MASA_' + 'b'.repeat(30), icerikGoster: false },
      eskiCihaz: { belirtec: 'OLU_' + 'c'.repeat(30), icerikGoster: true },
      /* Yanlış servis hesabı hatası veren cihaz: SİLİNMEMELİ. */
      anahtarsiz: { belirtec: 'YANLISANAHTAR_' + 'e'.repeat(30), icerikGoster: true }
    },
    PATLAYAN: { tek: { belirtec: 'PATLA_' + 'd'.repeat(30), icerikGoster: true } }
  }
};
fs.mkdirSync(SINAMA, { recursive: true });
fs.writeFileSync(veriYolu, JSON.stringify(veri));
if (fs.existsSync(kayitYolu)) fs.unlinkSync(kayitYolu);

try {
  execFileSync(process.execPath, [path.join(__dirname, 'index.js')], {
    cwd: __dirname,
    timeout: 20000,
    env: Object.assign({}, process.env, {
      NODE_PATH: path.join(SINAMA, 'sahte-moduller'),
      MERIDYEN_SERVIS_HESABI: JSON.stringify({ type: 'service_account', project_id: 'sinama' }),
      SINAMA_VERI: veriYolu,
      SINAMA_KAYIT: kayitYolu,
      PORT: '0',
      MERIDYEN_TEK_SEFER: '1',
      /* Geri çekilme tabanını küçültüyoruz: beş denemenin gerçek beklemesi
         (2+4+8+16 sn) sınamayı yarım dakika uzatırdı. Mantık aynı, süre
         kısa. */
      MERIDYEN_GERI_CEKILME_MS: '20'
    }),
    stdio: 'pipe'
  });
  ok('sunucu tek sefer kipinde kendi kendine çıktı', true);
} catch (e) {
  ok('sunucu tek sefer kipinde kendi kendine çıktı', false);
}

const kayit = JSON.parse(fs.readFileSync(kayitYolu, 'utf8'));
const tumMesajlar = [].concat.apply([], kayit.gonderilen);

ok('sunucu doğru veritabanına bağlandı',
   /meridyen-830fb/.test((kayit.baslatma || {}).veritabani || ''));
/* AYSE'nin dört cihazı var (ikisi bilerek hatalı: ölü belirteç ve yanlış
   anahtar). Mesaj HEPSİNE birden gönderilmeli — hangisinin başarısız
   olacağına FCM karar veriyor, biz önceden elemiyoruz. */
ok('mesaj bildirimi hedefin TÜM cihazlarına gitti',
   kayit.gonderilen.some((grup) => grup.length === 4));
ok('içerik açık cihazda metin var',
   tumMesajlar.some((m) => /TELEFON/.test(m.token) && m.data.body === 'gizli metin'));
ok('içerik kapalı cihaza metin GİTMEDİ',
   tumMesajlar.every((m) => !/MASA/.test(m.token) || !JSON.stringify(m).includes('gizli metin')));
ok('çağrı bildirimi gönderildi',
   tumMesajlar.some((m) => m.data.tur === 'arama' && m.data.aramaTuru === 'ses'));
ok('ölü belirteç cihaz listesinden silindi',
   kayit.silinen.some((y) => /cihazlar\/AYSE\/eskiCihaz/.test(y)));
ok('canlı belirteçler silinmedi',
   !kayit.silinen.some((y) => /telefon|masaustu/.test(y)));
/* FELAKET SENARYOSU: yanlış servis hesabı anahtarıyla kurulumda her gönderim
   hata veriyor. O hatada cihaz kayıtları silinirse veritabanı tek seferde
   boşalır ve anahtar düzeltilse bile kimse bildirim alamaz. */
ok('kurulum hatası veren cihaz SİLİNMEDİ',
   !kayit.silinen.some((y) => /anahtarsiz/.test(y)));
ok('işlenen kayıtlar kuyruktan silindi',
   ['k1', 'k2'].every((k) => kayit.kuyruktanSilinen.some((y) => y.endsWith('/' + k))));
ok('ESKİ kayıt gönderilmeden silindi',
   kayit.kuyruktanSilinen.some((y) => y.endsWith('/kEski')) &&
   !tumMesajlar.some((m) => JSON.stringify(m).includes('dünkü mesaj')));
ok('bozuk kayıt gönderilmeden silindi',
   kayit.kuyruktanSilinen.some((y) => y.endsWith('/kBozuk')));
ok('cihazı olmayan hedefin kaydı silindi',
   kayit.kuyruktanSilinen.some((y) => y.endsWith('/kCihazsiz')));

/* ---- yeniden deneme SINIRI ----
   Kalıcı bir geçici hatada sunucu sonsuza kadar denememeli. Sınır
   index.js'teki EN_COK_DENEME (5). Sayac sahte SDK'dan geliyor. */
ok('kalıcı geçici hatada deneme sayısı sınırlı (' + kayit.patlayanDeneme + ' ≤ 5)',
   kayit.patlayanDeneme > 0 && kayit.patlayanDeneme <= 5);
ok('vazgeçilen kayıt kuyruktan silindi',
   kayit.kuyruktanSilinen.some((y) => y.endsWith('/kPatla')));

console.log('');
T.forEach(([a, k]) => console.log((k ? '  ✓ ' : '  ✗ ') + a));
const kotu = T.filter((x) => !x[1]).length;
console.log(kotu ? '\n  ' + kotu + ' BAŞARISIZ / ' + T.length
                 : '\n  TUMU GECTI (' + T.length + ')');
process.exit(kotu ? 1 : 0);
