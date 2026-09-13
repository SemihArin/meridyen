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
  /* Mesaj bildirimini artık kendi eklentimiz çiziyor. Capacitor'un yerel
     bildirim eklentisi her çağrıda aynı id'yi SİLİP yeniden yayınlıyor, bu
     yüzden aynı sohbetin ikinci mesajı birincinin üstüne yazıyordu —
     "bildirimler birbirini siliyor" şikayetinin sebebi buydu. Kendi yolumuz
     mesajları biriktiriyor ve bildirimleri tek başlık altında grupluyor.
     Eklenti yoksa (eski APK) eski yola düşülüyor. */
  var IP = cap && cap.Plugins && cap.Plugins.MeridyenIlerleme;
  var BIRIKEN = !!(IP && typeof IP.mesajBildirimi === 'function');

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
    birikenBildirim: BIRIKEN,
    push: !!(cap && cap.Plugins && cap.Plugins.PushNotifications)
  };

  if (!window.MeridyenKopru.yerli) return;
  // Gerçek API varsa (ileride WebView desteklerse) ona karışma.
  if ('Notification' in window) { window.MeridyenKopru.gercekApi = true; return; }

  /* Kendi eklentimiz varsa yerel bildirim eklentisine ihtiyaç yok; yoksa
     eski yol için gerekiyor. İkisi de yoksa shim kurulamaz. */
  if (!YB && !BIRIKEN) return;

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
    this.data = secenekler.data || null;
    this.onclick = null;
    this.onclose = null;
    this.onerror = null;
    this.onshow = null;

    this._id = etiketId(secenekler.tag);
    acikOlanlar[this._id] = this;

    var self = this;

    if (BIRIKEN) {
      /* Web'in Notification API'sinde `data` standart bir alan; tarayıcıda
         yok sayılıyor, burada gönderenin kim olduğunu taşıyor ki bildirime
         dokununca doğru sohbet açılsın. */
      var d = secenekler.data || {};
      try {
        IP.mesajBildirimi({
          baslik: String(baslik == null ? 'Meridyen' : baslik),
          govde: String(this.body),
          etiket: String(secenekler.tag == null ? 'meridyen-' + this._id : secenekler.tag),
          gonderen: d.gonderen ? String(d.gonderen) : null,
          tur: d.tur ? String(d.tur) : null
        }).then(function () {
          if (typeof self.onshow === 'function') { try { self.onshow(); } catch (e) {} }
        }).catch(function () {
          if (typeof self.onerror === 'function') { try { self.onerror(); } catch (e) {} }
        });
      } catch (e) {
        if (typeof this.onerror === 'function') { try { this.onerror(); } catch (e2) {} }
      }
      return;
    }

    try {
      var istek = {
        id: this._id,
        title: String(baslik == null ? 'Meridyen' : baslik),
        body: String(this.body),
        // Kilit ekranında da okunabilsin diye tek satıra sığmayan metinler
        // açılabilir olsun.
        largeBody: String(this.body),
        autoCancel: true,
        /* Bildirimler tek yerde toplansın: aynı gruba giren 4+ bildirimi
           Android kendiliğinden tek satırda özetliyor. */
        group: 'meridyen_mesajlar'
      };
      /* MESAJ KANALI: varsayılan kanal DÜŞÜK önemli — bildirim ekranın
         üstünde belirmiyor, ses ve titreşim vermiyor. Mesaj bildiriminin
         YÜKSEK önemli olması gerekiyor ve Android'de önem kanal başına
         ayarlanıyor, bildirim başına değil. Kanalı native taraf açılışta
         kuruyor (MeridyenBildirimler.mesajKanaliniKur); eklenti yoksa
         kanal adı vermiyoruz, yoksa Android bildirimi hiç göstermez. */
      if (cap && cap.Plugins && cap.Plugins.MeridyenIlerleme) {
        istek.channelId = 'meridyen_mesaj';
      }
      YB.schedule({ notifications: [istek] }).then(function () {
        if (typeof self.onshow === 'function') { try { self.onshow(); } catch (e) {} }
      }).catch(function () {
        if (typeof self.onerror === 'function') { try { self.onerror(); } catch (e) {} }
      });
    } catch (e) {
      if (typeof this.onerror === 'function') { try { this.onerror(); } catch (e2) {} }
    }
  }

  Bildirim.prototype.close = function () {
    if (BIRIKEN) {
      /* Yalnız bildirimi kaldırmakla kalmıyor, biriken satırları da siliyor:
         kullanıcı o sohbeti açtığı için kapatılıyor, okunmuş sayılmalı. */
      try { IP.bildirimTemizle({ etiket: this.tag || '' }).catch(function () {}); } catch (e) {}
      delete acikOlanlar[this._id];
      if (typeof this.onclose === 'function') { try { this.onclose(); } catch (e) {} }
      return;
    }
    try { YB.cancel({ notifications: [{ id: this._id }] }); } catch (e) {}
    delete acikOlanlar[this._id];
    if (typeof this.onclose === 'function') { try { this.onclose(); } catch (e) {} }
  };

  Bildirim.requestPermission = function (geriCagri) {
    if (!YB) return Promise.resolve(izin);
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
    if (YB) YB.addListener('localNotificationActionPerformed', function (olay) {
      var id = olay && olay.notification && olay.notification.id;
      var n = acikOlanlar[id];
      if (n && typeof n.onclick === 'function') { try { n.onclick(); } catch (e) {} }
      delete acikOlanlar[id];
    });
  } catch (e) {}

  /* Açılışta mevcut izni öğren (kullanıcı daha önce izin vermiş olabilir) ve
     hiç sorulmadıysa BİR KEZ sor.

     Android 13'ten beri bildirim ayrı bir çalışma-zamanı izni. Kullanıcı
     Ayarlar'a girip "İzin ver"e basana kadar tek bir bildirim bile çıkmıyor
     — ve çıkmadığı için de kimse Ayarlar'a bakmayı akıl etmiyor. Gerçek
     mesajlaşma uygulamaları izni ilk açılışta ister; biz de öyle yapıyoruz.

     Yalnız bir kez: kullanıcı reddettiyse her açılışta tekrar sormuyoruz
     (zaten Android ikinci redden sonra pencereyi hiç göstermiyor). */
  var SORULDU = 'meridyen_bildirim_soruldu';

  function izniHazirla() {
    if (!YB) return;
    try {
      YB.checkPermissions().then(function (sonuc) {
        izin = durumCevir(sonuc);
        arayuzuTazele();
        if (izin !== 'default') return;
        var soruldu = false;
        try { soruldu = localStorage.getItem(SORULDU) === '1'; } catch (e) {}
        if (soruldu) return;
        try { localStorage.setItem(SORULDU, '1'); } catch (e) {}
        Bildirim.requestPermission();
      }).catch(function () {});
    } catch (e) {}
  }

  izniHazirla();

  /* Kullanıcı sistem ayarlarından izni değiştirip geri dönebiliyor; o zaman
     `izin` bayatlıyor ve Ayarlar ekranı yanlış durumu gösteriyordu. */
  try {
    document.addEventListener('visibilitychange', function () {
      if (document.hidden || !YB) return;
      YB.checkPermissions().then(function (sonuc) {
        var yeni = durumCevir(sonuc);
        if (yeni === izin) return;
        izin = yeni;
        arayuzuTazele();
      }).catch(function () {});
    });
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
  var sonBelirtec = null;   // en son alınan FCM belirteci
  var sonUid = null;        // o an oturum açmış kullanıcı
  var yazmaDenemesi = 0;    // başarısız yazımlar için geri çekilme sayacı

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

  /* Belirteç ile oturum İKİ AYRI zamanda hazır oluyor ve sırası garanti
     değil: FCM belirteci oturum açılmadan önce de gelebiliyor, sonra da.
     Eskiden yalnız "belirteç geldi" anında yazılıyordu; belirteç önce
     gelirse sessizce düşüyordu ve o cihaza hiçbir push ulaşmıyordu.
     Artık ikisini de saklayıp, ikisi birden hazır olduğunda yazıyoruz. */
  function yazmayiDene() {
    if (!sonBelirtec || !sonUid) return;
    belirteciYaz(sonUid, sonBelirtec);
  }

  /* Bildirime dokunulduğunda ilgili sohbeti açar. index.html'in kendi
     `sistemBildirimi` fonksiyonu bunu onclick içinde yapıyor ama o yalnız
     uygulama ÇALIŞIRKEN gösterilen bildirimler için geçerli. Kapalıyken
     gelen bildirime dokunulduğunda uygulama sıfırdan açılıyor ve o onclick
     artık yok — hedef bilgisi niyetin (intent) içinden geliyor. */
  function sohbeteGit(uid) {
    if (!uid) return;
    try {
      if (typeof window.panelGirisTalebi !== 'function') return;
      window.panelGirisTalebi(function () {
        try { window.paneleGec(); } catch (e) {}
        try { window.sohbetAc(uid); } catch (e) {}
      });
    } catch (e) {}
  }

  function acilisiIsle(veri) {
    var uid = veri && (veri.gonderen || (veri.notification && veri.notification.data &&
      (veri.notification.data.gonderen || veri.notification.data.uid)));
    if (uid) sohbeteGit(String(uid));
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
      yazmaDenemesi = 0;
      // Uygulamanın kendi değişkenini dolduruyoruz: içerik tercihi değişince
      // ve çıkış yapılınca index.html'in mevcut kodu devreye girsin.
      try { cihazBelirteci = belirtec; } catch (e) {}
      if (window.MeridyenKopru) window.MeridyenKopru.belirtecYazildi = true;
    }).catch(function (e) {
      /* En olası iki sebep: (a) Realtime Database kurallarında `cihazlar`
         düğümü için yazma izni yok, (b) o an ağ yok. İkisi de geçici
         olabildiği için TEKRAR deniyoruz — yazılamazsa sunucu bu cihaza
         hiç gönderemez, yani sessizce vazgeçmek bildirimleri tamamen
         kapatmak demek. Geri çekilerek en fazla 5 kez. */
      if (window.MeridyenKopru) {
        window.MeridyenKopru.belirtecYazildi = false;
        window.MeridyenKopru.belirtecHatasi = (e && e.message) || 'bilinmiyor';
      }
      console.warn('Meridyen: bildirim belirteci yazılamadı —', e && e.message);
      if (yazmaDenemesi >= 5) return;
      var bekle = Math.pow(2, yazmaDenemesi) * 2000;   // 2, 4, 8, 16, 32 sn
      yazmaDenemesi++;
      setTimeout(yazmayiDene, bekle);
    });
  }

  function kur() {
    if (kuruldu) return;
    kuruldu = true;

    PB.addListener('registration', function (belirtecBilgisi) {
      var belirtec = belirtecBilgisi && belirtecBilgisi.value;
      if (!belirtec) return;
      /* Bu olay yalnız register() sonrası değil, FCM belirteci YENİLENDİĞİNDE
         de geliyor (onNewToken). Eski belirteç artık ölü olduğu için yenisini
         mutlaka yazmamız gerekiyor, yoksa cihaz sessizce erişilmez oluyor. */
      sonBelirtec = belirtec;
      if (window.MeridyenKopru) window.MeridyenKopru.belirtecVar = true;
      yazmaDenemesi = 0;
      try {
        var k = window.firebase.auth().currentUser;
        if (k) sonUid = k.uid;
      } catch (e) {}
      yazmayiDene();
    });

    PB.addListener('registrationError', function (hata) {
      var m = (hata && (hata.error || hata.message)) || 'bilinmiyor';
      if (window.MeridyenKopru) window.MeridyenKopru.kayitHatasi = String(m);
      console.warn('Meridyen: push kaydı başarısız —', m);
    });

    /* Uygulama ÖNDEYKEN gelen push'u yutuyoruz. index.html zaten veritabanı
       dinleyicisinden kendi bildirimini gösteriyor; ikisi birden çalışsa aynı
       mesaj iki kez görünürdü. Web tarafı da aynısını yapıyor
       (`mesajlasma.onMessage(() => {})`). */
    PB.addListener('pushNotificationReceived', function () {});

    /* Uygulama önde DEĞİLKEN bildirimi native taraf çiziyor
       (MeridyenMesajServisi); bu dinleyici o durumda hiç çalışmıyor.
       FCM'in kendi çizdiği bildirime dokunulduğunda ise buraya düşüyor. */
    PB.addListener('pushNotificationActionPerformed', acilisiIsle);
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
        sonUid = null;
        return;
      }
      sonUid = kullanici.uid;
      /* Belirteç zaten elimizdeyse (oturumdan ÖNCE geldiyse) beklemeden
         yazıyoruz; yoksa register() sonucu 'registration' dinleyicisine
         düşecek ve oradan yazılacak. */
      yazmayiDene();
      try {
        PB.register().catch(function (e) {
          console.warn('Meridyen: push kaydı yapılamadı —', e && e.message);
        });
      } catch (e) {}
    });
  }, 100);

  /* Kendi çizdiğimiz bildirime dokunulduğunda: uygulama açıksa olay olarak
     gelir; kapalıyken açılıyorsa köprü o an henüz yüklenmemiş olabildiği
     için native taraf değeri saklıyor, biz burada bir kez soruyoruz. */
  var IP = cap.Plugins && cap.Plugins.MeridyenIlerleme;
  if (IP) {
    try { IP.addListener('bildirimAcildi', acilisiIsle); } catch (e) {}
    if (typeof IP.bekleyenAcilis === 'function') {
      setTimeout(function () {
        try {
          IP.bekleyenAcilis().then(function (s) {
            if (s && s.gonderen) sohbeteGit(String(s.gonderen));
          }).catch(function () {});
        } catch (e) {}
      }, 1200);   // uygulamanın kendi açılışı bitsin
    }
  }
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

/* ================= BİLDİRİM TANISI =================
 *
 * "Bildirim gelmiyor" tek bir arıza değil, birbirine benzeyen bir sürü ayrı
 * arıza: izin verilmemiş olabilir, kullanıcı kanalı kapatmış olabilir,
 * uygulamanın bildirimleri tümden kapalı olabilir, FCM belirteci alınamamış
 * ya da veritabanına yazılamamış olabilir, ya da köprü hiç yüklenmemiştir.
 * Dışarıdan hepsi aynı görünüyor ve her seferinde tahminle ilerlemek
 * gerekiyordu.
 *
 * Burası hepsini ayrı ayrı okuyup tek bir nesne olarak veriyor; Ayarlar
 * ekranı bunu insan diline çeviriyor. Ayrıca gerçek bildirim yolunun
 * aynısını kullanan bir sınama düğmesi var: sınama görünüyorsa izin, kanal,
 * ikon ve dokunma niyeti çalışıyor demektir.
 */
(function () {
  'use strict';

  var cap = window.Capacitor;
  var yerli = !!(cap && typeof cap.isNativePlatform === 'function' && cap.isNativePlatform());
  var IP = yerli && cap.Plugins && cap.Plugins.MeridyenIlerleme;
  var K = window.MeridyenKopru || (window.MeridyenKopru = {});

  K.tani = function () {
    var temel = {
      yerli: yerli,
      kopru: true,
      izin: (typeof Notification !== 'undefined' && Notification.permission) || 'yok',
      belirtecVar: !!K.belirtecVar,
      belirtecYazildi: K.belirtecYazildi === true,
      belirtecHatasi: K.belirtecHatasi || '',
      kayitHatasi: K.kayitHatasi || ''
    };
    if (!IP || typeof IP.tani !== 'function') return Promise.resolve(temel);
    return IP.tani().then(function (n) {
      for (var a in n) { if (Object.prototype.hasOwnProperty.call(n, a)) temel[a] = n[a]; }
      return temel;
    }).catch(function () { return temel; });
  };

  /* Sınama GERÇEK bildirim yolundan geçiyor (native tarafta
     MeridyenBildirimler.mesaj). Ayrı bir sınama kodu yazsaydık gerçek yolu
     değil kendisini sınamış olurduk. */
  K.sina = function () {
    if (IP && typeof IP.sina === 'function') {
      return IP.sina().then(function () { return true; }).catch(function () { return false; });
    }
    // Tarayıcıda: web'in kendi Notification API'siyle aynı işi yap.
    try {
      if (typeof Notification === 'undefined' || Notification.permission !== 'granted') {
        return Promise.resolve(false);
      }
      new Notification('Meridyen', {
        body: 'Sınama bildirimi — bunu gördüysen bildirimler çalışıyor.',
        tag: 'meridyen-sinama'
      });
      return Promise.resolve(true);
    } catch (e) {
      return Promise.resolve(false);
    }
  };

  K.bildirimAyarlariniAc = function () {
    if (IP && typeof IP.bildirimAyarlariniAc === 'function') {
      try { return IP.bildirimAyarlariniAc().catch(function () {}); } catch (e) {}
    }
    return Promise.resolve();
  };
})();

/* ================= KAYAN EKRAN ve ARKA PLAN NÖBETİ =================
 *
 * İkisi de yalnız APK'da anlamlı; tarayıcıda bu nesneler tanımlı ama hiçbir
 * şey yapmıyor, index.html koşulsuz çağırabilsin diye.
 *
 * KAYAN EKRAN: Web'in Picture-in-Picture API'si Android WebView'da YOK, o
 * yüzden uygulamada düğme hiç görünmüyordu. Android'in kendi PiP'i Activity
 * düzeyinde; giriş kararı native tarafta veriliyor (Activity ön plandayken
 * verilmek zorunda), web tarafı yalnız "görüntülü görüşme sürüyor" bilgisini
 * geçiyor ve kipe girildiğinde haber alıyor.
 *
 * NÖBET: Arka planda bir süre sonra Android işlemi donduruyor, veritabanı
 * bağlantısı ölüyor ve bildirimler kesiliyor. Ön plan servisi bunu
 * engelliyor. Servis uygulama GÖRÜNÜRKEN başlatılıyor: Android 12'den beri
 * arka plandan başlatmak reddediliyor.
 */
(function () {
  'use strict';

  var cap = window.Capacitor;
  var IP = cap && cap.Plugins && cap.Plugins.MeridyenIlerleme;
  var yerli = !!(cap && typeof cap.isNativePlatform === 'function' && cap.isNativePlatform() && IP);
  var K = window.MeridyenKopru || (window.MeridyenKopru = {});

  K.kayanEkranVar = yerli && typeof IP.kayanEkranaGec === 'function';
  K.nobetVar = yerli && typeof IP.nobet === 'function';

  /* Görüntülü görüşme başladı/bitti. en/boy, küçük pencerenin oranı:
     yanlış oran Android'de hata fırlatıp görüşmeyi düşürebiliyor, o yüzden
     native tarafta ayrıca sınırlanıyor. */
  K.kayanEkranDurumu = function (gorusmeSuruyor, en, boy) {
    if (!K.kayanEkranVar) return Promise.resolve(false);
    try {
      return IP.kayanEkranDurumu({
        gorusme: !!gorusmeSuruyor,
        en: en || 16,
        boy: boy || 9
      }).then(function (s) { return !!(s && s.destek); }).catch(function () { return false; });
    } catch (e) { return Promise.resolve(false); }
  };

  K.kayanEkranaGec = function () {
    if (!K.kayanEkranVar) return Promise.resolve(false);
    try {
      return IP.kayanEkranaGec()
        .then(function (s) { return !!(s && s.oldu); })
        .catch(function () { return false; });
    } catch (e) { return Promise.resolve(false); }
  };

  /* Kipe girildi/çıkıldı: index.html body'ye 'kayan-ekran' sınıfını koyup
     yalnız karşı tarafın görüntüsünü çiziyor. */
  if (K.kayanEkranVar) {
    try {
      IP.addListener('kayanEkranDegisti', function (v) {
        var icinde = !!(v && v.icinde);
        try { document.body.classList.toggle('kayan-ekran', icinde); } catch (e) {}
        try {
          if (typeof window.kayanEkranDegisti === 'function') window.kayanEkranDegisti(icinde);
        } catch (e) {}
      });
    } catch (e) {}
  }

  K.nobet = function (acik) {
    if (!K.nobetVar) return Promise.resolve(false);
    try {
      return IP.nobet({ acik: !!acik })
        .then(function (s) { return !!(s && s.calisiyor); })
        .catch(function () { return false; });
    } catch (e) { return Promise.resolve(false); }
  };

  K.pilIzniIste = function () {
    if (!yerli || typeof IP.pilIzniIste !== 'function') return Promise.resolve();
    try { return IP.pilIzniIste().catch(function () {}); } catch (e) { return Promise.resolve(); }
  };
})();

/* ================= BİLDİRİM TEMİZLEME =================
 * Sohbet uygulamada açıldığında o sohbetin biriken bildirimi düşmeli:
 * okunan mesaj bildirim gölgesinde durmamalı.
 */
(function () {
  'use strict';
  var cap = window.Capacitor;
  var IP = cap && cap.Plugins && cap.Plugins.MeridyenIlerleme;
  var K = window.MeridyenKopru || (window.MeridyenKopru = {});
  var var_ = !!(IP && typeof IP.bildirimTemizle === 'function');
  K.bildirimTemizleVar = var_;
  K.bildirimTemizle = function (etiket) {
    if (!var_) return Promise.resolve(false);
    try {
      return IP.bildirimTemizle({ etiket: etiket || '' })
        .then(function () { return true; }).catch(function () { return false; });
    } catch (e) { return Promise.resolve(false); }
  };
})();
