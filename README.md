# Meridyen — Android sarmalayıcısı

Bu depo, `index.html`'i (mevcut web uygulamanla birebir aynı dosya) gerçek,
kurulabilir bir Android uygulamasına ([Capacitor](https://capacitorjs.com)
ile) çeviriyor.

`android/` klasörü bilerek depoya eklenmiyor. Onun yerine her derlemede
Capacitor'un KENDİ resmi şablonundan taze bir `android/` projesi üretiliyor,
üstüne de iki küçük betikle ikonlar (`scripts/copy_icons.sh`) ve izinler
(`scripts/patch_manifest.py`) yamanıyor. Böylece elle taşınmış, zamanla
bayatlayan bir Gradle projesini sürüklemek zorunda kalmıyoruz.

## Durum: derleme doğrulandı ✅

Proje baştan sona derlendi ve çıkan APK incelendi — artık "umarım Actions'ta
çalışır" değil, çalıştığı görülmüş bir kurulum:

| | |
|---|---|
| Paket kimliği | `com.meridyen.app` |
| Uygulama adı | Meridyen |
| APK boyutu | ~4,2 MB |
| targetSdk / compileSdk | 35 (Android 15) |
| Capacitor | 7.6.9 |
| Android Gradle Plugin / Gradle | 8.7.2 / 8.11.1 |
| JDK | 21 |
| İmza | debug (sideload'a uygun) |

Doğrulananlar: `com.meridyen.app` paketi ve "Meridyen" adı doğru gömülmüş,
altı iznin (kamera, mikrofon, ses ayarı, bildirim, ağ durumu, wake lock)
hepsi manifestte, uyarlanabilir ikon yerinde, `index.html` ve
`firebase-messaging-sw.js` APK içine `assets/public/` altına eksiksiz
kopyalanmış.

Not: `npm ci` ile kurulum yapıldığı ve `package-lock.json` depoda olduğu için
GitHub Actions'ın kuracağı sürümler burada doğrulananlarla birebir aynı olur.

## APK nasıl alınır

1. Bu depoyu GitHub'a gönder (push).
2. GitHub'da **Actions** sekmesine git → "APK derle" iş akışı otomatik
   başlar (`main`, `master` ve `claude/**` dallarına yapılan push'larda;
   ayrıca "Run workflow" ile elle de tetiklenebilir).
3. Birkaç dakika sürer. Bittiğinde alt kısımdaki **Artifacts** bölümünden
   `meridyen-debug-apk` dosyasını indir — içinde `app-debug.apk` var.
4. Bu `.apk`'yı telefonuna aktarıp aç, "Bilinmeyen kaynaklardan yükleme"ye
   izin ver, kur. Play Store'dan gelmediği için bu uyarı normal.

## Şu an neler hazır

- Uygulaman `www/index.html` olarak birebir kopyalandı — web sürümüyle aynı
  dosya, hiçbir satırı değiştirilmedi.
- Uygulama ikonu, sitendeki mevcut "M" logosundan otomatik üretildi
  (klasik + Android 8+ uyarlanabilir ikon olarak).
- Kamera, mikrofon, bildirim gibi izinler manifest'e otomatik ekleniyor.
- **Kamera/mikrofon (aramalar) çalışır durumda**: Capacitor'un WebView
  köprüsü `getUserMedia` çağrısını yakalayıp Android'in kendi izin
  penceresini açıyor (`BridgeWebChromeClient.onPermissionRequest`), izin
  verilince akışı web tarafına geçiriyor. Yani ek bir native yama gerekmiyor;
  yine de ilk kurulumdan sonra bir arama başlatıp gerçek cihazda test etmekte
  fayda var.
- `firebase-messaging-sw.js` yeniden oluşturuldu (önceki bir ortam
  sıfırlanmasında kaybolmuştu) — index.html'deki mevcut FIREBASE_CONFIG'le
  birebir aynı.

## Bilinen sınırlama: bildirimler (önemli — önceki not yanlıştı)

Önceki README "uygulama açıkken bildirimler çalışır, sadece kapalıyken
gecikebilir" diyordu. Kodu ve WebView'ın yeteneklerini inceleyince durumun
bundan daha keskin olduğu ortaya çıktı, düzeltiyorum:

**Android WebView, web'in `Notification` API'sini hiç sunmuyor** (Push API'yi
de). Yani APK içinde `window.Notification` tanımsız. `index.html` bunu zaten
her yerde kontrol ediyor (`if (!('Notification' in window)) return;`), o
yüzden **hiçbir şey çökmez** — uygulama sorunsuz açılır, mesajlaşma ve
aramalar çalışır. Ama:

- Sistem bildirimi hiç çıkmaz (ne uygulama açıkken, ne kapalıyken).
- Menüdeki "Bildirimlere izin ver" satırı kendini gizler, Ayarlar'da bildirim
  durumu "Tarayıcın desteklemiyor" yazar. Bu bir hata değil, kodun kendi
  zarif geri çekilmesi.
- Manifest'e eklenen `POST_NOTIFICATIONS` izni bu yüzden şimdilik atıl
  duruyor; native entegrasyon geldiğinde kullanılacak.

**Çözümü tek adım, sende:** Firebase konsolunda bu Android paketine
(`com.meridyen.app`) özel bir uygulama kaydı aç, `google-services.json`
dosyasını indirip bana gönder. Ardından `@capacitor/push-notifications` +
`@capacitor/local-notifications` ekleyip native tarafa bağlarım — bildirimler
uygulama kapalıyken de gelir, ki bu web sürümünden bile güvenilir olur.

## Diğer sıradaki adımlar

- **İmzalama / Play Store**: Şu anki APK "debug" imzalı — sideload (elle
  kurulum) için sorun değil, ama Play Store'a yüklenemez. Ayrıca debug imzası
  derleme ortamına bağlı olduğundan, ileride farklı bir ortamda üretilen APK
  telefondaki kurulumun üstüne gelmeyebilir (o durumda önce kaldırıp yeniden
  kurmak gerekir). Play Store'a gidecekse gerçek bir "release keystore" üretip
  GitHub Secrets'a koyarız — ayrı bir adım.

## Uygulama adını / paket kimliğini değiştirmek

`capacitor.config.json` içindeki `appId` (paket kimliği, örn.
`com.meridyen.app`) ve `appName` (görünen ad) değerlerini değiştirip tekrar
push'lamak yeterli — bir sonraki derlemede otomatik yansır.

## Web uygulamasını güncellemek

`www/index.html`'i canlı sitendeki yeni sürümle değiştirip push'la; bir
sonraki derleme yeni içerikle APK üretir. Bildirimlerle ilgili
`firebase-messaging-sw.js` dosyasının da aynı FIREBASE_CONFIG'i kullandığından
emin ol.
