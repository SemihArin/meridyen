#!/usr/bin/env python3
"""Meridyen — bildirim sunucusu nabzının uygulamadaki yorumu.

Sunucu `sistem/bildirimSunucusu`na düzenli aralıkla zamanını yazıyor
(sunucu/index.js, nabizAt). Uygulama tanısı buradan "sunucu çalışıyor mu"
sonucunu çıkarıyor. Yanlış eşik iki yönde de zararlı: çalışan sunucuya
"durmuş" demek kullanıcıyı boşuna uğraştırır, durmuşa "çalışıyor" demek
asıl sebebi gizler. Gerçek fonksiyonlar index.html'den çıkarılıp Node'da
koşuyor.
"""
import json
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from test_oyun import islev_cikar  # noqa: E402

html = open("www/index.html", encoding="utf-8").read()
js = "\n".join(islev_cikar(html, ad) for ad in ("sureMetni", "sunucuNabziDurumu"))
js += r"""
const DK = 60000, S = 1e12;
const d = (n, yas) => sunucuNabziDurumu(n, S + yas);
const sonuc = [];
const ok = (ad, k) => sonuc.push([ad, !!k]);
const surekli = { nabiz: S, kip: 'surekli', aralikMs: DK };
ok('nabız yok → çalışmıyor', !d(null, 0).calisiyor && /hiç görülmedi/.test(d(null, 0).metin));
ok('nabız alanı bozuk → çalışmıyor', !d({ nabiz: 'x' }, 0).calisiyor);
ok('sürekli: 1 dk önce → çalışıyor', d(surekli, DK).calisiyor);
ok('sürekli: 3 dk önce (sınır) → çalışıyor', d(surekli, 3 * DK).calisiyor);
ok('sürekli: 4 dk önce → DURMUŞ', !d(surekli, 4 * DK).calisiyor && /DURMUŞ/.test(d(surekli, 4 * DK).metin));
ok('sürekli: süre metinde', /4 dk önce/.test(d(surekli, 4 * DK).metin));
ok('aralık sunucudan okunuyor (5 dk aralık, 10 dk önce → çalışıyor)',
   d({ nabiz: S, kip: 'surekli', aralikMs: 5 * DK }, 10 * DK).calisiyor);
ok('tek sefer: 2 dk önce → çalışıyor ama "anlık değil"',
   d({ nabiz: S, kip: 'tek', aralikMs: 0 }, 2 * DK).calisiyor && /anlık değil/.test(d({ nabiz: S, kip: 'tek' }, 2 * DK).metin));
ok('tek sefer: 10 dk önce → durmuş', !d({ nabiz: S, kip: 'tek' }, 10 * DK).calisiyor);
ok('kurulum hatası → taze olsa da çalışmıyor', !d(Object.assign({ kurulumHatasi: true }, surekli), 0).calisiyor);
ok('saat farkıyla gelecekte görünen nabız → çalışıyor', d(surekli, -30000).calisiyor);
console.log(JSON.stringify(sonuc));
"""
cikti = subprocess.run(["node", "-e", js], capture_output=True, text=True)
if cikti.returncode:
    sys.exit(cikti.stderr)
sonuc = json.loads(cikti.stdout)
for ad, k in sonuc:
    print(("  ✓ " if k else "  ✗ ") + ad)
kotu = [a for a, k in sonuc if not k]
print(f"\n  {len(kotu)} BAŞARISIZ" if kotu else f"\n  TUMU GECTI ({len(sonuc)})")
sys.exit(1 if kotu else 0)
