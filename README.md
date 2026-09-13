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

## Aşamalı oynatma (MSE + parçalı MP4)

Video artık **dosyanın tamamı inmeden izlenebiliyor**: başlatma parçası ve ilk
görüntü parçası gelir gelmez oynatma başlıyor, kalan parçalar arka planda inip
akışa ekleniyor.

### Neden eski yöntem bozuktu, bu neden değil

Daha önce denenen yöntem, indirme sürerken `video.src`'i **yarım inmiş**
baytlardan kurulan bir Blob'a değiştirmekti. Tarayıcıya eksik bir dosya
veriliyordu: `moov` videonun tam süresini tarif ederken `mdat` yalnız bir ön
ekti; bu çelişkide video sona sıçrıyordu.

MSE'de böyle bir çelişki yok. Her parça **kendi başına geçerli** bir
moof+mdat çifti ve tarayıcı akışın devam edeceğini biliyor. Eksik dosya diye
bir şey yok, yalnız henüz gelmemiş parçalar var.

### Nasıl çalışıyor

MediaSource düz MP4 kabul etmiyor; parçalı MP4 (fMP4) istiyor. Bu yüzden video
**gönderilirken** bu biçime çevriliyor — tek bir kare bile yeniden kodlanmadan,
yalnız kaplama yeniden yazılarak:

| | |
|---|---|
| `parca/0` | başlatma parçası: `ftyp` + `moov` (örnek tabloları boş, `mvex`/`trex` var) |
| `parca/1..n` | birer `moof` + `mdat` çifti, her biri anahtar kareyle başlıyor |

Kritik tasarım kararı: **RTDB dilim sınırları parça sınırlarıyla çakıştırıldı.**
Yani inen her dilim tek başına doğrudan `SourceBuffer`'a verilebiliyor;
oynatıcının tampon biriktirip kutu sınırı araması gerekmiyor.

Başlık da genişledi: `parcali`, `kodekler` (MSE'ye verilecek codec dizesi) ve
`sureTam` eklendi. `sureTam` kasıtlı olarak ayrı: arayüz etiketleri yuvarlak
saniye kullanıyor, ama MediaSource'a yuvarlanmış süre verilirse video erken
biter ya da sonda boş bekleme olur.

Süre `mvhd`'den değil **örnek zaman çizgisinden** hesaplanıyor. Testler
sırasında `mvhd`'nin yanlış süre taşıyabildiği görüldü; MSE'de bu doğrudan
hataya dönüşürdü.

### Her adımda geri çekilme

MSE bir iyileştirme, bağımlılık değil:

- Gönderirken parçalı biçime çevrilemezse (desteklenmeyen kodek, parçalı
  kaynak, bozuk kutu) video eskisi gibi düz olarak saklanıyor.
- Ses yalnız AAC ise taşınıyor: codec dizesini yanlış bildirmek MSE'de sessiz
  başarısızlık demek, o yüzden emin olunmayan ses hiç eklenmiyor (video oynar).
- Oynatırken `MediaSource` yoksa, codec desteklenmiyorsa, `sourceopen` hiç
  gelmezse (15 sn) ya da herhangi bir ekleme hata verirse otomatik olarak eski
  tam indirme yoluna düşülüyor.
- Parçalı kayıtlar tam indirme yoluyla da açılıyor: parçalar arka arkaya
  eklenince geçerli bir MP4 dosyası oluşuyor.

### Doğrulama

Bu turda eklenen 47 test dahil, tüm takım (12 dosya, 151 kontrol) geçti.
Öne çıkanlar:

- **fMP4 üretimi (20 test)**: sentetik ama yapısal olarak gerçek MP4'ler
  bağımsız bir ayrıştırıcıyla çözülüp kaynakla karşılaştırıldı. Video ve ses
  **baytları birebir aynı**; örnek sayıları, `trun` veri konumları, `tfdt`
  zaman damgalarının kesintisizliği ve her parçanın anahtar kareyle başladığı
  doğrulandı.
- **MSE oynatıcı (13 test)**: parçaların sırayla eklenmesi, `onHazir`'ın tam
  bir kez çağrılması, `endOfStream`, desteklenmeyen codec, ekleme hatası,
  eksik parça ve iptal senaryoları.
- **Uçtan uca (14 test)**: gerçek bir MP4 parçalı olarak yazılıp geri okundu;
  başlık alanları ve birleşen dosyanın parçaların birebir birleşimi olduğu
  doğrulandı.

Cihazda gerçek oynatma testi yapılamadı (burada tarayıcı/telefon yok); bu
yüzden her hata yolunda eski davranışa düşülüyor.

## Galeri ve sohbet yüklemeleri: küçük resimler mesajdan çıkarıldı

Asıl sorun taramanın kendisi değildi — taşınan yüktü.

### Neydi

Her görsel/video mesajı küçük resmini **kendi içinde**, base64 data URL olarak
taşıyordu (~60–90 KB). Bu bedel her ekranda ayrı ayrı ödeniyordu:

- Galeri bir sayfada ~80 kayıt çekiyor; hepsi küçük resmiyle birlikte inince
  birkaç MB ediyordu.
- Sohbette geriye kaydırmak, ekranda hiç görünmeyecek mesajların küçük
  resimlerini de indiriyordu.
- Medya dizini taraması aynı yükü bir kez daha ödüyordu.

Yani sunucu tarafı filtre (`orderByChild('tip')`) zaten vardı ve doğru
çalışıyordu; sorun, filtrenin döndürdüğü her kaydın kilolarca ağır olmasıydı.

### Ne yapıldı

Küçük resim artık medya kaydının kendi düğümünde: `medya/<medyaId>/kucuk`.
Mesajda yalnız `kucukVar` bayrağı duruyor. Kayıt **ekranda görününce** tek ve
küçük bir okumayla çekiliyor (`IntersectionObserver`, 300px önden).

| | Eskiden | Şimdi |
|---|---|---|
| Mesaj kaydı | ~80 KB (küçük resim gömülü) | birkaç yüz bayt |
| Galeri sayfası (80 kayıt) | birkaç MB | ~50 KB + yalnız görünen karolar |
| Ekranda görünmeyen kayıt | yine de iniyordu | hiç inmiyor |

Küçük resim medya düğümünün altında durduğu için **fazladan kural
gerekmiyor** ve medya silinince küçük resim de gidiyor — ayrı temizlik yok.

Aynı medya için birden çok öğe aynı anda isterse tek okuma yapılıyor, gelen
resimler 400 kayıtlık bir önbellekte tutuluyor.

**Geriye dönük:** eski mesajlar `kucuk` alanını taşımaya devam ediyor ve
olduğu gibi, anında çiziliyor. Hiçbir eski mesaj bozulmuyor, dönüştürme
gerekmiyor.

### Galeri sıralamasındaki boşluk da düzeltildi

Galeri iki türü (`gorsel` + `video`) ayrı ayrı sayfalıyor ve imleçleri
bağımsız ilerliyor. Türlerden biri zamanda daha geriye gittiğinde, aradaki
henüz inmemiş kayıtlar listede **görünmeyen bir boşluk** bırakıyordu:
kullanıcı kaydırırken arada eksik öğeler oluyor ve bunu fark edemiyordu.

Artık gösterim, henüz bitmemiş türlerin en geri ortak noktasıyla
sınırlanıyor. Bir tür tamamen bittiyse sınır dayatmıyor, yedek tarama
kipinde (tek akış) ise hiç uygulanmıyor.

### Doğrulama

24 yeni test: küçük resim katmanı 16 (eski kayıt anında ve okumasız, yeni
kayıt görünene kadar okunmuyor, önbellek, aynı medya için tek okuma, arka
plan kipi, kapağı olmayan kayıt) ve galeri sınırı 8 (boşluk gizleniyor,
türler bitince tamamı görünüyor, biten tür sınır dayatmıyor, yedek kipte
sınır yok). Tüm takım — 14 dosya, 175 kontrol — geçti.

## Bildirim arızası: köprü APK'ya giriyordu ama hiç yüklenmiyordu

Bir süre bildirimler tamamen kayboldu ve Ayarlar yine "Tarayıcın
desteklemiyor" dedi. Sebep WebView ya da izinler değildi — **kendi derleme
betiğimdeki bir hataydı.**

### Ne oldu

`scripts/inject_native_script.py`, köprünün zaten ekli olup olmadığını
`<script>` etiketine değil, yalnızca **dosya adına** bakarak anlıyordu:

```python
if "meridyen-native.js" in html:      # ESKİ, HATALI
    print("köprü zaten ekli"); sys.exit(0)
```

Sonraki bir turda `www/index.html` içine o dosya adını anan bir **yorum**
yazıldı ("bkz. meridyen-native.js"). Betik bunu görüp "zaten ekli" sandı ve
`<script>` etiketini hiç koymadı. Yani:

- `meridyen-native.js` APK'ya kopyalanmaya devam etti (dosya oradaydı),
- ama sayfaya hiç yüklenmedi,
- `window.Notification` tanımsız kaldı → "Tarayıcın desteklemiyor",
- FCM belirteci de yazılmadı (aynı dosyadaki push kodu da çalışmadı),
- ve hiçbir yerde hata görünmedi.

### Üç katmanlı önlem

1. **Kesin denetim.** Artık dosya adı değil, etiketin kendisi düzenli ifadeyle
   aranıyor. Üstelik betik önce var olan etiketleri temizleyip tam bir tane
   ekliyor — yani tanım gereği idempotent, kaç kez çalışırsa çalışsın.
2. **Sessiz başarısızlık yok.** Betik işini bitirince etiketin gerçekten ve
   tam bir kez orada olduğunu doğruluyor; değilse hata koduyla çıkıp derlemeyi
   kırıyor. İş akışına ayrıca bir doğrulama adımı kondu: etiket ve dosya
   derlenen kopyada yoksa APK hiç üretilmiyor.
3. **Regresyon testi.** `scripts/test_inject_native_script.py` tam da bu
   senaryoyu kilitliyor: "dosya adı yalnızca bir yorumda geçiyorsa etiket yine
   de eklenmeli". Test her derlemede CI'da çalışıyor.

### Arıza artık ekranda ayırt ediliyor

Asıl can sıkıcı yanı, iki bambaşka arızanın aynı mesajı vermesiydi. Ayarlar
ekranı artık ayırıyor:

| Durum | Mesaj |
|---|---|
| Gerçekten desteklemeyen tarayıcı | "Tarayıcın desteklemiyor" |
| Uygulamadayız, köprü hiç yüklenmemiş | "Uygulama köprüsü yüklenmedi" |
| Köprü yüklenmiş ama bildirimi açamamış | "Uygulama köprüsü bildirimi açamadı" |

Bunu mümkün kılan şey köprünün artık kendi imzasını bırakması
(`window.MeridyenKopru` — yüklendi mi, native mi, hangi eklentiler var).
İmza, erken çıkış yollarından ÖNCE yazılıyor; yani köprü işini yapamasa bile
yüklendiğini söyleyebiliyor.

## Gönderim bildirimi: gerçek ilerleme çubuğu, yerinde güncelleniyor

İlk sürümde iki şikâyet geldi: ilerleme yüzde **sayısı** olarak görünüyordu
(çubuk değil) ve her güncellemede **yeni bir bildirim** geliyordu. İkisinin de
sebebi aynıydı ve `@capacitor/local-notifications` eklentisinin kendi
kaynağında yazılı:

- `LocalNotificationManager.schedule()` her çağrıda önce
  `dismissVisibleNotification(id)` çağırıyor — yani bildirimi **silip**
  yeniden yayınlıyor. Bu yüzden yerinde güncellenmiyor, her seferinde yeni
  bildirim gibi davranıyor.
- Aynı dosyada `// TODO Progressbar support` yazıyor: **ilerleme çubuğu
  desteği yok**. Geriye yüzdeyi metne yazmaktan başka seçenek kalmıyordu.

Yani bu iş için yanlış araçtı. Gönderim bildirimi artık kendi küçük native
eklentimizden geçiyor (`android-assets/java/MeridyenIlerleme.java`):

- `NotificationCompat.Builder.setProgress(100, yuzde, false)` → **gerçek
  ilerleme çubuğu**. Metinde yüzde yazmıyor; alt satırda ne gönderildiği
  yazıyor ("3 dosya" ya da dosya adı).
- `notify()` **aynı id ile, silmeden** çağrılıyor → Android bildirimi yerinde
  günceller.
- `setOnlyAlertOnce(true)` + `setSilent(true)` + düşük önemli kanal →
  güncellemede ses, titreşim ve ekranın üstünde belirme yok.
- Başlangıçta çubuk **belirsiz** kipte: ilk bayt gitmeden "%0" göstermek
  takılmış izlenimi veriyordu.
- Bildirim id'si (2000000001) bilerek 1.9 milyarın üstünde; mesaj bildirimi
  id'leri `% 1900000000` ile o sınırın altına sıkıştırılıyor, ikisi asla
  birbirinin üstüne yazmıyor.

`android/` her derlemede sıfırdan üretildiği için eklentiyi
`scripts/install_native_plugin.py` kuruyor: sınıfı kopyalıyor ve
`MainActivity`'de kaydediyor. Java paketi `capacitor.config.json`'daki
`appId`'den okunuyor, yani paket kimliği değişirse kendiliğinden uyuyor.
Betik işini bitirince dosyanın ve kayıt satırının yerinde olduğunu
doğruluyor; iş akışında ayrıca bağımsız bir doğrulama adımı var.

Doğrulama: APK yeniden derlendi, eklenti sınıfının ve `setProgress`
çağrısının derlenmiş dex içinde olduğu doğrulandı. JS tarafı 15 testle
sınandı (belirsiz başlangıç, kısma, %100'ün hemen yazılması, metinde yüzde
bulunmaması, eklenti yokken sessizce geçme).

## Bildirimler artık birikiyor ve gruplanıyor

Şikayet: "bildirimler birbirlerini siliyor".

Doğruydu ve sebebi bizim kendi kararımızdı. Aynı sohbetin bildirimi hep **aynı
id'ye** yazılıyordu, yani ikinci mesaj birincinin üstüne biniyordu. Amaç "her
mesaj için ayrı bildirim yığılmasın" idi ama sonucu, gelen mesajı okumadan
kaybetmek oldu: bildirime bakan kişi yalnız sonuncu mesajı görüyordu.

Artık WhatsApp'taki gibi: **sohbet başına tek bildirim, içinde biriken
mesajlar.**

- Satırlar `MessagingStyle` ile yazılıyor — Android açılmamış hâlde "3 yeni
  mesaj" diyor, bildirimi açınca hepsini alt alta gösteriyor.
- Birden çok kişiden mesaj varsa hepsi tek bir **Meridyen** başlığı altında
  toplanıyor; özet satırında "5 mesaj · 2 sohbet" yazıyor.
- Bir sohbette en fazla 8 satır tutuluyor; sınır aşılınca **en eski** satır
  düşüyor.

### Tek yol

Bunun için bildirim yolu birleştirildi. Uygulama açıkken bildirimi Capacitor'un
yerel bildirim eklentisi çiziyordu ve o eklenti her çağrıda aynı id'yi **silip
yeniden yayınlıyor** — biriktirmenin önündeki asıl engel buydu. Artık açıkken de
kapalıyken de bildirim aynı native yoldan geçiyor (`MeridyenBildirimler`).
Eklentisi olmayan eski bir APK'da kod eski yola düşüyor, yani kurulu sürüm
eskiyse hiçbir şey bozulmuyor.

### Ne zaman düşüyor

- **Sohbeti açınca** o sohbetin bildirimi ve birikimi siliniyor: okunan mesaj
  bildirim gölgesinde durmamalı.
- **Kaydırıp atınca** birikim de unutuluyor. Bunun için bildirime bir "silindi"
  niyeti bağlandı (`MeridyenBildirimSil`). Olmasaydı bir sonraki mesajda
  kullanıcının zaten kapattığı eski satırlar geri gelirdi — attığı bildirim
  dirilmiş gibi görünürdü.

### Birkaç ayrıntı

- Biriken satırlar **diskte** tutuluyor, bellekte değil: uygulama kapalıyken
  bildirimi FCM servisi çiziyor ve o servis işlem öldükten sonra sıfırdan
  başlayabiliyor. Bellekte tutsaydık her uyanışta önceki mesajlar kaybolurdu.
- Özet **yalnız iki ve daha fazla sohbet varken** çiziliyor. Android tek
  çocuklu bir grubu özetin kendisiyle gösteriyor; tek sohbette özet çizseydik
  kullanıcı mesajı değil "1 sohbet" yazısını görürdü.
- Özet sessiz: ses ve titreşimi asıl sohbet bildirimi veriyor. İkisi birden
  uyarsaydı her mesajda çift titreşim olurdu.
- Her bildirimin ve her "silindi" niyetinin `requestCode`'u kendi id'si.
  Hepsine 0 verilseydi `FLAG_UPDATE_CURRENT` yüzünden açık olan bütün
  bildirimlerin hedefi sonuncusununkine döner, yanlış sohbet açılır ve yanlış
  birikim silinirdi.
- Bildirime dokununca doğru sohbetin açılması için gönderenin kimliği web'den
  native'e `data` alanıyla geçiyor — `data` web'in Notification API'sinde
  standart bir alan, tarayıcıda yok sayılıyor.

### Doğrulama

Bu davranışın doğrudan gözleneceği tek yer bir telefon ve burada cihaz yok. Bu
yüzden biriktirme kuralları Android'e **hiç dokunmayan** saf metotlara ayrıldı
(`depoyaEkle`, `depodanSil`, `ozetSatirlari`, `ozetMesajSayisi`,
`ozetGerekliMi`) ve `scripts/test_biriken_bildirim.py` onları **gerçek kaynak
dosyadan çıkarıp** çalıştırıyor — kopyasını değil. 20 kural sınanıyor: ikinci
mesajın üstüne yazmaması, sohbetlerin ayrı birikmesi, sınır aşılınca en
eskinin (en yeninin değil) atılması, yalnız açılan sohbetin düşmesi, özetin ne
zaman gerektiği, boş/bozuk depoda çökmemesi.

> `android.jar` içindeki `org.json` yalnız bir iskelet — her metodu "Stub!"
> diye hata fırlatıyor. Sınama bu yüzden gerçek uygulamayı sabit sürümle
> indiriyor ve önbelleğe alıyor.

Köprü tarafında 20 senaryo daha: mesajın kendi eklentimize gitmesi, yerel
bildirim eklentisinin artık hiç kullanılmaması, aynı etiketli ikinci mesajın
ayıklanmadan yollanması, kapatmanın birikimi silmesi, eski APK'da eski yola
düşülmesi. Önceki 129 senaryo da geçiyor.

## Kamera, kayan ekran ve arka planda bağlı kalma

### 1) Doğrudan kamera

Yazma çubuğuna bir kamera düğmesi geldi: **Fotoğraf çek** / **Video çek**.
Dosya seçiciyi atlayıp telefonun kamerasını doğrudan açıyor.

Yeni bir eklenti gerekmedi — `<input type="file" capture="environment">`
Capacitor'un WebView'ı tarafından karşılanıyor (`ACTION_IMAGE_CAPTURE` /
`ACTION_VIDEO_CAPTURE`) ve mobil tarayıcılar da destekliyor. Yani aynı düğme
sitede de çalışıyor. Masaüstünde karşılığı olmadığı için orada gizleniyor:
tıklayınca sıradan bir dosya seçici açılması kullanıcıyı yanıltırdı.

Çekilen dosya gönderim yoluna dosya seçiciyle **aynı** yerden giriyor
(`ekleriAl`) — kamera yalnız dosyanın nereden geldiğini değiştiriyor, ne
olduğunu değil. Yani sıkıştırma, önizleme, arka planda yükleme ve ilerleme
bildirimi olduğu gibi çalışıyor.

### 2) Kayan ekran (görüntülü görüşmede resim-içinde-resim)

Uygulamada bir "ayrı pencerede sürdür" düğmesi zaten vardı ama **APK'da hiç
görünmüyordu**: web'in Picture-in-Picture API'si Android WebView'da yok
(`document.pictureInPictureEnabled` false döner), kod da bunu doğru şekilde
denetleyip düğmeyi gizliyordu. Artık orada Android'in kendi kayan ekranı
devreye giriyor.

Üç ince nokta vardı:

- **Giriş anı.** `enterPictureInPictureMode` yalnız pencere **henüz
  öndeyken** kabul ediliyor. JavaScript'in `visibilitychange` olayı bunun için
  geç kalıyor — o an pencere zaten arkaya geçmiş oluyor. Bu yüzden karar
  native tarafta, `Activity.onUserLeaveHint` içinde veriliyor; Android 12 ve
  üstünde ayrıca sistemin kendi otomatik girişi (`setAutoEnterEnabled`)
  açılıyor, çünkü jestle çıkışta o daha güvenilir.
- **Yalnız görüşme sürerken.** Web tarafı görüşmenin başladığını/bittiğini
  native tarafa bildiriyor. Bildirmeseydik ana ekrana her dönüşte vitrin küçük
  bir pencerede asılı kalırdı.
- **Küçük pencerede ne görünecek.** Android'in PiP'i Activity düzeyinde:
  pencere küçülünce sayfanın **tamamı** küçülüyor. Avuç içi kadar bir alanda
  vitrini ve düğmeleri göstermenin anlamı yok, o yüzden native taraf kipe
  girildiğini web'e bildiriyor ve `body.kayan-ekran` yalnız karşı tarafın
  görüntüsünü bırakıyor.

Manifestte `supportsPictureInPicture` ve `resizeableActivity` açıldı. `configChanges`
içindeki `screenSize/screenLayout/smallestScreenSize` ayrıca **denetleniyor**:
biri eksik olsa pencere küçülürken activity yeniden yaratılır ve görüşme düşerdi.

### 3) Arka planda bağlı kalma — "bir süre sonra bildirimler duruyor"

Sebep Android'in kendi davranışı: arka plandaki uygulama bir süre sonra
"önbelleğe alınmış" sayılıyor, Android 14'ten beri işlem **dondurulabiliyor**
ve Doze kipinde ağ erişimi kesiliyor. WebView'daki JavaScript durunca
veritabanı bağlantısı ölüyor; yeni mesaj gelse bile kimse görmüyor.

Çözüm bir ön plan servisi (`MeridyenNobet`). Tek işi **var olmak** — hiçbir şey
hesaplamıyor, uyanık tutma kilidi almıyor. Varlığı işlemi "önbelleğe alınmış"
olmaktan çıkarıyor: dondurulmuyor ve Doze'da ağ erişimi sürüyor.

Bedeli dürüstçe: Android 8'den beri ön plan servisi **kalıcı bir bildirim**
göstermek zorunda. Bu yüzden bildirim en düşük önemde ve sessiz — gölgenin en
altında tek satır. Ayarlar → Bildirimler → **Arka planda bağlı kal** ile
kapatılabiliyor (varsayılan açık).

Birkaç karar:

- Servis uygulama **görünürken** başlatılıyor (oturum açılınca, ayar
  değişince). Android 12'den beri arka plandan ön plan servisi başlatmak
  reddediliyor; sayfa gizlenince başlatmaya çalışsaydık tam ihtiyaç anında
  başarısız olurdu.
- Ön plan servisi türü `specialUse`. `dataSync` bilerek seçilmedi: Android
  15'te 24 saatte 6 saatle sınırlanıyor ve nöbet sessizce sona ererdi.
- `START_STICKY`: sistem belleğe ihtiyaç duyup servisi kapatırsa yeniden
  başlatsın — nöbetin anlamı sürekliliği.
- Ayrıca **Pil kısıtını kaldır** düğmesi eklendi; muafiyet olmadan üretici
  katmanları (Xiaomi, Huawei, Samsung...) uygulamayı yine uyutabiliyor.

Bildirim tanısı da bunu biliyor: ayar kapalıysa "arka planda bir süre sonra
bildirimler kesilebilir", servis başlatılamadıysa onu söylüyor.

> **Neyi çözmüyor:** uygulama tamamen kapatıldığında (görevlerden atıldığında)
> çalışan bir kod kalmıyor; orada bildirim yine sunucunun gönderdiği FCM'e
> bağlı (bkz. *Bildirimler sağlamlaştırıldı*). Bu servis "açık ama arka planda"
> durumunu çözüyor — senin tarif ettiğin durum bu.

### Doğrulama

22 yeni senaryo geçti (kayan ekran yetenek bildirimi, görüşme durumu ve oranın
aktarılması, elle geçiş, kip değişiminde gövde sınıfı, nöbetin açılıp
kapanması, pil izni, tarayıcıda ve eklentisiz APK'da sessizce devre dışı
kalma, nöbet karar tablosu). Önceki 107 senaryo da hâlâ geçiyor. APK açıldı:
`supportsPictureInPicture` ve `resizeableActivity` açık, nöbet servisi
`specialUse` türüyle tanımlı, izin yerinde, `onUserLeaveHint` /
`onPictureInPictureModeChanged` / `enterPictureInPictureMode` /
`setAutoEnterEnabled` derlenmiş dex içinde.

## Siteyi geçici olarak kapatma, ziyaret günlüğü ve uzaktan yenileme

Üç ayrı iş, hepsi Yönetim ekranından (Ayarlar → Yönetim → **Site durumu**).

### 1) Siteyi kapatmak ve açmak

Durum tek bir düğümde: `sistem/bakim`. Anahtarı çevirdiğin anda, açık olan
**her sekmede** perde iniyor; geri çevirdiğinde kalkıyor. Altındaki sayfa yok
edilmiyor, o yüzden site yeniden açıldığında kimsenin sayfayı yenilemesi
gerekmiyor — kaldığı yerden devam ediyor.

Kapalıyken görünecek yazıyı sen belirliyorsun (160 karaktere kadar); boş
bırakırsan varsayılan metin çıkıyor. Yazıyı değiştirmek sitenin açık/kapalı
durumunu **değiştirmiyor** — o yüzden kapalıyken metni serbestçe düzeltebilirsin.

Sen perdeyi görmüyorsun: yönetici muaf. Ama kapattığını unutmayasın diye
ekranın üstünde turuncu bir şerit duruyor ("Site KAPALI — yalnız sen
görüyorsun"). Muafiyet `profil/<uid>/yonetici` alanından okunuyor.

Kural bloğu okunamazsa (henüz yayımlamadıysan) site **açık** kabul ediliyor.
Bu bilerek böyle: bir kural hatası yüzünden herkesin dışarıda kalması,
kapalıyken birinin içeri girmesinden çok daha kötü.

> **Sınırını açıkça söylemek gerekiyor:** bu bir nezaket kapısı, kasa kapısı
> değil. Perde tarayıcıda çiziliyor; teknik bilgisi olan biri geliştirici
> araçlarıyla kaldırabilir. Gerçekten kilitlemek için veritabanı kurallarının
> da bakım açıkken okumayı reddetmesi gerekir — bu, uygulamanın 26 düğümünün
> hepsini etkileyen ayrı ve riskli bir adım. İstersen ayrı bir turda yaparız.

### 2) Kapalıyken linke kim girdi

Perde her indiğinde bir kayıt düşüyor: `bakimGunlugu/<ziyaretçi>/<deneme>`.
Yönetim ekranında her satır bir kişi, sağdaki sayı kaç kez denediği; altında
deneme saatleri ve cihazı yazıyor ("Chrome · Android", "Meridyen uygulaması ·
Android" gibi).

Kim olduğu şuna bağlı:

- **Giriş yapmışsa** adı ve `uid`'si yazılıyor.
- **Giriş yapmamışsa** tarayıcısına özel, kalıcı bir kimlik üretiliyor
  (`z_...`). Aynı kişi ikinci kez denediğinde aynı satırda sayılıyor.
  Tarayıcı verilerini silerse yeni bir kimlik alır; site verilerini tümden
  engelliyorsa her deneme ayrı görünür.

**IP adresi yok.** Tarayıcı kendi IP'sini göremiyor; onu ancak bir sunucu
kaydedebilir. Bunu uydurmak yerine olmadığını söylüyorum.

Aynı sayfa açılışında bir kez yazılıyor. Sekme uzun süre (5 dk) arkada kalıp
geri geldiyse yeni bir deneme sayılıyor — kullanıcının bakış açısıyla gerçekten
yeniden denemiş oluyor. Kayıt yazma izni yalnız **bakım açıkken** var; site
açıkken o düğüme kimse yazamıyor. Kayıtlar oluşturulabiliyor ama
değiştirilemiyor ve silinemiyor; yalnız yönetici okuyup temizleyebiliyor.

### 3) İstediğin kişinin sayfasını yenilemek

Yönetim → Kullanıcılar listesinde her satırın sağında bir yenileme düğmesi var.
Bastığında `cihazKomut/<uid>` altına bir komut düşüyor; o kişinin açık olan
sayfası komutu görüp kendini yeniliyor. "Herkesin sayfasını yenile" düğmesi de
aynı işi her kullanıcı için ayrı ayrı yapıyor.

> Neden herkese tek düğümden komut göndermiyoruz: komutu ilk gören siler ve
> diğerleri hiç görmez. Her kullanıcının kendi kutusu olması şart.

Sonsuz yenilenen bir sayfa uygulamayı tamamen kullanılmaz yapacağı için
**üç ayrı emniyet** var:

1. Komut işlenir işlenmez siliniyor.
2. İşlenen komut anahtarları tarayıcıda tutuluyor — silme başarısız olsa bile
   aynı komut ikinci kez tetiklenmiyor.
3. Bir oturumda en fazla 3 yenileme; fazlası sayılıp durduruluyor ve kullanıcıya
   söyleniyor.

Yazma iznini yalnız yönetici alıyor; kullanıcı kendi kutusunu okuyup işlediği
komutu silebiliyor, başkasınınkine dokunamıyor.

### Kural kopyası artık kendiliğinden denetleniyor

`index.html`'in başındaki yorum bloğu kuralların kopyala-yapıştır kopyasını
taşıyor ve dosyanın kendisi bunun neden tehlikeli olduğunu yazıyor: ikisi
saparsa biri oradaki **eski ve gevşek** kuralları konsola yapıştırıp daha önce
kapatılmış bir açığı kendi eliyle yeniden açabilir.

Uyarı yazmak yetmiyor — unutmak bedava. `scripts/test_kurallar_ayni.py` artık
yorumdaki metni JSON olarak okuyup `database.rules.json` ile anlam düzeyinde
karşılaştırıyor (girinti ve anahtar sırası önemsiz) ve saptıklarında derlemeyi
kırıyor. İş akışında koşuyor; kasıtlı bir sapmayla denenip gerçekten yakaladığı
doğrulandı.

### Doğrulama

35 senaryo geçti: perde açılıp kapanması, yöneticinin muafiyeti ve şeridi,
kural hatasında açık kalma, günlüğe yazma ve tekrar yazmama, misafir kimliğinin
kalıcılığı, yenileme komutunun bir kez çalışması, aynı komutun tekrarlanmaması,
oturum başına 3 yenileme sınırı ve cihaz özetinin okunur çıkması. APK yeniden
derlendi, yeni kodun içinde olduğu doğrulandı.

### Senin yapman gereken

`database.rules.json`'ı Firebase konsoluna yeniden yapıştır — **üç yeni düğüm**
var (`sistem`, `bakimGunlugu`, `cihazKomut`) ve bunlar olmadan ne kapatma ne
günlük ne de yenileme çalışır. Ayrıca `profil/<uid>/yonetici` alanının senin
hesabında `true` olması gerekiyor (konsoldan elle; uygulamadan yönetici
yapılamıyor).

## Bildirimler sağlamlaştırıldı

"Bildirim gelmiyor" tek bir arıza değil — birbirine hiç benzemeyen birkaç ayrı
arızanın hepsi dışarıdan aynı görünüyor. Bu parti hem en büyük boşluğu
kapatıyor hem de kalanları **söyleyebilir** hâle getiriyor.

### 1) Uygulama kapalıyken bildirim: artık sunucunun ne gönderdiğine bağlı değil

Asıl boşluk buydu. Capacitor'un push eklentisi gelen mesajı yalnızca
JavaScript'e **iletiyor**, kendisi hiçbir bildirim çizmiyor
(`PushNotificationsPlugin.sendRemoteMessage`). Uygulama kapalıyken çalışan bir
WebView olmadığı için mesaj `lastMessage` alanında bekletiliyor ve kullanıcı
hiçbir şey görmüyordu. Yani bildirim yalnızca sunucu yükünün içine bir
`notification` bloğu koyduğunda çıkıyordu — onu da FCM'in kendi SDK'sı
çiziyordu. Sunucu yalnız `data` gönderdiğinde bildirim **sessizce**
kayboluyordu.

Artık kendi FCM servisimiz var (`MeridyenMesajServisi`). Capacitor'unkini
miras alıyor — JS'e iletim ve belirteç yenileme aynen sürüyor — ama üstüne,
uygulama önde değilse bildirimi kendisi çiziyor. Alan adlarında hem Türkçe hem
İngilizce karşılıklar kabul ediliyor (`baslik`/`title`, `metin`/`body`...), o
yüzden **sunucu tarafında hiçbir değişiklik gerekmiyor**.

Manifestte Capacitor'un servisi kaldırılıyor (`tools:node="remove"`). Aynı
intent-filter'a sahip iki servis kalırsa FCM teslimi belirsiz bir sırayla
birine gider; tek servis bırakmak bunu kesinleştiriyor. APK açılıp doğrulandı:
`MessagingService` girişi 1 tane ve o bizimki.

Küçük ama gerekli bir yan iş: kendi servisimiz uygulama modülünde derleniyor,
`firebase-messaging`'i ise push eklentisi `implementation` olarak alıyor —
Gradle bunu **aktarmıyor**, derleme `cannot find symbol: RemoteMessage` diye
kırılıyordu. `scripts/patch_gradle.py` bağımlılığı uygulama modülüne ekliyor;
sürümü eklentinin kendi `build.gradle`'ından okuyor ki sınıf yolunda iki farklı
firebase-messaging çakışmasın.

### 2) Aynı mesaj için iki bildirim çıkmıyor

Bildirim iki ayrı yerden çıkabiliyor: uygulama açıkken web tarafı
(`new Notification`), kapalıyken native servis. İkisi aynı etiket için aynı
sayısal id üretmezse Android bunları ayrı bildirim sayar ve aynı mesaj iki kez
görünür.

İki ayrı dilde elle yazılmış iki karma fonksiyonu olduğu için bu sessizce
ayrışmaya çok açık. `scripts/test_bildirim_id.py` ikisini de **gerçek kaynak
dosyalardan çıkarıp** çalıştırıyor ve karşılaştırıyor — Türkçe harfler, emoji
(vekil çiftler), boş etiket ve çok uzun etiket dahil. İş akışında da koşuyor.

> Sınamayı ilk yazdığımda Türkçe harfli etikette fark çıktı. Sebep üründe
> değildi: bu ortamda JVM komut satırı argümanlarını ASCII olarak çözüyor
> (`sun.jnu.encoding=ANSI_X3.4-1968`) ve harfleri bozuyordu. Girdi artık kod
> birimi listesi olarak veriliyor; 11/11 eşit.

### 3) Bildirime dokununca doğru sohbet açılıyor

Uygulama açıkken bunu `sistemBildirimi` kendi `onclick`'inde yapıyordu — ama
kapalıyken gelen bildirime dokunulduğunda uygulama sıfırdan açılıyor ve o
`onclick` artık yok. Hedef bilgisi şimdi bildirimin niyetinin (intent) içinde
taşınıyor.

İki ince nokta: her bildirimin `PendingIntent`'i kendi id'siyle üretiliyor
(hepsine 0 verilseydi `FLAG_UPDATE_CURRENT` yüzünden açık olan tüm
bildirimlerin hedefi sonuncusununkiyle değişir, her biri yanlış sohbeti
açardı); ve soğuk açılışta köprü henüz yüklenmemiş olabildiği için native taraf
hedefi saklıyor, web tarafı hazır olunca bir kez soruyor. Açılış her durumda
`panelGirisTalebi` üzerinden geçiyor — kilit atlanmıyor.

### 4) Mesajlar için ayrı, yüksek önemli kanal

Android'de önem bildirim başına değil **kanal** başına. Gönderim ilerlemesi
bilerek sessiz ve düşük önemli; mesaj bildirimi aynı kanalda kalsaydı o da
sessiz olurdu. Artık ayrı bir `meridyen_mesaj` kanalı var: yüksek önem, ses ve
titreşim, ekranın üstünde belirme. FCM'in kendi çizdiği bildirimler de
manifestteki `default_notification_channel_id` sayesinde aynı kanala düşüyor.

Kilit ekranı görünürlüğüne bilerek dokunulmadı: sabitleseydik uygulamanın kendi
"bildirimde mesajı göster" tercihini ezerdik.

### 5) Belirteç artık sessizce düşmüyor

Belirteç ile oturum iki ayrı zamanda hazır oluyor ve **sırası garanti değil**.
Eski kod yalnız "belirteç geldi" anında yazıyordu: belirteç oturumdan önce
gelirse sessizce düşüyor ve o cihaza hiçbir push ulaşmıyordu. Artık ikisi de
saklanıp ikisi birden hazır olduğunda yazılıyor.

Yazma başarısız olursa (kurallar yayımlanmamış, ya da o an ağ yok) geri
çekilerek en fazla beş kez yeniden deneniyor — yazılamazsa sunucu o cihaza hiç
gönderemez, yani sessizce vazgeçmek bildirimleri tümden kapatmak demek. Belirteç
yenilendiğinde (`onNewToken`) de yenisi yazılıyor; eski belirteç ölü olduğu için
bu yapılmazsa cihaz bir gün sessizce erişilemez oluyor.

### 6) İzin ilk açılışta bir kez isteniyor

Android 13'ten beri bildirim ayrı bir çalışma-zamanı izni. Kullanıcı Ayarlar'a
girip "İzin ver"e basana kadar tek bir bildirim bile çıkmıyor — ve çıkmadığı
için kimse Ayarlar'a bakmayı akıl etmiyor. Artık ilk açılışta bir kez soruluyor
(yalnız bir kez; reddedildiyse her açılışta rahatsız edilmiyor). Kullanıcı
sistem ayarlarından izni değiştirip geri dönerse de durum tazeleniyor.

### 7) Ayarlar artık *hangi* arızanın olduğunu söylüyor

Ayarlar → Bildirimler altında yeni bir **Bildirim tanısı** satırı var. Her
sebebi ayrı ayrı okuyup tek bir cümleye çeviriyor:

- köprü yüklenmemiş
- izin verilmemiş / engellenmiş
- uygulamanın bildirimleri sistemden kapatılmış
- **"Mesajlar" kanalı kapatılmış** — izin açık görünür ama tek bildirim çıkmaz;
  en çok yanıltan durum bu
- kanal sessize alınmış
- belirteç alınamadı (FCM hatası aynen gösteriliyor)
- belirteç veritabanına yazılamadı (kurallar?) — uygulama kapalıyken bildirim gelmez
- pil iyileştirmesi açık — bildirim gecikebilir

Bir şey kapalıysa düğme "Ayarlar" olup sistemin bildirim ekranını açıyor; değilse
"Sına" olup **gerçek bildirim yolundan** bir sınama gönderiyor. Ayrı bir sınama
kodu yazsaydık gerçek yolu değil kendisini sınamış olurduk.

Web'de de çalışıyor (izin ve tarayıcı desteği kısmı); native ayrıntılar yalnız
APK'da doldurulur.

### Doğrulama

- `scripts/test_bildirim_id.py` — native ↔ web bildirim id'leri, 11/11 eşit,
  hepsi ilerleme bildiriminin bandının dışında.
- Köprü sınamaları: 15 + 12 + 15 + 16 (yeni: belirteç sırası, yeniden deneme,
  belirteç yenileme, bildirime dokunma, soğuk açılış, tanı/sınama API'si).
- Tanı karar tablosu: 15 senaryo, hepsi doğru cümleyi üretiyor.
- APK açıldı: FCM servisi tek ve bizimki, varsayılan kanal `meridyen_mesaj`,
  `MeridyenBildirimler`/`MeridyenMesajServisi` derlenmiş dex içinde.
- CI sırasının aynısıyla sıfırdan temiz derleme: `BUILD SUCCESSFUL`.

### Sunucu tarafı: şart değil, ama önerilir

Uygulama artık iki yükü de kaldırıyor, o yüzden **acele bir değişiklik
gerekmiyor**. Yine de en temizi sunucunun yalnız `data` göndermesi:

```json
{
  "token": "<cihazlar/<uid> altındaki belirteç>",
  "android": { "priority": "high" },
  "data": {
    "baslik": "Ayşe",
    "metin": "Yarın uğrayabilir misin?",
    "gonderen": "<gönderenin uid'si>",
    "tur": "mesaj"
  }
}
```

Neden: `notification` bloğu gönderildiğinde bildirimi FCM'in kendi SDK'sı
çiziyor ve o bildirim bizim id mantığımızın dışında kalıyor — uygulama arka
planda ama **açıkken** aynı mesaj için hem FCM'in hem web tarafının bildirimi
çıkabiliyor. Yalnız `data` gönderilirse her bildirimi biz çiziyoruz: tek kanal,
tek id, doğru sohbete dokunma. `"priority": "high"` da cihaz uykudayken teslimi
geciktirmiyor.

`gonderen` alanı zaten `bildirimKuyrugu` kaydında var; sunucunun tek yapması
gereken onu `data` içine geçirmek. Veritabanı kurallarındaki `cihazlar` düğümü
(bkz. `database.rules.json`) hâlâ yayımlanmış olmalı — o olmadan belirteç
yazılamaz ve tanı satırı bunu açıkça söyler.

## Uygulama formuna doğru — 1. adım

Site zaten bir APK'nın içinde çalışıyordu ama hâlâ "web sayfası" gibi
duruyordu. İlk parti, en çok göze batan iki farkı kapatıyor. İkisi de görsel
ve düşük riskli: yerleşime, gezinmeye ya da klavye davranışına dokunulmadı.

### Zaten hazır olanlar (değiştirmeye gerek yoktu)

İncelemede iki şey beklediğimden iyi çıktı, bu yüzden bunlara dokunmadım:

- **Donanım geri tuşu çalışıyor.** Uygulamada `pushState`/`popstate` üzerine
  kurulu gerçek bir gezinme yığını var (`gezYigin`); geri tuşu katmanları
  sırayla kapatıyor, uygulamadan düşmüyor.
- **Güvenli alanlar (çentik/durum çubuğu) hesaba katılmış.** `viewport-fit=cover`
  ve 49 ayrı yerde `env(safe-area-inset-*)` kullanılıyor.

### 1) Markalı açılış ekranı

Capacitor'un şablonu jenerik bir `splash.png` ile geliyor; uygulama her
açılışta onu gösteriyordu. Artık zemini uygulamanın vitrin rengi (`#e7e4dd`)
olan ve ortasında Meridyen'in kendi "M" işareti bulunan bir açılış ekranı var.

Zemin rengi bilerek `index.html`'in ilk boyadığı renkle aynı: açılış
ekranından uygulamaya geçerken göze çarpan bir renk sıçraması olmuyor.
`capacitor.config.json`'daki `backgroundColor` da aynı değere hizalandı.

**Burada sessiz bir tuzak vardı:** şablon `splash.png`'yi yalnız `drawable/`
altına değil, yönelim ve yoğunluğa göre **on ayrı klasöre** daha koyuyor
(`drawable-port-xxhdpi` gibi). Android daha özel olanı seçtiği için, yalnız
`drawable/splash.png`'yi silmek markalı ekranı neredeyse hiçbir cihazda
göstermezdi. APK'yı açıp baktığımda on jenerik dosyanın da durduğunu gördüm;
hepsi temizlendi ve iş akışına "hiç `splash.png` kalmasın" doğrulaması eklendi.

### 2) Durum çubuğu ekrana uyuyor

Meridyen'in iki yüzü var: vitrin **açık** zeminli, sohbet paneli **koyu**.
Sistem çubuğunun simgeleri sabit kalınca birinde okunmaz oluyordu — açık
zeminde beyaz saat/pil, koyu zeminde siyah.

Artık ekranla birlikte değişiyor. Hangi yüzde olduğumuzu web tarafı zaten
biliyor (`<body>` panel açıkken `panel-acik` sınıfını taşıyor); köprü o sınıfı
izleyip native tarafa bildiriyor, native taraf da
`WindowInsetsControllerCompat` ile simge rengini ayarlıyor. Gereksiz köprü
çağrısı yok: yalnız değer değiştiğinde gidiyor.

Çubukların **zeminine** bilerek dokunulmadı: Android 15'te (targetSdk 35)
`statusBarColor` yok sayılıyor, ekran zaten kenardan kenara çiziliyor ve
arkasını uygulamanın kendi içeriği dolduruyor.

### Doğrulama

APK açılıp içine bakıldı: jenerik `splash.png`'lerin hiçbiri kalmamış, markalı
`splash.xml` ve logo yerinde, açılış zemin rengi `#ffe7e4dd` olarak gömülü,
`durumCubugu` metodu ve `setAppearanceLightStatusBars` çağrısı derlenmiş dex
içinde. Köprü testleri de geçti.

### Sırada ne var

Riskli oldukları için bilerek bu partiye alınmadı; istersen tek tek ele alırız:

- **Geri tuşuyla çıkışta onay** ("çıkmak için tekrar bas") — geri tuşunu
  yakalamak gerekiyor, mevcut çalışan gezinmeyi bozma riski var.
- **Klavye davranışı** (`windowSoftInputMode`) — uygulamanın kendi görsel
  viewport mantığı var, native ayarla çakışabilir.
- **Dokunsal geri bildirim (haptics)** ve **paylaşım sayfasına bağlanma**
  (dışarıdan Meridyen'e dosya paylaşma).

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
