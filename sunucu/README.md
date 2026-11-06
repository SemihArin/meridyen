# Meridyen bildirim sunucusu (Python)

Uygulama **tamamen kapalıyken** (görev listesinden atılmış, hiç açılmamış ya da
telefon uykuda) gelen mesaj ve çağrılar için bildirim üretebilecek tek yol
Google'ın push altyapısıdır: sayfada çalışan hiçbir kod kalmaz. Bu sunucu o
boşluğu kapatıyor. 7/24 açık duran bir makinede (Raspberry Pi, eski bir
bilgisayar, VPS) çalışmak üzere yazıldı.

**Ne yapıyor:** veritabanındaki `bildirimKuyrugu` düğümünü izliyor. Biri mesaj
gönderdiğinde ya da aradığında istemci oraya bir kayıt bırakıyor; sunucu kaydı
yakalayıp hedefin **bütün cihazlarına** (Android APK + web tarayıcısı) FCM
push'u gönderiyor, sonra kaydı siliyor.

> Eski Node.js sunucusu (`index.js`) kaldırıldı. Bir yerde hâlâ çalışıyorsa
> **kapat**: kayıt sahiplenmeyi bilmiyor, ikisi birlikte çalışırsa alıcılar çift
> bildirim alır. Python sunucusu bunu fark edip günlüğe ve uygulamanın
> tanısına yazıyor.

---

## Kurulum

Gereken: Python 3.9+ ve Firebase servis hesabı anahtarı.

### 1. Servis hesabı anahtarı al

Firebase konsolu → ⚙ Proje ayarları → **Servis hesapları** → *Yeni özel anahtar
oluştur*. İnen JSON dosyasını `sunucu/servis-hesabi.json` olarak kaydet.

> Bu dosya projenin tamamına yetki verir. **Depoya girmez** (`.gitignore`'da),
> kimseyle paylaşma.

### 2. Bağımlılıkları kur

```bash
cd sunucu
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Yalnız `requests` ve `google-auth` kuruluyor. `firebase-admin` bilerek yok:
grpc gibi ağır bağımlılıklar getiriyor, eski Raspberry Pi'de ya da Termux'ta
derlenmesi saatler sürüyor veya hiç olmuyor.

### 3. Ayarları yaz ve dene

```bash
cp ornek.env .env          # içindeki anahtar dosyası yolunu düzelt
set -a; . ./.env; set +a
venv/bin/python dene.py --cihazlar <kullanıcıUid>     # kayıtlı cihazlar
venv/bin/python dene.py <kullanıcıUid> "merhaba"      # deneme bildirimi
venv/bin/python sunucu.py                             # sunucuyu başlat (Ctrl+C ile dur)
```

Uid'yi Firebase konsolu → Authentication listesinden alabilirsin.

### 4. Kalıcı hizmet yap (systemd)

```bash
# meridyen-bildirim.service içindeki User ve yolları kendine göre düzelt
sudo cp meridyen-bildirim.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now meridyen-bildirim
journalctl -u meridyen-bildirim -f          # günlüğü izle
```

Makine yeniden başlayınca sunucu kendiliğinden açılır. Çökerse ya da takılırsa
5 sn sonra yeniden başlar.

---

## Çalıştığını doğrula

- **Uygulamada:** Ayarlar → Bildirimler tanısı "bildirim sunucusu: çalışıyor,
  son nabız 30 sn önce" demeli. Sunucu her dakika veritabanına nabız yazıyor;
  durursa birkaç dakika içinde "DURMUŞ" görünür.
- **Sunucuda:** `curl localhost:8080` çalışma süresini, sayaçları, akışın bağlı
  olup olmadığını ve varsa kurulum hatasını gösterir (sorun varsa HTTP 503).
- `venv/bin/python dene.py --durum` nabzı veritabanından okur.

---

## Sağlamlık: nelere karşı korunuyor

| Durum | Ne oluyor |
|---|---|
| İnternet kesildi / modem yeniden başladı | Her istekte zaman aşımı var. Olay akışı koparsa artan beklemeyle yeniden bağlanıyor; bağlanınca kuyruğu baştan okuyor, arada kalan kayıt kaybolmuyor. Akıştan bağımsız olarak kuyruk 30 sn'de bir ayrıca taranıyor. |
| Bağlantı "yarı açık" kaldı (veri gelmiyor ama kopmadı da) | Veritabanı 30 sn'de bir canlılık olayı yolluyor; 90 sn hiçbir şey gelmezse bağlantı ölü sayılıp yeniden kuruluyor. |
| Sunucu bir yerde takıldı | Bekçi iş parçacığı ana döngü 3 dk ilerlemezse süreci bitiriyor, systemd yeniden başlatıyor. |
| Sunucu gönderirken çöktü (elektrik gitti) | Kayıt silinmeden önce gönderiliyor; yeniden başlayınca kayıt tekrar işleniyor. Telefon aynı mesajı anahtarından (`mid`) tanıyıp **ikinci kez göstermiyor**. |
| Yanlışlıkla iki sunucu çalışıyor | Her kayıt göndermeden önce bir **kira** ile sahipleniliyor (koşullu yazma). İki sunucu aynı kaydı gördüğünde yalnız biri gönderiyor; öbürü yedek gibi bekliyor. |
| FCM geçici hata verdi | Yalnız **başarısız olan cihaza** artan beklemeyle (2, 4, 8, 16 sn) en çok 5 kez yeniden deneniyor. Başarılı cihazlara ikinci kez gitmiyor. Kalan cihazlar kayda yazılıyor: sunucu bu arada çökerse kaldığı yerden devam ediyor. |
| Sunucu saatlerce kapalı kaldı | 30 dk'dan eski mesajlar, 60 sn'den eski **çağrılar** gönderilmeden atılıyor: biten bir aramanın zili çalmıyor. Yaş, bu makinenin saatiyle değil ölçülmüş **sunucu saatiyle** hesaplanıyor. |
| Telefonda hesap değiştirildi | Aynı belirteç yeni hesapta daha yeni kayıtlıysa eski hesabın mesajları o telefona **gönderilmiyor**, eski kayıt siliniyor (eskiden telefon iki hesabın bildirimini birden alıyordu). |
| Aynı telefon iki kez kayıtlı | Aynı belirtece tek push. |
| Servis hesabı yanlış projenin | Cihaz kayıtlarına **dokunulmuyor** (silseydik tek yanlış anahtar bütün kayıtları uçururdu); günlüğe büyük uyarı, uygulamada "KURULUM HATASI". |
| Bozuk/kötü niyetli istemci kuyruğu dolduruyor | Gönderen başına hız sınırı: 30'luk patlama, sonra saniyede bir. |

---

## Çift bildirime karşı uçtan uca

Bir mesajın bildirimi iki yoldan gelebiliyor: alıcının **kendi uygulaması**
(arka planda canlıyken veritabanı dinleyicisi) ve bu **sunucunun push'u**.

- **APK:** iki yol da mesajın anahtarını (`mid`) taşıyor; telefon bir anahtarı
  bir kez gösteriyor (`MeridyenBildirimler`, 48 saatlik görülenler listesi).
  Sohbet açılıp bildirim silindikten sonra geç gelen bir kopya da tanınıyor.
- **Web:** iki yol aynı etiketi (`meridyen-<gönderen>`) kullanıyor; tarayıcı
  aynı etiketli bildirimi yenisiyle değiştiriyor, ikinci bir bildirim çıkmıyor.
- **Çağrı:** iki yol aynı çağrı bildirimine yazıyor ve zil bir kez çalıyor;
  uygulama kapalıyken arayan vazgeçerse çağrı bildirimi 60 sn sonra kalkıyor.

---

## Gizlilik

Bildirimde mesaj metninin görünüp görünmeyeceği **cihaz başına** ayarlanıyor
(uygulamada Ayarlar > bildirimde içerik). Kapalıysa metin sunucudan **hiç
çıkmıyor**: o cihaza yalnız "Yeni bir mesajın var." gidiyor. Çağrılarda arayanın
adı gönderiliyor, metin yine ayara tabi.

---

## Web bildirimleri için ek şart

1. `www/firebase-messaging-sw.js` sitenin **kök dizininde** yayında olmalı.
2. Site **HTTPS** olmalı (web push'un şartı).

---

## Zamanlanmış görevle (sürekli açık makine yoksa)

`MERIDYEN_TEK_SEFER=1` ile kuyruğu boşaltıp çıkar. Anlık olmaz; cron ile dakikada
bir çağrılabilir:

```
* * * * * cd /yol/sunucu && MERIDYEN_TEK_SEFER=1 PORT=0 MERIDYEN_SERVIS_HESABI_DOSYASI=/yol/servis-hesabi.json venv/bin/python sunucu.py
```

---

## Sınama

```bash
python3 sinama/test_mantik.py          # saf mantık, ağ yok
venv/bin/python sinama/test_uctan_uca.py   # gerçek sunucu süreçleri + veritabanı emülatörü
```

Uçtan uca sınama (Java ve firebase-tools gerekir) gerçek `sunucu.py`
süreçlerini Realtime Database emülatörüne bağlıyor; FCM'in yerinde sahte bir
HTTP sunucusu var. Ölçülenler: iki sunucu aynı anda çalışırken 40 kaydın her
birinin her cihaza **tam bir kez** gitmesi; sunucu yeniden denemenin ortasında
`kill -9` ile öldürülüp yeniden başlatılınca başarılı cihaza ikinci kez
gitmemesi; veritabanı bağlantısı kopup geri gelince yeni kaydın işlenmesi;
bayat çağrı, hesap değişimi, kurulum hatası, hız sınırı ve tek sefer kipi.
