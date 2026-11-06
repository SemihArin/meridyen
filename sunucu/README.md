# Meridyen bildirim sunucusu (Python)

Uygulama **tamamen kapalıyken** (görev listesinden atılmış, hiç açılmamış ya da
telefon uykuda) gelen mesaj ve çağrılar için bildirim üretebilecek tek yol
Google'ın push altyapısıdır: sayfada çalışan hiçbir kod kalmaz. Bu sunucu o
boşluğu kapatıyor. 7/24 açık duran bir makinede (Android'de Termux, Raspberry
Pi, eski bir bilgisayar, VPS) çalışmak üzere yazıldı. Tek bağımlılığı `requests`;
hiçbir şey derlenmiyor.

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

Gereken: Python 3.9+ (Raspberry Pi OS ve güncel Linux'larda hazır; Termux'ta
`pkg install python`) ve Firebase
servis hesabı anahtarı.

**1. Anahtarı indir.** Firebase konsolu → ⚙ Proje ayarları → **Servis hesapları**
→ *Yeni özel anahtar oluştur*. Bir JSON dosyası iner.

> Bu dosya projenin tamamına yetki verir. Kimseyle paylaşma; depoya girmez
> (`.gitignore`'da).

**2. Klasörü makineye koy ve kur.sh'ı çalıştır:**

```bash
tar xzf meridyen-bildirim-sunucusu.tar.gz
cd sunucu
./kur.sh --anahtar ~/Downloads/meridyen-830fb-xxxxxxxx.json
```

`--anahtar` vermezsen yolunu sorar. Kurulum betiği sırayla:

1. Python'u ve `venv` modülünü denetler (Debian'da eksikse `python3-venv`'i
   kurmayı önerir),
2. `venv/` oluşturup bağımlılığı kurar (yalnız `requests`; derlenen paket yok),
3. anahtarı `servis-hesabi.json` olarak yerleştirir ve `.env`'i yazar (ikisi de
   yalnız sana okunur, izin 600),
4. **bildirim göndermeden** kurulumu denetler: anahtar geçerli mi, veritabanı
   okunuyor mu, FCM gönderme izni var mı — sorun varsa nerede olduğunu söyleyip
   durur,
5. pm2'de eski Node sunucusu kayıtlıysa durdurmayı önerir,
6. sunucuyu kalıcı başlatır — Linux'ta açılışta başlayan bir **systemd
   hizmeti**, Termux'ta arka plan çalıştırıcısı + Termux:Boot (aşağıda) —
   başlatır ve çalıştığını sağlık ucundan doğrular.

Yeniden çalıştırmak güvenli: bağımlılıkları günceller, `.env`'deki ayarlarına
dokunmaz. Güncelleme için yeni dosyaları üstüne açıp `./kur.sh`'ı yeniden
çalıştırman yeterli.

| Komut | Ne yapar |
|---|---|
| `./kur.sh --hizmet-yok` | hizmet kurmadan yalnız ortamı hazırlar |
| `./kur.sh --hizmet-dosyasi` | doldurulmuş hizmet tanımını gösterir |
| `./kur.sh --kaldir` | hizmeti durdurup kaldırır (ayarlar ve venv kalır) |
| `journalctl -u meridyen-bildirim -f` | sunucunun günlüğü |
| `sudo systemctl restart meridyen-bildirim` | yeniden başlat |
| `venv/bin/python dene.py --kontrol` | kurulumu yeniden denetle |
| `venv/bin/python dene.py <uid> "merhaba"` | deneme bildirimi gönder |
| `venv/bin/python dene.py --cihazlar <uid>` | kullanıcının kayıtlı cihazları |

Uid'yi Firebase konsolu → Authentication listesinden alabilirsin.

### Ayarlar: `.env`

Sunucu ve `dene.py`, yanlarındaki `.env` dosyasını **kendileri okuyor** (paket
gerekmiyor, `set -a` gerekmiyor). Ortamda zaten tanımlı bir değişken dosyadakini
ezer. Kullanılabilen ayarlar `ornek.env`'de. Elle çalıştırmak için:

```bash
venv/bin/python sunucu.py
```

systemd olmayan (ve Termux olmayan) bir makinede kur.sh hizmet adımını atlayıp
elle başlatma komutunu yazar.

### Android telefonda (Termux)

1. Termux'u **F-Droid**'den kur (Play Store sürümü eski ve güncellenmiyor).
   Telefonun açılınca sunucuyu kendiliğinden başlatması için F-Droid'den
   **Termux:Boot**'u da kur ve bir kez aç.
2. Termux'ta:
   ```bash
   pkg install python
   termux-setup-storage          # telefonun İndirilenler klasörüne erişim
   tar xzf ~/storage/downloads/meridyen-bildirim-sunucusu.tar.gz -C ~
   cd ~/sunucu
   ./kur.sh --anahtar ~/storage/downloads/meridyen-830fb-xxxxxxxx.json
   ```
3. Telefonda **Ayarlar → Uygulamalar → Termux → Pil → "Kısıtlama yok"**. Bu
   yapılmazsa Android ekran kapanınca Termux'u uyutur ya da öldürür ve
   bildirimler kesilir.

kur.sh Termux'ta systemd yerine `calistir.sh`'ı arka planda başlatıyor:
sunucuyu çalıştırıyor, çökerse 5 sn sonra yeniden başlatıyor ve uyanık tutma
kilidini (`termux-wake-lock`) alıyor. Telefon açılınca Termux:Boot aynı
çalıştırıcıyı başlatıyor. Günlük `sunucu.log`'da (`tail -f sunucu.log`).

> Android 12+ bazı telefonlarda arka plan süreçlerini yine de öldürebiliyor
> ("[Process completed (signal 9)]"). Görürsen Termux'u bildirimdeki
> "Acquire wakelock" ile kilitle; sürerse bilgisayardan bir kez
> `adb shell "device_config put activity_manager max_phantom_processes 2147483647"`.

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
| Sunucu bir yerde takıldı | Bekçi iş parçacığı ana döngü 3 dk ilerlemezse süreci bitiriyor; systemd (Termux'ta `calistir.sh`) yeniden başlatıyor. |
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
venv/bin/python sinama/test_erisim.py  # saf Python RSA/JWT imzası OpenSSL'e karşı
python3 sinama/test_kur.py             # kur.sh (Linux ve Termux yolu) geçici kopyada
venv/bin/python sinama/test_uctan_uca.py   # gerçek sunucu süreçleri + veritabanı emülatörü
```

Uçtan uca sınama (Java ve firebase-tools gerekir) gerçek `sunucu.py`
süreçlerini Realtime Database emülatörüne bağlıyor; FCM'in yerinde sahte bir
HTTP sunucusu var. Ölçülenler: iki sunucu aynı anda çalışırken 40 kaydın her
birinin her cihaza **tam bir kez** gitmesi; sunucu yeniden denemenin ortasında
`kill -9` ile öldürülüp yeniden başlatılınca başarılı cihaza ikinci kez
gitmemesi; veritabanı bağlantısı kopup geri gelince yeni kaydın işlenmesi;
bayat çağrı, hesap değişimi, kurulum hatası, hız sınırı ve tek sefer kipi.
