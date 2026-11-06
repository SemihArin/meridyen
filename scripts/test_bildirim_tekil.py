#!/usr/bin/env python3
"""Meridyen — aynı mesajın iki yoldan gelen bildirimi AYNI anahtarı taşıyor mu?

APK arka plandayken bir mesajın bildirimi iki yoldan geliyor:
  (a) alıcının kendi uygulaması: veritabanı dinleyicisi → sistemBildirimi →
      köprü (meridyen-native.js) → MeridyenBildirimler.mesaj(…, anahtar)
  (b) bildirim sunucusu: kuyruk kaydı → FCM push verisi `mid` →
      MeridyenMesajServisi → MeridyenBildirimler.mesaj(…, mid)
Yerli taraf ikisinden yalnız birini gösteriyor — ama YALNIZ anahtarlar aynıysa.
Anahtar zincirin herhangi bir halkasında düşerse (bir alan adı değişir, bir
çağrıda unutulur) çift bildirim sessizce geri gelir; hiçbir tekil sınama
bunu yakalamaz. Bu sınama zinciri baştan sona GERÇEK kodla koşturuyor:
gönderenin mesajYaz'ı, alıcının sistemBildirimi'si, köprünün kendisi ve
sunucunun mesaj_kur'u. (Yerli tarafın aynı anahtarı atladığı
test_biriken_bildirim.py'de.)
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sunucu'))
from test_oyun import islev_cikar  # noqa: E402
import bildirim as B  # noqa: E402

html = open('www/index.html', encoding='utf-8').read()
kopru = open('www/meridyen-native.js', encoding='utf-8').read()


def islev(ad):
    f = islev_cikar(html, ad)
    return f if f.startswith('async') or 'await' not in f else 'async ' + f


js = r"""
const yazilan = [], kopruCagrilari = [];
globalThis.window = globalThis;
globalThis.document = { hidden: true, addEventListener(){} };
globalThis.navigator = { userAgent: 'sinama' };
window.Capacitor = {
  isNativePlatform: () => true,
  Plugins: {
    LocalNotifications: {           // APK'da var; köprü izni ondan okuyor
      checkPermissions: () => Promise.resolve({ display: 'granted' }),
      requestPermissions: () => Promise.resolve({ display: 'granted' }),
      addListener(){}, schedule: () => Promise.resolve()
    },
    MeridyenIlerleme: {
    mesajBildirimi: (o) => { kopruCagrilari.push(o); return Promise.resolve(); },
    bildirimTemizle: () => Promise.resolve(),
    addListener(){}, bekleyenAcilis: () => Promise.resolve(null),
    checkPermissions: () => Promise.resolve({ display: 'granted' })
  } }
};
require('vm').runInThisContext(""" + json.dumps(kopru) + r""");

let anahtarSayaci = 0;
const ref = (y) => ({
  push(v) { const key = '-Nsinama' + (++anahtarSayaci); yazilan.push(['push', y, key, v]);
            const p = Promise.resolve(); p.key = key; return p; },
  update(v) { yazilan.push(['update', y, v]); return Promise.resolve(); },
  catch() { return this; }
});
const db = { ref };
const firebase = { database: { ServerValue: { TIMESTAMP: { '.sv': 'timestamp' } } } };
const ben = { uid: 'GONDEREN' }; const benimAdim = 'Semih';
const ozetle = (k) => k.metin || 'Fotoğraf';
const okunduIsaretle = () => {};
const aktifSohbet = null, profilKesi = { GONDEREN: { ad: 'Semih' } };
const tercihler = { bildirimIcerik: true };
const baglantiNotu = () => {}; const panelGirisTalebi = () => {};
""" + '\n'.join(islev(a) for a in ('mesajYaz', 'bildirimKuyruguna', 'sistemBildirimi')) + r"""
(async () => {
  await new Promise(r => setTimeout(r, 10));      // köprünün izin okuması bitsin
  if (Notification.permission !== 'granted') throw new Error('köprü izni okumadı');
  // GÖNDEREN tarafı
  const mid = await mesajYaz({ uid: 'GONDEREN', metin: 'merhaba', ts: 1 }, { sid: 'S1', uid: 'ALICI' });
  const kuyruk = yazilan.find(y => y[0] === 'push' && y[1] === 'bildirimKuyrugu');
  const ozet = yazilan.find(y => y[0] === 'update' && y[1] === 'kisiler/ALICI/GONDEREN');
  // ALICI tarafı: kisiler dinleyicisi yeni mesajı görüp bildirim çiziyor
  sistemBildirimi('GONDEREN', ozet[2].sonMesaj, ozet[2].sonMid);
  await new Promise(r => setTimeout(r, 20));
  console.log(JSON.stringify({ mid, mesajYolu: yazilan[0][1], mesajAnahtari: yazilan[0][2],
                               kuyruk: kuyruk && kuyruk[3], ozet: ozet && ozet[2], kopru: kopruCagrilari }));
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
"""

cikti = subprocess.run(['node', '-e', js], capture_output=True, text=True, timeout=60)
if cikti.returncode:
    sys.exit(cikti.stderr or cikti.stdout)
d = json.loads(cikti.stdout.strip().splitlines()[-1])

sonuc = []


def ok(ad, k, ayrinti=''):
    sonuc.append((ad, bool(k)))
    print(('  ✓ ' if k else '  ✗ ') + ad + ('' if k else '  — ' + str(ayrinti)))


mid = d['mid']
ok('mesajYaz mesajın anahtarını döndürüyor', mid and mid == d['mesajAnahtari'] and
   d['mesajYolu'] == 'sohbetler/S1/mesajlar', d)
ok('alıcının kişi özetinde sonMid = mesaj anahtarı', d['ozet'] and d['ozet'].get('sonMid') == mid, d['ozet'])
ok('kuyruk kaydında mid = mesaj anahtarı', d['kuyruk'] and d['kuyruk'].get('mid') == mid, d['kuyruk'])
ok('köprü yerli tarafa anahtarı geçiriyor', len(d['kopru']) == 1 and d['kopru'][0].get('anahtar') == mid, d['kopru'])

push = B.mesaj_kur(d['kuyruk'], {'belirtec': 'T' * 30, 'icerikGoster': True}, 'kuyrukAnahtari')['data']
ok('sunucunun push verisinde mid = AYNI anahtar', push['mid'] == mid, push)
ok('iki yolun etiketi aynı (aynı bildirim kimliğine düşüyor)',
   d['kopru'] and d['kopru'][0].get('etiket') == push['etiket'], (d['kopru'], push.get('etiket')))

kotu = [a for a, k in sonuc if not k]
print('\n  %d BAŞARISIZ' % len(kotu) if kotu else '\n  TUMU GECTI (%d)' % len(sonuc))
sys.exit(1 if kotu else 0)
