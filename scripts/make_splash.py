#!/usr/bin/env python3
"""Meridyen — açılış (splash) ekranı logosunu üretir.

Capacitor'un şablonu genel bir `splash.png` ile geliyor; uygulama her
açılışta o jenerik görseli gösteriyordu. Burada uyarlanabilir ikonun ön plan
katmanındaki "M" işareti alınıp, açılış ekranında kullanılacak boyutta ve
saydam zeminli bir PNG olarak kaydediliyor. Zemin rengini drawable/splash.xml
veriyor; böylece logo her yoğunlukta orantılı kalıyor ve zemin ile arasında
sıkışma/bozulma olmuyor.
"""
from PIL import Image
import os

KAYNAK = "android-assets/mipmap-xxxhdpi/ic_launcher_foreground.png"
HEDEF_KLASOR = "android-assets/drawable-xxhdpi"
HEDEF = os.path.join(HEDEF_KLASOR, "splash_logo.png")
KENAR = 360          # xxhdpi'de ~120dp: açılışta rahat okunur, taşmaz

im = Image.open(KAYNAK).convert("RGBA")
kutu = im.split()[3].getbbox()
if kutu is None:
    raise SystemExit("Kaynak ikonun alfa kanalı boş: " + KAYNAK)

kirpik = im.crop(kutu)
kenar = max(kirpik.size)
kare = Image.new("RGBA", (kenar, kenar), (0, 0, 0, 0))
kare.paste(kirpik, ((kenar - kirpik.size[0]) // 2, (kenar - kirpik.size[1]) // 2))

os.makedirs(HEDEF_KLASOR, exist_ok=True)
kare.resize((KENAR, KENAR), Image.LANCZOS).save(HEDEF)
print("yazıldı:", HEDEF, "(%dx%d)" % (KENAR, KENAR))
