#!/usr/bin/env python3
"""Meridyen — uygulama modülüne firebase-messaging bağımlılığını ekler.

NEDEN GEREKLİ: Kendi FCM servisimiz (MeridyenMesajServisi) uygulama
modülünde derleniyor ve `RemoteMessage` ile Capacitor'un `MessagingService`
sınıfını kullanıyor. Capacitor'un push eklentisi firebase-messaging'i
`implementation` olarak alıyor — Gradle'da bu bağımlılık AKTARILMAZ, yalnız
o modülün kendi derlemesinde görünür. Bu yüzden uygulama modülü
"cannot find symbol: RemoteMessage" diyerek derlenmiyor.

Sürüm, eklentinin KENDİ build.gradle'ından okunuyor: iki farklı
firebase-messaging sürümü sınıf yolunda çakışmasın ve eklenti güncellenince
burası kendiliğinden ona uysun.

android/ her derlemede sıfırdan üretildiği için bu yama her seferinde
uygulanıyor. Betik idempotent ve sonunda doğrulama yapıyor.
"""
import io
import os
import re
import sys

APP_GRADLE = "android/app/build.gradle"
DEGISKENLER = "android/variables.gradle"
EKLENTI_GRADLE = "node_modules/@capacitor/push-notifications/android/build.gradle"
ANAHTAR = "com.google.firebase:firebase-messaging"


def eklenti_surumu():
    with io.open(EKLENTI_GRADLE, encoding="utf-8") as f:
        g = f.read()
    m = re.search(r"firebaseMessagingVersion\s*=.*?:\s*'([^']+)'", g, re.S)
    if not m:
        sys.exit("HATA: push eklentisinin firebase-messaging sürümü okunamadı.")
    return m.group(1)


def main():
    for yol in (APP_GRADLE, DEGISKENLER, EKLENTI_GRADLE):
        if not os.path.isfile(yol):
            sys.exit("HATA: dosya yok: " + yol)

    surum = eklenti_surumu()

    # 1) Sürümü variables.gradle'a koy (Capacitor'un kendi düzenine uyarak).
    with io.open(DEGISKENLER, encoding="utf-8") as f:
        degiskenler = f.read()
    if "firebaseMessagingVersion" not in degiskenler:
        yeni = degiskenler.replace(
            "ext {",
            "ext {\n    // Meridyen: kendi FCM servisimiz için; sürüm Capacitor'un push\n"
            "    // eklentisinden okunuyor ki sınıf yolunda iki sürüm çakışmasın.\n"
            "    firebaseMessagingVersion = '" + surum + "'",
            1,
        )
        if yeni == degiskenler:
            sys.exit("HATA: variables.gradle beklenen biçimde değil (ext { yok).")
        degiskenler = yeni
        with io.open(DEGISKENLER, "w", encoding="utf-8") as f:
            f.write(degiskenler)

    # 2) Bağımlılığı app/build.gradle'a ekle.
    with io.open(APP_GRADLE, encoding="utf-8") as f:
        app = f.read()
    if ANAHTAR not in app:
        satir = (
            '    // Meridyen: MeridyenMesajServisi burada derleniyor. Capacitor\'un\n'
            '    // push eklentisi bu bağımlılığı `implementation` olarak aldığı için\n'
            '    // uygulama modülüne AKTARILMIYOR; açıkça eklemek gerekiyor.\n'
            '    implementation "' + ANAHTAR + ':$firebaseMessagingVersion"\n'
        )
        yeni = re.sub(r"(dependencies \{\n)", r"\1" + satir.replace("\\", "\\\\"), app, count=1)
        if yeni == app:
            sys.exit("HATA: app/build.gradle içinde dependencies bloğu bulunamadı.")
        app = yeni
        with io.open(APP_GRADLE, "w", encoding="utf-8") as f:
            f.write(app)

    # 3) DOĞRULAMA
    with io.open(APP_GRADLE, encoding="utf-8") as f:
        son_app = f.read()
    with io.open(DEGISKENLER, encoding="utf-8") as f:
        son_deg = f.read()
    if ANAHTAR not in son_app:
        sys.exit("HATA: firebase-messaging bağımlılığı eklenmedi.")
    if "firebaseMessagingVersion" not in son_deg:
        sys.exit("HATA: firebaseMessagingVersion tanımlanmadı.")

    print("gradle yamandı: firebase-messaging %s (uygulama modülü)" % surum)


if __name__ == "__main__":
    main()
