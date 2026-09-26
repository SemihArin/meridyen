#!/usr/bin/env python3
"""Meridyen — işleyici süreci ölümünden diriltmeyi sınar.

NE SINANIYOR: android-assets/java/MeridyenDirilis.java'nın GERÇEK kodu.
Kopyası değil, benzeri değil; dosyanın kendisi derleniyor ve çalıştırılıyor.

NASIL: Android SDK'sı burada yok, cihaz da yok. Onun yerine MeridyenDirilis'in
dokunduğu birkaç Android sınıfının davranışına SADIK saplaması derleniyor
(android-assets/sinama/saplama/). Capacitor tarafında saplama YOK: gerçek
WebViewListener node_modules'ten alınıyor, böylece imza uyuşmazlığı burada
yakalanıyor.

NİÇİN: Bu mantığın iki sessiz kötü sonucu var ve ikisi de cihazda aylar sonra
ortaya çıkıyor — pili bitiren sonsuz diriltme döngüsü, ya da tek ölümden sonra
kullanıcıyı ölü sayfayla bırakmak. İkisi de kullanıcı şikayet edene kadar
görünmüyor; bu yüzden derlemede sınanıyor.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SINAMA = os.path.join(KOK, "android-assets/sinama")
SAPLAMA = os.path.join(SINAMA, "saplama")
GERCEK = os.path.join(KOK, "android-assets/java")
CAPACITOR = os.path.join(
    KOK, "node_modules/@capacitor/android/capacitor/src/main/java/com/getcapacitor")

# Sınamada derlenen GERÇEK dosyalar. Buraya bir şey eklerken dikkat: saplama
# yığınının büyümesi sınamanın değerini düşürür.
GERCEK_DOSYALAR = ["MeridyenDirilis.java"]
CAPACITOR_DOSYALAR = ["WebViewListener.java"]


def yaz(hedef, icerik):
    os.makedirs(os.path.dirname(hedef), exist_ok=True)
    with io.open(hedef, "w", encoding="utf-8") as f:
        f.write(icerik)


def oku(yol):
    with io.open(yol, encoding="utf-8") as f:
        return f.read()


def main():
    with io.open(os.path.join(KOK, "capacitor.config.json"), encoding="utf-8") as f:
        paket = json.load(f)["appId"]
    paket_yol = paket.replace(".", "/")

    if not os.path.isdir(CAPACITOR):
        sys.exit("HATA: Capacitor kaynağı yok (npm ci çalıştı mı?): " + CAPACITOR)

    gecici = tempfile.mkdtemp(prefix="meridyen-dirilis-")
    try:
        kaynak = os.path.join(gecici, "src")
        cikti = os.path.join(gecici, "out")
        os.makedirs(cikti)

        # 1) Android saplamaları — olduğu gibi.
        shutil.copytree(os.path.join(SAPLAMA, "android"),
                        os.path.join(kaynak, "android"))

        # 2) Capacitor'un GERÇEK sınıfları.
        for ad in CAPACITOR_DOSYALAR:
            yaz(os.path.join(kaynak, "com/getcapacitor", ad),
                oku(os.path.join(CAPACITOR, ad)))

        # 3) Bizim GERÇEK sınıflarımız + kendi saplamalarımız + sınama.
        #    Paket adı derleme betiğindeki İLE AYNI yolla konuyor: yer tutucu
        #    bozulursa burada da patlar.
        for kaynak_klasor, adlar in (
                (GERCEK, GERCEK_DOSYALAR),
                (os.path.join(SAPLAMA, "meridyen"),
                 sorted(a for a in os.listdir(os.path.join(SAPLAMA, "meridyen"))
                        if a.endswith(".java"))),
                (SINAMA, ["Sinama.java"])):
            for ad in adlar:
                java = oku(os.path.join(kaynak_klasor, ad))
                if "__PAKET__" not in java:
                    sys.exit("HATA: %s içinde __PAKET__ yer tutucusu yok." % ad)
                yaz(os.path.join(kaynak, paket_yol, ad),
                    java.replace("__PAKET__", paket))

        dosyalar = []
        for kk, _, adlar in os.walk(kaynak):
            dosyalar += [os.path.join(kk, a) for a in adlar if a.endswith(".java")]

        d = subprocess.run(["javac", "-nowarn", "-d", cikti] + sorted(dosyalar),
                           capture_output=True, text=True)
        if d.returncode != 0:
            sys.stdout.write(d.stdout)
            sys.stderr.write(d.stderr)
            sys.exit("HATA: MeridyenDirilis derlenemedi.")

        c = subprocess.run(["java", "-cp", cikti, paket + ".Sinama"],
                           capture_output=True, text=True)
        cikti_metin = (c.stdout or "") + (c.stderr or "")
        # JAVA_TOOL_OPTIONS satırı her çalıştırmada başa düşüyor; gürültü.
        print("\n".join(s for s in cikti_metin.splitlines()
                        if not s.startswith("Picked up JAVA_TOOL")).strip())
        if c.returncode != 0:
            sys.exit("HATA: diriltme sınaması başarısız.")
    finally:
        shutil.rmtree(gecici, ignore_errors=True)


if __name__ == "__main__":
    main()
