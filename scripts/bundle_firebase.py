#!/usr/bin/env python3
"""Firebase SDK'sını APK'nın İÇİNE koyar.

NEDEN: Uygulama her açılışta SDK'nın dört dosyasını gstatic'ten indiriyordu.
Mobil ağda bu soğuk başlangıçta saniyeler demek: kullanıcı uygulamayı açıyor,
mesajlar ancak SDK inip oturum çözüldükten sonra görünüyor ("2-3 saniye sonra
yükleniyor"). Dosyalar APK'nın içindeyse ağ hiç beklenmiyor.

Yalnız DERLENEN kopyaya kopyalanıyor; www/index.html (canlı site) CDN'i
kullanmaya devam ediyor. Sayfa yerel dosya yoksa kendiliğinden CDN'e düşüyor.
"""
import hashlib
import os
import sys
import urllib.request

SURUM = "10.14.1"
DOSYALAR = [
    "firebase-app-compat.js",
    "firebase-auth-compat.js",
    "firebase-database-compat.js",
    "firebase-messaging-compat.js",
]
TABAN = "https://www.gstatic.com/firebasejs/" + SURUM + "/"
HEDEF = "android/app/src/main/assets/public/fb"
ENAZ = 10 * 1024          # bundan küçük dosya = bozuk indirme


def indir(ad):
    adres = TABAN + ad
    for deneme in range(3):
        try:
            with urllib.request.urlopen(adres, timeout=60) as y:
                veri = y.read()
            if len(veri) < ENAZ:
                raise RuntimeError("dosya çok küçük: %d bayt" % len(veri))
            return veri
        except Exception as hata:
            if deneme == 2:
                raise
            print("  yeniden deneniyor (%s): %s" % (ad, hata))
    raise RuntimeError("inmedi")


def main():
    if not os.path.isdir("android/app/src/main/assets/public"):
        sys.exit("android/ klasörü yok — önce `npx cap add android` ve `npx cap sync`")
    os.makedirs(HEDEF, exist_ok=True)
    toplam = 0
    for ad in DOSYALAR:
        veri = indir(ad)
        yol = os.path.join(HEDEF, ad)
        with open(yol, "wb") as f:
            f.write(veri)
        toplam += len(veri)
        print("  %-34s %6d KB  %s" % (ad, len(veri) // 1024,
                                      hashlib.sha256(veri).hexdigest()[:12]))
    print("Firebase SDK APK'ya kondu: %d dosya, %d KB (sürüm %s)"
          % (len(DOSYALAR), toplam // 1024, SURUM))


if __name__ == "__main__":
    main()
