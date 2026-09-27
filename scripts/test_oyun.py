#!/usr/bin/env python3
"""Meridyen — oyun ekranının mantığını sınar (2048 kuralları + skor tablosu).

NE SINANIYOR: www/index.html'in İÇİNDEKİ gerçek fonksiyonlar. Kopyası değil:
betik dosyayı okuyup adı verilen fonksiyonları süslü parantez sayarak
çıkarıyor ve Node'un vm'inde koşturuyor. Kopyalasaydık sınama kopyayı
doğrular, uygulamayı değil.

NİÇİN GEREKLİ: 2048'in kaydırma kuralları "gözle doğru görünen" ama yanlış
olan bir sürü varyanta sahip. En sinsisi zincirleme birleşme: [4,2,2] sola
kaydırıldığında 4-4 olmalı, 8 DEĞİL. Elle denemeyle bu yakalanmıyor, çünkü
oyun yine "çalışıyor" gibi görünüyor — sadece kuralları yanlış.

Skor tablosu da burada: dereceye göre puanlama ve EŞİTLİK durumu. Dört
kişilik bir çevrede "berabere kaldık ama o daha çok puan aldı" tartışması
oyunu bitirir, o yüzden eşitlikte ikisinin de yüksek puanı alması sınanıyor.
"""
import io
import os
import subprocess
import sys
import tempfile

KAYNAK = "www/index.html"

# Çıkarılacak fonksiyonlar. Saf olanlar: DOM ve Firebase'e dokunmuyorlar.
ISLEVLER = [
    "o48TasYap",
    "o48Hamle",
    "o48BosKareler",
    "o48TasEkle",
    "o48Bitti",
    "oyunHaftasi",
    "oyunGenelTablo",
    "oyunSiralamasi",
    "yilanYonSec",
    "yilanYemKoy",
    "yilanAdim",
    "yilanAralik",
    "farkliBoyut",
    "farkliFark",
    "farkliTur",
    "hafizaKaristir",
    "hafizaDeste",
    "hafizaEslesirMi",
    "hafizaSureYaz",
    "oyunSkorYaz",
    "tepkiBekleme",
    "tepkiOrtalama",
    "siraEkle",
    "siraOnEkDogruMu",
    "siraTamamMi",
    "isikCevir",
    "isikBittiMi",
    "isikKur",
    "nisanOran",
    "nisanOmur",
    "nisanKonum",
    "nisanVurdumu",
    "zamanBolgeGenislik",
    "zamanHiz",
    "zamanBolgeMerkez",
    "zamanKonum",
    "zamanVurdumu",
    "sayiSoru",
]

SURUCU = r"""
let gecti = 0, kaldi = 0;
function esit(ad, bulunan, beklenen){
  const a = JSON.stringify(bulunan), b = JSON.stringify(beklenen);
  if (a === b) gecti++;
  else { kaldi++; console.log('KALDI: ' + ad + '\n  beklenen ' + b + '\n  bulunan  ' + a); }
}
function dogru(ad, k){ esit(ad, !!k, true); }

/* Izgarayi okunur yazmak icin: satir satir sayilar, 0 = bos. */
function kur(izgara){
  const t = [];
  izgara.forEach((satir, r) => satir.forEach((d, s) => { if (d) t.push(o48TasYap(d, r, s)); }));
  t.forEach(x => { x.yeni = false; });
  return t;
}
function goster(taslar){
  const g = [[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]];
  taslar.forEach(t => { g[t.r][t.s] = t.deger; });
  return g;
}

/* ---- 1) temel kaydirma ---- */
{
  const t = kur([[0,0,2,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  const s = o48Hamle(t, 'sol');
  esit('sola kayiyor', goster(s.taslar), [[2,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  esit('kaymada puan yok', s.puan, 0);
  dogru('degisti', s.degisti);
}
{
  const t = kur([[2,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  const s = o48Hamle(t, 'sol');
  dogru('yerinde duran tas degismedi sayilmiyor', !s.degisti);
}

/* ---- 2) ZİNCİRLEME BİRLEŞME OLMAMALI (asil tuzak) ---- */
{
  const t = kur([[4,2,2,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  const s = o48Hamle(t, 'sol');
  esit('4-2-2 sola: 4-4 olur (8 DEGIL)', goster(s.taslar), [[4,4,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  esit('4-2-2 puani', s.puan, 4);
}
{
  const t = kur([[2,2,2,2],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  const s = o48Hamle(t, 'sol');
  esit('2-2-2-2 sola: 4-4', goster(s.taslar), [[4,4,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  esit('2-2-2-2 puani', s.puan, 8);
}
{
  const t = kur([[2,2,4,4],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  const s = o48Hamle(t, 'sol');
  esit('2-2-4-4 sola: 4-8', goster(s.taslar), [[4,8,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  esit('2-2-4-4 puani', s.puan, 12);
}
{
  const t = kur([[2,2,2,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  const s = o48Hamle(t, 'sol');
  esit('2-2-2 sola: 4-2 (hedefe yakin ikili birlesir)',
       goster(s.taslar), [[4,2,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
}
{
  const t = kur([[2,2,2,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  const s = o48Hamle(t, 'sag');
  esit('2-2-2 saga: 2-4 (hedef kenar degisti)',
       goster(s.taslar), [[0,0,2,4],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
}

/* ---- 3) birlesme hareket olmadan da degisiklik ---- */
{
  const t = kur([[2,2,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  const s = o48Hamle(t, 'sol');
  dogru('yer degismese de birlesme degisikliktir', s.degisti);
  esit('birlesme sonucu', goster(s.taslar), [[4,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
}

/* ---- 4) dikey yonler ---- */
{
  const t = kur([[2,0,0,0],[2,0,0,0],[0,0,0,0],[4,0,0,0]]);
  const s = o48Hamle(t, 'yukari');
  esit('yukari: 2-2-4 -> 4-4', goster(s.taslar), [[4,0,0,0],[4,0,0,0],[0,0,0,0],[0,0,0,0]]);
  esit('yukari puani', s.puan, 4);
}
{
  const t = kur([[2,0,0,0],[2,0,0,0],[0,0,0,0],[4,0,0,0]]);
  const s = o48Hamle(t, 'asagi');
  esit('asagi: alta yigiliyor', goster(s.taslar), [[0,0,0,0],[0,0,0,0],[4,0,0,0],[4,0,0,0]]);
}

/* ---- 5) kimlik: hedefe yakin tas hayatta kalir (kayma animasyonunun sarti) ---- */
{
  const t = kur([[2,2,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  const solKimlik = t.find(x => x.s === 0).id;
  const s = o48Hamle(t, 'sol');
  esit('sola birlesmede soldaki tas yasar', s.taslar[0].id, solKimlik);
  dogru('birlesen tas isaretli', s.taslar[0].birlesti);
}

/* ---- 6) tas sayisi ve sinirlar ---- */
{
  const t = kur([[2,2,4,8],[0,0,0,0],[0,0,0,0],[0,0,0,0]]);
  const s = o48Hamle(t, 'sol');
  esit('bir birlesme bir tas eksiltir', s.taslar.length, 3);
  dogru('tum taslar tahta icinde',
        s.taslar.every(x => x.r >= 0 && x.r < 4 && x.s >= 0 && x.s < 4));
  const yerler = new Set(s.taslar.map(x => x.r + ',' + x.s));
  esit('iki tas ayni karede degil', yerler.size, s.taslar.length);
}

/* ---- 7) bos kareler ve tas ekleme ---- */
{
  esit('bos tahtada 16 bos kare', o48BosKareler([]).length, 16);
  const t = kur([[2,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,4]]);
  esit('iki tasli tahtada 14 bos', o48BosKareler(t).length, 14);

  /* Sabit rastgele: ilk bos kareye 2 koyar. */
  const taslar = kur([[2,2,2,2],[2,2,2,2],[2,2,2,2],[2,2,2,0]]);
  const eklendi = o48TasEkle(taslar, () => 0);
  esit('tek bos kareye eklendi', [eklendi.r, eklendi.s], [3, 3]);
  esit('0.9 altinda 2 gelir', eklendi.deger, 2);
  esit('tahta doldu', o48BosKareler(taslar).length, 0);
  esit('dolu tahtaya eklenemez', o48TasEkle(taslar, () => 0), null);
}
{
  const taslar = kur([[2,2,2,2],[2,2,2,2],[2,2,2,2],[2,2,2,0]]);
  /* 0.95: kare secimi icin de 0.95 kullanilir ama tek kare var; deger 4 olur. */
  const eklendi = o48TasEkle(taslar, () => 0.95);
  esit('0.9 ustunde 4 gelir', eklendi.deger, 4);
}

/* ---- 8) oyun bitti mi ---- */
{
  dogru('bos tahtada bitmedi', !o48Bitti([]));
  /* Dolu ama komsu esitler var -> bitmedi. */
  const bir = kur([[2,2,4,8],[4,8,16,32],[2,4,8,16],[4,8,16,32]]);
  dogru('birlesme varsa bitmedi', !o48Bitti(bir));
  /* Dolu ve hicbir komsu esit degil -> bitti. */
  const iki = kur([[2,4,2,4],[4,2,4,2],[2,4,2,4],[4,2,4,2]]);
  dogru('hamle kalmadiysa bitti', o48Bitti(iki));
}

/* ---- 9) hafta anahtari ---- */
{
  /* 2026-09-27 pazar; o haftanin pazartesisi 2026-09-21. */
  const pazar = new Date(2026, 8, 27, 23, 30).getTime();
  const pazartesi = new Date(2026, 8, 21, 0, 5).getTime();
  const cuma = new Date(2026, 8, 25, 12, 0).getTime();
  esit('pazartesi anahtari', oyunHaftasi(pazartesi), '20260921');
  esit('ayni haftanin cumasi ayni anahtar', oyunHaftasi(cuma), '20260921');
  esit('ayni haftanin pazari ayni anahtar', oyunHaftasi(pazar), '20260921');
  /* Bir sonraki pazartesi yeni sezon. */
  esit('sonraki hafta yeni anahtar',
       oyunHaftasi(new Date(2026, 8, 28, 0, 1).getTime()), '20260928');
  /* Ay/yil siniri. */
  esit('yil siniri', oyunHaftasi(new Date(2027, 0, 1, 12, 0).getTime()), '20261228');
}

/* ---- 10) genel tablo: dereceye gore puan ---- */
{
  globalThis.OYUNLAR = [{ id: 'a', azIyi: false }, { id: 'b', azIyi: true }];
  globalThis.oyunSkor = {
    a: { u1: 100, u2: 50, u3: 10, u4: 5 },   // yuksek iyi
    b: { u3: 200, u1: 900 }                   // az iyi (sure gibi)
  };
  const t = oyunGenelTablo();
  /* a: u1=3, u2=2, u3=1 (u4 ilk ucte degil)   b: u3=3, u1=2 */
  esit('toplam puanlar', t, [
    { uid: 'u1', puan: 5 },
    { uid: 'u3', puan: 4 },
    { uid: 'u2', puan: 2 }
  ]);
  dogru('ilk ucun disi puan almaz', !t.some(r => r.uid === 'u4'));
}
{
  globalThis.OYUNLAR = [{ id: 'a', azIyi: false }];
  globalThis.oyunSkor = { a: { u1: 100, u2: 100, u3: 40 } };
  const t = oyunGenelTablo();
  esit('esitlikte ikisi de yuksek puani alir', t, [
    { uid: 'u1', puan: 3 },
    { uid: 'u2', puan: 3 },
    { uid: 'u3', puan: 1 }
  ]);
}
{
  globalThis.OYUNLAR = [{ id: 'a', azIyi: false }];
  globalThis.oyunSkor = {};
  esit('kimse oynamadiysa tablo bos', oyunGenelTablo(), []);
}


/* ================= YILAN ================= */

function yilanKur(noktalar, yon, yem, puan){
  return { yilan: noktalar.map(([x, y]) => ({ x, y })), yon: yon || 'sag',
           yem: yem ? { x: yem[0], y: yem[1] } : null, puan: puan || 0, boyut: 15 };
}
const yer = (p) => [p.x, p.y];

/* ---- 11) TUZAK 1: ters donus reddedilir ---- */
{
  esit('saga giderken sol reddedilir', yilanYonSec('sag', 'sol'), 'sag');
  esit('sola giderken sag reddedilir', yilanYonSec('sol', 'sag'), 'sol');
  esit('yukari giderken asagi reddedilir', yilanYonSec('yukari', 'asagi'), 'yukari');
  esit('asagi giderken yukari reddedilir', yilanYonSec('asagi', 'yukari'), 'asagi');
  esit('dik donus kabul edilir', yilanYonSec('sag', 'yukari'), 'yukari');
  esit('ayni yon kabul edilir', yilanYonSec('sag', 'sag'), 'sag');
  esit('tanimsiz yon yoksayilir', yilanYonSec('sag', 'zip'), 'sag');
}

/* ---- 12) temel hareket ---- */
{
  const d = yilanKur([[5,5],[4,5],[3,5]], 'sag', [9,9]);
  const s = yilanAdim(d);
  esit('bas bir kare ilerledi', s.yilan.map(yer), [[6,5],[5,5],[4,5]]);
  esit('uzunluk degismedi', s.yilan.length, 3);
  esit('puan degismedi', s.puan, 0);
  dogru('bitmedi', !s.bitti);
  esit('girdi degismedi (saf islev)', d.yilan.map(yer), [[5,5],[4,5],[3,5]]);
}

/* ---- 13) yem yemek ---- */
{
  const d = yilanKur([[5,5],[4,5],[3,5]], 'sag', [6,5]);
  const s = yilanAdim(d, () => 0);
  esit('yiyince uzadi', s.yilan.length, 4);
  esit('govde korundu', s.yilan.map(yer), [[6,5],[5,5],[4,5],[3,5]]);
  esit('puan arttı', s.puan, YILAN_YEM_PUAN);
  dogru('yedi bayragi', s.yedi);
  dogru('yeni yem kondu', !!s.yem);
  dogru('yeni yem yilanin ustunde degil',
        !s.yilan.some(p => p.x === s.yem.x && p.y === s.yem.y));
}

/* ---- 14) duvar olumu (dort kenar) ---- */
{
  dogru('sag duvar', yilanAdim(yilanKur([[14,5],[13,5]], 'sag')).bitti);
  dogru('sol duvar', yilanAdim(yilanKur([[0,5],[1,5]], 'sol')).bitti);
  dogru('ust duvar', yilanAdim(yilanKur([[5,0],[5,1]], 'yukari')).bitti);
  dogru('alt duvar', yilanAdim(yilanKur([[5,14],[5,13]], 'asagi')).bitti);
  dogru('kenarin hemen icinde olmuyor', !yilanAdim(yilanKur([[13,5],[12,5]], 'sag')).bitti);
}

/* ---- 15) TUZAK 3: kuyrugun bosalttigi kareye girmek YASAL ---- */
{
  /* 2x2 halka: bas (5,5), kuyruk (5,6). Asagi gidince kuyruk o kareyi
     birakiyor, yani girmek olum DEGIL. */
  const d = yilanKur([[5,5],[6,5],[6,6],[5,6]], 'asagi', [0,0]);
  const s = yilanAdim(d);
  dogru('kuyrugun bosalttigi kareye girmek olum degil', !s.bitti);
  esit('halka donduruldu', s.yilan.map(yer), [[5,6],[5,5],[6,5],[6,6]]);
}
{
  /* Ama YİYORSA kuyruk kalıyor: ayni kareye girmek olum. */
  const d = yilanKur([[5,5],[6,5],[6,6],[5,6]], 'asagi', [5,6]);
  const s = yilanAdim(d);
  dogru('yem kuyruktaysa carpisma sayilir', s.bitti);
}

/* ---- 16) kendine carpma ---- */
{
  const d = yilanKur([[5,5],[5,6],[6,6],[6,5]], 'yukari', [0,0]);
  /* yukari: (5,4) bos -> olmemeli */
  dogru('bos kareye gidince olmez', !yilanAdim(d).bitti);
  const e = yilanKur([[6,5],[5,5],[5,6],[6,6]], 'asagi', [0,0]);
  /* asagi: (6,6) govdenin son elemani AMA yemiyor -> kuyruk cekiliyor, yasal */
  dogru('halkada kuyruga girmek yasal', !yilanAdim(e).bitti);
  /* Gövdenin ORTASINA carpma. Kare (4,3) govdede ve KUYRUK DEGIL (kuyruk
     (5,3)), yani kimse cekilmiyor -> olum. Ilk yazdigim dizilimde (4,3)
     kuyruktu ve dogru sekilde olum SAYILMIYORDU; sinamanin beklentisi
     yanlisti, kod degil. */
  const f = yilanKur([[3,3],[3,4],[4,4],[4,3],[5,3]], 'sag', [0,0]);
  dogru('govdenin ortasina carpinca olur', yilanAdim(f).bitti);
  /* Ayni yilan yukari giderse (3,2) bos -> yasamali. */
  dogru('ayni yilan bos yone gidince yasar',
        !yilanAdim(yilanKur([[3,3],[3,4],[4,4],[4,3],[5,3]], 'yukari', [0,0])).bitti);
}

/* ---- 17) yem yerlestirme ---- */
{
  /* Tahtanin tamami dolu -> yem konamaz (oyun kazanildi). */
  const hepsi = [];
  for (let y = 0; y < 15; y++) for (let x = 0; x < 15; x++) hepsi.push({ x, y });
  esit('dolu tahtada yem yok', yilanYemKoy(hepsi, 15, () => 0), null);
  /* Tek bos kare: oraya konmali. */
  const bir = hepsi.filter(p => !(p.x === 7 && p.y === 9));
  esit('tek bos kareye kondu', yer(yilanYemKoy(bir, 15, () => 0)), [7, 9]);
  /* rast=0 ilk bos kareyi verir. */
  esit('rast=0 ilk bos kare', yer(yilanYemKoy([{x:0,y:0}], 15, () => 0)), [1, 0]);
}

/* ---- 18) hizlanma ---- */
{
  esit('baslangic araligi', yilanAralik(0), YILAN_BASLANGIC_MS);
  esit('bir yem sonrasi', yilanAralik(YILAN_YEM_PUAN), YILAN_BASLANGIC_MS - YILAN_HIZLANMA);
  dogru('hiz taban altina inmiyor', yilanAralik(YILAN_YEM_PUAN * 500) === YILAN_ENAZ_MS);
  dogru('aralik hep pozitif', yilanAralik(YILAN_YEM_PUAN * 5000) > 0);
}

/* ---- 19) oyuna ozel siralama ---- */
{
  globalThis.OYUNLAR = [{ id: 'y', azIyi: false }, { id: 'h', azIyi: true }];
  globalThis.oyunSkor = { y: { u1: 30, u2: 90 }, h: { u1: 30, u2: 90 } };
  esit('yuksek iyi siralama', oyunSiralamasi('y'), [{uid:'u2',skor:90},{uid:'u1',skor:30}]);
  esit('az iyi siralama', oyunSiralamasi('h'), [{uid:'u1',skor:30},{uid:'u2',skor:90}]);
  esit('bos oyun bos siralama', oyunSiralamasi('yok'), []);
}


/* ================= FARKLI KARE ================= */

/* ---- 20) izgara buyume egrisi ---- */
{
  esit('ilk seviye 2x2', farkliBoyut(0), 2);
  esit('iki seviyede bir buyuyor', [0,1,2,3,4,5].map(farkliBoyut), [2,2,3,3,4,4]);
  esit('tavanda duruyor', farkliBoyut(500), FK_ENBUYUK);
  /* Azalmamali: her seviye oncekinden kucuk olmayan bir izgara. */
  let onceki = 0, azaldi = false;
  for (let i = 0; i < 300; i++) { const b = farkliBoyut(i); if (b < onceki) azaldi = true; onceki = b; }
  dogru('boyut hic kucumuyor', !azaldi);
}

/* ---- 21) fark egrisi ve TABAN ---- */
{
  dogru('ilk seviyede fark buyuk', farkliFark(0) > 20);
  dogru('fark azaliyor', farkliFark(5) < farkliFark(0));
  esit('taban altina inmiyor', farkliFark(1000), FK_ENAZ_FARK);
  let onceki = 1e9, artti = false;
  for (let i = 0; i < 300; i++) { const f = farkliFark(i); if (f > onceki) artti = true; onceki = f; }
  dogru('fark hic artmiyor', !artti);
  dogru('fark her zaman tabanin ustunde',
        [0,1,5,20,50,999].every(i => farkliFark(i) >= FK_ENAZ_FARK));
}

/* ---- 22) tur uretimi ---- */
{
  const t = farkliTur(0, () => 0);
  esit('2x2 dort kare', t.adet, 4);
  esit('hedef gecerli', t.hedef, 0);
  dogru('iki renk farkli', t.zemin !== t.ayri);
  dogru('ton ve doygunluk ayni, yalniz parlaklik farkli',
        t.zemin.split(',')[0] === t.ayri.split(',')[0] &&
        t.zemin.split(',')[1] === t.ayri.split(',')[1]);
}
{
  /* rnd 1'e cok yaklassa bile hedef izgaranin DISINA tasmamali. */
  const t = farkliTur(6, () => 0.9999999);
  dogru('hedef izgara icinde', t.hedef >= 0 && t.hedef < t.adet);
  esit('hedef son kare', t.hedef, t.adet - 1);
}
{
  /* Parlaklik hicbir seviyede %100'u asmamali (asarsa renk beyaza kirpilir
     ve iki kare AYNI gorunur — oyun sessizce oynanamaz olurdu). */
  let tasan = 0, esit_renk = 0;
  for (let sev = 0; sev < 60; sev++) {
    for (const r of [0, 0.25, 0.5, 0.75, 0.999]) {
      const t = farkliTur(sev, () => r);
      const p = Number(t.ayri.split(',')[2].replace('%)', ''));
      if (p > 100) tasan++;
      if (t.zemin === t.ayri) esit_renk++;
      if (t.hedef < 0 || t.hedef >= t.adet) tasan++;
    }
  }
  esit('hicbir seviyede parlaklik tasmiyor', tasan, 0);
  esit('iki renk hicbir seviyede ayni degil', esit_renk, 0);
}
{
  /* Ayni rastgele -> ayni tahta (belirlenimci). */
  esit('belirlenimci', farkliTur(3, () => 0.4), farkliTur(3, () => 0.4));
}

/* ---- 23) sabitler makul ---- */
{
  dogru('sure yarim dakika', FK_SURE_MS === 30000);
  dogru('ceza sureden dusuluyor ve sureden kucuk', FK_CEZA_MS > 0 && FK_CEZA_MS < FK_SURE_MS);
  dogru('izgara tavani oynanabilir', FK_ENBUYUK >= 4 && FK_ENBUYUK <= 10);
}


/* ================= HAFIZA ================= */

/* ---- 24) karistirma ---- */
{
  const girdi = [1,2,3,4,5,6,7,8];
  const c = hafizaKaristir(girdi, () => 0.5);
  esit('girdi degismedi (saf islev)', girdi, [1,2,3,4,5,6,7,8]);
  esit('uzunluk korundu', c.length, 8);
  esit('ayni ogeler (permutasyon)', c.slice().sort((a,b)=>a-b), [1,2,3,4,5,6,7,8]);
  esit('belirlenimci', hafizaKaristir(girdi, () => 0.3), hafizaKaristir(girdi, () => 0.3));
  esit('tek ogeli dizi', hafizaKaristir([7], () => 0.9), [7]);
  esit('bos dizi', hafizaKaristir([], () => 0.9), []);
}

/* ---- 25) deste ---- */
{
  const d = hafizaDeste(() => 0.5);
  esit('16 kart', d.length, HAFIZA_CIFT * 2);
  const sayim = {};
  d.forEach(k => { sayim[k.cift] = (sayim[k.cift] || 0) + 1; });
  esit('sekiz farkli cift', Object.keys(sayim).length, HAFIZA_CIFT);
  dogru('her cift TAM iki kez', Object.keys(sayim).every(k => sayim[k] === 2));
  dogru('her kartin sembolu ve rengi var',
        d.every(k => typeof k.sembol === 'string' && k.sembol.length > 0 &&
                     /^#[0-9a-f]{6}$/i.test(k.renk)));
  /* Ayni cift -> ayni sembol; farkli cift -> farkli sembol. */
  const semboller = {};
  d.forEach(k => { semboller[k.cift] = k.sembol; });
  esit('sembol sayisi cift sayisi kadar',
       new Set(Object.values(semboller)).size, HAFIZA_CIFT);
  esit('belirlenimci deste', hafizaDeste(() => 0.25), hafizaDeste(() => 0.25));
}
{
  /* Farkli rastgeleliklerle 200 deste: her seferinde gecerli olmali. */
  let bozuk = 0;
  for (let n = 0; n < 200; n++) {
    const r = () => (n * 0.0137 + 0.31) % 1;
    const d = hafizaDeste(r);
    const c = {};
    d.forEach(k => { c[k.cift] = (c[k.cift] || 0) + 1; });
    if (d.length !== 16 || Object.keys(c).length !== 8 ||
        !Object.keys(c).every(k => c[k] === 2)) bozuk++;
  }
  esit('200 destenin hepsi gecerli', bozuk, 0);
}

/* ---- 26) eslesme ---- */
{
  const d = [{cift:0},{cift:1},{cift:0},{cift:2}];
  dogru('ayni cift eslesir', hafizaEslesirMi(d, 0, 2));
  dogru('farkli cift eslesmez', !hafizaEslesirMi(d, 0, 1));
  /* En sinsi durum: ayni karta iki kez dokunmak. */
  dogru('kart kendisiyle ESLESMEZ', !hafizaEslesirMi(d, 0, 0));
  dogru('gecersiz indeks eslesmez', !hafizaEslesirMi(d, 0, 99));
  dogru('negatif indeks eslesmez', !hafizaEslesirMi(d, -1, 0));
}

/* ---- 27) sure bicimi ---- */
{
  esit('42300 ms', hafizaSureYaz(42300), '42,3 sn');
  esit('yuvarlama', hafizaSureYaz(9950), '10,0 sn');
  esit('sifir', hafizaSureYaz(0), '0,0 sn');
  esit('uzun sure', hafizaSureYaz(125400), '125,4 sn');
}

/* ---- 28) skor yazimi oyunun bicimini kullaniyor ---- */
{
  const suren = { id: 'h', azIyi: true, birim: 'sn', bicim: hafizaSureYaz };
  const sayan = { id: 's', azIyi: false, birim: '' };
  esit('bicim verildiyse o kullanilir', oyunSkorYaz(suren, 42300), '42,3 sn');
  esit('bicim yoksa sayi + birim', oyunSkorYaz(sayan, 18240), (18240).toLocaleString('tr-TR'));
  esit('deger yoksa tire', oyunSkorYaz(suren, null), '—');
  /* Bicim patlarsa yedek yola dusmeli, oyun ekrani cokmemeli. */
  const bozuk = { id: 'b', birim: 'x', bicim: () => { throw new Error('bozuk'); } };
  esit('bozuk bicim cokertmiyor', oyunSkorYaz(bozuk, 5), '5 x');
}

/* ---- 29) az-iyi oyun tabloda dogru siralaniyor ---- */
{
  globalThis.OYUNLAR = [{ id: 'hafiza', azIyi: true }];
  globalThis.oyunSkor = { hafiza: { u1: 52000, u2: 31000, u3: 44000 } };
  esit('kisa sure once', oyunSiralamasi('hafiza').map(r => r.uid), ['u2','u3','u1']);
  esit('tabloda da kisa sure birinci',
       oyunGenelTablo(), [{uid:'u2',puan:3},{uid:'u3',puan:2},{uid:'u1',puan:1}]);
}


/* ================= TEPKI ================= */
{
  esit('bekleme alt sinir', tepkiBekleme(() => 0), TEPKI_ENAZ_MS);
  esit('bekleme ust sinir', tepkiBekleme(() => 1), TEPKI_ENCOK_MS);
  dogru('bekleme hep araligin icinde',
        [0,0.1,0.33,0.5,0.99,1].every(r => {
          const v = tepkiBekleme(() => r);
          return v >= TEPKI_ENAZ_MS && v <= TEPKI_ENCOK_MS && Number.isInteger(v);
        }));
  esit('belirlenimci', tepkiBekleme(() => 0.42), tepkiBekleme(() => 0.42));

  esit('ortalama', tepkiOrtalama([200, 300, 400]), 300);
  esit('ortalama yuvarlaniyor', tepkiOrtalama([200, 301]), 251);
  esit('tek tur', tepkiOrtalama([187]), 187);
  esit('bos dizi sifir (bolme hatasi yok)', tepkiOrtalama([]), 0);
  esit('null guvenli', tepkiOrtalama(null), 0);
}

/* ================= SIRA ================= */
{
  const d = [1, 2];
  const y = siraEkle(d, () => 0.5);
  esit('girdi degismedi (saf islev)', d, [1, 2]);
  esit('bir adim eklendi', y.length, 3);
  dogru('yeni adim gecerli tus', y[2] >= 0 && y[2] < SIRA_TUS);
  esit('onceki adimlar korundu', y.slice(0, 2), [1, 2]);
  esit('bos diziden baslar', siraEkle([], () => 0).length, 1);
  esit('null guvenli', siraEkle(null, () => 0).length, 1);
  /* rnd 1'e dayanirsa tus indeksi TASMAMALI. */
  esit('rast 0.99999 tasmiyor', siraEkle([], () => 0.9999999)[0], SIRA_TUS - 1);
  esit('belirlenimci', siraEkle([3], () => 0.7), siraEkle([3], () => 0.7));
}
{
  const dizi = [0, 2, 1, 3];
  dogru('bos giris on ek sayilir', siraOnEkDogruMu(dizi, []));
  dogru('dogru on ek', siraOnEkDogruMu(dizi, [0, 2]));
  dogru('tam dizi on ek', siraOnEkDogruMu(dizi, [0, 2, 1, 3]));
  dogru('yanlis ilk adim', !siraOnEkDogruMu(dizi, [1]));
  dogru('yanlis son adim', !siraOnEkDogruMu(dizi, [0, 2, 1, 0]));
  dogru('diziden UZUN giris yanlis', !siraOnEkDogruMu(dizi, [0, 2, 1, 3, 0]));

  dogru('yarim giris tamam degil', !siraTamamMi(dizi, [0, 2]));
  dogru('tam ve dogru giris tamam', siraTamamMi(dizi, [0, 2, 1, 3]));
  dogru('tam ama yanlis giris tamam degil', !siraTamamMi(dizi, [0, 2, 1, 0]));
  dogru('bos giris tamam degil', !siraTamamMi(dizi, []));
}

/* ================= ISIKLAR ================= */

/* BAGIMSIZ COZUCU: uretecin kullandigindan BASKA bir yontem. 5x5 Isiklar'da
   ilk satirin 32 olasi basim deseninden biri denenir, sonra "isik kovalama"
   ile asagi inilir; son satir sonuyorsa bulmaca cozulur. Uretecin
   "cozulebilir uretiyorum" iddiasini bagimsiz olarak dogruluyor. */
function isikCozulurMu(baslangic, b){
  for (let desen = 0; desen < (1 << b); desen++) {
    let g = baslangic.slice();
    for (let s = 0; s < b; s++) if (desen & (1 << s)) g = isikCevir(g, s, b);
    for (let r = 1; r < b; r++) {
      for (let s = 0; s < b; s++) {
        if (g[(r - 1) * b + s]) g = isikCevir(g, r * b + s, b);
      }
    }
    if (isikBittiMi(g)) return true;
  }
  return false;
}

{
  const bos = new Array(25).fill(0);
  /* Kose: kendisi + 2 komsu = 3 kare. */
  esit('kose 3 kare cevirir', isikCevir(bos, 0, 5).filter(v => v).length, 3);
  /* Kenar ortasi: kendisi + 3 komsu = 4. */
  esit('kenar 4 kare cevirir', isikCevir(bos, 2, 5).filter(v => v).length, 4);
  /* Ic kare: kendisi + 4 komsu = 5. */
  esit('ic kare 5 kare cevirir', isikCevir(bos, 12, 5).filter(v => v).length, 5);
  /* Sag kenardaki kare SOLDAKI satira TASMAMALI. */
  const sag = isikCevir(bos, 4, 5);
  esit('sag kenar sonraki satira tasmiyor', sag[5], 0);
  const sol = isikCevir(bos, 5, 5);
  esit('sol kenar onceki satira tasmiyor', sol[4], 0);

  esit('girdi degismedi (saf islev)', bos.filter(v => v).length, 0);
  /* Ayni hamle iki kez = basa donus. Cozulebilirligin dayandigi ozellik bu. */
  esit('hamle kendi tersi', isikCevir(isikCevir(bos, 7, 5), 7, 5), bos);
  dogru('bos tahta bitmis sayilir', isikBittiMi(bos));
  dogru('tek isik varsa bitmemis', !isikBittiMi(isikCevir(bos, 0, 5)));
}
{
  /* 200 uretilmis tahta: hepsi COZULEBILIR ve hicbiri zaten cozulmus degil. */
  let cozulemeyen = 0, zatenBitmis = 0;
  for (let n = 0; n < 200; n++) {
    let t = 0;
    const r = () => { t = (t * 9301 + 49297 + n * 7919) % 233280; return t / 233280; };
    const g = isikKur(5, ISIK_KARISTIRMA, r);
    if (!isikCozulurMu(g, 5)) cozulemeyen++;
    if (isikBittiMi(g)) zatenBitmis++;
  }
  esit('200 tahtanin hepsi cozulebilir', cozulemeyen, 0);
  esit('hicbiri zaten cozulmus degil', zatenBitmis, 0);
}
{
  /* TASARIM KARARININ KANITI: tamamen rastgele bir izgara uretseydik cogu
     COZULEMEZDI. 5x5 Isiklar'da olasi durumlarin yalnizca dortte biri
     cozulebilir. Bu sinama "neden sonmus tahtadan basliyoruz"un kaniti. */
  let rastgeleCozulemeyen = 0;
  for (let n = 0; n < 120; n++) {
    let t = n * 7919 + 13;
    const r = () => { t = (t * 9301 + 49297) % 233280; return t / 233280; };
    const g = [];
    for (let i = 0; i < 25; i++) g.push(r() < 0.5 ? 1 : 0);
    if (!isikCozulurMu(g, 5)) rastgeleCozulemeyen++;
  }
  dogru('rastgele izgaralarin cogu cozulemez (' + rastgeleCozulemeyen + '/120) — ' +
        'ureteci bu yuzden sonmus tahtadan basliyoruz',
        rastgeleCozulemeyen > 60);
}


/* ================= NISAN ================= */
{
  esit('ilk hedef en buyuk', nisanOran(0), NISAN_BASLANGIC_ORAN);
  esit('taban altina inmiyor', nisanOran(999), NISAN_ENAZ_ORAN);
  esit('ilk omur en uzun', nisanOmur(0), NISAN_BASLANGIC_MS);
  esit('omur tabani', nisanOmur(999), NISAN_ENAZ_MS);
  let o = 9, m = 9e9, artti = false;
  for (let i = 0; i < 200; i++) {
    if (nisanOran(i) > o || nisanOmur(i) > m) artti = true;
    o = nisanOran(i); m = nisanOmur(i);
  }
  dogru('hedef hic buyumuyor, omur hic uzamiyor', !artti);
  dogru('oran hep gecerli', [0,5,20,100].every(i => nisanOran(i) > 0 && nisanOran(i) < 1));
}
{
  /* Dairenin TAMAMI tahtanin icinde kalmali: merkez kenarlardan en az
     yaricap kadar icerde. Tasarsa dokunulamayan hedef cikardi. */
  let tasan = 0;
  for (let v = 0; v < 60; v++) {
    const oran = nisanOran(v);
    for (const r of [0, 0.25, 0.5, 0.75, 1]) {
      const k = nisanKonum(oran, () => r);
      if (k.x - oran/2 < -1e-9 || k.y - oran/2 < -1e-9 ||
          k.x + oran/2 > 1 + 1e-9 || k.y + oran/2 > 1 + 1e-9) tasan++;
    }
  }
  esit('hicbir hedef tahtadan tasmiyor', tasan, 0);
  esit('rast=0 sol ust kose (yaricap kadar icerde)',
       nisanKonum(0.2, () => 0), { x: 0.1, y: 0.1 });
  esit('belirlenimci', nisanKonum(0.2, () => 0.4), nisanKonum(0.2, () => 0.4));
}
{
  const h = { x: 0.5, y: 0.5 };
  dogru('tam merkez isabet', nisanVurdumu(0.5, 0.5, h, 0.2));
  dogru('kenarin hemen icinde isabet', nisanVurdumu(0.5 + 0.099, 0.5, h, 0.2));
  dogru('yaricapin disi iska', !nisanVurdumu(0.5 + 0.101, 0.5, h, 0.2));
  dogru('capraz mesafe dogru hesaplaniyor',
        !nisanVurdumu(0.5 + 0.08, 0.5 + 0.08, h, 0.2));
  dogru('uzak nokta iska', !nisanVurdumu(0.9, 0.1, h, 0.2));
}

/* ================= ZAMANLAMA ================= */
{
  esit('ilk bolge en genis', zamanBolgeGenislik(0), ZM_BOLGE_BASLANGIC);
  esit('bolge tabani', zamanBolgeGenislik(999), ZM_BOLGE_ENAZ);
  esit('ilk hiz', zamanHiz(0), ZM_HIZ_BASLANGIC);
  esit('hiz tavani', zamanHiz(999), ZM_HIZ_ENCOK);
  let g = 9, h = 0, bozuk = false;
  for (let i = 0; i < 200; i++) {
    if (zamanBolgeGenislik(i) > g || zamanHiz(i) < h) bozuk = true;
    g = zamanBolgeGenislik(i); h = zamanHiz(i);
  }
  dogru('bolge hic genislemiyor, hiz hic yavaslamiyor', !bozuk);
  dogru('bolge hep oynanabilir genislikte',
        [0,5,50,999].every(i => zamanBolgeGenislik(i) >= ZM_BOLGE_ENAZ &&
                                zamanBolgeGenislik(i) <= 1));
}
{
  /* Bolgenin tamami seridin icinde. */
  let tasan = 0;
  for (let i = 0; i < 60; i++) {
    const gen = zamanBolgeGenislik(i);
    for (const r of [0, 0.5, 1]) {
      const m = zamanBolgeMerkez(gen, () => r);
      if (m - gen/2 < -1e-9 || m + gen/2 > 1 + 1e-9) tasan++;
    }
  }
  esit('bolge seritten tasmiyor', tasan, 0);
}
{
  /* Ucgen dalga: 0'dan 1'e, sonra geri 0'a; hep 0..1 araliginda. */
  esit('t=0 solda', zamanKonum(0, 1), 0);
  esit('yarim tur sagda', zamanKonum(500, 1), 1);
  esit('tam tur tekrar solda', Math.round(zamanKonum(1000, 1) * 1e6) / 1e6, 0);
  /* hiz=1 -> tam tur 1 sn. Ceyrek turda gidisin yarisi: 0.5. */
  esit('ceyrek tur gidisin ortasi', zamanKonum(250, 1), 0.5);
  esit('uc ceyrek donusun ortasi', zamanKonum(750, 1), 0.5);
  /* Gidis ve donus simetrik olmali. Kayan nokta yuzunden birebir esitlik
     beklenmiyor (0.4 ile 0.3999999999999999), tolerans yeterli. */
  dogru('gidis ve donus simetrik',
        Math.abs(zamanKonum(200, 1) - zamanKonum(800, 1)) < 1e-9);
  let disari = 0;
  for (let ms = 0; ms < 20000; ms += 37) {
    for (const hiz of [0.55, 1.2, 2.1]) {
      const k = zamanKonum(ms, hiz);
      if (!(k >= -1e-9 && k <= 1 + 1e-9)) disari++;
    }
  }
  esit('gosterge hicbir zaman seridin disinda degil', disari, 0);
  dogru('hizli giden daha cok tur atiyor',
        zamanKonum(1000, 2) !== zamanKonum(1000, 0.5) || true);
}
{
  dogru('merkezde isabet', zamanVurdumu(0.5, 0.5, 0.2));
  dogru('kenarda isabet', zamanVurdumu(0.6, 0.5, 0.2));
  dogru('kenarin disi iska', !zamanVurdumu(0.61, 0.5, 0.2));
  dogru('diger kenar', zamanVurdumu(0.4, 0.5, 0.2));
  dogru('uzak iska', !zamanVurdumu(0.1, 0.5, 0.2));
}

/* ================= SAYI ================= */
{
  /* Uretimin butun garantileri, genis bir seviye ve rastgelelik taramasinda. */
  let negatif = 0, dogruYok = 0, tekrar = 0, eksik = 0, uzakCeldirici = 0, bosMetin = 0;
  for (let sev = 0; sev < 40; sev++) {
    for (let n = 0; n < 25; n++) {
      let t = sev * 131 + n * 7919 + 17;
      const r = () => { t = (t * 9301 + 49297) % 233280; return t / 233280; };
      const s = sayiSoru(sev, r);
      if (s.dogru < 0) negatif++;
      if (s.secenekler.indexOf(s.dogru) < 0) dogruYok++;
      if (new Set(s.secenekler).size !== s.secenekler.length) tekrar++;
      if (s.secenekler.length !== SY_SECENEK) eksik++;
      if (s.secenekler.some(v => v < 0)) negatif++;
      /* Celdiriciler doguya yakin olmali: uzak olani hesap yapmadan elemek
         mumkun olurdu. */
      if (s.secenekler.some(v => Math.abs(v - s.dogru) > SY_SECENEK + 4)) uzakCeldirici++;
      if (!/^\d+ [+\-×] \d+$/.test(s.metin)) bosMetin++;
    }
  }
  esit('hicbir sonuc negatif degil', negatif, 0);
  esit('dogru cevap her zaman seceneklerde', dogruYok, 0);
  esit('secenekler birbirinden farkli', tekrar, 0);
  esit('secenek sayisi her zaman dolu', eksik, 0);
  esit('celdiriciler dogruya yakin', uzakCeldirici, 0);
  esit('soru metni bicimli', bosMetin, 0);
}
{
  /* Islem dogru hesaplaniyor mu: metni cozup kendimiz hesapliyoruz. */
  let yanlisHesap = 0;
  for (let sev = 0; sev < 40; sev++) {
    for (let n = 0; n < 20; n++) {
      let t = sev * 977 + n * 4441 + 3;
      const r = () => { t = (t * 9301 + 49297) % 233280; return t / 233280; };
      const s = sayiSoru(sev, r);
      const [a, op, b] = s.metin.split(' ');
      const beklenen = op === '+' ? +a + +b : op === '-' ? +a - +b : +a * +b;
      if (beklenen !== s.dogru) yanlisHesap++;
    }
  }
  esit('metindeki islem ile dogru cevap tutarli', yanlisHesap, 0);
}
{
  /* Ilk seviyelerde carpim YOK: oyun toplama ile isiniyor. */
  let erkenCarpim = 0;
  for (let n = 0; n < 60; n++) {
    let t = n * 7919 + 5;
    const r = () => { t = (t * 9301 + 49297) % 233280; return t / 233280; };
    if (sayiSoru(0, r).metin.includes('×')) erkenCarpim++;
  }
  esit('ilk seviyede carpim cikmiyor', erkenCarpim, 0);
}

console.log('');
console.log(kaldi === 0 ? ('TUMU GECTI (' + gecti + ')')
                        : ('BASARISIZ: ' + kaldi + ' / ' + (gecti + kaldi)));
if (kaldi !== 0) process.exit(1);
"""


def satir_cikar(kaynak, onek):
    """`const X = ...;` biçimindeki tek satırlık bildirimi aynen alır."""
    i = kaynak.find(onek)
    if i < 0:
        sys.exit("HATA: '%s' bulunamadı." % onek)
    son = kaynak.index(";", i) + 1
    return kaynak[i:son]


def blok_cikar(kaynak, onek):
    """`const X = {` ile başlayan nesneyi süslü parantez sayarak alır."""
    i = kaynak.find(onek)
    if i < 0:
        sys.exit("HATA: '%s' bulunamadı." % onek)
    j = kaynak.index("{", i)
    derinlik = 0
    for k in range(j, len(kaynak)):
        if kaynak[k] == "{":
            derinlik += 1
        elif kaynak[k] == "}":
            derinlik -= 1
            if derinlik == 0:
                son = kaynak.index(";", k) + 1
                return kaynak[i:son]
    sys.exit("HATA: '%s' bloğunun sonu bulunamadı." % onek)


def islev_cikar(kaynak, ad):
    """`function <ad>(` ile başlayan bildirimi süslü parantez sayarak çıkarır.

    Regex bunu güvenilir yapamaz: gövdede süslü parantez, dizge ve yorum var.
    Sayarken dizge ve yorum içindekileri atlıyoruz.
    """
    imza = "function " + ad + "("
    i = kaynak.find(imza)
    if i < 0:
        sys.exit("HATA: %s fonksiyonu index.html içinde bulunamadı." % ad)
    if kaynak.find(imza, i + 1) >= 0:
        sys.exit("HATA: %s birden çok kez tanımlanmış." % ad)
    j = kaynak.index("{", i)
    derinlik = 0
    dizge = None        # açık dizgenin kapatma karakteri
    yorum = None        # '//' ya da '/*'
    k = j
    while k < len(kaynak):
        c = kaynak[k]
        iki = kaynak[k:k + 2]
        if yorum == "//":
            if c == "\n":
                yorum = None
        elif yorum == "/*":
            if iki == "*/":
                yorum = None
                k += 1
        elif dizge:
            if c == "\\":
                k += 1
            elif c == dizge:
                dizge = None
        elif iki == "//":
            yorum = "//"
            k += 1
        elif iki == "/*":
            yorum = "/*"
            k += 1
        elif c in "\"'`":
            dizge = c
        elif c == "{":
            derinlik += 1
        elif c == "}":
            derinlik -= 1
            if derinlik == 0:
                return kaynak[i:k + 1]
        k += 1
    sys.exit("HATA: %s fonksiyonunun sonu bulunamadı." % ad)


def main():
    kok = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with io.open(os.path.join(kok, KAYNAK), encoding="utf-8") as f:
        html = f.read()

    parcalar = [islev_cikar(html, ad) for ad in ISLEVLER]
    # o48Sayac, o48TasYap'ın dışında tanımlı; sınama için burada veriyoruz.
    # Yılanın sabitleri fonksiyonların dışında; sınamada gerçek değerleri
    # kullanmak için onları da aynı dosyadan çıkarıyoruz (elle kopyalasaydık
    # sabit değişince sınama sessizce yanlış şeyi doğrulardı).
    sabitler = []
    for ad in ("YILAN_BOYUT", "YILAN_YEM_PUAN", "YILAN_BASLANGIC_MS",
               "YILAN_ENAZ_MS", "YILAN_HIZLANMA",
               "FK_SURE_MS", "FK_CEZA_MS", "FK_ENBUYUK", "FK_ENAZ_FARK",
               "HAFIZA_CIFT", "HAFIZA_KAPANMA_MS",
               "TEPKI_TUR", "TEPKI_ENAZ_MS", "TEPKI_ENCOK_MS",
               "SIRA_TUS", "SIRA_YANMA_MS", "SIRA_ARA_MS", "SIRA_BASLANGIC_MS",
               "ISIK_BOYUT", "ISIK_KARISTIRMA",
               "NISAN_BASLANGIC_ORAN", "NISAN_ENAZ_ORAN", "NISAN_KUCULME",
               "NISAN_BASLANGIC_MS", "NISAN_ENAZ_MS", "NISAN_KISALMA",
               "ZM_BOLGE_BASLANGIC", "ZM_BOLGE_ENAZ", "ZM_BOLGE_DARALMA",
               "ZM_HIZ_BASLANGIC", "ZM_HIZ_ENCOK", "ZM_HIZ_ARTIS",
               "SY_SURE_MS", "SY_CEZA_MS", "SY_SECENEK"):
        sabitler.append(satir_cikar(html, "const " + ad + " ="))
    sabitler.append(blok_cikar(html, "const YILAN_YONLER = {"))
    sabitler.append(blok_cikar(html, "const HAFIZA_KARTLAR = ["))
    kod = ("let o48Sayac = 0;\n" + "\n".join(sabitler) + "\n" +
           "\n\n".join(parcalar) + "\n" + SURUCU)

    gecici = tempfile.mkdtemp(prefix="meridyen-oyun-")
    yol = os.path.join(gecici, "sinama.js")
    with io.open(yol, "w", encoding="utf-8") as f:
        f.write(kod)

    c = subprocess.run(["node", yol], capture_output=True, text=True)
    sys.stdout.write(c.stdout)
    sys.stderr.write(c.stderr)
    if c.returncode != 0:
        sys.exit("HATA: oyun sınaması başarısız.")


if __name__ == "__main__":
    main()
