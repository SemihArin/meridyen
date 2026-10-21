#!/usr/bin/env node
/* Meridyen — veritabanı kurallarını GERÇEK RTDB emülatöründe sınar.

   Kural davranışını okuyarak tahmin etmek yanıltıyor: RTDB'de üst düğümde
   verilen .write izni alt düğümlerde GERİ ALINAMIYOR. Eskiden
   `sohbetler/$sid/.write` katılımcıya açıktı; altındaki "mesajı yalnız
   sahibi değiştirir" kuralı bu yüzden hiç işlemiyordu ve karşı taraf
   başkasının mesajını düzenleyip silebiliyor, onun adına mesaj
   yazabiliyordu. Bu sınama izin/ret tablosunu emülatörde ölçüyor.

   Çalıştırma (firebase-tools ve @firebase/rules-unit-testing gerekli, Java
   da — emülatör bir jar):
     firebase emulators:exec --only database --project demo-meridyen \
       "node scripts/test_kurallar_emulator.js [kural-dosyasi]"
   Emülatör adresi FIREBASE_DATABASE_EMULATOR_HOST'tan okunuyor. */
'use strict';
const fs = require('fs');
const path = require('path');

const modul = process.env.MERIDYEN_RUT || '@firebase/rules-unit-testing';
const { initializeTestEnvironment } = require(modul);

const KURAL = process.argv[2] || path.join(__dirname, '..', 'database.rules.json');
const [host, port] = (process.env.FIREBASE_DATABASE_EMULATOR_HOST || '127.0.0.1:9000').split(':');

const A = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const B = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const C = 'cccccccccccccccccccccccccccc';
const SID = [A, B].sort().join('_');
const SAAT = 3600000;
const ZAMAN = { '.sv': 'timestamp' };

let gecen = 0, kalan = 0;
async function bekle(ad, izinli, is) {
  let oldu;
  try { await is(); oldu = true; } catch (e) { oldu = false; }
  if (oldu === izinli) { gecen++; console.log('  ✓ ' + ad); }
  else { kalan++; console.log('  ✗ ' + ad + ' — beklenen ' + (izinli ? 'İZİN' : 'RET') + ', olan ' + (oldu ? 'İZİN' : 'RET')); }
}
const izin = (ad, is) => bekle(ad, true, is);
const ret  = (ad, is) => bekle(ad, false, is);

(async () => {
  const ortam = await initializeTestEnvironment({
    projectId: 'demo-meridyen',
    database: { host, port: Number(port), rules: fs.readFileSync(KURAL, 'utf8') }
  });

  /* Her durum temiz bir tohumdan başlıyor; biri ötekinin sonucuna yaslanmasın. */
  const tohumla = async () => {
    await ortam.clearDatabase();
    await ortam.withSecurityRulesDisabled(async (c) => {
      const db = c.database();
      const simdi = Date.now();
      await db.ref().update({
        ['sohbetler/' + SID + '/ayar/kaybolan']: { sure: SAAT, baslangic: 1000 },
        ['sohbetler/' + SID + '/mesajlar/eski']:   { uid: A, metin: 'süresi doldu', ts: 2000, medyaId: 'mdSohbet' },
        ['sohbetler/' + SID + '/mesajlar/once']:   { uid: A, metin: 'ayardan önce', ts: 500 },
        ['sohbetler/' + SID + '/mesajlar/taze']:   { uid: A, metin: 'yeni', ts: simdi },
        ['tepkiler/' + SID + '/taze/' + A]: '👍',
        ['tepkiler/' + SID + '/eski/' + B]: '👍',
        ['medya/mdSohbet/bilgi']: { uid: A, sid: SID, parca: 1, ts: 1 },
        ['medya/mdAkis/bilgi']:   { uid: A, parca: 1, ts: 1 },
        ['medya/mdKucuk']:        { veri: 'data:image/png;base64,AA', bilgi: { uid: A, ts: 1 } },
        ['medya/mdEski/veri']:    'data:image/png;base64,AA'
      });
    });
  };
  const db = (uid) => ortam.authenticatedContext(uid).database();
  const m = (id) => 'sohbetler/' + SID + '/mesajlar/' + id;

  const durumlar = [
    ['--- izin verilmesi gerekenler', null],
    [izin, 'A kendi mesajını gönderiyor', () => db(A).ref('sohbetler/' + SID + '/mesajlar').push({ uid: A, metin: 'selam', ts: ZAMAN })],
    [izin, 'A kendi mesajını düzenliyor', () => db(A).ref(m('taze')).update({ metin: 'düzeltildi', duzenlendi: 1 })],
    [izin, 'A kendi mesajını siliyor', () => db(A).ref(m('taze')).remove()],
    [izin, "B, A'nın SÜRESİ DOLMUŞ mesajını siliyor (kaybolan)", () => db(B).ref(m('eski')).remove()],
    [izin, 'B kaybolan mesajı açıyor (sunucu saatiyle)', () => db(B).ref('sohbetler/' + SID + '/ayar/kaybolan').set({ sure: SAAT, baslangic: ZAMAN })],
    [izin, 'B kaybolan mesajı kapatıyor', () => db(B).ref('sohbetler/' + SID + '/ayar/kaybolan').set(0)],
    [izin, 'B kendi okundu damgasını yazıyor', () => db(B).ref('sohbetler/' + SID + '/okundu/' + B).set(Date.now())],
    [izin, 'A sohbeti okuyor', () => db(A).ref('sohbetler/' + SID).get()],
    [izin, 'B sohbeti okuyor', () => db(B).ref('sohbetler/' + SID).get()],
    [izin, "B, A'nın mesajına tepki bırakıyor", () => db(B).ref('tepkiler/' + SID + '/taze/' + B).set('❤')],
    [izin, 'A kendi tepkisini kaldırıyor', () => db(A).ref('tepkiler/' + SID + '/taze/' + A).remove()],
    [izin, 'A kendi mesajının tüm tepkilerini siliyor', () => db(A).ref('tepkiler/' + SID + '/taze').remove()],
    [izin, 'B silinmiş mesajın tepkilerini temizliyor', async () => {
      await db(B).ref(m('eski')).remove();
      await db(B).ref('tepkiler/' + SID + '/eski').remove();
    }],
    [izin, 'A kendi sohbet medyasını siliyor', () => db(A).ref('medya/mdSohbet').remove()],
    [izin, "B, A'nın SOHBET medyasını siliyor (kaybolan temizliği)", () => db(B).ref('medya/mdSohbet').remove()],
    [izin, 'A tek düğümlü görseli bilgiyle birlikte yazıyor', () => db(A).ref('medya/yeniKucuk').update({ veri: 'data:x', bilgi: { uid: A, ts: 1, sid: SID } })],
    [izin, 'A kendi medyasına küçük resim ekliyor', () => db(A).ref('medya/mdSohbet/kucuk').set('data:x')],
    [izin, 'yeni medya kimliğine parça yazılabiliyor', () => db(A).ref('medya/yeniParcali/parca/0').set('AA')],

    ['--- reddedilmesi gerekenler', null],
    [ret, "B, A'nın mesajını düzenliyor", () => db(B).ref(m('taze')).update({ metin: 'B yazdı' })],
    [ret, "B, A'nın mesajını kendi adına geçiriyor", () => db(B).ref(m('taze')).update({ uid: B })],
    [ret, "B, A'nın süresi dolmamış mesajını siliyor", () => db(B).ref(m('taze')).remove()],
    [ret, "B, A'nın kaybolan ayarından ÖNCEKİ mesajını siliyor", () => db(B).ref(m('once')).remove()],
    [ret, "B, A'nın süresi dolmuş mesajını SİLMEK yerine değiştiriyor", () => db(B).ref(m('eski')).update({ metin: 'x' })],
    [ret, 'B, A adına mesaj gönderiyor', () => db(B).ref('sohbetler/' + SID + '/mesajlar').push({ uid: A, metin: 'sahte', ts: ZAMAN })],
    [ret, 'A kendi mesajını B adına geçiriyor', () => db(A).ref(m('taze')).update({ uid: B })],
    [ret, "B, A'nın okundu damgasını yazıyor", () => db(B).ref('sohbetler/' + SID + '/okundu/' + A).set(1)],
    [ret, 'B kaybolan ayarını geçmişe tarihliyor', () => db(B).ref('sohbetler/' + SID + '/ayar/kaybolan').set({ sure: SAAT, baslangic: 0 })],
    [ret, 'B sohbete keyfi düğüm yazıyor', () => db(B).ref('sohbetler/' + SID + '/baska').set(1)],
    [ret, 'B sohbetin tamamını siliyor', () => db(B).ref('sohbetler/' + SID).remove()],
    [ret, 'B mesajlar düğümünü toptan siliyor', () => db(B).ref('sohbetler/' + SID + '/mesajlar').remove()],
    [ret, 'yabancı C sohbeti okuyor', () => db(C).ref('sohbetler/' + SID).get()],
    [ret, 'yabancı C sohbete kendi adıyla yazıyor', () => db(C).ref('sohbetler/' + SID + '/mesajlar').push({ uid: C, metin: 'x', ts: ZAMAN })],
    [ret, 'yabancı C kaybolan ayarını değiştiriyor', () => db(C).ref('sohbetler/' + SID + '/ayar/kaybolan').set(0)],
    [ret, 'B, A adına tepki bırakıyor', () => db(B).ref('tepkiler/' + SID + '/taze/' + A).set('💩')],
    [ret, "B, A'nın var olan mesajının tepkilerini siliyor", () => db(B).ref('tepkiler/' + SID + '/taze').remove()],
    [ret, 'yabancı C tepki bırakıyor', () => db(C).ref('tepkiler/' + SID + '/taze/' + C).set('x')],
    [ret, "B, A'nın sohbet medyasının ÜSTÜNE yazıyor", () => db(B).ref('medya/mdSohbet/parca/0').set('BB')],
    [ret, "B, A'nın sohbet medyasının başlığını değiştiriyor", () => db(B).ref('medya/mdSohbet/bilgi').set({ uid: B, sid: SID })],
    [ret, "yabancı C, A'nın sohbet medyasını siliyor", () => db(C).ref('medya/mdSohbet').remove()],
    [ret, "B, A'nın sohbet dışı medyasını siliyor", () => db(B).ref('medya/mdAkis').remove()],
    [ret, "B, A'nın tek düğümlü görselinin üstüne yazıyor", () => db(B).ref('medya/mdKucuk/veri').set('data:kotu')],
    [ret, 'oturumsuz biri medya yazıyor', () => ortam.unauthenticatedContext().database().ref('medya/x/veri').set('x')]
  ];

  console.log('Kural dosyası: ' + KURAL);
  for (const [tur, ad, is] of durumlar) {
    if (typeof tur === 'string') { console.log(tur); continue; }
    await tohumla();
    await tur(ad, is);
  }
  await ortam.cleanup();
  console.log('\n' + gecen + ' geçti, ' + kalan + ' kaldı');
  process.exit(kalan ? 1 : 0);
})().catch((e) => { console.error('HATA', e && e.stack || e); process.exit(2); });
