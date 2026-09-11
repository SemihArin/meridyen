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
- **Bildirimler, uygulama açık/arka plandayken çalışıyor** — WebView'ın
  sunmadığı `Notification` API'si yerel bildirim eklentisiyle desteklendi
  (ayrıntı aşağıda).
- `firebase-messaging-sw.js` yeniden oluşturuldu (önceki bir ortam
  sıfırlanmasında kaybolmuştu) — index.html'deki mevcut FIREBASE_CONFIG'le
  birebir aynı.

## Bildirimler

Kısa özet: bildirimler hem uygulama açık/arka plandayken (yerel bildirim) hem
de tamamen kapalıyken (native FCM push) çalışacak şekilde bağlandı. Kapalıyken
gelmesi için ayrıca **veritabanı kuralının yüklü olması ve sunucunun push'a
`notification` bloğu koyması** gerekiyor — ikisi de aşağıda anlatıldı.

### Sorun neydi

Android'in WebView'ı, web'in `Notification` API'sini hiç sunmuyor (Push API'yi
de). Yani APK içinde `window.Notification` tanımsızdı. `index.html` bunu her
yerde kontrol ettiği için hiçbir şey çökmüyordu, ama Ayarlar'da "Tarayıcın
desteklemiyor" yazıyor ve hiçbir bildirim çıkmıyordu.

### Ne yapıldı

Eksik API, Capacitor'un **yerel bildirim** eklentisiyle desteklenerek yerine
kondu (`www/meridyen-native.js`). Uygulamanın kodu hiç değişmedi — hâlâ
`new Notification(...)` çağırıyor, altta Android'in kendi bildirim sistemi
çalışıyor. Köprünün karşıladıkları:

- `Notification.permission` ve `Notification.requestPermission()` → Android'in
  kendi izin penceresi (Android 13+ için gereken `POST_NOTIFICATIONS` izni
  artık gerçekten isteniyor, manifestte atıl durmuyor).
- `new Notification(baslik, {body, tag})` → gerçek bir Android bildirimi.
  `tag` sabit bir sayısal id'ye çevriliyor, böylece aynı sohbetten gelen ikinci
  mesaj web'deki gibi öncekinin üstüne yazıyor, alt alta yığılmıyor.
- Bildirime dokunma → uygulamanın kendi `onclick` davranışı (ilgili sohbete
  veya bildirime gitme) ve `close()`.

Durum çubuğu için ayrıca logodan tek renk bir "M" ikonu üretildi
(`scripts/make_notification_icon.py`). Android bildirim ikonlarını yalnız
siluet olarak çizdiği için renkli launcher ikonu orada beyaz bir leke olarak
görünürdü.

`www/index.html` bilerek canlı sitedekiyle **birebir aynı** bırakıldı: köprü
oraya elle eklenmiyor, `npx cap sync`'ten sonra yalnızca derlenen kopyaya bir
`<script>` satırı olarak enjekte ediliyor (`scripts/inject_native_script.py`).
Siteyi güncellediğinde dosyayı olduğu gibi kopyalayabilirsin.

Köprü yalnız APK içinde devreye giriyor; tarayıcıda gerçek `Notification` API'si
bulunduğu için hiçbir şeye dokunmadan çıkıyor. Eklenti bulunamazsa da sessizce
devre dışı kalıyor, yani en kötü ihtimalle eski davranışa dönülüyor.

### Uygulama kapalıyken bildirim (native FCM)

Yerel bildirim, cihazda çalışan koddan doğuyor; uygulama tamamen kapatıldığında
çalışan kod kalmadığı için yetmiyor. Bu yüzden native FCM de bağlandı:
`@capacitor/push-notifications` eklendi ve `google-services.json` depoya kondu
(Capacitor'un kendi `app/build.gradle` şablonu bu dosyayı görünce
google-services eklentisini kendisi uyguluyor, Gradle'a elle dokunmadık).

Belirteci (token) native tarafta alıp uygulamanın zaten kullandığı
`cihazlar/<uid>` düğümüne yazıyoruz — yani **sunucunda değişiklik gerekmiyor**,
aynı düğümü okumaya devam ediyor. Yazarken uygulamanın kendi
`belirtecAnahtari()` fonksiyonunu kullanıyoruz; bulunamazsa birebir aynı karmayı
üreten bir yedek devreye giriyor (ikisinin aynı sonucu verdiği test edildi).

Köprü ayrıca uygulamanın `cihazBelirteci` değişkenini dolduruyor. Bunun faydası:
"bildirimde içerik göster" tercihi değiştiğinde ve çıkış yapıldığında
`index.html`'in KENDİ mevcut kodu belirteci güncelliyor/siliyor — o mantık
burada tekrar yazılmadı.

Uygulama öndeyken gelen push yutuluyor, çünkü index.html zaten veritabanı
dinleyicisinden kendi bildirimini gösteriyor; ikisi birden çalışsa aynı mesaj
iki kez görünürdü (web tarafı da aynısını yapıyor).

### Çalışması için gereken iki şey (sunucu/konsol tarafı)

Bunlar APK'nın dışında kaldığı için buradan yapılamıyor, kontrol etmen gerek:

1. **`cihazlar` veritabanı kuralı yüklü olmalı.** Telefon belirtecini
   `cihazlar/<uid>/...` altına yazıyor; kural yoksa yazma reddedilir ve sunucu
   o cihaza hiç gönderemez. Gereken kural:

   ```json
   "cihazlar": { "$uid": { ".read": "auth.uid === $uid", ".write": "auth.uid === $uid" } }
   ```

   Bu kural `www/index.html` içindeki kural bloğunda var, ama canlı sitedeki
   sürümde yok — yani Firebase konsolunda yüklü olup olmadığını doğrulaman
   gerekiyor. Yazma reddedilirse köprü tarayıcı konsoluna
   "bildirim belirteci yazılamadı" uyarısı düşürüyor.

2. **Sunucu, push'a `notification` bloğu koymalı.** Uygulama tamamen
   kapalıyken bildirimi Android'in kendisi çiziyor ve bunu yalnız `notification`
   bloğundan yapabiliyor. Yalnızca `data` gönderilirse (web Service Worker'ı
   bununla da başa çıkabiliyordu) kapalı uygulamada hiçbir şey görünmez.
   Yani sunucu hem `notification` hem `data` göndermeli: ilki kapalıyken
   görünmesi, ikincisi uygulama açılınca yönlendirme için.

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
