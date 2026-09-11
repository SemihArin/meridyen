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

- Uygulaman `www/index.html` olarak kopyalandı. Tek içerik değişikliği:
  medya yazımı Firebase Storage yerine RTDB'ye döndürüldü (aşağıda).
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

## Medya paylaşımı: Storage kaldırıldı, her şey RTDB'de

APK'dan görsel paylaşılamamasının sebebi şuydu: `www/index.html`, canlı
sitedekinden farklı bir sürümdü ve medyayı **Firebase Storage**'a yüklüyordu.
Canlı sitede Storage hiç kullanılmıyor. Storage bu projede hiç kurulmamış
olduğu için yükleme "izin yok" ile reddediliyor, uygulama da bunu genel bir
"Dosya okunamadı." mesajına çeviriyordu.

Projede kullanılan tek arka uç RTDB olduğu için **Storage tamamen çıkarıldı**
ve medya yazımı Realtime Database'e döndürüldü. Böylece konsolda ek bir
kurulum gerekmiyor; yüklenecek tek kural kümesi `database.rules.json`.

### Ne değişti

- `medyaYaz` / `medyaYazDosya` artık RTDB'ye yazıyor. Yazılan biçim, bu
  dosyanın **okuma** tarafının (`medyaGetir`) zaten tanıdığı biçimle birebir
  aynı — okuma koduna hiç dokunulmadı:

  | Düğüm | İçerik |
  |---|---|
  | `medya/<id>/veri` | küçük medya (sıkıştırılmış görseller): tek düğümde data: URL |
  | `medya/<id>/bilgi` | `{ parca, ikili:true, mime, uzunluk, uid, ts }` |
  | `medya/<id>/parca/<i>` | o dilimin ham baytlarının base64'ü |

- Büyük dosyalar belleğe alınmadan, 256 KB'lık dilimler hâlinde yazılıyor.
- `bilgi` en sona yazılıyor: dilimler tamamlanmadan yazılsaydı, o aralıkta
  kaydı açan biri "bozuk kayıt" görürdü.
- Yükleme iptal edilirse o ana kadar yazılan dilimler siliniyor, veritabanında
  sahipsiz çöp kalmıyor.
- Firebase Storage SDK'sı artık hiç yüklenmiyor, `storage.rules` dosyası
  depodan kaldırıldı.
- Okuma tarafındaki `bilgi.depo === 'storage'` dalı duruyor: Storage'a yazılmış
  bir kayıt varsa bozulmasın diye. Yeni hiçbir yazma oraya gitmiyor.

### Doğrulama

Yazma ve okuma fonksiyonları dosyadan çıkarılıp sahte bir RTDB üzerinde
çalıştırıldı (18 test): küçük görsel tek düğüme yazılıp aynen geri okunuyor,
700 KB'lık ikili dosya üç dilime bölünüp birleştirildiğinde **baytlar birebir
aynı** geliyor, mime ve uzunluk korunuyor, `bilgi` dilimlerden sonra yazılıyor
ve iptal edilen yükleme geriye kayıt bırakmıyor.

### Bilmen gereken iki bedel

1. **Kota**: base64, ham veriden ~%37 daha büyük ve medya artık veritabanının
   içinde duruyor. RTDB'nin ücretsiz kotası 1 GB — birkaç büyük video tek
   başına kotayı doldurabilir. Uygulamadaki üst sınır hâlâ 700 MB
   (`PAYLASIM_MAKS`); küçültmek istersen söyle.
2. **Videoda gerçek atlama yok**: bir JSON düğümünden bayt-aralığı (Range)
   istenemediği için "istediğin ana atla", aşamalı oynatma mantığıyla taklit
   ediliyor.

### Önemli: canlı siteyi de güncelle

Bu değişiklik `www/index.html` üzerinde yapıldı, yani APK'daki kopya artık
canlı sitedekinden farklı. Aynı dosyayı siteye de yüklemezsen web ve APK
zamanla birbirinden ayrışır. Bu dosyayı yeni kaynak olarak almanı öneririm.

## Video oynatma: kök nedenler giderildi

Video tarafı üç yapısal eksikten dolayı kırılgandı. Üçü de giderildi.

### 1) Yarım dosyadan oynatma (asıl kırılganlık)

Oynatıcı, indirme sürerken `video.src`'i **henüz yarım inmiş** baytlardan
kurulan yeni bir Blob'a düzenli aralıklarla değiştiriyordu. Bu yapısal olarak
bozuk: `moov` kutusu videonun TAM süresini ve örnek tablosunu tarif ederken
elimizdeki `mdat` yalnız bir ön ek oluyor. Tarayıcı bu tutarsızlıkta videoyu
sonuna sıçratıyor ve oynatma erken kesiliyor — "6 saniyelik video 4 saniyede
bitiyor, sürekli sona atlıyor" belirtisinin kaynağı buydu.

İlginç olan: bu tespit dosyanın kendi yorumlarında **Storage yolu için zaten
yapılmış** ve orada bu yöntem terk edilmişti; dilimli yolda gözden kaçmıştı.
Artık kaynak yalnız bir kez, tamamı inmiş ve geçerli bir dosyadan kuruluyor;
bütünlük başlıktaki `uzunluk` ile doğrulanıyor, eksikse hiç gösterilmiyor.

Bunun yan etkisi: video oynamaya başlamadan önce tamamının inmesi bekleniyor.
Doğru davranışın bedeli bu; yarım dosyadan oynatmanın düzgün yolu MSE ve
parçalı MP4'tür, o da ayrı bir iş.

### 2) Önden hazırlık yoktu — ve pahalıya mal oluyordu

Telefon kameraları `moov` kutusunu dosyanın SONUNA yazar. Eski kodda bu
durumda "dönüşüm gerekli" deniyor ve dosya **bütünüyle yeniden kodlanıyordu**
(libx264, crf 27, 1280'e küçültme) — dakikalar süren, kaliteyi düşüren bir iş.
Oysa gereken tek şey bir kutuyu başa taşımaktı.

Artık saf JS bir **faststart remuxer** var (`mp4MoovBasaAl`): tek bir kare bile
yeniden kodlanmıyor, hiçbir bayt kaybolmuyor. `moov` başa alınıyor ve
içindeki chunk offset tabloları (`stco`/`co64`) yeni yerleşime göre
düzeltiliyor — bu tablolar düzeltilmezse dosya sessizce bozulur, oynatıcı
kareleri yanlış baytlarda arar. Dosyanın tamamı belleğe alınmıyor: yalnız
`moov` okunuyor, gerisi Blob dilimi olarak referansla taşınıyor, yani 700 MB'lık
bir dosyada bile maliyet birkaç yüz KB. Beceremediği bir dosyada `null` dönüp
eski yola bırakıyor, yani davranış hiçbir zaman eskisinden kötü olmuyor.

### 3) Tüm bilgiyi taşıyan bir başlık yoktu

Medya kaydının `bilgi` düğümü artık oynatıcının medyanın tek bir baytı
inmeden ihtiyaç duyduğu her şeyi taşıyor:

```json
{ "parca": 12, "dilimBayt": 262144, "ikili": true, "mime": "video/mp4",
  "uzunluk": 3145728, "sure": 17, "en": 1920, "boy": 1080,
  "hizliBaslangic": true, "uid": "...", "ts": 0 }
```

`sure`, `en` ve `boy` zaten gönderen tarafta kapak karesi alınırken
ölçülüyordu ama hiçbir yere yazılmıyordu. Artık oynatıcı en-boy oranını daha
ilk anda kurup yerleşim zıplamasını önlüyor ve tanılama günlüğüne tam künyeyi
yazıyor.

### Doğrulama

- **Faststart remuxer, 21 test**: sentetik ama yapısal olarak geçerli MP4'ler
  üzerinde, hem `stco` hem `co64` tablolarıyla. En kritik olanı: remux sonrası
  offsetlerin **gerçekten doğru öbek baytlarını** gösterdiği bayt bayt
  doğrulandı. Ayrıca boyut korunuyor, kutu sırası `ftyp,moov,mdat` oluyor,
  `mdat` yükü bozulmuyor ve zaten faststart olan dosyada işlem tekrarlanınca
  dosya değişmiyor.
- **Başlık, 8 test**: süre/en/boy/dilim boyutu/uzunluk doğru yazılıyor, video
  olmayan medyaya video alanları eklenmiyor.
- **Medya gidiş-dönüş, 18 test**: değişikliklerden sonra da baytlar birebir
  aynı geliyor.

## Arka planda gönderim ve yerel ilerleme bildirimi

### Gönderirken arayüz artık kilitlenmiyor

`gonder()` bütün eklerin yüklenmesini `await` ediyordu ve bu sırada global
`gonderimSuruyor` bayrağı açık kalıyordu. Sonuç: 60 MB'lık bir video giderken
**hiçbir sohbete** mesaj gönderilemiyor, gönder düğmesi kapalı kalıyordu.

Artık yüklemeler arayüzden bağımsız bir kuyrukta akıyor:

- "Gönder"e basıldığı an kompoze çubuğu ve yanıt temizleniyor, ek
  "gönderiliyor" baloncuğuyla konuşmada beliriyor ve `gonder()` bitiyor.
- Başka sohbete geçebilir, yazabilir, oraya da mesaj yollayabilirsin; yükleme
  arka planda devam eder ve **yakalanmış hedefe** gider (sohbet değiştirmek
  mesajı yanlış kişiye göndermez, bu koruma zaten vardı).
- Kuyruk bilerek tek işli: gönderim sırası korunuyor ve aynı anda birden çok
  büyük dosya yazıp ağı boğmuyoruz. Başarısız bir yükleme kuyruğu durdurmuyor.
- "Tekrar dene" de kuyruğa giriyor, akan bir yüklemeyle yarışmıyor.

Bilinen sınır: yükleme sürerken başka sohbete geçip geri dönersen o sohbetin
görünümü yeniden çizildiği için "gönderiliyor" baloncuğu kaybolur. Yükleme
kesilmez, bittiğinde mesaj normal şekilde belirir — ve bu sırada ilerlemeyi
aşağıdaki bildirimden izleyebilirsin.

### Yükleme bildirimi (tamamen yerel)

Gönderim sürerken cihazın kendi bildirim alanında bir ilerleme bildirimi
duruyor. **Sunucuyla, FCM'le ya da ağla hiçbir ilgisi yok** — doğrudan yerel
bildirim olarak yazılıyor (`meridyen-native.js` içindeki `MeridyenYukleme`).

- `ongoing` işaretli: kaydırarak silinemiyor, çünkü iş hâlâ sürüyor.
- Güncellemeler sessiz: eklenti her bildirimde `setOnlyAlertOnce(true)`
  kurduğu için aynı id'ye yeniden yazmak telefonu yeniden titretmiyor.
- Yüzde yalnız tam sayı değiştiğinde ve en fazla saniyede bir yazılıyor;
  %100 her hâlükârda yazılıyor. Büyük bir dosyada saniyede onlarca köprü
  çağrısı yapmanın anlamı yok.
- Bildirim id'leri ayrılmış bir bantta (1.9 milyar ve üstü); mesaj bildirimi
  id'leri bu bandın altına sıkıştırıldı ki ikisi birbirinin bildirimini
  ezmesin.
- Tarayıcıda bu API tanımlı ama hiçbir şey yapmıyor, böylece uygulama kodu
  koşulsuz çağırabiliyor.

Not: bildirimin görünmesi için bildirim izni verilmiş olmalı (Ayarlar →
Bildirimler). İzin yoksa yükleme yine sorunsuz çalışır, yalnız bildirim çıkmaz.

### Video ön yükleme

Video, oynatılmadan önce tamamının inmesini bekliyor (yarım dosyadan oynatmak
yapısal olarak bozuktu, yukarıda anlatıldı). Bunun bedeli "oynata bas →
bekle"ydi. Artık bir video kutusu ekranda görününce, **küçükse** arka planda
sessizce inmeye başlıyor; oynata basıldığında dosya çoktan önbellekte oluyor.

Bunu mümkün kılan şey yeni başlık: tek bir küçük okumayla dosyanın boyutunu
öğrenip indirmeden karar verebiliyoruz. Sınırlar bilerek dar:

- yalnız 8 MB'ın altındaki videolar (mobil veriyi habersiz tüketmemek için),
- aynı anda tek ön yükleme,
- ve bir gönderim sürerken ön yükleme bekler — kullanıcının gönderdiği dosya
  her zaman öncelikli.

### Doğrulama

Bu turda 73 test çalıştırıldı, hepsi geçti: kuyruk 5 (sıra korunuyor, tek iş,
hata kuyruğu durdurmuyor), bildirim 14 (ongoing/sessiz/kısma/id bandı — 3000
mesaj etiketinin ayrılmış banda hiç düşmediği de sınandı), ön yükleme 7 (boyut
sınırı, tekilleştirme, gönderime yol verme), faststart remuxer 21, başlık 8,
medya gidiş-dönüş 18.

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
