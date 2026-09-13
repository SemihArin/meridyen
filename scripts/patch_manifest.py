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
import io
import json
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
    # Arka planda bağlı kalma (MeridyenNobet): ön plan servisi olmadan
    # Android uygulamayı bir süre sonra donduruyor ve bildirimler kesiliyor.
    '    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />',
    '    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_SPECIAL_USE" />',
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
    # FCM'in KENDİ çizdiği bildirim (sunucu yükünde `notification` bloğu
    # varsa) da mesaj kanalımıza düşsün. Bu satır olmadan Android kendi
    # "Miscellaneous" kanalını kullanır: kullanıcı sesi/önemi bizim
    # kanalımızdan ayarlasa bile o bildirimlere uygulanmaz.
    '        <meta-data android:name="com.google.firebase.messaging.default_notification_channel_id" android:value="meridyen_mesaj" />',
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

# ---------------------------------------------------------------------------
# FCM SERVİSİ
#
# Capacitor'un push eklentisi gelen mesajı yalnızca JavaScript'e İLETİYOR,
# kendisi bildirim çizmiyor. Uygulama kapalıyken çalışan bir WebView olmadığı
# için mesaj hiçbir yerde görünmüyordu — bildirim ancak sunucu yüke bir
# `notification` bloğu koyduğunda çıkıyor, yalnız `data` gönderildiğinde
# SESSİZCE kayboluyordu.
#
# Kendi servisimiz (MeridyenMesajServisi) Capacitor'unkini miras alıyor: JS'e
# iletim ve belirteç yenileme aynen sürüyor, üstüne uygulama önde değilse
# bildirimi kendisi çiziyor.
#
# Capacitor'un servisi KALDIRILIYOR. Aynı intent-filter'a sahip iki servis
# bırakılırsa FCM teslimi hangisine yapacağını belirsiz bir sırayla seçer
# (PackageManager'ın döndürdüğü ilk eşleşme); tek servis bunu kesinleştiriyor.
# ---------------------------------------------------------------------------
with io.open("capacitor.config.json", encoding="utf-8") as f:
    PAKET = json.load(f)["appId"]

CAP_SERVIS = "com.capacitorjs.plugins.pushnotifications.MessagingService"
BIZIM_SERVIS = PAKET + ".MeridyenMesajServisi"

SERVIS_BLOGU = (
    '\n        <!-- Capacitor\'un kendi FCM servisi: bildirim çizmediği için\n'
    '             kaldırılıyor, yerine aşağıdaki miras alan servis geçiyor. -->\n'
    '        <service android:name="' + CAP_SERVIS + '" tools:node="remove" />\n'
    '        <service android:name="' + BIZIM_SERVIS + '" android:exported="false">\n'
    '            <intent-filter>\n'
    '                <action android:name="com.google.firebase.MESSAGING_EVENT" />\n'
    '            </intent-filter>\n'
    '        </service>'
)

if BIZIM_SERVIS not in manifest:
    # tools: ad alanı `tools:node="remove"` için şart; şablonda yok.
    if "xmlns:tools=" not in manifest:
        manifest = manifest.replace(
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android"',
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android"\n'
            '    xmlns:tools="http://schemas.android.com/tools"',
            1,
        )
        if "xmlns:tools=" not in manifest:
            raise SystemExit("HATA: <manifest> etiketi beklenen biçimde değil, tools ad alanı eklenemedi.")

    eslesme = re.search(r"<application\b[^>]*>", manifest)
    if not eslesme:
        raise SystemExit("HATA: <application> etiketi bulunamadı, FCM servisi eklenemedi.")
    yer = eslesme.end()
    manifest = manifest[:yer] + SERVIS_BLOGU + manifest[yer:]
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        f.write(manifest)
    print("FCM servisi eklendi (Capacitor'unki kaldırıldı): " + BIZIM_SERVIS)
else:
    print("FCM servisi zaten tanımlı.")

# DOĞRULAMA — bu üçü sessizce eksik kalırsa bildirimler yine kaybolur.
with io.open(MANIFEST_PATH, encoding="utf-8") as f:
    son = f.read()
for beklenen, aciklama in (
    (BIZIM_SERVIS, "kendi FCM servisimiz"),
    ('tools:node="remove"', "Capacitor servisinin kaldırılması"),
    ("default_notification_channel_id", "varsayılan bildirim kanalı"),
    ("POST_NOTIFICATIONS", "bildirim izni"),
):
    if beklenen not in son:
        raise SystemExit("HATA: manifestte %s yok (%s)." % (beklenen, aciklama))
print("manifest doğrulandı.")

# ---------------------------------------------------------------------------
# KAYAN EKRAN (Picture-in-Picture)
#
# Web'in kendi PiP API'si Android WebView'da yok. Android'inki Activity
# düzeyinde çalışıyor ve iki şey istiyor: activity'nin PiP desteklediğini
# BİLDİRMESİ ve boyut değişimlerini kendisinin karşılaması (configChanges'te
# screenSize/screenLayout/smallestScreenSize zaten var — yoksa pencere
# küçülürken activity yeniden yaratılır ve görüşme düşerdi).
# ---------------------------------------------------------------------------
with io.open(MANIFEST_PATH, encoding="utf-8") as f:
    manifest = f.read()

if "supportsPictureInPicture" not in manifest:
    eslesme = re.search(r'(<activity\b[^>]*android:name="\.MainActivity"[^>]*)(>)', manifest, re.S)
    if not eslesme:
        raise SystemExit("HATA: MainActivity etiketi bulunamadı, kayan ekran açılamadı.")
    ek = ('\n            android:supportsPictureInPicture="true"'
          '\n            android:resizeableActivity="true"')
    manifest = manifest[:eslesme.end(1)] + ek + manifest[eslesme.end(1):]
    for gerekli in ("screenSize", "screenLayout", "smallestScreenSize"):
        if gerekli not in manifest:
            raise SystemExit(
                "HATA: configChanges içinde %s yok; kayan ekranda activity yeniden "
                "yaratılır ve görüşme düşer." % gerekli)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        f.write(manifest)
    print("kayan ekran (PiP) açıldı: supportsPictureInPicture + resizeableActivity")
else:
    print("kayan ekran zaten açık.")

# ---------------------------------------------------------------------------
# ARKA PLAN NÖBETİ
#
# Android 14'ten beri her ön plan servisinin bir TÜRÜ olmak zorunda.
# Buradaki iş "gerçek zamanlı mesajlaşma bağlantısını açık tutmak" — hazır
# türlerin hiçbiri bunu tam karşılamıyor, o yüzden specialUse ve alt türü
# açıkça yazılıyor. dataSync bilerek seçilmedi: Android 15'te 24 saatte
# 6 saatle sınırlanıyor ve nöbet sessizce sona ererdi.
# ---------------------------------------------------------------------------
NOBET_SERVIS = PAKET + ".MeridyenNobet"
if NOBET_SERVIS not in manifest:
    blok = (
        '\n        <service android:name="' + NOBET_SERVIS + '"\n'
        '            android:exported="false"\n'
        '            android:foregroundServiceType="specialUse">\n'
        '            <property\n'
        '                android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE"\n'
        '                android:value="Gercek zamanli mesaj baglantisini acik tutar" />\n'
        '        </service>'
    )
    eslesme = re.search(r"<application\b[^>]*>", manifest)
    if not eslesme:
        raise SystemExit("HATA: <application> etiketi bulunamadı, nöbet servisi eklenemedi.")
    yer = eslesme.end()
    manifest = manifest[:yer] + blok + manifest[yer:]
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        f.write(manifest)
    print("nöbet servisi eklendi: " + NOBET_SERVIS)
else:
    print("nöbet servisi zaten tanımlı.")

with io.open(MANIFEST_PATH, encoding="utf-8") as f:
    son = f.read()
for beklenen, aciklama in (
    (NOBET_SERVIS, "arka plan nöbeti servisi"),
    ('android:foregroundServiceType="specialUse"', "ön plan servisi türü"),
    ("FOREGROUND_SERVICE_SPECIAL_USE", "ön plan servisi izni"),
    ('android:supportsPictureInPicture="true"', "kayan ekran desteği"),
):
    if beklenen not in son:
        raise SystemExit("HATA: manifestte %s yok (%s)." % (beklenen, aciklama))
print("kayan ekran ve nöbet doğrulandı.")
