"""Meridyen bildirim sunucusu — SAF MANTIK.

Burada ağ yok, Firebase yok, saat yok (saat hep parametre olarak geliyor):
yalnız "kuyruktaki kayıt + hedefin cihazları" alıp FCM mesajlarını kuran,
hataları sınıflandıran ve kararları veren işlevler. Bütün davranış ağsız
sınanabiliyor (bkz. sinama/test_mantik.py).
"""
from __future__ import annotations

import re

# ---- süreler ----
# Bildirimin FCM'de bekleyebileceği süre. Çağrı kısa: yarım dakika sonra çalan
# bir çağrı kullanıcıyı yanıltır. Mesaj uzun: telefon kapalıysa açılınca gelsin.
OMUR_CAGRI_SN = 45
OMUR_MESAJ_SN = 24 * 60 * 60

# Kuyrukta bundan eski kayıt GÖNDERİLMİYOR, atılıyor. Sunucu saatlerce kapalı
# kaldıysa açıldığında dünkü mesajların bildirimini yağdırmamalı; çağrı için
# sınır çok daha sıkı: biten bir aramanın zili çalmamalı.
EN_ESKI_MESAJ_SN = 30 * 60
EN_ESKI_CAGRI_SN = 60

# Geçici hatada bir belirteç en çok bu kadar denenir.
EN_COK_DENEME = 5

# Mesaj anahtarı (mid) sınırı: Firebase push anahtarları 20 karakter.
_ANAHTAR_DESENI = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


# ================= KAYIT =================

def kayit_gecerli_mi(kayit) -> bool:
    """Eksik kayıt sessizce atılmalı, ama sunucu da onun yüzünden durmamalı."""
    if not isinstance(kayit, dict):
        return False
    for alan in ('hedef', 'gonderen'):
        if not isinstance(kayit.get(alan), str) or not kayit.get(alan):
            return False
    if kayit['hedef'] == kayit['gonderen']:
        return False            # kendine bildirim yok
    return True


def cagri_mi(kayit) -> bool:
    return str(kayit.get('tur') or '') in ('arama', 'cagri')


def arama_turu(kayit) -> str:
    """Çağrı türü: kayıtta varsa o, yoksa metinden makul bir tahmin."""
    t = kayit.get('aramaTuru')
    if t in ('goruntu', 'ses'):
        return t
    return 'goruntu' if re.search(r'görüntü|goruntu|video', str(kayit.get('metin') or ''), re.I) else 'ses'


def bayat_mi(kayit, sunucu_simdi_ms: float):
    """Kayıt gönderilemeyecek kadar eski mi? Eskiyse nedenini döndürür.

    `ts` istemcinin yazdığı SUNUCU zamanı (ServerValue.TIMESTAMP); karşısına
    bu makinenin saati değil, ölçülmüş sunucu saati konuyor. Saat farkı
    yüzünden geçerli kayıtlar atılmasın.
    """
    ts = kayit.get('ts')
    if not isinstance(ts, (int, float)):
        return None             # zaman yok: eski istemci, gönder
    yas_sn = (sunucu_simdi_ms - ts) / 1000.0
    sinir = EN_ESKI_CAGRI_SN if cagri_mi(kayit) else EN_ESKI_MESAJ_SN
    if yas_sn > sinir:
        return 'bayat %s (%d sn)' % ('çağrı' if cagri_mi(kayit) else 'mesaj', yas_sn)
    return None


def mesaj_anahtari(kayit, kuyruk_anahtari: str) -> str:
    """Cihaz tarafında TEKİLLEŞTİRME anahtarı.

    Aynı mesajın bildirimi iki yoldan gelebiliyor: uygulamanın kendi
    veritabanı dinleyicisi ve bu sunucunun push'u. Cihaz ikisini aynı
    anahtardan tanıyıp bir kez gösteriyor. İstemci mesajın kendi anahtarını
    (`mid`) kayda yazıyor; yazmayan eski istemcide kuyruk anahtarı
    kullanılıyor — en azından sunucunun AYNI kaydı iki kez göndermesi
    (çökme sonrası yeniden deneme) cihazda tek bildirime iniyor.
    """
    mid = kayit.get('mid')
    if isinstance(mid, str) and _ANAHTAR_DESENI.match(mid):
        return mid
    return 'k-' + kuyruk_anahtari


# ================= MESAJ =================

def metin_kur(kayit, icerik_goster: bool):
    """Bildirim başlığı ve gövdesi.

    GİZLİLİK: metin yalnız HEDEF CİHAZIN kendi ayarı izin veriyorsa gidiyor.
    Ayar cihaz başına: telefonda kapalı, masaüstünde açık olabilir. Kapalıysa
    metin sunucudan hiç ÇIKMIYOR — kilit ekranına düşme ihtimali de kalmıyor.
    """
    ad = str(kayit.get('baslik') or kayit.get('gonderenAd') or 'Meridyen')[:60]
    if cagri_mi(kayit):
        # Çağrıda "kim arıyor" zaten gerekli; içerik gizliliği metin için.
        return ad, (str(kayit.get('metin') or 'Arıyor') if icerik_goster else 'Arıyor')
    if not icerik_goster:
        return 'Meridyen', 'Yeni bir mesajın var.'
    return ad, str(kayit.get('metin') or 'Yeni mesaj')[:180]


def etiket_kur(kayit) -> str:
    """Hangi bildirimin hangisinin üstüne yazacağı.

    Mesajda 'meridyen-<gönderen>': uygulamanın kendi bildirimi de aynı etiketi
    üretiyor (index.html sistemBildirimi, MeridyenBildirimler.etiketId); aynı
    kişinin bildirimleri tek yerde toplanıyor. Çağrıda ayrı etiket: web'de
    çağrı bildirimi, aynı kişiden gelmiş okunmamış mesaj bildirimini SİLMESİN.
    """
    g = str(kayit['gonderen'])
    return ('meridyen-cagri-' + g) if cagri_mi(kayit) else ('meridyen-' + g)


def mesaj_kur(kayit, cihaz, kuyruk_anahtari: str) -> dict:
    """Tek cihaz için FCM v1 mesajı (`message` alanının içi).

    SADECE `data`: bilerek. `notification` bloğu olursa Android uygulama arka
    plandayken bildirimi SİSTEM çiziyor, bizim servisimiz (MeridyenMesajServisi)
    hiç çağrılmıyor — ne biriktirme, ne tekilleştirme, ne de tam ekran çağrı
    çalışır. Data-only + yüksek öncelik uygulama kapalıyken de servisi
    uyandırıyor.

    Anahtarlar hem Türkçe (yerli servis) hem İngilizce (web service worker):
    tek yük iki platforma birden gidiyor.
    """
    icerik = not (isinstance(cihaz, dict) and cihaz.get('icerikGoster') is False)
    baslik, govde = metin_kur(kayit, icerik)
    cagri = cagri_mi(kayit)
    etiket = etiket_kur(kayit)
    veri = {
        # yerli (Android) taraf
        'baslik': baslik, 'metin': govde,
        'gonderen': str(kayit['gonderen']),
        'tur': 'arama' if cagri else str(kayit.get('tur') or 'mesaj'),
        'etiket': etiket,
        'mid': mesaj_anahtari(kayit, kuyruk_anahtari),
        # web service worker
        'title': baslik, 'body': govde, 'tag': etiket, 'url': './',
    }
    if cagri:
        veri['aramaTuru'] = arama_turu(kayit)
    if kayit.get('sid'):
        veri['sid'] = str(kayit['sid'])
    omur = OMUR_CAGRI_SN if cagri else OMUR_MESAJ_SN
    return {
        'token': cihaz['belirtec'],
        'data': veri,
        'android': {'priority': 'HIGH', 'ttl': '%ds' % omur},
        'webpush': {'headers': {'Urgency': 'high', 'TTL': str(omur)}},
    }


def gecerli_belirtec(cihaz) -> bool:
    return (isinstance(cihaz, dict) and isinstance(cihaz.get('belirtec'), str)
            and len(cihaz['belirtec']) >= 20)


def sahiplik_haritasi(tum_cihazlar) -> dict:
    """belirteç → (uid, ts): her belirtecin EN YENİ sahibi.

    Aynı telefonda hesap değiştirilince belirteç yeni hesabın altına da
    yazılıyor; çıkış yapılırken eskisinden silinemediyse (çevrimdışı çıkış,
    uygulama verisini silme, yeniden kurma) telefon ESKİ hesabın mesajlarını
    da almaya devam ediyordu — hem çift bildirim hem gizlilik açığı.
    """
    harita = {}
    for uid, cihazlar in (tum_cihazlar or {}).items():
        if not isinstance(cihazlar, dict):
            continue
        for c in cihazlar.values():
            if not gecerli_belirtec(c):
                continue
            ts = c.get('ts') if isinstance(c.get('ts'), (int, float)) else 0
            onceki = harita.get(c['belirtec'])
            if onceki is None or ts > onceki[1]:
                harita[c['belirtec']] = (uid, ts)
    return harita


def mesajlari_kur(kayit, cihazlar, kuyruk_anahtari: str, sahiplik=None, yalniz=None):
    """Hedefin cihazları için gönderilecek mesajlar.

    Döner: (isler, devredilen)
      isler      : [(cihaz_anahtari, mesaj)]
      devredilen : [cihaz_anahtari] — belirteç artık BAŞKA bir hesaba ait
                   (o hesapta daha yeni kayıtlı); bu hesaptan silinmeli.
    yalniz: yeniden denemede yalnız bu cihaz anahtarları.

    Aynı belirteç hedefin altında iki kez kayıtlıysa (farklı anahtarlarla)
    tek kez gönderiliyor: yoksa aynı telefona iki push gider.
    """
    hedef = kayit['hedef']
    isler, devredilen, gorulen = [], [], set()
    for anahtar in sorted((cihazlar or {}).keys()):
        if yalniz is not None and anahtar not in yalniz:
            continue
        c = cihazlar[anahtar]
        if not gecerli_belirtec(c):
            continue
        b = c['belirtec']
        if b in gorulen:
            continue
        if sahiplik:
            sahip = sahiplik.get(b)
            ts = c.get('ts') if isinstance(c.get('ts'), (int, float)) else 0
            if sahip and sahip[0] != hedef and sahip[1] > ts:
                devredilen.append(anahtar)
                continue
        gorulen.add(b)
        isler.append((anahtar, mesaj_kur(kayit, c, kuyruk_anahtari)))
    return isler, devredilen


# ================= HATALAR =================

def fcm_hatasi_coz(http_kodu: int, govde) -> tuple:
    """FCM v1 hata yanıtından (durum, hata_kodu, metin) çıkarır."""
    durum, kod, metin = '', '', ''
    hata = govde.get('error') if isinstance(govde, dict) else None
    if isinstance(hata, dict):
        durum = str(hata.get('status') or '')
        metin = str(hata.get('message') or '')
        for d in hata.get('details') or []:
            if isinstance(d, dict) and d.get('errorCode'):
                kod = str(d['errorCode'])
    if not durum:
        durum = {400: 'INVALID_ARGUMENT', 401: 'UNAUTHENTICATED', 403: 'PERMISSION_DENIED',
                 404: 'NOT_FOUND', 429: 'RESOURCE_EXHAUSTED', 500: 'INTERNAL',
                 503: 'UNAVAILABLE'}.get(http_kodu, 'HTTP_%d' % http_kodu)
    return durum, kod, metin


_BELIRTEC_METNI = re.compile(r'registration token|not a valid fcm', re.I)


def hata_turu(durum: str, kod: str, metin: str, basari_goruldu: bool) -> str:
    """Hatanın ne yapılacağını söyleyen türü:

      'olu'     : belirteç artık geçersiz → cihaz kaydı silinir
      'gecici'  : bir süre sonra yeniden denenir
      'kurulum' : sunucunun kendi kurulumu bozuk → yüksek sesle uyar, SİLME
      'diger'   : günlüğe yaz, vazgeç

    SİLMEDE CÖMERT OLMAK TEHLİKELİ. Yanlış servis hesabıyla kurulumda HER
    gönderim hata veriyor; o hatada belirteç silinseydi veritabanındaki bütün
    cihaz kayıtları tek seferde uçardı ve anahtar düzeltilse bile kimse
    bildirim alamazdı. INVALID_ARGUMENT hem bozuk belirteç hem bozuk YÜK için
    dönüyor; yükü biz kuruyoruz, yalnız metin belirteci işaret ediyorsa ölü.

    SENDER_ID_MISMATCH iki anlama geliyor: ya belirteç başka bir projenin
    (o belirteç ölü), ya da sunucunun anahtarı yanlış projenin (kurulum).
    Bu süreçte daha önce EN AZ BİR gönderim başarılı olduysa anahtar doğru
    demektir; o zaman belirtece özgüdür.
    """
    if kod == 'UNREGISTERED' or (durum == 'NOT_FOUND' and not kod):
        return 'olu'
    if durum == 'INVALID_ARGUMENT' or kod == 'INVALID_ARGUMENT':
        return 'olu' if _BELIRTEC_METNI.search(metin or '') else 'diger'
    if kod == 'SENDER_ID_MISMATCH':
        return 'olu' if basari_goruldu else 'kurulum'
    if kod in ('UNAVAILABLE', 'INTERNAL', 'QUOTA_EXCEEDED') or durum in (
            'UNAVAILABLE', 'INTERNAL', 'RESOURCE_EXHAUSTED', 'DEADLINE_EXCEEDED', 'AG'):
        return 'gecici'
    if kod in ('THIRD_PARTY_AUTH_ERROR', 'APNS_AUTH_ERROR') or durum in (
            'UNAUTHENTICATED', 'PERMISSION_DENIED'):
        return 'kurulum'
    return 'diger'


def geri_cekilme_sn(deneme: int, taban: float = 1.0, tavan: float = 30.0) -> float:
    """1., 2., 3. yeniden deneme: 2, 4, 8 … sn (tavanla)."""
    return min(tavan, taban * (2 ** max(1, deneme)))


# ================= HIZ SINIRI =================

class HizSiniri:
    """Gönderen başına jeton kovası.

    Kuyruğa her oturum açmış kullanıcı yazabiliyor. Bozuk ya da kötü niyetli
    bir istemci saniyede yüzlerce kayıt bırakırsa hedefin telefonunu
    bildirim yağmuruna tutmayalım, FCM kotasını da tüketmeyelim. Sınır
    gerçek kullanımın çok üstünde: 30'luk anlık patlama, sonra saniyede bir.
    """

    def __init__(self, kapasite: float = 30, saniyede: float = 1.0):
        self.kapasite = kapasite
        self.saniyede = saniyede
        self._kova = {}

    def izin_ver(self, kim: str, simdi_sn: float) -> bool:
        jeton, son = self._kova.get(kim, (self.kapasite, simdi_sn))
        jeton = min(self.kapasite, jeton + (simdi_sn - son) * self.saniyede)
        if jeton < 1:
            self._kova[kim] = (jeton, simdi_sn)
            return False
        self._kova[kim] = (jeton - 1, simdi_sn)
        if len(self._kova) > 5000:          # uzun süre çalışırken bellek büyümesin
            self._kova = {k: v for k, v in self._kova.items() if simdi_sn - v[1] < 600}
        return True


# ================= SAHİPLENME =================

def sahiplenilebilir_mi(kayit, kimlik: str, sunucu_simdi_ms: float) -> bool:
    """Kayıt bu sunucu tarafından işlenebilir mi?

    İki sunucu (ya da bir sunucunun iki kopyası) aynı anda çalışırsa ikisi de
    aynı kaydı görür ve ikisi de gönderirse alıcıya iki bildirim gider. Kayıt
    önce bir KİRA ile sahipleniliyor (koşullu yazma); kirası dolmamış başka
    bir sahibin kaydına dokunulmuyor. Sahip çöküp kirayı bırakamazsa kira
    dolunca başkası (ya da yeniden başlayan aynı sunucu) devralıyor.
    """
    if not isinstance(kayit, dict):
        return False
    i = kayit.get('isleyen')
    if not isinstance(i, dict):
        return True
    if i.get('kimlik') == kimlik:
        return True
    bitis = i.get('bitis')
    return not isinstance(bitis, (int, float)) or bitis <= sunucu_simdi_ms
