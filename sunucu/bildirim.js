/* Meridyen bildirim sunucusu — SAF MANTIK.
 *
 * Burada ağ yok, Firebase yok: yalnız "kuyruktaki kayıt + hedef cihaz" alıp
 * FCM mesajını kuran, hangi belirtecin atılacağına karar veren işlevler var.
 * Böylece bütün davranış ağsız sınanabiliyor (bkz. test.js).
 */
'use strict';

/* Bir mesajın yaşam süresi. Çağrı kısa: yarım dakika sonra çalan bir çağrı
   bildirimi kullanıcıyı yanıltır. Mesaj uzun: telefon kapalıysa açılınca
   gelsin. */
const OMUR_CAGRI_SN = 45;
const OMUR_MESAJ_SN = 24 * 60 * 60;

/* Kuyruk kaydı geçerli mi? Eksik kayıt sessizce atılmamalı, ama sunucu da
   onun yüzünden durmamalı. */
function kayitGecerliMi(kayit) {
  if (!kayit || typeof kayit !== 'object') return false;
  if (!kayit.hedef || typeof kayit.hedef !== 'string') return false;
  if (!kayit.gonderen || typeof kayit.gonderen !== 'string') return false;
  return true;
}

function cagriMi(kayit) {
  const t = String(kayit.tur || '');
  return t === 'arama' || t === 'cagri';
}

/* Çağrı türü: kayıtta varsa o, yoksa metinden makul bir tahmin. */
function aramaTuru(kayit) {
  if (kayit.aramaTuru === 'goruntu' || kayit.aramaTuru === 'ses') return kayit.aramaTuru;
  return /görüntü|goruntu|video/i.test(String(kayit.metin || '')) ? 'goruntu' : 'ses';
}

/* Bildirim başlığı ve gövdesi.
 * GİZLİLİK: metin yalnız HEDEF CİHAZIN kendi ayarı izin veriyorsa gidiyor.
 * Ayar cihaz başına: telefonda kapalı, masaüstünde açık olabilir. Kapalıysa
 * metin sunucudan hiç ÇIKMIYOR — kilit ekranına düşme ihtimali de kalmıyor.
 */
function metinKur(kayit, icerikGoster) {
  const ad = String(kayit.baslik || kayit.gonderenAd || 'Meridyen').slice(0, 60);
  if (cagriMi(kayit)) {
    // Çağrıda "kim arıyor" bilgisi zaten gerekli; içerik gizliliği metin için.
    return { baslik: ad, govde: icerikGoster ? String(kayit.metin || 'Arıyor') : 'Arıyor' };
  }
  if (!icerikGoster) return { baslik: 'Meridyen', govde: 'Yeni bir mesajın var.' };
  return { baslik: ad, govde: String(kayit.metin || 'Yeni mesaj').slice(0, 180) };
}

/* Bildirimlerin üst üste yazma etiketi. Web tarafı ve yerli taraf AYNI
   etiketi üretmeli ki aynı kişiden gelen ikinci mesaj birincinin üstüne
   yazsın (yerli tarafta ayrıca birikerek gruplanıyor). */
function etiketKur(kayit) {
  return 'meridyen-' + String(kayit.gonderen);
}

/* Tek bir cihaz için FCM mesajı.
 *
 * SADECE "data": bilerek. FCM'in `notification` bloğu gönderilirse Android
 * uygulama arka plandayken bildirimi SİSTEM çiziyor ve bizim servisimiz
 * (MeridyenMesajServisi) hiç çağrılmıyor — o zaman ne biriktirme/gruplama,
 * ne de çağrılar için tam ekran çağrı ekranı çalışıyor. Data-only + yüksek
 * öncelik ise uygulama kapalıyken bile onMessageReceived'i tetikliyor.
 *
 * Anahtarlar hem Türkçe (yerli servis) hem İngilizce (web service worker)
 * yazılıyor; iki taraf da kendi beklediğini buluyor, tek yük iki platforma
 * birden gidiyor.
 */
function mesajKur(kayit, cihaz) {
  const icerikGoster = cihaz && cihaz.icerikGoster !== false;
  const { baslik, govde } = metinKur(kayit, icerikGoster);
  const cagri = cagriMi(kayit);
  const veri = {
    // yerli (Android) tarafın okuduğu adlar
    baslik: baslik,
    metin: govde,
    gonderen: String(kayit.gonderen),
    tur: cagri ? 'arama' : String(kayit.tur || 'mesaj'),
    etiket: etiketKur(kayit),
    // web service worker'ın okuduğu adlar
    title: baslik,
    body: govde,
    tag: etiketKur(kayit),
    url: './'
  };
  if (cagri) veri.aramaTuru = aramaTuru(kayit);
  if (kayit.sid) veri.sid = String(kayit.sid);

  const omur = cagri ? OMUR_CAGRI_SN : OMUR_MESAJ_SN;
  return {
    token: cihaz.belirtec,
    data: veri,
    android: {
      priority: 'high',            // Doze'da bile teslim edilir
      ttl: omur * 1000
    },
    webpush: {
      headers: {
        Urgency: 'high',
        TTL: String(omur)
      }
    }
  };
}

/* Bir cihaz listesinden gönderilecek mesajları kurar. Belirteci olmayan
   kayıtlar atlanıyor (eski/bozuk kayıtlar kuyruğu durdurmasın). */
function mesajlariKur(kayit, cihazlar) {
  const liste = [];
  Object.keys(cihazlar || {}).forEach((anahtar) => {
    const cihaz = cihazlar[anahtar];
    if (!cihaz || typeof cihaz.belirtec !== 'string' || cihaz.belirtec.length < 20) return;
    liste.push({ anahtar: anahtar, mesaj: mesajKur(kayit, cihaz) });
  });
  return liste;
}

/* Bu hata belirtecin ARTIK GEÇERSİZ olduğunu mu söylüyor? Öyleyse kayıt
   silinmeli: yoksa her mesajda aynı ölü belirtece gönderim denenir. */
const ATILACAK_KODLAR = [
  'messaging/registration-token-not-registered',
  'messaging/invalid-registration-token',
  'messaging/invalid-argument',
  'messaging/mismatched-credential'
];
function belirtecOlduMu(hata) {
  if (!hata) return false;
  const kod = String((hata.errorInfo && hata.errorInfo.code) || hata.code || '');
  return ATILACAK_KODLAR.indexOf(kod) !== -1;
}

/* Geçici hata mı (tekrar denemeye değer mi)? */
function geciciHataMi(hata) {
  if (!hata) return false;
  const kod = String((hata.errorInfo && hata.errorInfo.code) || hata.code || '');
  return kod === 'messaging/server-unavailable' ||
         kod === 'messaging/internal-error' ||
         kod === 'messaging/quota-exceeded' ||
         kod === 'messaging/unknown-error' ||
         /ECONNRESET|ETIMEDOUT|ENOTFOUND|socket hang up/i.test(String(hata.message || ''));
}

module.exports = {
  OMUR_CAGRI_SN, OMUR_MESAJ_SN,
  kayitGecerliMi, cagriMi, aramaTuru, metinKur, etiketKur,
  mesajKur, mesajlariKur, belirtecOlduMu, geciciHataMi
};
