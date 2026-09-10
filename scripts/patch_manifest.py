#!/usr/bin/env python3
"""Meridyen — üretilen AndroidManifest.xml'e ihtiyaç duyduğumuz izinleri ekler.

`npx cap add android`, Capacitor'un kendi şablonundan taze bir proje
üretiyor (INTERNET izni zaten var). Ama bu uygulamada kamera/mikrofon
gerektiren aramalar (WebRTC) ve bildirimler (FCM) var — bunlar için
Android'in kendi çalışma-zamanı izinlerini de manifestte tanımlamak
gerekiyor. Elle bir android/ projesi taşımak yerine (SDK'sız burada test
edilemez, hataya çok açık) her derlemede TAZE üretilen manifesti bu betikle
yamıyoruz — böylece Capacitor'un kendi şablonu neyse ondan sapmıyoruz.
"""
import re
import sys

MANIFEST_PATH = sys.argv[1] if len(sys.argv) > 1 else "android/app/src/main/AndroidManifest.xml"

PERMISSIONS = [
    '    <uses-permission android:name="android.permission.CAMERA" />',
    '    <uses-permission android:name="android.permission.RECORD_AUDIO" />',
    '    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />',
    '    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />',
    '    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />',
    '    <uses-permission android:name="android.permission.WAKE_LOCK" />',
]

FEATURES = [
    '    <uses-feature android:name="android.hardware.camera" android:required="false" />',
    '    <uses-feature android:name="android.hardware.camera.autofocus" android:required="false" />',
    '    <uses-feature android:name="android.hardware.microphone" android:required="false" />',
]

with open(MANIFEST_PATH, encoding="utf-8") as f:
    manifest = f.read()

eklenecek = []
for satir in PERMISSIONS + FEATURES:
    # satırdaki izin/özellik adını çıkar (name="...") — zaten varsa tekrar eklemeyelim.
    ad = re.search(r'android:name="([^"]+)"', satir).group(1)
    if ad not in manifest:
        eklenecek.append(satir)

if eklenecek:
    blok = "\n".join(eklenecek) + "\n"
    manifest = re.sub(r"(<application)", blok + r"\1", manifest, count=1)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        f.write(manifest)
    print(f"{len(eklenecek)} izin/özellik satırı eklendi:")
    for s in eklenecek:
        print("  " + s.strip())
else:
    print("Eklenecek yeni izin yok (zaten hepsi mevcut).")
