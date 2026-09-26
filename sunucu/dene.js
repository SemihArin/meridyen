#!/usr/bin/env node
/* Kurulumu DOĞRULAMA aracı.
 *
 * Gerçek bir mesaj beklemeden, seçtiğin kullanıcıya deneme bildirimi gönderir.
 * Böylece "servis hesabı doğru mu, cihaz belirteci kayıtlı mı, push geliyor
 * mu" sorularının üçü birden tek komutta yanıtlanıyor.
 *
 *   node dene.js <hedefUid> [mesaj]
 *   node dene.js --cihazlar <hedefUid>     → kayıtlı cihazları listeler
 */
'use strict';
const admin = require('firebase-admin');
const B = require('./bildirim');

const VERITABANI = process.env.MERIDYEN_DB ||
  'https://meridyen-830fb-default-rtdb.europe-west1.firebasedatabase.app';

function kimlikAl() {
  const satir = process.env.MERIDYEN_SERVIS_HESABI;
  if (satir) return admin.credential.cert(JSON.parse(satir));
  if (process.env.GOOGLE_APPLICATION_CREDENTIALS) return admin.credential.applicationDefault();
  console.error('Servis hesabı anahtarı yok (bkz. README.md).');
  process.exit(1);
}

(async () => {
  const arg = process.argv.slice(2);
  const yalnizListe = arg[0] === '--cihazlar';
  const hedef = yalnizListe ? arg[1] : arg[0];
  const metin = (yalnizListe ? arg[2] : arg.slice(1).join(' ')) || 'Deneme bildirimi — her şey çalışıyor.';
  if (!hedef) {
    console.error('Kullanım: node dene.js <hedefUid> [mesaj]');
    console.error('          node dene.js --cihazlar <hedefUid>');
    process.exit(1);
  }

  admin.initializeApp({ credential: kimlikAl(), databaseURL: VERITABANI });
  const cihazlar = (await admin.database().ref('cihazlar/' + hedef).once('value')).val() || {};
  const anahtarlar = Object.keys(cihazlar);

  console.log('Hedef:', hedef);
  console.log('Kayıtlı cihaz:', anahtarlar.length);
  anahtarlar.forEach((a) => {
    const c = cihazlar[a] || {};
    console.log('  -', a,
      '| içerik:', c.icerikGoster ? 'açık' : 'kapalı',
      '| belirteç:', String(c.belirtec || '').slice(0, 18) + '…',
      '|', String(c.tarayici || '').slice(0, 40));
  });
  if (!anahtarlar.length) {
    console.log('\nHiç cihaz yok. Kullanıcı uygulamayı açıp bildirim iznini vermiş olmalı;');
    console.log('web tarafında ayrıca firebase-messaging-sw.js sitenin kökünde bulunmalı.');
    process.exit(2);
  }
  if (yalnizListe) process.exit(0);

  const kayit = { hedef: hedef, gonderen: 'DENEME', gonderenAd: 'Meridyen',
                  tur: 'mesaj', baslik: 'Meridyen', metin: metin, ts: Date.now() };
  const isler = B.mesajlariKur(kayit, cihazlar);
  const sonuc = await admin.messaging().sendEach(isler.map((i) => i.mesaj));
  console.log('\nGönderildi:', sonuc.successCount, '/', isler.length);
  sonuc.responses.forEach((y, i) => {
    if (y.success) console.log('  ✓', isler[i].anahtar, y.messageId);
    else console.log('  ✗', isler[i].anahtar, (y.error && y.error.code) || y.error);
  });
  await admin.app().delete();
  process.exit(sonuc.failureCount ? 3 : 0);
})().catch((e) => { console.error('HATA:', e && e.message); process.exit(1); });
