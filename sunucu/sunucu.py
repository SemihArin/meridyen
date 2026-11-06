#!/usr/bin/env python3
"""Meridyen bildirim sunucusu.

NE YAPAR: Realtime Database'deki `bildirimKuyrugu` düğümünü izler. Biri mesaj
ya da çağrı gönderdiğinde istemci oraya bir kayıt bırakıyor; sunucu kaydı
yakalayıp hedefin CİHAZLARINA (Android + web) FCM push'u gönderiyor ve kaydı
siliyor. Uygulama tamamen kapalıyken bildirimi yalnız bu yol ulaştırabilir.

NEDEN SDK DEĞİL, DOĞRUDAN REST: firebase-admin'in Python dinleyicisi uzun
süre çalışan bir süreç için güvenilmez: ağ kopunca dinleyici iş parçacığı
sessizce ölüyor, yarı açık bir bağlantıda (modem yeniden başladı) sonsuza
kadar bekliyor ve bunu dışarıdan anlamanın yolu yok. Burada her istekte
zaman aşımı var, akış kopunca yeniden bağlanılıyor ve akış ne olursa olsun
kuyruk düzenli aralıkla ayrıca taranıyor. Bağımlılık yalnız `requests` ve
`google-auth`: Raspberry Pi'ye de, eski bir bilgisayara da kurulabiliyor.

ÇİFT BİLDİRİME KARŞI:
  - Kayıt göndermeden ÖNCE kira ile sahipleniliyor (koşullu yazma). İki
    sunucu aynı anda çalışsa bile bir kaydı yalnız biri gönderiyor.
  - Geçici hatada YALNIZ başarısız olan cihaza yeniden deneniyor; başarılı
    olanlara ikinci kez gitmiyor. Kalan cihazlar kayda yazılıyor: sunucu
    yeniden denemenin ortasında çökerse kaldığı yerden devam ediyor.
  - Her push'ta mesajın anahtarı (`mid`) var; telefon aynı mesajı ikinci
    kez göstermiyor (uygulamanın kendi bildirimi ya da yeniden gönderim).
  - Hesap değiştirilmiş telefonun eski hesaptaki kaydına gönderilmiyor.

ÇALIŞTIRMA: README.md.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests

import bildirim as B

SURUM = '2.0'
VARSAYILAN_DB = 'https://meridyen-830fb-default-rtdb.europe-west1.firebasedatabase.app'
VARSAYILAN_PROJE = 'meridyen-830fb'
NABIZ_YOLU = 'sistem/bildirimSunucusu'
KAPSAMLAR = [
    'https://www.googleapis.com/auth/firebase.database',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/firebase.messaging',
]
KIRA_MS = 120_000           # sahiplenilmiş kaydın kirası
ZAMAN_ASIMI = (10, 30)      # (bağlanma, okuma) sn — her istekte
AKIS_OKUMA_SN = 90          # akışta bu kadar veri gelmezse bağlantı ölü sayılır
                            # (veritabanı her ~30 sn'de bir canlılık olayı yolluyor)

log = logging.getLogger('meridyen')


# ================= AYARLAR =================

class Ayar:
    def __init__(self, ortam=os.environ):
        self.db = ortam.get('MERIDYEN_DB', VARSAYILAN_DB).rstrip('/')
        self.kuyruk = ortam.get('MERIDYEN_KUYRUK', 'bildirimKuyrugu')
        self.port = int(ortam.get('PORT', '8080'))
        self.nabiz_sn = float(ortam.get('MERIDYEN_NABIZ_SN', '60'))
        self.tarama_sn = float(ortam.get('MERIDYEN_TARAMA_SN', '30'))
        self.geri_cekilme_taban = float(ortam.get('MERIDYEN_GERI_CEKILME_SN', '1'))
        self.tek_sefer = ortam.get('MERIDYEN_TEK_SEFER') == '1'
        self.akis_kapali = ortam.get('MERIDYEN_AKIS_KAPALI') == '1'    # sınama: yalnız tarama
        self.fcm_taban = ortam.get('MERIDYEN_FCM_URL', 'https://fcm.googleapis.com').rstrip('/')
        self.emulator = ortam.get('FIREBASE_DATABASE_EMULATOR_HOST')
        self.ns = ortam.get('MERIDYEN_DB_NS') or (urlparse(self.db).hostname or '').split('.')[0]
        self.kimlik_dosyasi = ortam.get('MERIDYEN_KIMLIK_DOSYASI') or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '.sunucu-kimligi')
        self.servis_hesabi = self._servis_hesabi(ortam)
        self.proje = (ortam.get('MERIDYEN_PROJE')
                      or (self.servis_hesabi or {}).get('project_id') or VARSAYILAN_PROJE)

    @staticmethod
    def _servis_hesabi(ortam):
        ham = ortam.get('MERIDYEN_SERVIS_HESABI')
        if ham:
            try:
                return json.loads(ham)
            except ValueError as e:
                cik('MERIDYEN_SERVIS_HESABI okunamadı (geçerli JSON değil): %s' % e)
        yol = ortam.get('MERIDYEN_SERVIS_HESABI_DOSYASI') or ortam.get('GOOGLE_APPLICATION_CREDENTIALS')
        if yol:
            try:
                with open(yol, encoding='utf-8') as f:
                    return json.load(f)
            except (OSError, ValueError) as e:
                cik('Servis hesabı dosyası okunamadı (%s): %s' % (yol, e))
        return None


def cik(mesaj, kod=1):
    sys.stderr.write('\n[HATA] %s\n\n' % mesaj)
    sys.exit(kod)


def kimlik_al(dosya):
    """Sunucunun kalıcı kimliği. Yeniden başlayınca AYNI kimlik: kendi
    sahiplendiği kayıtların kirasının dolmasını beklemeden devam edebilsin."""
    try:
        with open(dosya, encoding='utf-8') as f:
            k = f.read().strip()
            if k:
                return k
    except OSError:
        pass
    k = 'py-' + uuid.uuid4().hex[:12]
    try:
        with open(dosya, 'w', encoding='utf-8') as f:
            f.write(k + '\n')
    except OSError as e:
        log.warning('kimlik dosyası yazılamadı (%s); kimlik bu çalışmaya özel: %s', dosya, e)
    return k


# ================= ERİŞİM =================

class Erisim:
    """Google erişim belirteci. Servis hesabı yoksa (yalnız emülatörde)
    emülatörün yönetici belirteci kullanılıyor."""

    def __init__(self, servis_hesabi):
        self._kilit = threading.Lock()
        self._kimlik = None
        if servis_hesabi:
            from google.oauth2 import service_account
            self._kimlik = service_account.Credentials.from_service_account_info(
                servis_hesabi, scopes=KAPSAMLAR)

    def baslik(self):
        if self._kimlik is None:
            return {'Authorization': 'Bearer owner'}
        with self._kilit:
            if not self._kimlik.valid:
                from google.auth.transport.requests import Request
                self._kimlik.refresh(Request())
            return {'Authorization': 'Bearer ' + self._kimlik.token}

    def yenile(self):
        """401 alındı: belirteç süresinden önce geçersiz olmuş olabilir."""
        if self._kimlik is None:
            return
        with self._kilit:
            from google.auth.transport.requests import Request
            self._kimlik.refresh(Request())


class _Oturumlar:
    """requests.Session iş parçacıkları arasında paylaşılmamalı."""

    def __init__(self):
        self._yerel = threading.local()

    def al(self):
        s = getattr(self._yerel, 'oturum', None)
        if s is None:
            s = self._yerel.oturum = requests.Session()
        return s


class VeritabaniHatasi(Exception):
    def __init__(self, mesaj, kod=0):
        super().__init__(mesaj)
        self.kod = kod


def gecici_ag_hatasi_mi(e) -> bool:
    """Ağ kopukluğu ya da sunucu tarafı geçici hata: kayıt ATILMAMALI."""
    if isinstance(e, requests.RequestException):
        return True
    return isinstance(e, VeritabaniHatasi) and (e.kod >= 500 or e.kod in (401, 429))


class Veritabani:
    """Realtime Database REST istemcisi."""

    def __init__(self, ayar: Ayar, erisim: Erisim):
        self.taban = ('http://' + ayar.emulator) if ayar.emulator else ayar.db
        self.params = {'ns': ayar.ns} if ayar.emulator else {}
        self.erisim = erisim
        self._oturum = _Oturumlar()

    def url(self, yol):
        return '%s/%s.json' % (self.taban, yol.strip('/'))

    def _istek(self, yontem, yol, *, json_=None, basliklar=None, params=None, kabul=(200, 204)):
        p = dict(self.params)
        if params:
            p.update(params)
        for deneme in (1, 2):
            b = dict(self.erisim.baslik())
            if basliklar:
                b.update(basliklar)
            y = self._oturum.al().request(yontem, self.url(yol), json=json_, headers=b,
                                          params=p, timeout=ZAMAN_ASIMI)
            if y.status_code == 401 and deneme == 1:
                self.erisim.yenile()
                continue
            if y.status_code not in kabul:
                raise VeritabaniHatasi('%s %s → %d %s' % (yontem, yol, y.status_code, y.text[:200]),
                                       y.status_code)
            return y

    def oku(self, yol, shallow=False):
        y = self._istek('GET', yol, params={'shallow': 'true'} if shallow else None)
        return y.json()

    def oku_etiketli(self, yol):
        y = self._istek('GET', yol, basliklar={'X-Firebase-ETag': 'true'})
        return y.json(), y.headers.get('ETag')

    def kosullu_yaz(self, yol, deger, etag) -> bool:
        """Değer bizim okuduğumuzdan beri değişmediyse yazar.
        (if-match ile print=silent birlikte kullanılamıyor; REST reddediyor.)"""
        y = self._istek('PUT', yol, json_=deger, basliklar={'if-match': etag or ''},
                        kabul=(200, 204, 412))
        return y.status_code != 412

    def yaz(self, yol, deger):
        self._istek('PUT', yol, json_=deger, params={'print': 'silent'})

    def sil(self, yol):
        self._istek('DELETE', yol, params={'print': 'silent'})


class Fcm:
    """FCM HTTP v1 istemcisi."""

    def __init__(self, ayar: Ayar, erisim: Erisim):
        self.url = '%s/v1/projects/%s/messages:send' % (ayar.fcm_taban, ayar.proje)
        self.erisim = erisim
        self._oturum = _Oturumlar()

    def gonder(self, mesaj):
        """(True, None) ya da (False, (durum, kod, metin))."""
        try:
            y = self._oturum.al().post(self.url, json={'message': mesaj},
                                       headers=self.erisim.baslik(), timeout=ZAMAN_ASIMI)
        except requests.RequestException as e:
            return False, ('AG', '', str(e)[:200])
        if 200 <= y.status_code < 300:
            return True, None
        if y.status_code == 401:
            try:
                self.erisim.yenile()
            except Exception:
                pass
        try:
            govde = y.json()
        except ValueError:
            govde = None
        return False, B.fcm_hatasi_coz(y.status_code, govde)


# ================= SUNUCU =================

class Sunucu:
    def __init__(self, ayar: Ayar, db: Veritabani, fcm: Fcm, kimlik: str):
        self.ayar, self.db, self.fcm, self.kimlik = ayar, db, fcm, kimlik
        self.kuyruk = ayar.kuyruk
        self.dur = threading.Event()
        self.zil = threading.Event()
        self.kilit = threading.Lock()
        self.isleniyor = set()          # bu süreçte şu an işlenen kayıtlar
        self.yeniden = {}               # kayıt → monotonik vade (geçici hata sonrası)
        self.hata_sayisi = {}           # kayıt → beklenmedik hata sayısı
        self.havuz = ThreadPoolExecutor(max_workers=4, thread_name_prefix='isci')
        self.hiz = B.HizSiniri()
        self.basladi = int(time.time() * 1000)
        self.fark_ms = 0.0              # sunucu saati − bu makinenin saati
        self.son_nabiz = None           # yazdığımız son nabzın sunucu zamanı
        self.cakisma = None             # başka bir sunucu çalışıyor mu (açıklama)
        self.basari_goruldu = False     # bu süreçte en az bir gönderim başarılı oldu mu
        self.kurulum_hatasi = None
        self.akis_bagli = False
        self.son_tarama = 0.0
        self.son_tarama_basarili = 0.0
        self.son_dongu = time.monotonic()
        self._akis_yaniti = None
        self._sahiplik = ({}, -1e9)
        self._sinirli = {}
        self.sayac = dict(alinan=0, gonderilen=0, basarisiz=0, olu_belirtec=0,
                          devredilen=0, eski=0, hatali=0, hiz_siniri=0, yeniden_deneme=0)

    # ---- yardımcılar ----

    def sunucu_simdi(self):
        return time.time() * 1000 + self.fark_ms

    def _sinirli_gunluk(self, anahtar, mesaj, *args, aralik=60.0, seviye=logging.WARNING):
        """Aynı hata ağ kopukken saniyede bir yazılıp günlüğü boğmasın."""
        simdi = time.monotonic()
        if simdi - self._sinirli.get(anahtar, -1e9) >= aralik:
            self._sinirli[anahtar] = simdi
            log.log(seviye, mesaj, *args)

    def _say(self, ad, n=1):
        with self.kilit:
            self.sayac[ad] += n

    # ---- nabız ----

    def nabiz_at(self):
        """Uygulamanın "bildirim sunucusu çalışıyor mu" sorusunun yanıtı.

        Ayrıca iki işi var:
          - SAAT FARKI: nabzı sunucu saatiyle yazıp geri okuyoruz; bayat kayıt
            kararı bu makinenin saatine değil sunucununkine dayanıyor.
          - ÇAKIŞMA: son yazdığımızdan beri nabzın üstüne BAŞKASI yazdıysa
            aynı veritabanında ikinci bir sunucu çalışıyor (örneğin eski Node
            sunucusu kapatılmadı). Kayıt sahiplenme iki Python sunucusunu
            ayırıyor ama eski sunucu sahiplenmeyi bilmiyor: alıcıya iki
            bildirim gider. Bunu yüksek sesle söylüyoruz.
        """
        onceki = self.db.oku(NABIZ_YOLU)
        if (self.son_nabiz is not None and isinstance(onceki, dict)
                and onceki.get('kimlik') != self.kimlik):
            if onceki.get('dil') == 'python':
                # Bu sürümün bir kopyası: kayıt sahiplenmeyi o da yapıyor,
                # ikisi birlikte çift gönderim yapmaz (biri yedek gibi çalışır).
                self._sinirli_gunluk('es', 'aynı veritabanında bir sunucu kopyası daha çalışıyor (%s); '
                                     'kayıt sahiplenme sayesinde çift gönderim olmaz',
                                     onceki.get('kimlik'), aralik=3600, seviye=logging.INFO)
            else:
                ne = 'eski (Node) bildirim sunucusu'
                if self.cakisma is None:
                    log.error('!!! BAŞKA BİR BİLDİRİM SUNUCUSU ÇALIŞIYOR: %s. O kayıt sahiplenmeyi '
                              'bilmiyor; ikisi birden çalıştıkça alıcılar ÇİFT bildirim alır. '
                              'Eskisini kapat.', ne)
                self.cakisma = ne
        elif isinstance(onceki, dict) and onceki.get('kimlik') == self.kimlik:
            self.cakisma = None
        t0 = time.time() * 1000
        with self.kilit:
            sayac = dict(self.sayac)
        self.db.yaz(NABIZ_YOLU, {
            'nabiz': {'.sv': 'timestamp'},
            'basladi': self.basladi,
            'kip': 'tek' if self.ayar.tek_sefer else 'surekli',
            'aralikMs': 0 if self.ayar.tek_sefer else int(self.ayar.nabiz_sn * 1000),
            'gonderilen': sayac['gonderilen'],
            'basarisiz': sayac['basarisiz'],
            'kurulumHatasi': self.kurulum_hatasi is not None,
            'cakisma': self.cakisma is not None,
            'dil': 'python',
            'kimlik': self.kimlik,
            'surum': SURUM,
        })
        deger = self.db.oku(NABIZ_YOLU + '/nabiz')
        t1 = time.time() * 1000
        if isinstance(deger, (int, float)):
            self.fark_ms = deger - (t0 + t1) / 2
            self.son_nabiz = deger

    def _nabiz_dongusu(self):
        while not self.dur.wait(self.ayar.nabiz_sn):
            try:
                self.nabiz_at()
            except Exception as e:
                self._sinirli_gunluk('nabiz', 'nabız yazılamadı: %s', e)

    # ---- akış (zil) ----

    def _akis_dongusu(self):
        """Kuyruktaki değişiklikleri anında haber veren olay akışı.

        Akıştan gelen veriyi YORUMLAMIYORUZ: her olay yalnız bir zil, zil
        çalınca kuyruk baştan okunuyor. Böylece kaçan, yarım gelen ya da
        yeniden bağlanırken arada kalan bir olay hiçbir kaydı kaybettirmiyor.
        """
        bekle = 1.0
        url = self.db.url(self.kuyruk)
        oturum = requests.Session()
        while not self.dur.is_set():
            try:
                b = dict(self.db.erisim.baslik())
                b['Accept'] = 'text/event-stream'
                y = oturum.get(url, headers=b, params=self.db.params, stream=True,
                               timeout=(10, AKIS_OKUMA_SN))
                if y.status_code == 401:
                    self.db.erisim.yenile()
                y.raise_for_status()
                self._akis_yaniti = y
                if not self.akis_bagli:
                    log.info('kuyruk akışına bağlanıldı')
                self.akis_bagli, bekle = True, 1.0
                self.zil.set()                  # bağlanırken arada kalan olmasın
                satir = bytearray()
                for parca in y.iter_content(chunk_size=1):
                    if self.dur.is_set():
                        break
                    if parca != b'\n':
                        satir += parca
                        continue
                    if satir.startswith(b'event:'):
                        olay = satir[6:].strip().decode('utf-8', 'replace')
                        if olay in ('put', 'patch'):
                            self.zil.set()
                        elif olay == 'auth_revoked':
                            self.db.erisim.yenile()
                            break
                        elif olay == 'cancel':
                            self._sinirli_gunluk('akis-iptal', 'akış izin hatasıyla kapandı '
                                                 '(servis hesabı bu veritabanına erişebiliyor mu?)')
                            break
                    satir.clear()
            except Exception as e:
                if not self.dur.is_set():
                    self._sinirli_gunluk('akis', 'kuyruk akışı koptu (%s); yeniden bağlanılacak',
                                         type(e).__name__)
            finally:
                self._akis_yaniti = None
            if self.dur.is_set():
                break
            if self.akis_bagli:
                log.info('kuyruk akışı kapandı; yeniden bağlanılıyor')
            self.akis_bagli = False
            self.zil.set()
            self.dur.wait(bekle)
            bekle = min(30.0, bekle * 2)

    # ---- tarama ----

    def tara(self):
        veri = self.db.oku(self.kuyruk)
        self.son_tarama_basarili = time.monotonic()
        if not isinstance(veri, dict):
            with self.kilit:
                self.yeniden.clear()
            return
        simdi_m = time.monotonic()
        for anahtar in sorted(veri):          # push anahtarı: sözlük sırası = zaman sırası
            with self.kilit:
                if anahtar in self.isleniyor:
                    continue
                vade = self.yeniden.get(anahtar)
                if vade is not None and vade > simdi_m:
                    continue
                if not B.sahiplenilebilir_mi(veri[anahtar], self.kimlik, self.sunucu_simdi()):
                    continue
                self.yeniden.pop(anahtar, None)
                self.isleniyor.add(anahtar)
            self.havuz.submit(self.isle, anahtar)
        with self.kilit:
            for a in list(self.yeniden):
                if a not in veri:
                    del self.yeniden[a]

    def _vadesi_gelen_var(self):
        simdi = time.monotonic()
        with self.kilit:
            return any(v <= simdi for v in self.yeniden.values())

    # ---- tek kayıt ----

    def _sahiplen(self, anahtar):
        yol = '%s/%s' % (self.kuyruk, anahtar)
        for _ in range(8):
            veri, etag = self.db.oku_etiketli(yol)
            if veri is None:
                return None
            if not B.sahiplenilebilir_mi(veri, self.kimlik, self.sunucu_simdi()):
                return None
            # Önceki sahibin yarım bıraktığı yeniden denemeyi (kalan cihazlar)
            # koruyoruz: devralan sunucu başarılı olanlara ikinci kez yollamasın.
            isleyen = dict(veri.get('isleyen') or {}) if isinstance(veri.get('isleyen'), dict) else {}
            isleyen.update(kimlik=self.kimlik, bitis=int(self.sunucu_simdi() + KIRA_MS))
            yeni = dict(veri)
            yeni['isleyen'] = isleyen
            if self.db.kosullu_yaz(yol, yeni, etag):
                return yeni
        return None

    def isle(self, anahtar):
        try:
            veri = self._sahiplen(anahtar)
            if veri is not None:
                self._isle(anahtar, veri)
            with self.kilit:
                self.hata_sayisi.pop(anahtar, None)
        except Exception as e:
            ag = gecici_ag_hatasi_mi(e)
            with self.kilit:
                # Ağ hatası SAYILMIYOR: bağlantı gidip gelirken kayıtlar atılmasın.
                n = self.hata_sayisi.get(anahtar, 0) + (0 if ag else 1)
                self.hata_sayisi[anahtar] = n
            self._sinirli_gunluk('isle-' + type(e).__name__, 'kayıt işlenemedi (%s): %s', anahtar, e)
            if n >= 5:
                # Hep aynı yerde patlayan bir kayıt kuyruğu sonsuza kadar meşgul etmesin.
                log.error('kayıt 5 kez işlenemedi, atılıyor: %s', anahtar)
                self._say('hatali')
                try:
                    self.db.sil('%s/%s' % (self.kuyruk, anahtar))
                except Exception:
                    pass
            else:
                with self.kilit:
                    self.yeniden[anahtar] = time.monotonic() + B.geri_cekilme_sn(
                        max(1, n), self.ayar.geri_cekilme_taban)
        finally:
            with self.kilit:
                self.isleniyor.discard(anahtar)

    def _sahiplik_haritasi(self):
        harita, zaman = self._sahiplik
        if time.monotonic() - zaman > 120:
            harita = B.sahiplik_haritasi(self.db.oku('cihazlar') or {})
            self._sahiplik = (harita, time.monotonic())
        return harita

    def _kurulum_uyarisi(self, hata):
        if self.kurulum_hatasi is None:
            log.error('========================================================')
            log.error('[KURULUM HATASI] FCM gönderimi reddedildi: %s %s', hata[0], hata[1])
            log.error('Servis hesabı anahtarı BU Firebase projesine ait değil gibi.')
            log.error('Firebase konsolu → Proje ayarları → Servis hesapları → yeni özel anahtar.')
            log.error('Cihaz kayıtlarına DOKUNULMADI.')
            log.error('========================================================')
        self.kurulum_hatasi = '%s %s %s' % hata

    def _isle(self, anahtar, veri):
        yol = '%s/%s' % (self.kuyruk, anahtar)
        isleyen = veri.get('isleyen') or {}
        deneme = int(isleyen.get('deneme') or 0)
        kalan = isleyen.get('kalan')
        kayit = {k: v for k, v in veri.items() if k != 'isleyen'}
        if deneme == 0:
            self._say('alinan')

        if not B.kayit_gecerli_mi(kayit):
            self._say('hatali')
            log.info('geçersiz kayıt atıldı: %s', anahtar)
            return self.db.sil(yol)
        neden = B.bayat_mi(kayit, self.sunucu_simdi())
        if neden:
            self._say('eski')
            log.info('%s, gönderilmeden atıldı: %s', neden, anahtar)
            return self.db.sil(yol)
        if deneme == 0 and not self.hiz.izin_ver(kayit['gonderen'], time.monotonic()):
            self._say('hiz_siniri')
            self._sinirli_gunluk('hiz-' + kayit['gonderen'], 'hız sınırı aşıldı, kayıtlar atılıyor: %s',
                                 kayit['gonderen'][:8])
            return self.db.sil(yol)

        hedef = kayit['hedef']
        cihazlar = self.db.oku('cihazlar/' + hedef) or {}
        isler, devredilen = B.mesajlari_kur(
            kayit, cihazlar, anahtar, self._sahiplik_haritasi(),
            set(kalan) if isinstance(kalan, list) else None)
        for a in devredilen:
            self._say('devredilen')
            log.info('belirteç başka bir hesaba geçmiş, %s altından silindi: %s', hedef[:8], a)
            self.db.sil('cihazlar/%s/%s' % (hedef, a))
        if not isler:
            log.info('hedefin gönderilecek cihazı yok: %s', hedef[:8])
            return self.db.sil(yol)

        yeniden, basarili = [], 0
        for cihaz_anahtari, mesaj in isler:
            tamam, hata = self.fcm.gonder(mesaj)
            if tamam:
                basarili += 1
                self.basari_goruldu = True
                continue
            self._say('basarisiz')
            tur = B.hata_turu(hata[0], hata[1], hata[2], self.basari_goruldu)
            if tur == 'olu':
                self._say('olu_belirtec')
                log.info('ölü belirteç silindi (%s): %s/%s', hata[1] or hata[0], hedef[:8], cihaz_anahtari)
                self.db.sil('cihazlar/%s/%s' % (hedef, cihaz_anahtari))
            elif tur == 'gecici':
                yeniden.append(cihaz_anahtari)
            elif tur == 'kurulum':
                self._kurulum_uyarisi(hata)
            else:
                log.warning('gönderilemedi (%s %s): %s', hata[0], hata[1], hata[2][:120])
        self._say('gonderilen', basarili)
        log.info('gönderildi: %s → %s | cihaz %d/%d%s', kayit.get('tur') or 'mesaj', hedef[:8],
                 basarili, len(isler), (' | yeniden: %d' % len(yeniden)) if yeniden else '')

        if yeniden and deneme + 1 < B.EN_COK_DENEME:
            bekle = B.geri_cekilme_sn(deneme + 1, self.ayar.geri_cekilme_taban)
            self._say('yeniden_deneme')
            self.db.yaz(yol + '/isleyen', {
                'kimlik': self.kimlik,
                'bitis': int(self.sunucu_simdi() + bekle * 1000 + KIRA_MS),
                'kalan': yeniden,
                'deneme': deneme + 1,
            })
            with self.kilit:
                self.yeniden[anahtar] = time.monotonic() + bekle
            return None
        if yeniden:
            log.warning('%d cihaza %d denemede ulaşılamadı, vazgeçildi: %s', len(yeniden),
                        B.EN_COK_DENEME, anahtar)
        return self.db.sil(yol)

    # ---- ana döngü ----

    def _bekci(self):
        """Ana döngü bir yerde takılırsa süreci bitir: systemd yeniden başlatır.
        Takılan bir sunucu, çökmüş bir sunucudan kötü: dışarıdan çalışıyor
        görünür ama hiçbir şey göndermez."""
        while not self.dur.wait(15):
            if time.monotonic() - self.son_dongu > 180:
                log.critical('ana döngü 3 dakikadır ilerlemiyor; süreç yeniden başlatılmak üzere bitiyor')
                logging.shutdown()
                os._exit(70)

    def durdur(self, *_):
        if not self.dur.is_set():
            log.info('kapanıyor…')
        self.dur.set()
        self.zil.set()
        # Akış bağlantısını kapatmak, okuyan iş parçacığının tuttuğu kilidi
        # bekleyebiliyor. Bunu sinyal işleyicisinde (ana iş parçacığı) yapmak
        # kapanışı 90 sn'ye kadar kilitliyordu — sınamada ölçüldü. Ayrı ve
        # arka plan iş parçacığında, bekletmeden.
        threading.Thread(target=self._akisi_kapat, daemon=True).start()

    def _akisi_kapat(self):
        y = self._akis_yaniti
        if y is not None:
            try:
                y.close()
            except Exception:
                pass

    def calistir(self):
        log.info('Meridyen bildirim sunucusu %s başladı. kimlik=%s kuyruk=%s%s', SURUM, self.kimlik,
                 self.kuyruk, ' (tek sefer)' if self.ayar.tek_sefer else '')
        try:
            self.nabiz_at()
            log.info('veritabanına ulaşıldı; saat farkı %+d ms', self.fark_ms)
        except Exception as e:
            log.warning('ilk nabız yazılamadı (%s); devam ediliyor', e)

        if self.ayar.tek_sefer:
            return self._tek_sefer()

        threading.Thread(target=self._nabiz_dongusu, name='nabiz', daemon=True).start()
        threading.Thread(target=self._bekci, name='bekci', daemon=True).start()
        if not self.ayar.akis_kapali:
            threading.Thread(target=self._akis_dongusu, name='akis', daemon=True).start()
        self.zil.set()
        while not self.dur.is_set():
            self.son_dongu = time.monotonic()
            calindi = self.zil.wait(1.0)
            if self.dur.is_set():
                break
            if calindi:
                self.zil.clear()
                time.sleep(0.05)        # art arda gelen olayları tek taramada topla
            gerek = (calindi or time.monotonic() - self.son_tarama >= self.ayar.tarama_sn
                     or self._vadesi_gelen_var())
            if not gerek:
                continue
            self.son_tarama = time.monotonic()
            try:
                self.tara()
            except Exception as e:
                self._sinirli_gunluk('tara', 'kuyruk okunamadı: %s', e)
        self.havuz.shutdown(wait=True)
        log.info('kapandı. sayaç: %s', json.dumps(self.sayac))

    def _tek_sefer(self):
        """Kuyruğu boşalt ve çık (zamanlanmış görevle çalıştırmak için)."""
        son = time.monotonic() + 600
        while time.monotonic() < son and not self.dur.is_set():
            try:
                self.tara()
            except Exception as e:
                self._sinirli_gunluk('tara', 'kuyruk okunamadı: %s', e)
            time.sleep(0.2)
            with self.kilit:
                bos = not self.isleniyor and not self.yeniden
            if bos:
                break
            # yalnız yeniden denemeler kaldıysa vadelerini bekle
            time.sleep(0.3)
        self.havuz.shutdown(wait=True)
        try:
            self.nabiz_at()
        except Exception:
            pass
        log.info('kuyruk boş, çıkılıyor. sayaç: %s', json.dumps(self.sayac))

    # ---- sağlık ucu ----

    def durum(self):
        simdi = time.monotonic()
        tarama_once = simdi - self.son_tarama_basarili if self.son_tarama_basarili else None
        saglikli = (tarama_once is not None and tarama_once < 3 * self.ayar.tarama_sn + 60
                    and self.kurulum_hatasi is None)
        with self.kilit:
            sayac = dict(self.sayac)
            isleniyor, yeniden = len(self.isleniyor), len(self.yeniden)
        return saglikli, {
            'durum': 'çalışıyor' if saglikli else 'SORUNLU',
            'surum': SURUM, 'kimlik': self.kimlik,
            'calismaSuresiSn': int(time.time() - self.basladi / 1000),
            'akisBagli': self.akis_bagli,
            'sonBasariliTaramaSnOnce': None if tarama_once is None else round(tarama_once, 1),
            'saatFarkiMs': round(self.fark_ms),
            'isleniyor': isleniyor, 'yenidenDenenecek': yeniden,
            'kurulumHatasi': self.kurulum_hatasi,
            'baskaSunucu': self.cakisma,
            'sayac': sayac,
        }

    def saglik_ucunu_ac(self):
        if self.ayar.port <= 0:
            return None
        sunucu = self

        class Isleyici(BaseHTTPRequestHandler):
            def do_GET(self):
                saglikli, d = sunucu.durum()
                govde = json.dumps(d, ensure_ascii=False, indent=1).encode('utf-8')
                self.send_response(200 if saglikli else 503)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(govde)))
                self.end_headers()
                self.wfile.write(govde)

            def log_message(self, *a):
                pass

        try:
            h = ThreadingHTTPServer(('0.0.0.0', self.ayar.port), Isleyici)
        except OSError as e:
            log.warning('sağlık ucu açılamadı (port %d): %s', self.ayar.port, e)
            return None
        threading.Thread(target=h.serve_forever, name='saglik', daemon=True).start()
        log.info('sağlık ucu: http://localhost:%d', h.server_address[1])
        return h


def kur(ortam=os.environ):
    ayar = Ayar(ortam)
    if not ayar.servis_hesabi and not ayar.emulator:
        cik('Servis hesabı anahtarı yok.\n'
            'MERIDYEN_SERVIS_HESABI_DOSYASI ile anahtar dosyasının yolunu ver (ya da\n'
            'MERIDYEN_SERVIS_HESABI ile JSON içeriğini). Bkz. README.md')
    erisim = Erisim(ayar.servis_hesabi)
    return ayar, Veritabani(ayar, erisim), Fcm(ayar, erisim)


def main():
    logging.basicConfig(level=os.environ.get('MERIDYEN_GUNLUK', 'INFO'),
                        format='%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    ayar, db, fcm = kur()
    s = Sunucu(ayar, db, fcm, os.environ.get('MERIDYEN_KIMLIK') or kimlik_al(ayar.kimlik_dosyasi))
    signal.signal(signal.SIGTERM, s.durdur)
    signal.signal(signal.SIGINT, s.durdur)
    s.saglik_ucunu_ac()
    s.calistir()


if __name__ == '__main__':
    main()
