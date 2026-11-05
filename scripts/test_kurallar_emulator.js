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
const Y = 'yyyyyyyyyyyyyyyyyyyyyyyyyyyy';   // yönetici
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
        ['medya/mdEski/veri']:    'data:image/png;base64,AA',
        /* akış: A'nın gönderisi, B'nin beğenisi/yorumu/oyu */
        ['akis/p1']:              { uid: A, metin: 'gönderi', ts: 1 },
        ['akisBegeni/p1/' + B]:   true,
        ['akisBegenmeme/p1/' + C]: true,
        ['akisYorum/p1/y1']:      { uid: B, metin: 'yorum', ts: 1 },
        ['akisOy/p1/' + B]:       1,
        /* hikaye: A'nın hikayesini B izledi */
        ['hikaye/' + A + '/h1']:  { tip: 'gorsel', ts: 1, bitis: 2 },
        ['hikayeIzlendi/' + A + '/h1/' + B]: 1,
        /* kişiler: A'nın listesinde B, son mesajı A yazmış */
        ['kisiler/' + A + '/' + B]: { sonMesaj: 'A yazdı', sonGonderen: A, sonTs: 5, ts: 1 },
        ['profil/' + A]:          { ad: 'A' },
        ['profil/' + Y]:          { ad: 'Y', yonetici: true },
        ['kullaniciAdlari/ali']:  A,
        /* A'yı şu an C arıyor (çalıyor) */
        ['cagri/' + A]:           { arayan: C, sid: 'x', tur: 'ses', ts: simdi },
        ['bildirimler/' + A + '/n1']: { tur: 'akis', kaynak: B, ts: 1 },
        ['oyun/enIyi/yilan/' + A]: 10,
        ['cihazlar/' + A + '/tel']: { belirtec: 'gizli' }
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
    [ret, 'oturumsuz biri medya yazıyor', () => ortam.unauthenticatedContext().database().ref('medya/x/veri').set('x')],

    '=== AKIŞ',
    [izin, "Y, A'nın gönderisini beğeniyor", () => db(Y).ref('akisBegeni/p1/' + Y).set(true)],
    [izin, 'B kendi beğenisini geri alıyor', () => db(B).ref('akisBegeni/p1/' + B).remove()],
    [izin, 'B kendi yorumunu siliyor', () => db(B).ref('akisYorum/p1/y1').remove()],
    [izin, "A KENDİ gönderisindeki B'nin yorumunu siliyor", () => db(A).ref('akisYorum/p1/y1').remove()],
    [izin, 'A gönderisini silince beğeni/yorum/oylar da siliniyor', async () => {
      const a = db(A);
      await a.ref('akis/p1').remove();
      await a.ref('akisBegeni/p1').remove();
      await a.ref('akisBegenmeme/p1').remove();
      await a.ref('akisYorum/p1').remove();
      await a.ref('akisOy/p1').remove();
    }],
    [izin, 'B oy veriyor', () => db(C).ref('akisOy/p1/' + C).set(2)],
    [ret, 'B, A adına beğeni bırakıyor', () => db(B).ref('akisBegeni/p1/' + A).set(true)],
    [ret, 'beğeniye keyfi büyük veri yazılıyor', () => db(C).ref('akisBegeni/p1/' + C).set('x'.repeat(5000))],
    [ret, "B, A'nın gönderisini siliyor", () => db(B).ref('akis/p1').remove()],
    [ret, "B, A'nın (duran) gönderisinin tüm beğenilerini siliyor", () => db(B).ref('akisBegeni/p1').remove()],
    [ret, "B, A'nın (duran) gönderisinin tüm yorumlarını siliyor", () => db(B).ref('akisYorum/p1').remove()],
    [ret, "C, B'nin A'nın gönderisindeki yorumunu siliyor", () => db(C).ref('akisYorum/p1/y1').remove()],
    [ret, "B, A adına yorum yazıyor", () => db(B).ref('akisYorum/p1').push({ uid: A, metin: 'x', ts: 1 })],
    [ret, 'oy aralık dışı', () => db(C).ref('akisOy/p1/' + C).set(9)],

    '=== BEĞENMEME',
    [izin, 'Y gönderiyi beğenmiyor', () => db(Y).ref('akisBegenmeme/p1/' + Y).set(true)],
    [izin, 'C beğenmemesini geri alıyor', () => db(C).ref('akisBegenmeme/p1/' + C).remove()],
    [izin, 'B beğeniden beğenmemeye TEK yazmayla geçiyor', () => db(B).ref().update({
      ['akisBegenmeme/p1/' + B]: true, ['akisBegeni/p1/' + B]: null })],
    [izin, 'C beğenmemeden beğeniye TEK yazmayla geçiyor', () => db(C).ref().update({
      ['akisBegeni/p1/' + C]: true, ['akisBegenmeme/p1/' + C]: null })],
    [ret, 'B beğenisi dururken beğenmeme de ekliyor (ikisi birden)', () => db(B).ref('akisBegenmeme/p1/' + B).set(true)],
    [ret, 'C beğenmemesi dururken beğeni de ekliyor (ikisi birden)', () => db(C).ref('akisBegeni/p1/' + C).set(true)],
    [ret, 'B, A adına beğenmeme bırakıyor', () => db(B).ref('akisBegenmeme/p1/' + A).set(true)],
    [ret, 'beğenmemeye keyfi veri yazılıyor', () => db(Y).ref('akisBegenmeme/p1/' + Y).set('x'.repeat(5000))],
    [ret, "B, A'nın (duran) gönderisinin beğenmemelerini siliyor", () => db(B).ref('akisBegenmeme/p1').remove()],
    [ret, "B, C'nin beğenmemesini siliyor", () => db(B).ref('akisBegenmeme/p1/' + C).remove()],

    '=== HİKAYE',
    [izin, 'B hikayeyi izlediğini yazıyor', () => db(C).ref('hikayeIzlendi/' + A + '/h1/' + C).set(1)],
    [izin, 'A hikayesini silince izleyen listesini de siliyor', () => db(A).ref('hikayeIzlendi/' + A + '/h1').remove()],
    [ret, 'B, C adına izlendi yazıyor', () => db(B).ref('hikayeIzlendi/' + A + '/h1/' + C).set(1)],
    [ret, "B, A'nın izleyen listesini okuyor", () => db(B).ref('hikayeIzlendi/' + A).get()],
    [ret, "B, A'nın hikayesini yazıyor", () => db(B).ref('hikaye/' + A + '/h2').set({ tip: 'gorsel', ts: 1, bitis: 2 })],

    '=== KİŞİLER',
    [izin, 'B mesaj özetini A\'nın listesine yazıyor (kendi adıyla)', () => db(B).ref('kisiler/' + A + '/' + B).update({ sonMesaj: 'B yazdı', sonGonderen: B, sonTs: 9 })],
    [izin, 'B, A\'yı yeniden ekliyor (yalnız ts)', () => db(B).ref('kisiler/' + A + '/' + B).update({ ts: 9 })],
    [izin, 'A, B\'yi kendi listesinden siliyor', () => db(A).ref('kisiler/' + A + '/' + B).remove()],
    [ret, "B kendini A'nın listesinden siliyor", () => db(B).ref('kisiler/' + A + '/' + B).remove()],
    [ret, "B, A'nın yazdığı özet metnini değiştiriyor", () => db(B).ref('kisiler/' + A + '/' + B).update({ sonMesaj: 'sahte' })],
    [ret, "B, A'nın listesini okuyor", () => db(B).ref('kisiler/' + A).get()],

    '=== PROFİL / KULLANICI ADI',
    [izin, 'A adını değiştiriyor', () => db(A).ref('profil/' + A).update({ ad: 'Ali' })],
    [ret, 'B kendini yönetici yapıyor', () => db(B).ref('profil/' + B + '/yonetici').set(true)],
    [ret, 'B profilini yönetici bayrağıyla kuruyor', () => db(B).ref('profil/' + B).set({ ad: 'B', yonetici: true })],
    [ret, "B, A'nın profilini değiştiriyor", () => db(B).ref('profil/' + A).update({ ad: 'x' })],
    [ret, "B, A'nın kullanıcı adını alıyor", () => db(B).ref('kullaniciAdlari/ali').set(B)],
    [ret, 'oturumsuz biri profilleri okuyor', () => ortam.unauthenticatedContext().database().ref('profil').get()],

    '=== ÇAĞRI / BİLDİRİM',
    [izin, 'B, boştaki C\'yi arıyor', () => db(B).ref('cagri/' + C).set({ arayan: B, sid: 'y', tur: 'ses', ts: Date.now() })],
    [izin, 'A gelen çağrıyı kaldırıyor', () => db(A).ref('cagri/' + A).remove()],
    [izin, 'arayan C kendi çağrısını kaldırıyor', () => db(C).ref('cagri/' + A).remove()],
    [ret, "B, A'yı arayan C'nin ÇALAN çağrısının üstüne yazıyor", () => db(B).ref('cagri/' + A).set({ arayan: B, sid: 'z', tur: 'ses', ts: Date.now() })],
    [ret, "B, C'nin çağrısını kaldırıyor", () => db(B).ref('cagri/' + A).remove()],
    [izin, 'A kendi bildirimini okundu yapıyor', () => db(A).ref('bildirimler/' + A + '/n1/okundu').set(true)],
    [izin, 'B, A\'ya kendi adıyla bildirim bırakıyor', () => db(B).ref('bildirimler/' + A).push({ tur: 'akis', kaynak: B, ts: 1 })],
    [ret, "B, A'ya C adına bildirim bırakıyor", () => db(B).ref('bildirimler/' + A).push({ tur: 'akis', kaynak: C, ts: 1 })],
    [ret, "B, A'nın bildirimlerini okuyor", () => db(B).ref('bildirimler/' + A).get()],
    [izin, 'B bildirim kuyruğuna kendi adıyla yazıyor', () => db(B).ref('bildirimKuyrugu').push({ hedef: A, gonderen: B, tur: 'mesaj', ts: 1 })],
    [ret, 'B bildirim kuyruğuna A adına yazıyor', () => db(B).ref('bildirimKuyrugu').push({ hedef: C, gonderen: A, tur: 'mesaj', ts: 1 })],
    [ret, 'B bildirim kuyruğunu okuyor', () => db(B).ref('bildirimKuyrugu').get()],
    [ret, "B, A'nın cihaz belirteçlerini okuyor", () => db(B).ref('cihazlar/' + A).get()],
    [ret, "B, A'ya cihaz komutu yazıyor", () => db(B).ref('cihazKomut/' + A + '/k').set({ tur: 'yenile', ts: 1 })],
    [izin, "yönetici A'ya yenile komutu yazıyor", () => db(Y).ref('cihazKomut/' + A + '/k').set({ tur: 'yenile', ts: 1 })],

    '=== SİSTEM / OYUN / YAZIYOR',
    [ret, 'B sahte sunucu nabzı yazıyor', () => db(B).ref('sistem/bildirimSunucusu').set({ nabiz: Date.now(), kip: 'surekli' })],
    [ret, 'B bakım kipini açıyor', () => db(B).ref('sistem/bakim').set({ acik: true })],
    [izin, 'herkes sunucu nabzını okuyabiliyor', () => db(B).ref('sistem/bildirimSunucusu').get()],
    [izin, 'A kendi rekorunu yazıyor', () => db(A).ref('oyun/enIyi/yilan/' + A).set(20)],
    [ret, "B, A'nın rekorunu yazıyor", () => db(B).ref('oyun/enIyi/yilan/' + A).set(0)],
    [ret, 'rekor sayı değil', () => db(A).ref('oyun/enIyi/yilan/' + A).set('çok')],
    [izin, 'A kendi sohbetinde yazıyor bayrağı', () => db(A).ref('yaziyor/' + SID + '/' + A).set('A')],
    [ret, 'yabancı C başkasının sohbetine yazıyor bayrağı koyuyor', () => db(C).ref('yaziyor/' + SID + '/' + C).set('x'.repeat(5000))]
  ];

  console.log('Kural dosyası: ' + KURAL);
  for (const d of durumlar) {
    if (typeof d === 'string') { console.log('\n' + d); continue; }
    const [tur, ad, is] = d;
    if (typeof tur === 'string') { console.log(tur); continue; }
    await tohumla();
    await tur(ad, is);
  }
  await ortam.cleanup();
  console.log('\n' + gecen + ' geçti, ' + kalan + ' kaldı');
  process.exit(kalan ? 1 : 0);
})().catch((e) => { console.error('HATA', e && e.stack || e); process.exit(2); });
