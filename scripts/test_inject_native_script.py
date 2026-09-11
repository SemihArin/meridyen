#!/usr/bin/env python3
"""inject_native_script.py için regresyon testleri.

Buradaki ilk senaryo gerçek bir arızadan geliyor: index.html içine
"meridyen-native.js" adını anan bir YORUM eklenince, eski betik bunu
"zaten ekli" sanıp <script> etiketini hiç koymamış ve bildirimler tamamen
kaybolmuştu. O senaryo artık testle kilitli.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject_native_script import enjekte_et, ETIKET_DESENI  # noqa: E402

SONUC = []


def ok(ad, kosul):
    SONUC.append((ad, bool(kosul)))


def adet(html):
    return len(ETIKET_DESENI.findall(html))


TEMEL = "<html><head><title>x</title>\n</head><body><script>var a=1;</script></body></html>"

# 1) düz ekleme
c = enjekte_et(TEMEL)
ok("boş sayfaya etiket eklendi", adet(c) == 1)
ok("etiket </head>'den önce", c.index("meridyen-native.js") < c.index("</head>"))

# 2) ASIL ARIZA: dosya adı yalnızca bir YORUM içinde geçiyor
yorumlu = TEMEL.replace("<title>x</title>", "<title>x</title>\n<!-- bkz. meridyen-native.js -->")
c2 = enjekte_et(yorumlu)
ok("yorumda adı geçse bile etiket ekleniyor", adet(c2) == 1)
ok("yorum korundu", "bkz. meridyen-native.js" in c2)

# 3) gövdedeki JS içinde adı geçiyor (kod yorumu)
koddaki = TEMEL.replace("var a=1;", "var a=1; /* meridyen-native.js icinde */")
ok("kod yorumunda adı geçse bile ekleniyor", adet(enjekte_et(koddaki)) == 1)

# 4) idempotent: iki kez çalıştırınca etiket çoğalmıyor
ok("iki kez çalıştırmak etiketi çoğaltmıyor", adet(enjekte_et(enjekte_et(TEMEL))) == 1)
ok("üç kez çalıştırmak da çoğaltmıyor", adet(enjekte_et(enjekte_et(enjekte_et(TEMEL)))) == 1)

# 5) farklı tırnak/nitelik biçimleri de tek etikete indirgeniyor
tuhaf = TEMEL.replace("</head>", "<script defer src='meridyen-native.js'></script>\n</head>")
ok("tek tırnaklı/defer'li eski etiket tanınıp yenileniyor", adet(enjekte_et(tuhaf)) == 1)

# 6) </head> yoksa sessizce geçmiyor, hata veriyor
try:
    enjekte_et("<html><body>yok</body></html>")
    ok("</head> yoksa hata veriyor", False)
except ValueError:
    ok("</head> yoksa hata veriyor", True)

hata = 0
for ad, gecti in SONUC:
    print(("OK  " if gecti else "HATA") + "  " + ad)
    if not gecti:
        hata += 1
print("\nTUMU GECTI (%d)" % len(SONUC) if hata == 0 else "\n%d BASARISIZ" % hata)
sys.exit(1 if hata else 0)
