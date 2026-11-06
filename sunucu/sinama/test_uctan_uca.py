#!/usr/bin/env python3
"""Bildirim sunucusu — UÇTAN UCA sınama.

Gerçek sunucu süreçleri (sunucu.py) GERÇEK bir Realtime Database emülatörüne
bağlanıyor; FCM'in yerinde sahte bir HTTP sunucusu var (sahte_fcm.py).
Ölçülenler: her bildirim her cihaza TAM BİR KEZ gidiyor mu — iki sunucu aynı
anda çalışırken, sunucu yeniden denemenin ortasında öldürülüp yeniden
başlatılırken, veritabanı bağlantısı kopup geri gelirken.

Gereken: Java + firebase-tools + requests + google-auth.
  python3 sinama/test_uctan_uca.py
firebase-tools yolu: MERIDYEN_FIREBASE (yoksa ~/.cache/meridyen-araclar).
"""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import traceback

import requests

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sahte_fcm import SahteFcm  # noqa: E402

FIREBASE = os.environ.get('MERIDYEN_FIREBASE') or os.path.expanduser(
    '~/.cache/meridyen-araclar/node_modules/.bin/firebase')
NS = 'demo-meridyen'
T = []


def ok(ad, kosul, ayrinti=''):
    T.append((ad, bool(kosul)))
    print(('  ✓ ' if kosul else '  ✗ ') + ad + ('' if kosul or not ayrinti else '  — ' + str(ayrinti)))


def bos_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def bekle(kosul, sure=20.0, aralik=0.1):
    son = time.time() + sure
    while time.time() < son:
        try:
            if kosul():
                return True
        except Exception:
            pass
        time.sleep(aralik)
    return False


def belirtec(ad):
    return (ad + '_' + 'x' * 30)[:40]


class Emulator:
    def __init__(self, gecici):
        self.port = bos_port()
        self.dizin = os.path.join(gecici, 'emu')
        os.makedirs(self.dizin, exist_ok=True)
        with open(os.path.join(self.dizin, 'firebase.json'), 'w') as f:
            json.dump({'emulators': {'database': {'port': self.port, 'host': '127.0.0.1'},
                                     'ui': {'enabled': False}}}, f)
        self.surec = None
        self.taban = 'http://127.0.0.1:%d' % self.port

    def baslat(self):
        self.gunluk = open(os.path.join(self.dizin, 'emu.log'), 'a')
        self.surec = subprocess.Popen(
            [FIREBASE, 'emulators:start', '--only', 'database', '--project', NS,
             '--config', os.path.join(self.dizin, 'firebase.json')],
            cwd=self.dizin, stdout=self.gunluk, stderr=subprocess.STDOUT, start_new_session=True)
        if not bekle(lambda: requests.get(self.url(''), timeout=2).status_code == 200, 90, 0.5):
            raise RuntimeError('emülatör açılmadı; günlük: ' + os.path.join(self.dizin, 'emu.log'))

    def durdur(self):
        """Emülatörü SERT öldürür: bağlantılar bir anda kopsun.

        firebase-tools emülatörün Java sürecini AYRI bir süreç grubunda
        başlatıyor; yalnız komutun grubunu öldürmek Java'yı ayakta bırakıyordu
        (sınama da eski emülatörle devam edip "bağlantı koptu" senaryosunu hiç
        sınamamış oluyordu). Java'yı portundan bulup öldürüyoruz."""
        if self.surec and self.surec.poll() is None:
            os.killpg(self.surec.pid, signal.SIGKILL)
            self.surec.wait()
        subprocess.run(['pkill', '-9', '-f', '--', 'database-emulator.*--port %d' % self.port], check=False)
        if not bekle(lambda: not self._acik(), 20):
            raise RuntimeError('emülatör kapanmadı (port %d hâlâ açık)' % self.port)

    def _acik(self):
        try:
            socket.create_connection(('127.0.0.1', self.port), 0.5).close()
            return True
        except OSError:
            return False

    def url(self, yol):
        return '%s/%s.json?ns=%s' % (self.taban, yol.strip('/'), NS)

    H = {'Authorization': 'Bearer owner'}

    def put(self, yol, deger):
        requests.put(self.url(yol), json=deger, headers=self.H, timeout=10).raise_for_status()

    def get(self, yol):
        return requests.get(self.url(yol), headers=self.H, timeout=10).json()

    def push(self, yol, deger):
        y = requests.post(self.url(yol), json=deger, headers=self.H, timeout=10)
        y.raise_for_status()
        return y.json()['name']


class SunucuSureci:
    def __init__(self, gecici, emu, fcm, ad, ek_ortam=None):
        self.ad = ad
        self.gunluk_yolu = os.path.join(gecici, ad + '.log')
        self.saglik_port = bos_port()
        self.ortam = dict(os.environ)
        self.ortam.update({
            'FIREBASE_DATABASE_EMULATOR_HOST': '127.0.0.1:%d' % emu.port,
            'MERIDYEN_DB_NS': NS,
            'MERIDYEN_FCM_URL': 'http://127.0.0.1:%d' % fcm.port,
            'MERIDYEN_PROJE': 'demo',
            'MERIDYEN_KIMLIK_DOSYASI': os.path.join(gecici, ad + '.kimlik'),
            # Makinede gerçek bir sunucu/.env varsa sınama sunucuları onu OKUMASIN.
            'MERIDYEN_ENV_DOSYASI': os.path.join(gecici, 'olmayan.env'),
            'MERIDYEN_GERI_CEKILME_SN': '0.25',
            'MERIDYEN_TARAMA_SN': '2',
            'MERIDYEN_NABIZ_SN': '1',
            'PORT': str(self.saglik_port),
            'PYTHONUNBUFFERED': '1',
        })
        self.ortam.pop('MERIDYEN_SERVIS_HESABI', None)
        self.ortam.update(ek_ortam or {})
        self.surec = None

    def baslat(self):
        self.gunluk = open(self.gunluk_yolu, 'a')
        self.surec = subprocess.Popen([sys.executable, os.path.join(KOK, 'sunucu.py')], env=self.ortam,
                                      cwd=KOK, stdout=self.gunluk, stderr=subprocess.STDOUT,
                                      start_new_session=True)
        return self

    def saglik(self):
        return requests.get('http://127.0.0.1:%d/' % self.saglik_port, timeout=2)

    def oldur(self):          # kill -9: kapanış kodu hiç çalışmasın
        if self.surec and self.surec.poll() is None:
            os.kill(self.surec.pid, signal.SIGKILL)
            self.surec.wait()

    def durdur(self):
        if self.surec and self.surec.poll() is None:
            self.surec.send_signal(signal.SIGTERM)
            try:
                self.surec.wait(15)
            except subprocess.TimeoutExpired:
                self.oldur()

    def gunluk_metni(self):
        with open(self.gunluk_yolu, encoding='utf-8', errors='replace') as f:
            return f.read()


def sayim(basarilar, mid=None):
    """(belirteç, mid) → kaç kez başarıyla gönderildi."""
    s = {}
    for t, d in basarilar:
        if mid is None or d.get('mid') == mid:
            s[(t, d.get('mid'))] = s.get((t, d.get('mid')), 0) + 1
    return s


def simdi_ms():
    return int(time.time() * 1000)


def kayit(hedef, gonderen='SEMIH', **ek):
    k = {'hedef': hedef, 'gonderen': gonderen, 'gonderenAd': 'Semih', 'tur': 'mesaj',
         'baslik': 'Semih', 'metin': 'merhaba', 'ts': {'.sv': 'timestamp'}}
    k.update(ek)
    return k


def senaryolar(emu, fcm, gecici):
    def temiz(veri):
        fcm.sifirla()
        emu.put('', veri)

    # ---------------------------------------------------------------- temel
    print('\n— temel gönderim, gizlilik, ölü belirteç')
    temiz({'cihazlar': {
        'AYSE': {
            'tel': {'belirtec': belirtec('TEL'), 'icerikGoster': True, 'ts': 10},
            'tel2': {'belirtec': belirtec('TEL'), 'icerikGoster': True, 'ts': 10},   # aynı belirteç
            'masa': {'belirtec': belirtec('MASA'), 'icerikGoster': False, 'ts': 10},
            'olu': {'belirtec': belirtec('OLU'), 'ts': 10},
            'yuk': {'belirtec': belirtec('YUKHATASI'), 'ts': 10},
        }}})
    s = SunucuSureci(gecici, emu, fcm, 's1').baslat()
    emu.push('bildirimKuyrugu', kayit('AYSE', mid='-MID1', metin='gizli metin'))
    ok('kayıt işlenip kuyruktan silindi', bekle(lambda: emu.get('bildirimKuyrugu') is None))
    _, b = fcm.kopya()
    ok('her farklı belirtece TAM bir kez (aynı belirteç iki kayıtta: tek)',
       sayim(b) == {(belirtec('TEL'), '-MID1'): 1, (belirtec('MASA'), '-MID1'): 1}, sayim(b))
    ok('mesaj anahtarı (mid) push verisinde', all(d['mid'] == '-MID1' for _, d in b))
    ok('içerik açık cihazda metin var', any(t == belirtec('TEL') and d['body'] == 'gizli metin' for t, d in b))
    ok('içerik kapalı cihaza metin GİTMEDİ', all('gizli metin' not in json.dumps(d) for t, d in b if t == belirtec('MASA')))
    c = emu.get('cihazlar/AYSE') or {}
    ok('ölü belirteç silindi', 'olu' not in c)
    ok('yük hatası belirteci silmedi', 'yuk' in c)
    ok('canlı belirteçler duruyor', 'tel' in c and 'masa' in c)
    n = emu.get('sistem/bildirimSunucusu') or {}
    ok('nabız yazıldı (python, kimlik, sunucu zamanı)',
       n.get('dil') == 'python' and n.get('kimlik') and isinstance(n.get('nabiz'), int) and n.get('kip') == 'surekli')
    y = s.saglik()
    ok('sağlık ucu 200 ve sayaç', y.status_code == 200 and y.json()['sayac']['gonderilen'] >= 2, y.text[:200])

    # ---------------------------------------------------------------- bayat/geçersiz
    print('\n— bayat çağrı, bayat mesaj, geçersiz kayıt, kendine bildirim')
    fcm.sifirla()
    simdi = simdi_ms()
    emu.push('bildirimKuyrugu', kayit('AYSE', tur='arama', ts=simdi - 120_000, mid='-ESKICAGRI'))
    emu.push('bildirimKuyrugu', kayit('AYSE', ts=simdi - 2 * 3600_000, mid='-ESKIMESAJ'))
    emu.push('bildirimKuyrugu', {'gonderen': 'X'})
    emu.push('bildirimKuyrugu', kayit('SEMIH'))
    emu.push('bildirimKuyrugu', kayit('AYSE', tur='arama', aramaTuru='goruntu', mid='-YENICAGRI'))
    ok('hepsi kuyruktan silindi', bekle(lambda: emu.get('bildirimKuyrugu') is None))
    _, b = fcm.kopya()
    mids = {d['mid'] for _, d in b}
    ok('2 dk önceki çağrının zili ÇALMADI', '-ESKICAGRI' not in mids)
    ok('2 saat önceki mesaj gönderilmedi', '-ESKIMESAJ' not in mids)
    ok('taze çağrı gitti (tür, görüntülü, ayrı etiket)',
       any(d['mid'] == '-YENICAGRI' and d['tur'] == 'arama' and d['aramaTuru'] == 'goruntu'
           and d['tag'] == 'meridyen-cagri-SEMIH' for _, d in b))
    ok('geçersiz ve kendine kayıt gönderilmedi', mids == {'-YENICAGRI'}, mids)

    # ---------------------------------------------------------------- kısmi geçici hata
    print('\n— kısmi geçici hata: yalnız başarısız cihaza yeniden')
    temiz({'cihazlar': {'MERT': {
        'iyi': {'belirtec': belirtec('IYI'), 'ts': 1},
        'gecici': {'belirtec': belirtec('GECICI2'), 'ts': 1},
        'hep': {'belirtec': belirtec('HEP_GECICI'), 'ts': 1}}}})
    emu.push('bildirimKuyrugu', kayit('MERT', mid='-KISMI'))
    ok('kayıt sonunda silindi', bekle(lambda: emu.get('bildirimKuyrugu') is None, 40))
    d, b = fcm.kopya()
    deneme = {}
    for t, _ in d:
        deneme[t] = deneme.get(t, 0) + 1
    ok('başarılı cihaza İKİNCİ kez gitmedi', deneme.get(belirtec('IYI')) == 1, deneme)
    ok('geçici hatalı cihaz yeniden denendi ve ulaştı (3 deneme, 1 başarı)',
       deneme.get(belirtec('GECICI2')) == 3 and sayim(b).get((belirtec('GECICI2'), '-KISMI')) == 1, deneme)
    ok('hep başarısız cihaz en çok 5 kez denendi', deneme.get(belirtec('HEP_GECICI')) == 5, deneme)
    ok('geçici hata belirteci silmedi', 'hep' in (emu.get('cihazlar/MERT') or {}))

    # ---------------------------------------------------------------- hesap değişimi
    print('\n— hesap değiştirilmiş telefon')
    temiz({'cihazlar': {
        'ESKI': {'x': {'belirtec': belirtec('ORTAK'), 'ts': 1000}},
        'YENI': {'y': {'belirtec': belirtec('ORTAK'), 'ts': 2000}}}})
    time.sleep(0.2)
    s.durdur()                 # sahiplik önbelleği taze okunsun
    s = SunucuSureci(gecici, emu, fcm, 's1').baslat()
    emu.push('bildirimKuyrugu', kayit('ESKI', mid='-ESKIYE'))
    emu.push('bildirimKuyrugu', kayit('YENI', mid='-YENIYE'))
    ok('kuyruk boşaldı', bekle(lambda: emu.get('bildirimKuyrugu') is None))
    _, b = fcm.kopya()
    ok('eski hesabın mesajı telefona GİTMEDİ', not any(d['mid'] == '-ESKIYE' for _, d in b))
    ok('yeni hesabın mesajı gitti', any(d['mid'] == '-YENIYE' for _, d in b))
    ok('eski hesaptaki kayıt silindi', emu.get('cihazlar/ESKI') is None)
    s.durdur()

    # ---------------------------------------------------------------- iki sunucu
    print('\n— İKİ sunucu aynı anda: her bildirim tam bir kez')
    temiz({'cihazlar': {'ZEY': {'a': {'belirtec': belirtec('ZA'), 'ts': 1},
                                'b': {'belirtec': belirtec('ZB'), 'ts': 1}}}})
    s1 = SunucuSureci(gecici, emu, fcm, 'c1').baslat()
    s2 = SunucuSureci(gecici, emu, fcm, 'c2').baslat()
    time.sleep(2.5)
    mids = []
    for i in range(40):
        mids.append('-IKI%02d' % i)
        emu.push('bildirimKuyrugu', kayit('ZEY', gonderen='G%d' % (i % 4), mid=mids[-1]))
    ok('40 kayıt işlendi', bekle(lambda: emu.get('bildirimKuyrugu') is None, 40))
    time.sleep(1)
    _, b = fcm.kopya()
    sy = sayim(b)
    ok('80 gönderim (40 kayıt × 2 cihaz), hiçbiri iki kez değil',
       len(b) == 80 and all(v == 1 for v in sy.values()) and len(sy) == 80, (len(b), max(sy.values()) if sy else 0))
    i1 = s1.saglik().json()['sayac']['alinan']
    i2 = s2.saglik().json()['sayac']['alinan']
    ok('iş iki sunucuya bölündü (%d + %d)' % (i1, i2), i1 + i2 == 40)
    n = emu.get('sistem/bildirimSunucusu') or {}
    ok('iki Python sunucusu birbirini çakışma saymıyor', n.get('cakisma') is False, n)
    s1.durdur(); s2.durdur()

    # ---------------------------------------------------------------- eski Node sunucusu
    print('\n— eski (Node) sunucusu hâlâ açık: yüksek sesle uyarı')
    temiz({})
    s = SunucuSureci(gecici, emu, fcm, 's3').baslat()
    ok('nabız yazıldı', bekle(lambda: (emu.get('sistem/bildirimSunucusu') or {}).get('dil') == 'python'))
    for _ in range(4):        # Node sunucusu da her saniye kendi nabzını yazıyor gibi
        emu.put('sistem/bildirimSunucusu', {'nabiz': simdi_ms(), 'kip': 'surekli', 'aralikMs': 60000})
        time.sleep(1.1)
    ok('çakışma fark edildi (nabızda ve sağlık ucunda)',
       bekle(lambda: (emu.get('sistem/bildirimSunucusu') or {}).get('cakisma') is True, 10)
       and s.saglik().json()['baskaSunucu'])
    s.durdur()

    # ---------------------------------------------------------------- kill -9 yeniden denemenin ortasında
    print('\n— sunucu yeniden denemenin ORTASINDA öldürülüyor (kill -9)')
    temiz({'cihazlar': {'CAN': {'iyi': {'belirtec': belirtec('CIYI'), 'ts': 1},
                                'gec': {'belirtec': belirtec('GECICI4'), 'ts': 1}}}})
    s = SunucuSureci(gecici, emu, fcm, 's4', {'MERIDYEN_GERI_CEKILME_SN': '1.5'}).baslat()
    emu.push('bildirimKuyrugu', kayit('CAN', mid='-OLDUR'))
    ok('ilk tur gönderildi', bekle(lambda: len(fcm.kopya()[1]) == 1))
    ok('kalan cihaz kayda yazıldı', bekle(lambda: (list((emu.get('bildirimKuyrugu') or {}).values()) or [{}])[0]
                                          .get('isleyen', {}).get('kalan') == ['gec']))
    s.oldur()
    s = SunucuSureci(gecici, emu, fcm, 's4', {'MERIDYEN_GERI_CEKILME_SN': '0.25'}).baslat()  # AYNI kimlik
    ok('yeniden başlayan sunucu bitirdi', bekle(lambda: emu.get('bildirimKuyrugu') is None, 40))
    d, b = fcm.kopya()
    ok('başarılı cihaza ikinci kez gitmedi', sayim(b).get((belirtec('CIYI'), '-OLDUR')) == 1, sayim(b))
    ok('kalan cihaz sonunda ulaştı', sayim(b).get((belirtec('GECICI4'), '-OLDUR')) == 1, d)
    s.durdur()

    # ---------------------------------------------------------------- başka sunucunun kirası
    print('\n— başka sunucunun kirası')
    temiz({'cihazlar': {'KIRA': {'a': {'belirtec': belirtec('KA'), 'ts': 1}}},
           'bildirimKuyrugu': {
               'dolmus': dict(kayit('KIRA', mid='-DOLMUS', ts=simdi_ms()),
                              isleyen={'kimlik': 'baska', 'bitis': simdi_ms() - 1000}),
               'gecerli': dict(kayit('KIRA', mid='-GECERLI', ts=simdi_ms()),
                               isleyen={'kimlik': 'baska', 'bitis': simdi_ms() + 600_000})}})
    s = SunucuSureci(gecici, emu, fcm, 's5').baslat()
    ok('kirası dolmuş kayıt devralındı', bekle(lambda: 'dolmus' not in (emu.get('bildirimKuyrugu') or {})))
    time.sleep(3)
    ok('kirası süren başkasının kaydına dokunulmadı',
       'gecerli' in (emu.get('bildirimKuyrugu') or {}) and not any(d['mid'] == '-GECERLI' for _, d in fcm.kopya()[1]))
    s.durdur()

    # ---------------------------------------------------------------- bağlantı kopması
    print('\n— veritabanı bağlantısı kopuyor (emülatör öldürülüp yeniden açılıyor)')
    temiz({'cihazlar': {'KOP': {'a': {'belirtec': belirtec('KOPA'), 'ts': 1}}}})
    s = SunucuSureci(gecici, emu, fcm, 's6', {'MERIDYEN_TARAMA_SN': '600'}).baslat()  # tarama değil, AKIŞ
    emu.push('bildirimKuyrugu', kayit('KOP', mid='-ONCE'))
    ok('akış bağlı, kayıt anında işlendi', bekle(lambda: emu.get('bildirimKuyrugu') is None, 10))
    emu.durdur()
    time.sleep(3)
    emu.baslat()
    emu.put('cihazlar', {'KOP': {'a': {'belirtec': belirtec('KOPA'), 'ts': 1}}})
    emu.push('bildirimKuyrugu', kayit('KOP', mid='-SONRA'))
    ok('yeniden bağlanıp yeni kaydı işledi', bekle(lambda: emu.get('bildirimKuyrugu') is None, 60))
    ok('kopukluktan sonraki bildirim tam bir kez',
       sayim(fcm.kopya()[1]).get((belirtec('KOPA'), '-SONRA')) == 1, sayim(fcm.kopya()[1]))
    s.durdur()
    ok('sunucu SIGTERM ile düzgün kapandı', s.surec.returncode == 0, s.surec.returncode)

    # ---------------------------------------------------------------- yalnız tarama
    print('\n— akış hiç kurulamasa bile tarama kayıtları işliyor')
    temiz({'cihazlar': {'TAR': {'a': {'belirtec': belirtec('TARA'), 'ts': 1}}}})
    s = SunucuSureci(gecici, emu, fcm, 's7', {'MERIDYEN_AKIS_KAPALI': '1'}).baslat()
    emu.push('bildirimKuyrugu', kayit('TAR', mid='-TARAMA'))
    ok('tarama ile işlendi', bekle(lambda: emu.get('bildirimKuyrugu') is None, 15))
    s.durdur()

    # ---------------------------------------------------------------- kurulum hatası
    print('\n— yanlış servis hesabı: belirteçlere DOKUNULMUYOR')
    temiz({'cihazlar': {'KUR': {'a': {'belirtec': belirtec('YANLISANAHTAR'), 'ts': 1},
                                'b': {'belirtec': belirtec('UCUNCU'), 'ts': 1}}}})
    s = SunucuSureci(gecici, emu, fcm, 's8').baslat()     # hiç başarı görmemiş sunucu
    emu.push('bildirimKuyrugu', kayit('KUR', mid='-KUR'))
    ok('kayıt işlendi', bekle(lambda: emu.get('bildirimKuyrugu') is None))
    ok('cihaz kayıtları silinmedi', set((emu.get('cihazlar/KUR') or {}).keys()) == {'a', 'b'})
    ok('nabızda kurulum hatası bildiriliyor', bekle(
        lambda: (emu.get('sistem/bildirimSunucusu') or {}).get('kurulumHatasi') is True, 10))
    ok('sağlık ucu 503 diyor', s.saglik().status_code == 503)
    s.durdur()

    # ---------------------------------------------------------------- hız sınırı
    print('\n— hız sınırı')
    temiz({'cihazlar': {'HIZ': {'a': {'belirtec': belirtec('HIZA'), 'ts': 1}}}})
    for i in range(40):
        emu.push('bildirimKuyrugu', kayit('HIZ', gonderen='SELDUZ', mid='-H%02d' % i))
    s = SunucuSureci(gecici, emu, fcm, 's9').baslat()
    ok('kuyruk boşaldı', bekle(lambda: emu.get('bildirimKuyrugu') is None, 30))
    n = len(fcm.kopya()[1])
    ok('tek gönderenden 40 kayıt: en çok ~30 gönderildi (%d)' % n, 30 <= n <= 32)
    s.durdur()

    # ---------------------------------------------------------------- .env
    print('\n— ayarlar YALNIZ .env dosyasında (set -a yok)')
    temiz({'cihazlar': {'ENV': {'a': {'belirtec': belirtec('ENVA'), 'ts': 1}}}})
    s = SunucuSureci(gecici, emu, fcm, 's11')
    env_yolu = os.path.join(gecici, 'sinama.env')
    tasinan = ['FIREBASE_DATABASE_EMULATOR_HOST', 'MERIDYEN_DB_NS', 'MERIDYEN_FCM_URL', 'MERIDYEN_PROJE']
    with open(env_yolu, 'w') as f:
        f.write('# yorum\n')
        for ad in tasinan:
            f.write('%s="%s"\n' % (ad, s.ortam.pop(ad)))
    s.ortam['MERIDYEN_ENV_DOSYASI'] = env_yolu
    s.baslat()
    emu.push('bildirimKuyrugu', kayit('ENV', mid='-ENV'))
    ok('ortamda hiçbir ayar yokken .env ile bağlandı ve gönderdi',
       bekle(lambda: sayim(fcm.kopya()[1]).get((belirtec('ENVA'), '-ENV')) == 1, 15))
    ok('günlükte okunan dosya yazıyor', env_yolu in s.gunluk_metni())
    s.durdur()
    k = subprocess.run([sys.executable, os.path.join(KOK, 'dene.py'), '--kontrol'], cwd=gecici,
                       env=s.ortam, capture_output=True, text=True, timeout=60)
    ok('dene.py --kontrol .env ile "TAMAM" diyor, hiçbir şey göndermeden',
       k.returncode == 0 and 'Kurulum TAMAM' in k.stdout and fcm.dogrulamalar == 1
       and sayim(fcm.kopya()[1]).get((belirtec('ENVA'), '-ENV')) == 1, k.stdout + k.stderr)

    # ---------------------------------------------------------------- tek sefer
    print('\n— tek sefer kipi')
    temiz({'cihazlar': {'TEK': {'a': {'belirtec': belirtec('TEKA'), 'ts': 1}}}})
    emu.push('bildirimKuyrugu', kayit('TEK', mid='-TEK'))
    s = SunucuSureci(gecici, emu, fcm, 's10', {'MERIDYEN_TEK_SEFER': '1', 'PORT': '0'}).baslat()
    try:
        s.surec.wait(30)
    except subprocess.TimeoutExpired:
        s.oldur()
    ok('kuyruğu boşaltıp kendiliğinden çıktı', s.surec.returncode == 0 and emu.get('bildirimKuyrugu') is None)
    ok('gönderdi', sayim(fcm.kopya()[1]).get((belirtec('TEKA'), '-TEK')) == 1)
    ok('nabız kipi "tek"', (emu.get('sistem/bildirimSunucusu') or {}).get('kip') == 'tek')


def main():
    if not os.path.exists(FIREBASE) or not shutil.which('java'):
        sys.exit('HATA: firebase-tools (%s) ve java gerekli.' % FIREBASE)
    gecici = tempfile.mkdtemp(prefix='meridyen-uctan-uca-')
    emu = Emulator(gecici)
    fcm = SahteFcm()
    try:
        emu.baslat()
        senaryolar(emu, fcm, gecici)
    except Exception:
        traceback.print_exc()
        T.append(('beklenmeyen hata', False))
    finally:
        subprocess.run(['pkill', '-f', 'sunucu.py'], check=False) if os.environ.get('MERIDYEN_PKILL') else None
        emu.durdur()
        fcm.kapat()
    kotu = [a for a, k in T if not k]
    print('\n  günlükler: ' + gecici)
    print('\n  %d BAŞARISIZ / %d' % (len(kotu), len(T)) if kotu else '\n  TUMU GECTI (%d)' % len(T))
    sys.exit(1 if kotu else 0)


if __name__ == '__main__':
    main()
