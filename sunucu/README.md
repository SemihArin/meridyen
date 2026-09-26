# Meridyen bildirim sunucusu

Uygulama **tamamen kapalıyken** (görev listesinden atılmış, hiç açılmamış ya da
telefon uykuda) gelen mesaj ve çağrılar için bildirim üretebilecek tek yol
Google'ın push altyapısıdır: sayfada çalışan hiçbir kod kalmaz. Bu sunucu o
boşluğu kapatıyor.

**Ne yapıyor:** veritabanındaki `bildirimKuyrugu` düğümünü dinliyor. Biri mesaj
gönderdiğinde ya da aradığında istemci oraya bir kayıt bırakıyor; sunucu o
kaydı anında yakalayıp hedefin **bütün cihazlarına** (Android APK + web
tarayıcısı) FCM push'u gönderiyor, sonra kaydı siliyor.

**Ne yapmıyor:** uygulama açıkken bildirimlere karışmıyor. Android tarafı
uygulamayı önde bulursa push'u yok sayıyor, web tarafında da service worker
yalnız sayfa kapalı/arka plandayken çalışıyor. Yani aynı mesaj iki kez
görünmüyor.

---

## Kurulum — üç adım

### 1. Servis hesabı anahtarı al

1. [Firebase konsolu](https://console.firebase.google.com/) → **meridyen-830fb** projesi
2. Sol üstte dişli → **Proje ayarları**
3. **Servis hesapları** sekmesi
4. **Yeni özel anahtar oluştur** → **Anahtar oluştur** → bir `.json` dosyası iniyor

> Bu dosya projenin tamamına yetki verir. Kimseyle paylaşma, depoya koyma.
> (`.gitignore` zaten engelliyor.)

### 2. Bağımlılıkları kur

```bash
cd sunucu
npm install
```

### 3. Çalıştır

```bash
# Anahtarı dosya olarak verirsen:
GOOGLE_APPLICATION_CREDENTIALS=/tam/yol/anahtar.json npm start

# ya da içeriğini tek satır olarak (barındırma sağlayıcıları böyle istiyor):
MERIDYEN_SERVIS_HESABI='{"type":"service_account", ...}' npm start
```

Ekranda şunu görmelisin:

```
[2026-01-01 10:00:00] Meridyen bildirim sunucusu başladı. Kuyruk: bildirimKuyrugu
[2026-01-01 10:00:01] veritabanına bağlandı
```

---

## Çalıştığını doğrula

Gerçek bir mesaj beklemeden dene:

```bash
# Hedefin kayıtlı cihazlarını gör
node dene.js --cihazlar <kullanıcıUid>

# Deneme bildirimi gönder
node dene.js <kullanıcıUid> "merhaba"
```

Uid'yi uygulamada Ayarlar > hesap bölümünden ya da Firebase konsolu >
Authentication listesinden alabilirsin.

Sunucu ayrıca bir **sağlık ucu** açıyor: `http://localhost:8080` adresine
bakınca çalışma süresi ve sayaçlar JSON olarak görünüyor.

---

## Nerede çalıştırmalı

Sunucunun **sürekli açık** olması gerekiyor; kapalıyken kuyruk birikir, açılınca
(30 dakikadan yeni olanlar) teslim edilir.

| Yer | Nasıl |
|---|---|
| Kendi bilgisayarın | `npm start` — yalnız bilgisayar açıkken çalışır, denemek için iyi |
| Ücretsiz bulut (Render, Railway, Fly.io) | Depoyu bağla, kök dizin `sunucu`, başlangıç komutu `npm start`, ortam değişkeni `MERIDYEN_SERVIS_HESABI` |
| Kendi sunucun (VPS) | `pm2 start index.js --name meridyen-bildirim` ya da systemd servisi |

Sağlayıcı bir port bekliyorsa `PORT` değişkenini kendisi veriyor; sağlık ucu
onu kullanıyor, ek ayar gerekmiyor.

### Sürekli çalıştıramıyorsan

`MERIDYEN_TEK_SEFER=1` ile başlatırsan kuyruğu boşaltıp çıkar. Zamanlanmış bir
görevle (cron) örneğin dakikada bir çağırabilirsin — anlık olmaz ama hiç
yoktan iyidir:

```
* * * * * cd /yol/sunucu && MERIDYEN_TEK_SEFER=1 GOOGLE_APPLICATION_CREDENTIALS=... node index.js
```

---

## Web bildirimleri için ek şart

Android tarafı APK'nın içinde hazır. **Web** tarafında iki şey gerekiyor:

1. `www/firebase-messaging-sw.js` dosyası sitenin **kök dizininde** yayında
   olmalı (index.html ile aynı klasör). Yoksa tarayıcı push alamaz — hata da
   vermez, sessizce çalışmaz.
2. Site **HTTPS** olmalı (web push'un şartı).

Kullanıcı tarafında: siteyi açıp bildirim iznini vermiş olması gerekiyor. İzin
verildiğinde cihaz `cihazlar/<uid>` altına kendi belirtecini yazıyor; sunucu
oradan okuyor. `node dene.js --cihazlar <uid>` ile kontrol edebilirsin.

---

## Gizlilik

Bildirimde mesaj metninin görünüp görünmeyeceği **cihaz başına** ayarlanıyor
(uygulamada Ayarlar > bildirimde içerik). Kapalıysa metin sunucudan **hiç
çıkmıyor**: o cihaza yalnız "Yeni bir mesajın var." gidiyor. Telefonunda kapalı,
masaüstünde açık olabilir; sunucu her cihaza kendi ayarına göre gönderiyor.

Çağrılarda arayanın adı gönderiliyor (kimin aradığını bilmeden çağrıyı
yanıtlamak anlamsız), metin yine ayara tabi.

---

## Bakım

- **Ölü belirteçler** kendiliğinden temizleniyor: uygulama silinmiş bir cihaza
  gönderim "kayıtlı değil" hatası verince o kayıt `cihazlar` altından düşüyor.
- **Eski kayıtlar** gönderilmiyor: sunucu uzun süre kapalı kaldıysa 30
  dakikadan eski bildirimler sessizce siliniyor (gece yarısı dünkü mesajın
  bildirimi gelmesin). `MERIDYEN_EN_ESKI_DK` ile değiştirilebilir.
- **Geçici hatalarda** artan beklemeyle 5 kez yeniden deneniyor, sonra kayıt
  düşürülüyor ve günlüğe yazılıyor.

## Sınama

```bash
npm test
```

Ağ ve gerçek anahtar gerektirmiyor: yük biçimi, gizlilik kuralı, çağrı ayrımı,
ölü belirteç temizliği, eski/bozuk kayıt eleme ve kuyruk silme davranışları
sahte bir Firebase Admin SDK'sı üstünde **gerçek `index.js`** çalıştırılarak
doğrulanıyor.
