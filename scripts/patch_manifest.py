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

# FCM, uygulama KAPALIYKEN gelen bildirimi kendisi çiziyor — o an bizim
# JavaScript'imiz çalışmıyor. Hangi ikonu ve rengi kullanacağını yalnız
# manifestteki bu iki meta-data'dan okuyor. Koymazsak durum çubuğunda
# uygulamanın renkli ikonu beyaz bir leke olarak görünür.
META_VERILER = [
    '        <meta-data android:name="com.google.firebase.messaging.default_notification_icon" android:resource="@drawable/ic_stat_meridyen" />',
    '        <meta-data android:name="com.google.firebase.messaging.default_notification_color" android:resource="@color/meridyen_vurgu" />',
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

# meta-data satırları <application> ETİKETİNİN İÇİNE girmeli (izinler gibi
# dışına değil), bu yüzden ayrı ele alınıyor.
meta_eklenecek = []
for satir in META_VERILER:
    ad = re.search(r'android:name="([^"]+)"', satir).group(1)
    if ad not in manifest:
        meta_eklenecek.append(satir)

if meta_eklenecek:
    blok = "\n" + "\n".join(meta_eklenecek)
    # <application ...> açılış etiketinin bittiği ilk '>' işaretinden sonrası.
    eslesme = re.search(r"<application\b[^>]*>", manifest)
    if not eslesme:
        raise SystemExit("HATA: <application> etiketi bulunamadı, meta-data eklenemedi.")
    yer = eslesme.end()
    manifest = manifest[:yer] + blok + manifest[yer:]
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        f.write(manifest)
    print(f"{len(meta_eklenecek)} bildirim meta-data satırı eklendi:")
    for s2 in meta_eklenecek:
        print("  " + s2.strip())
else:
    print("Bildirim meta-data'ları zaten mevcut.")
