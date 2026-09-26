#!/usr/bin/env python3
"""Meridyen — kendi native Java sınıflarımızı üretilen android/ projesine kurar.

android/ klasörü depoda tutulmuyor; her derlemede Capacitor'un şablonundan
sıfırdan üretiliyor. Bu yüzden kendi sınıflarımızın oraya kopyalanması ve
Capacitor eklentisi olanların MainActivity'de kaydedilmesi gerekiyor.

android-assets/java/ altındaki TÜM dosyalar kuruluyor:
  MeridyenIlerleme.java     — gönderim ilerlemesi, durum çubuğu, bildirim tanısı
  MeridyenBildirimler.java  — mesaj bildirimlerinin ortak tarafı
  MeridyenMesajServisi.java — uygulama kapalıyken gelen push'u ekrana çıkarır

Paket adı capacitor.config.json'daki appId'den okunuyor: appId değişirse Java
paketi de kendiliğinden ona uyuyor, elle düzeltme gerekmiyor.

Betik idempotent ve sessiz başarısızlığa kapalı: işi bitince hem dosyaların
hem de kayıt satırlarının yerinde olduğunu doğruluyor, değilse hata koduyla
çıkıp derlemeyi kırıyor.
"""
import io
import json
import os
import re
import sys

KAYNAK_KLASOR = "android-assets/java"
KAYNAK_KAYNAKLAR = "android-assets/res"      # layout vb. (Capacitor'unkini ezen)

# Capacitor'un BridgeActivity'si burada. Ezdiğimiz layout'un adını ONDAN
# okuyoruz; sabit yazsaydık sürüm değişiminde sessizce yanlışa düşerdi.
BRIDGE_ACTIVITY = ("node_modules/@capacitor/android/capacitor/src/main/java/"
                   "com/getcapacitor/BridgeActivity.java")


def acilan_layout():
    """Capacitor'un GERÇEKTEN setContentView ettiği layout'un adını döndürür.

    NİÇİN OKUNUYOR: Capacitor 7 res/layout altında iki dosya taşıyor —
    bridge_layout_main.xml (eski, artık açılmıyor) ve
    capacitor_bridge_layout_main.xml (açılan). Bir kez yanlış olan ezildi:
    dosya APK'ya giriyordu, MeridyenWebView derleniyordu, ama Capacitor
    öbürünü açtığı için sınıf hiç örneklenmedi ve arka planda donma aylarca
    sürdü. Dışarıdan hiçbir belirtisi yoktu. Artık ad kaynaktan okunuyor:
    Capacitor yeniden adlandırırsa derleme burada kırılıyor.
    """
    if not os.path.isfile(BRIDGE_ACTIVITY):
        sys.exit("HATA: Capacitor kaynağı yok (npm ci çalıştı mı?): " + BRIDGE_ACTIVITY)
    with io.open(BRIDGE_ACTIVITY, encoding="utf-8") as f:
        java = f.read()
    # Hata yolundaki setContentView(R.layout.no_webview) elenmeli.
    adlar = [a for a in re.findall(r"setContentView\(R\.layout\.(\w+)\)", java)
             if a != "no_webview"]
    if len(set(adlar)) != 1:
        sys.exit("HATA: BridgeActivity'de açılan layout tek değil: %r" % (adlar,))
    return adlar[0]


def main():
    with io.open("capacitor.config.json", encoding="utf-8") as f:
        paket = json.load(f)["appId"]

    kok = os.path.join("android/app/src/main/java", *paket.split("."))
    if not os.path.isdir(kok):
        sys.exit("HATA: üretilen kaynak klasörü yok: " + kok)

    dosyalar = sorted(a for a in os.listdir(KAYNAK_KLASOR) if a.endswith(".java"))
    if not dosyalar:
        sys.exit("HATA: " + KAYNAK_KLASOR + " altında hiç .java yok.")

    # 0) Kaynak (res) dosyaları: Capacitor'un kendi layout'unu EZEN kopyalar.
    #    Uygulama modülünün kaynağı kitaplığınkinin önüne geçtiği için,
    #    aynı adlı bridge_layout_main.xml bizim WebView alt sınıfımızı
    #    kullandırıyor (arka planda donmayı engelleyen sınıf).
    if os.path.isdir(KAYNAK_KAYNAKLAR):
        for alt in sorted(os.listdir(KAYNAK_KAYNAKLAR)):
            kaynak_alt = os.path.join(KAYNAK_KAYNAKLAR, alt)
            if not os.path.isdir(kaynak_alt):
                continue
            hedef_alt = os.path.join("android/app/src/main/res", alt)
            os.makedirs(hedef_alt, exist_ok=True)
            for ad in sorted(os.listdir(kaynak_alt)):
                with io.open(os.path.join(kaynak_alt, ad), encoding="utf-8") as f:
                    icerik = f.read().replace("__PAKET__", paket)
                hedef = os.path.join(hedef_alt, ad)
                with io.open(hedef, "w", encoding="utf-8") as f:
                    f.write(icerik)
                print("kaynak kuruldu: res/" + alt + "/" + ad)

    # Layout ezmesi DOĞRU DOSYAYI mı eziyor? Bu kontrol olmasa yanlış adlı bir
    # ezme sessizce hiçbir şey yapmaz (bir kez tam olarak bu oldu).
    beklenen = acilan_layout()
    ezme = os.path.join(KAYNAK_KAYNAKLAR, "layout", beklenen + ".xml")
    if not os.path.isfile(ezme):
        sys.exit("HATA: Capacitor '%s' layout'unu açıyor ama ezmemiz yok: %s\n"
                 "     (android-assets/res/layout/ içeriği: %s)"
                 % (beklenen, ezme,
                    sorted(os.listdir(os.path.join(KAYNAK_KAYNAKLAR, "layout")))))
    with io.open(ezme, encoding="utf-8") as f:
        if "MeridyenWebView" not in f.read():
            sys.exit("HATA: %s bizim WebView alt sınıfımızı kullanmıyor." % ezme)
    kurulan = os.path.join("android/app/src/main/res/layout", beklenen + ".xml")
    if not os.path.isfile(kurulan):
        sys.exit("HATA: layout ezmesi kurulmadı: " + kurulan)
    print("layout ezmesi doğrulandı: Capacitor %s açıyor, ezme yerinde." % beklenen)

    # 1) Sınıfları kopyala (paket adını yerine koyarak)
    eklentiler = []          # @CapacitorPlugin taşıyanlar: MainActivity'de kaydedilecek
    hedefler = []
    for ad in dosyalar:
        with io.open(os.path.join(KAYNAK_KLASOR, ad), encoding="utf-8") as f:
            java = f.read()
        if "__PAKET__" not in java:
            sys.exit("HATA: %s içinde __PAKET__ yer tutucusu yok." % ad)
        java = java.replace("__PAKET__", paket)
        hedef = os.path.join(kok, ad)
        with io.open(hedef, "w", encoding="utf-8") as f:
            f.write(java)
        hedefler.append(hedef)
        if "@CapacitorPlugin" in java:
            eklentiler.append(ad[:-5])   # ".java" at

    if not eklentiler:
        sys.exit("HATA: hiçbir sınıfta @CapacitorPlugin yok, kaydedilecek eklenti bulunamadı.")

    # 2) MainActivity'de kaydet
    ana = os.path.join(kok, "MainActivity.java")
    with io.open(ana, encoding="utf-8") as f:
        icerik = f.read()

    eksik = [s for s in eklentiler if s + ".class" not in icerik]
    if eksik:
        """Capacitor'un şablonu boş bir gövde üretiyor:
               public class MainActivity extends BridgeActivity {}
           Eklentiyi super.onCreate'ten ÖNCE kaydetmek gerekiyor; köprü
           eklenti listesini orada kuruyor."""
        kayitlar = "".join(
            "        registerPlugin(" + s + ".class);\n" for s in eksik
        )
        yeni_govde = (
            "public class MainActivity extends BridgeActivity {\n"
            "    @Override\n"
            "    public void onCreate(android.os.Bundle savedInstanceState) {\n"
            "        // Kayıt super.onCreate'ten ÖNCE olmalı: köprü eklenti\n"
            "        // listesini orada kuruyor.\n"
            + kayitlar +
            "        super.onCreate(savedInstanceState);\n"
            "    }\n"
            "\n"
            "    /* Kayan ekran (Picture-in-Picture) iki Activity geri çağrısına\n"
            "       dayanıyor ve ikisi de Capacitor'un Plugin sınıfında YOK; bu\n"
            "       yüzden burada karşılanıp eklentiye aktarılıyor. */\n"
            "    @Override\n"
            "    public void onUserLeaveHint() {\n"
            "        // Ana ekrana dönülüyor. enterPictureInPictureMode yalnız\n"
            "        // BURADA kabul ediliyor; JavaScript'in visibilitychange'i\n"
            "        // geç kalıyor (pencere o an zaten arkaya geçmiş oluyor).\n"
            "        MeridyenIlerleme.ayrilirken(this);\n"
            "        super.onUserLeaveHint();\n"
            "    }\n"
            "\n"
            "    @Override\n"
            "    public void onPictureInPictureModeChanged(boolean icinde,\n"
            "            android.content.res.Configuration yapilandirma) {\n"
            "        super.onPictureInPictureModeChanged(icinde, yapilandirma);\n"
            "        // Web tarafı bu kipte yalnız karşı tarafın görüntüsünü\n"
            "        // çiziyor: küçük pencerede tüm arayüzün anlamı yok.\n"
            "        MeridyenIlerleme.kayanEkranDegisti(icinde);\n"
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
    for hedef in hedefler:
        if not os.path.isfile(hedef):
            sys.exit("HATA: sınıf kopyalanmadı: " + hedef)
        with io.open(hedef, encoding="utf-8") as f:
            if "package " + paket + ";" not in f.read():
                sys.exit("HATA: %s içinde paket adı yerine konmadı." % hedef)
    for s in eklentiler:
        if s + ".class" not in son:
            sys.exit("HATA: %s eklentisi MainActivity'de kayıtlı değil." % s)
    for geri, ne in (("onUserLeaveHint", "kayan ekrana otomatik geçiş"),
                     ("onPictureInPictureModeChanged", "kayan ekran kip bildirimi")):
        if geri not in son:
            sys.exit("HATA: MainActivity'de %s yok (%s çalışmaz)." % (geri, ne))

    print("native sınıflar kuruldu (paket %s): %s" % (paket, ", ".join(dosyalar)))
    print("kayıtlı eklentiler: %s" % ", ".join(eklentiler))


if __name__ == "__main__":
    main()
