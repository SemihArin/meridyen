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
  if (!cap || typeof cap.isNativePlatform !== 'function' || !cap.isNativePlatform()) return;
  // Gerçek API varsa (ileride WebView desteklerse) ona karışma.
  if ('Notification' in window) return;

  var YB = cap.Plugins && cap.Plugins.LocalNotifications;
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
    h = Math.abs(h) % 2147483647;
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
