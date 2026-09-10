#!/usr/bin/env python3
"""Meridyen — durum çubuğu (bildirim) ikonunu logodan üretir.

Android'in bildirim ikonu, uygulama ikonundan farklı kurallara tabi: renkli
olamaz, yalnız SİLUET olarak çizilir (sistem onu beyaza boyar, alfa kanalını
maske gibi kullanır). Renkli launcher ikonunu buraya verirsek durum çubuğunda
beyaz bir leke görünür.

Bu betik, uyarlanabilir ikonun ön plan katmanındaki "M" harfini alıp beyaz
siluete çeviriyor ve standart yoğunluklarda kaydediyor. Ön plan katmanı zaten
saydam zemin üzerinde duran bir harf olduğu için maske olarak birebir uygun.
"""
from PIL import Image
import os

KAYNAK = "android-assets/mipmap-xxxhdpi/ic_launcher_foreground.png"
AD = "ic_stat_meridyen"

# Android'in bildirim ikonu için beklediği kenar uzunlukları (dp cinsinden 24).
YOGUNLUKLAR = {
    "drawable-mdpi": 24,
    "drawable-hdpi": 36,
    "drawable-xhdpi": 48,
    "drawable-xxhdpi": 72,
    "drawable-xxxhdpi": 96,
}

# Harfin kutusunun ikonun kenarına yapışmaması için bırakılan pay. Android'in
# kendi tasarım kılavuzu 24dp'lik alanın içinde ~22dp'lik bir içerik öneriyor.
PAY_ORANI = 0.10

im = Image.open(KAYNAK).convert("RGBA")
alfa = im.split()[3]

kutu = alfa.getbbox()
if kutu is None:
    raise SystemExit("Kaynak ikonun alfa kanalı tamamen boş: " + KAYNAK)
alfa = alfa.crop(kutu)

# Kare tuval: harf orantısını bozmadan ortalanıyor.
kenar = max(alfa.size)
kare = Image.new("L", (kenar, kenar), 0)
kare.paste(alfa, ((kenar - alfa.size[0]) // 2, (kenar - alfa.size[1]) // 2))

for klasor, boyut in YOGUNLUKLAR.items():
    icerik = max(1, int(round(boyut * (1 - 2 * PAY_ORANI))))
    kucuk = kare.resize((icerik, icerik), Image.LANCZOS)

    maske = Image.new("L", (boyut, boyut), 0)
    maske.paste(kucuk, ((boyut - icerik) // 2, (boyut - icerik) // 2))

    # Beyaz dolgu + üretilen maske: sistem yeniden renklendirene kadar da
    # doğru görünür.
    ikon = Image.new("RGBA", (boyut, boyut), (255, 255, 255, 0))
    ikon.putalpha(maske)

    hedef = os.path.join("android-assets", klasor)
    os.makedirs(hedef, exist_ok=True)
    ikon.save(os.path.join(hedef, AD + ".png"))
    print("yazıldı:", os.path.join(hedef, AD + ".png"), "(%dx%d)" % (boyut, boyut))
