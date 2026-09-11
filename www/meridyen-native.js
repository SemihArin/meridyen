/* Meridyen — Android sarmalayıcısı için bildirim köprüsü.
 *
 * NEDEN VAR: Android'in WebView'ı, web'in Notification API'sini hiç sunmuyor
 * (Push API'yi de). Yani APK içinde `window.Notification` tanımsız kalıyor ve
 * index.html'deki bildirim kodu — kendini doğru şekilde koruduğu için —
 * sessizce devre dışı kalıyor: Ayarlar'da "Tarayıcın desteklemiyor" yazıyor,
 * hiçbir bildirim çıkmıyor.
 *
 * NE YAPAR: Eksik olan API'yi, Capacitor'un YEREL bildirim eklentisiyle
 * destekleyerek yerine koyar. index.html'in tek satırı değişmiyor; o hâlâ
 * `new Notification(...)` çağırıyor, altta Android'in kendi bildirim sistemi
 * çalışıyor. Böylece uygulama arka plandayken (açık ama önde değilken)
 * bildirimler gerçekten görünüyor.
 *
 * SINIRI: Bu YEREL bildirim. Uygulama tamamen kapatıldığında çalışan bir kod
 * kalmadığı için bildirim üretilemez — onun için sunucudan gelen native FCM
 * push'u gerekiyor (google-services.json ile). Ayrıntı README'de.
 *
 * Bu dosya yalnız APK içinde devreye girer: tarayıcıda gerçek Notification
 * API'si bulunduğu için hiçbir şeye dokunmadan çıkar.
 */
(function () {
  'use strict';

  var cap = window.Capacitor;
  var YB = cap && cap.Plugins && cap.Plugins.LocalNotifications;

  /* KÖPRÜ İMZASI — teşhis için.
     Bu dosya bir kez APK'ya girdiği hâlde sayfaya HİÇ yüklenmedi (enjeksiyon
     betiği <script> etiketini koymamıştı) ve bildirimler sessizce kayboldu.
     Dışarıdan bakınca "tarayıcı desteklemiyor" ile ayırt edilemiyordu.
     Bu imza sayesinde uygulama artık "köprü yüklendi ama bildirimi açamadı"
     ile "köprü hiç yüklenmedi" durumlarını ayırabiliyor. */
  window.MeridyenKopru = {
    yuklendi: true,
    yerli: !!(cap && typeof cap.isNativePlatform === 'function' && cap.isNativePlatform()),
    yerelBildirim: !!YB,
    push: !!(cap && cap.Plugins && cap.Plugins.PushNotifications)
  };

  if (!window.MeridyenKopru.yerli) return;
  // Gerçek API varsa (ileride WebView desteklerse) ona karışma.
  if ('Notification' in window) { window.MeridyenKopru.gercekApi = true; return; }

  if (!YB) return;

  var izin = 'default';           // Notification.permission ile aynı sözlük
  var acikOlanlar = {};           // id -> örnek (tıklama ve close() için)

  /* Web tarafı `tag` ile "aynı etiketli bildirimi değiştir" diyor; Android'de
     bunun karşılığı aynı sayısal id. Etiketi sabit bir sayıya çeviriyoruz ki
     aynı sohbetten gelen ikinci mesaj öncekinin üstüne yazsın. */
  function etiketId(etiket) {
    var h = 0;
    var s = String(etiket == null ? Math.random() : etiket);
    for (var i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) | 0; }
    /* Üst bant (1.9 milyar ve üstü) gönderim ilerleme bildirimine ayrıldı
       (bkz. MeridyenIlerleme.java, BILDIRIM_ID = 2000000001); mesaj
       bildirimleri oraya hiç düşmesin diye burada daraltıyoruz, yoksa ikisi
       birbirinin bildirimini ezebilirdi. */
    h = Math.abs(h) % 1900000000;
    return h === 0 ? 1 : h;
  }

  function durumCevir(sonuc) {
    var d = sonuc && sonuc.display;
    if (d === 'granted') return 'granted';
    if (d === 'denied') return 'denied';
    return 'default';
  }

  /* İzin durumu çözüldüğünde, ekranda o durumu gösteren yerler zaten
     çizilmiş olabilir. index.html bu fonksiyonları global tanımlıyor;
     varsa nazikçe tazeliyoruz, yoksa hiçbir şey olmuyor. */
  function arayuzuTazele() {
    ['bildirimDurumuYaz', 'ayarBildirimDurumuCiz', 'ayarBagimlilikTazele'].forEach(function (ad) {
      try { if (typeof window[ad] === 'function') window[ad](); } catch (e) {}
    });
  }

  function Bildirim(baslik, secenekler) {
    secenekler = secenekler || {};
    this.title = baslik;
    this.body = secenekler.body || '';
    this.tag = secenekler.tag;
    this.lang = secenekler.lang;
    this.onclick = null;
    this.onclose = null;
    this.onerror = null;
    this.onshow = null;

    this._id = etiketId(secenekler.tag);
    acikOlanlar[this._id] = this;

    var self = this;
    try {
      YB.schedule({
        notifications: [{
          id: this._id,
          title: String(baslik == null ? 'Meridyen' : baslik),
          body: String(this.body),
          // Kilit ekranında da okunabilsin diye tek satıra sığmayan metinler
          // açılabilir olsun.
          largeBody: String(this.body),
          autoCancel: true
        }]
      }).then(function () {
        if (typeof self.onshow === 'function') { try { self.onshow(); } catch (e) {} }
      }).catch(function () {
        if (typeof self.onerror === 'function') { try { self.onerror(); } catch (e) {} }
      });
    } catch (e) {
      if (typeof this.onerror === 'function') { try { this.onerror(); } catch (e2) {} }
    }
  }

  Bildirim.prototype.close = function () {
    try { YB.cancel({ notifications: [{ id: this._id }] }); } catch (e) {}
    delete acikOlanlar[this._id];
    if (typeof this.onclose === 'function') { try { this.onclose(); } catch (e) {} }
  };

  Bildirim.requestPermission = function (geriCagri) {
    return YB.requestPermissions().then(function (sonuc) {
      izin = durumCevir(sonuc);
      arayuzuTazele();
      if (typeof geriCagri === 'function') { try { geriCagri(izin); } catch (e) {} }
      return izin;
    }).catch(function () {
      return izin;
    });
  };

  // `Notification.permission` senkron okunuyor; altta yatan eklenti ise async.
  // Bu yüzden son bilinen durumu tutup aşağıda bir kez tazeliyoruz.
  Object.defineProperty(Bildirim, 'permission', {
    get: function () { return izin; },
    enumerable: true
  });

  Bildirim.maxActions = 0;

  window.Notification = Bildirim;

  // Bildirime dokunulduğunda uygulamayı ilgili yere götür: index.html bunu
  // onclick içinde tarif ediyor, biz yalnız tetikliyoruz.
  try {
    YB.addListener('localNotificationActionPerformed', function (olay) {
      var id = olay && olay.notification && olay.notification.id;
      var n = acikOlanlar[id];
      if (n && typeof n.onclick === 'function') { try { n.onclick(); } catch (e) {} }
      delete acikOlanlar[id];
    });
  } catch (e) {}

  // Açılışta mevcut izni öğren (kullanıcı daha önce izin vermiş olabilir).
  try {
    YB.checkPermissions().then(function (sonuc) {
      izin = durumCevir(sonuc);
      arayuzuTazele();
    }).catch(function () {});
  } catch (e) {}
})();

/* ================= NATIVE PUSH (uygulama kapalıyken de bildirim) =================
 *
 * Yukarıdaki köprü YEREL bildirim veriyordu: uygulama çalışırken iyi, ama
 * tamamen kapatıldığında çalışan kod kalmadığı için bildirim üretemiyor.
 * Kapalıyken bildirim, ancak sunucudan gelen FCM push'u ile mümkün.
 *
 * Web tarafındaki `uzakBildirimiKur()` bunu WebView'da yapamıyor: Service
 * Worker tabanlı web push'u kullanıyor ve `firebase.messaging.isSupported()`
 * WebView'da false dönüyor. Bu yüzden belirteci (token) NATIVE tarafta alıp
 * uygulamanın zaten kullandığı `cihazlar/<uid>` düğümüne biz yazıyoruz —
 * sunucun hiçbir değişiklik olmadan bu belirtece gönderebilir.
 *
 * Uygulamanın kendi `cihazBelirteci` değişkenini de dolduruyoruz; böylece
 * "bildirimde içerik göster" tercihi değiştiğinde ve çıkış yapıldığında
 * index.html'in KENDİ mevcut kodu belirteci güncelliyor/siliyor — o mantığı
 * burada tekrar yazmıyoruz.
 */
(function () {
  'use strict';

  var cap = window.Capacitor;
  if (!cap || typeof cap.isNativePlatform !== 'function' || !cap.isNativePlatform()) return;

  var PB = cap.Plugins && cap.Plugins.PushNotifications;
  if (!PB) return;

  var kuruldu = false;      // dinleyiciler bir kez bağlansın
  var yazilanYol = null;    // çıkışta temizlik için

  /* index.html'deki ile AYNI karma: belirteç, Firebase anahtarında yasak olan
     karakterleri içerebildiği için düğüm adı olarak kullanılamıyor. Uygulama
     kendi fonksiyonunu global tanımlıyor; varsa ONU kullanıyoruz ki iki taraf
     asla farklı anahtar üretmesin. */
  function belirtecAnahtariYerel(t) {
    if (typeof window.belirtecAnahtari === 'function') {
      try { return window.belirtecAnahtari(t); } catch (e) {}
    }
    var h = 0;
    for (var i = 0; i < t.length; i++) { h = (h * 31 + t.charCodeAt(i)) | 0; }
    return 'c' + Math.abs(h).toString(36) + '_' + t.slice(-12).replace(/[^A-Za-z0-9_-]/g, '');
  }

  // "Bildirimde mesaj metni görünsün mü" tercihi. Uygulamanın global
  // değişkeni; okunamazsa gizli tarafta kalıyoruz (güvenli varsayılan).
  function icerikGosterilsinMi() {
    try { return !!tercihler.bildirimIcerik; } catch (e) { return false; }
  }

  function belirteciYaz(uid, belirtec) {
    var vt;
    try { vt = window.firebase.database(); } catch (e) { return; }

    var yol = 'cihazlar/' + uid + '/' + belirtecAnahtariYerel(belirtec);
    yazilanYol = yol;

    vt.ref(yol).set({
      belirtec: belirtec,
      ts: Date.now(),
      icerikGoster: icerikGosterilsinMi(),
      tarayici: (navigator.userAgent || '').slice(0, 120)
    }).then(function () {
      // Uygulamanın kendi değişkenini dolduruyoruz: içerik tercihi değişince
      // ve çıkış yapılınca index.html'in mevcut kodu devreye girsin.
      try { cihazBelirteci = belirtec; } catch (e) {}
    }).catch(function (e) {
      // En olası sebep: Realtime Database kurallarında `cihazlar` düğümü için
      // yazma izni tanımlı değil. O zaman sunucu bu cihaza hiç gönderemez.
      console.warn('Meridyen: bildirim belirteci yazılamadı —', e && e.message);
    });
  }

  function kur() {
    if (kuruldu) return;
    kuruldu = true;

    PB.addListener('registration', function (belirtecBilgisi) {
      var belirtec = belirtecBilgisi && belirtecBilgisi.value;
      if (!belirtec) return;
      var kullanici = null;
      try { kullanici = window.firebase.auth().currentUser; } catch (e) {}
      if (kullanici) belirteciYaz(kullanici.uid, belirtec);
    });

    PB.addListener('registrationError', function (hata) {
      console.warn('Meridyen: push kaydı başarısız —', hata && (hata.error || hata.message));
    });

    /* Uygulama ÖNDEYKEN gelen push'u yutuyoruz. index.html zaten veritabanı
       dinleyicisinden kendi bildirimini gösteriyor; ikisi birden çalışsa aynı
       mesaj iki kez görünürdü. Web tarafı da aynısını yapıyor
       (`mesajlasma.onMessage(() => {})`). */
    PB.addListener('pushNotificationReceived', function () {});
  }

  // Firebase SDK'sı sayfaya sonradan (dinamik script ile) geliyor; hazır olana
  // kadar bekliyoruz.
  var deneme = 0;
  var zamanlayici = setInterval(function () {
    if (++deneme > 600) { clearInterval(zamanlayici); return; }  // ~60 sn
    var fb = window.firebase;
    if (!fb || !fb.apps || !fb.apps.length || !fb.auth) return;
    clearInterval(zamanlayici);

    kur();

    fb.auth().onAuthStateChanged(function (kullanici) {
      if (!kullanici) {
        // Çıkışta silmeyi index.html'in `uzakBildirimiBirak()` fonksiyonu
        // yapıyor (biz `cihazBelirteci`'ni doldurduğumuz için çalışıyor).
        yazilanYol = null;
        return;
      }
      // Belirteci iste: sonuç 'registration' dinleyicisine düşecek.
      try {
        PB.register().catch(function (e) {
          console.warn('Meridyen: push kaydı yapılamadı —', e && e.message);
        });
      } catch (e) {}
    });
  }, 100);
})();

/* ================= YÜKLEME İLERLEME BİLDİRİMİ =================
 *
 * "Bir şey gönderirken ilerleme bildirimi olsun, sunucudan bağımsız olsun."
 * Bu bildirim tamamen YEREL: hiçbir sunucuya, FCM'e ya da ağa bağlı değil.
 *
 * NEDEN KENDİ NATIVE EKLENTİMİZ:
 * Bu iş önce @capacitor/local-notifications ile yapıldı ve iki şikayet geldi:
 * ilerleme yüzde SAYISI olarak görünüyordu (çubuk değil) ve her güncellemede
 * yeni bir bildirim geliyordu. İkisinin de sebebi o eklentinin kendi
 * kaynağında yazılı:
 *   - schedule() her çağrıda önce dismissVisibleNotification(id) çağırıyor,
 *     yani bildirimi silip yeniden yayınlıyor → yerinde güncellenmiyor.
 *   - Kaynağında "// TODO Progressbar support" yazıyor → ilerleme çubuğu yok.
 *
 * Bu yüzden gönderim bildirimi artık kendi eklentimizden geçiyor
 * (android-assets/java/MeridyenIlerleme.java): aynı id ile, SİLMEDEN
 * notify() çağırıyor (Android yerinde günceller) ve setProgress ile gerçek
 * bir ilerleme çubuğu çiziyor.
 *
 * Tarayıcıda bu nesne yine tanımlı ama hiçbir şey yapmıyor; index.html
 * koşulsuz çağırabilsin diye.
 */
(function () {
  'use strict';

  var cap = window.Capacitor;
  var IP = cap && cap.Plugins && cap.Plugins.MeridyenIlerleme;
  var yerli = !!(cap && typeof cap.isNativePlatform === 'function' && cap.isNativePlatform() && IP);

  if (window.MeridyenKopru) window.MeridyenKopru.ilerleme = !!IP;

  var acik = {};   // anahtar -> { baslik, alt, yuzde, sonYazim }

  function yaz(k, yuzde, belirsiz) {
    try {
      IP.goster({ baslik: k.baslik, alt: k.alt, yuzde: yuzde, belirsiz: !!belirsiz })
        .catch(function () {});
    } catch (e) {}
  }

  window.MeridyenYukleme = {
    baslat: function (anahtar, baslik, alt) {
      if (!yerli || !anahtar) return;
      var k = { baslik: baslik || 'Gönderiliyor', alt: alt || '', yuzde: -1, sonYazim: 0 };
      acik[anahtar] = k;
      /* Başlangıçta BELİRSİZ çubuk: daha ilk bayt gitmeden "%0" göstermek
         takılmış izlenimi veriyor. */
      yaz(k, 0, true);
    },

    /* oran: 0..1. Çubuğu her ilerleme olayında değil, tam sayı yüzde
       değiştiğinde ve en fazla ~400 ms'de bir güncelliyoruz. Çubuk akıcı
       görünsün ama köprü de gereksiz yere çalışmasın. */
    guncelle: function (anahtar, oran) {
      if (!yerli || !anahtar) return;
      var k = acik[anahtar];
      if (!k) return;
      var y = Math.max(0, Math.min(100, Math.round((oran || 0) * 100)));
      var simdi = Date.now();
      if (y === k.yuzde) return;
      if (y < 100 && simdi - k.sonYazim < 400) return;
      k.yuzde = y; k.sonYazim = simdi;
      yaz(k, y, false);
    },

    bitir: function (anahtar) {
      if (!yerli || !anahtar) return;
      if (!acik[anahtar]) return;
      delete acik[anahtar];
      try { IP.gizle().catch(function () {}); } catch (e) {}
    }
  };
})();

/* ================= SİSTEM ÇUBUKLARINI EKRANA UYDUR =================
 *
 * "Uygulama formu"na doğru küçük ama çok belli olan bir adım: durum çubuğu
 * simgelerinin ekranla uyumlu olması.
 *
 * Meridyen'in iki yüzü var — vitrin AÇIK zeminli (kagit), sohbet paneli KOYU
 * (gece). Sistem çubuğunun simgeleri sabit kalırsa birinde okunmaz oluyor:
 * açık zeminde beyaz saat/pil, koyu zeminde siyah. Gerçek uygulamalar bunu
 * ekrana göre değiştirir.
 *
 * Hangi yüzde olduğumuzu web tarafı zaten biliyor: panel açıkken <body>
 * "panel-acik" sınıfını taşıyor. O sınıfı izleyip native tarafa bildiriyoruz.
 * Çubukların ZEMİNİNE dokunmuyoruz — Android 15'te ekran zaten kenardan
 * kenara çiziliyor ve arkasını uygulamanın kendi içeriği dolduruyor.
 */
(function () {
  'use strict';

  var cap = window.Capacitor;
  var IP = cap && cap.Plugins && cap.Plugins.MeridyenIlerleme;
  if (!cap || typeof cap.isNativePlatform !== 'function' || !cap.isNativePlatform()) return;
  if (!IP || typeof IP.durumCubugu !== 'function') return;

  var sonKoyu = null;

  function uygula() {
    /* panel-acik => koyu zemin => simgeler AÇIK renk olmalı (koyuSimge:false) */
    var panelde = document.body && document.body.classList.contains('panel-acik');
    var koyuSimge = !panelde;
    if (koyuSimge === sonKoyu) return;          // gereksiz köprü çağrısı yok
    sonKoyu = koyuSimge;
    try { IP.durumCubugu({ koyuSimge: koyuSimge }).catch(function () {}); } catch (e) {}
  }

  function baslat() {
    if (!document.body) return;
    uygula();
    try {
      new MutationObserver(uygula)
        .observe(document.body, { attributes: true, attributeFilter: ['class'] });
    } catch (e) {}
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', baslat, { once: true });
  } else {
    baslat();
  }
})();
