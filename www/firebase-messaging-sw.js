/* Meridyen — arka plan bildirim Service Worker'ı (Firebase Cloud Messaging).
   index.html içindeki navigator.serviceWorker.register('firebase-messaging-sw.js', {scope:'./'})
   çağrısı bu dosyayı yüklüyor. Sekme/uygulama arka plandayken ya da kapalıyken
   gelen push bildirimlerini burada yakalayıp göstermek FCM'in standart yolu.

   NOT: Bu dosya önceki bir ortam sıfırlanmasında kaybolmuştu; index.html'de
   zaten var olan FIREBASE_CONFIG (satır ~5457) ve aynı SDK sürümüyle (10.14.1)
   birebir aynı yapılandırmadan yeniden oluşturuldu — web push anahtarları özel
   değil, tarayıcıya zaten her sayfa yüklemesinde gönderiliyor. */
importScripts('https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyDXKW6MU7dGwwD2phD11XojyEEESlabNqY",
  authDomain: "meridyen-830fb.firebaseapp.com",
  databaseURL: "https://meridyen-830fb-default-rtdb.europe-west1.firebasedatabase.app",
  projectId: "meridyen-830fb",
  storageBucket: "meridyen-830fb.firebasestorage.app",
  messagingSenderId: "628310759714",
  appId: "1:628310759714:web:ac3f2e5c02194b2f78ed7b",
  measurementId: "G-8YG2JF52PQ"
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  const veri = payload.notification || payload.data || {};
  const baslik = veri.title || 'Meridyen';
  const govde = veri.body || '';
  const secenekler = {
    body: govde,
    icon: payload.data && payload.data.icon,
    badge: payload.data && payload.data.badge,
    data: payload.data || {},
    tag: (payload.data && payload.data.tag) || undefined,
  };
  self.registration.showNotification(baslik, secenekler);
});

/* Bildirime dokununca uygulamayı öne getir (açık bir sekme/pencere varsa ona
   odaklan, yoksa yeni aç). */
self.addEventListener('notificationclick', (olay) => {
  olay.notification.close();
  const hedefUrl = (olay.notification.data && olay.notification.data.url) || './';
  olay.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((liste) => {
      for (const istemci of liste) {
        if ('focus' in istemci) return istemci.focus();
      }
      if (clients.openWindow) return clients.openWindow(hedefUrl);
    })
  );
});
