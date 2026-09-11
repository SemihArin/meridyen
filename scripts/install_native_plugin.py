#!/usr/bin/env python3
"""Meridyen — kendi native eklentimizi üretilen android/ projesine kurar.

Gönderim ilerlemesi için küçük bir Capacitor eklentisi yazdık
(android-assets/java/MeridyenIlerleme.java). android/ klasörü her derlemede
sıfırdan üretildiği için dosyanın oraya kopyalanması ve MainActivity'de
kaydedilmesi gerekiyor; bu betik ikisini de yapıyor.

Paket adı capacitor.config.json'daki appId'den okunuyor: appId değişirse
Java paketi de kendiliğinden ona uyuyor, elle düzeltme gerekmiyor.

Betik idempotent ve sessiz başarısızlığa kapalı: işi bitince hem dosyanın
hem de kayıt satırının yerinde olduğunu doğruluyor, değilse hata koduyla
çıkıp derlemeyi kırıyor.
"""
import io
import json
import os
import re
import sys

KAYNAK = "android-assets/java/MeridyenIlerleme.java"
SINIF = "MeridyenIlerleme"


def main():
    with io.open("capacitor.config.json", encoding="utf-8") as f:
        paket = json.load(f)["appId"]

    kok = os.path.join("android/app/src/main/java", *paket.split("."))
    if not os.path.isdir(kok):
        sys.exit("HATA: üretilen kaynak klasörü yok: " + kok)

    # 1) Eklenti sınıfını kopyala (paket adını yerine koyarak)
    with io.open(KAYNAK, encoding="utf-8") as f:
        java = f.read().replace("__PAKET__", paket)
    hedef = os.path.join(kok, SINIF + ".java")
    with io.open(hedef, "w", encoding="utf-8") as f:
        f.write(java)

    # 2) MainActivity'de kaydet
    ana = os.path.join(kok, "MainActivity.java")
    with io.open(ana, encoding="utf-8") as f:
        icerik = f.read()

    if SINIF + ".class" not in icerik:
        """Capacitor'un şablonu boş bir gövde üretiyor:
               public class MainActivity extends BridgeActivity {}
           Eklentiyi super.onCreate'ten ÖNCE kaydetmek gerekiyor; köprü
           eklenti listesini orada kuruyor."""
        yeni_govde = (
            "public class MainActivity extends BridgeActivity {\n"
            "    @Override\n"
            "    public void onCreate(android.os.Bundle savedInstanceState) {\n"
            "        // Kayıt super.onCreate'ten ÖNCE olmalı: köprü eklenti\n"
            "        // listesini orada kuruyor.\n"
            "        registerPlugin(" + SINIF + ".class);\n"
            "        super.onCreate(savedInstanceState);\n"
            "    }\n"
            "}\n"
        )
        yeni = re.sub(
            r"public class MainActivity extends BridgeActivity \{\s*\}",
            yeni_govde,
            icerik,
            count=1,
        )
        if yeni == icerik:
            sys.exit("HATA: MainActivity gövdesi beklenen biçimde değil, eklenti kaydedilemedi.")
        with io.open(ana, "w", encoding="utf-8") as f:
            f.write(yeni)

    # 3) DOĞRULAMA
    with io.open(ana, encoding="utf-8") as f:
        son = f.read()
    if not os.path.isfile(hedef):
        sys.exit("HATA: eklenti sınıfı kopyalanmadı: " + hedef)
    if SINIF + ".class" not in son:
        sys.exit("HATA: eklenti MainActivity'de kayıtlı değil.")
    if "package " + paket + ";" not in java:
        sys.exit("HATA: eklentinin paket adı yerine konmadı.")

    print("native eklenti kuruldu: %s (paket %s)" % (SINIF, paket))


if __name__ == "__main__":
    main()
