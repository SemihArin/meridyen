#!/usr/bin/env python3
"""Meridyen — akış: beğen/beğenme geçişi, göreli zaman, uzun metin kesme.

Beğen/beğenme birbirini dışlıyor ve kural bunu zorluyor. Geçiş tek atomik
yazmayla yapılmazsa kural ilk yazmayı reddeder ve kullanıcı "bastım ama
olmadı" der; geçiş gerekmeyen durumda da eski tek yollu yazma korunmalı
(beğenmeme kuralı konsola yapıştırılmadan beğeni bozulmasın). Gerçek
fonksiyonlar index.html'den çıkarılıp Node'da koşuyor.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from test_oyun import islev_cikar  # noqa: E402

html = open("www/index.html", encoding="utf-8").read()
js = "\n".join(islev_cikar(html, ad) for ad in
               ("akisTepkiVer", "akisZamani", "gonderiMetniUzunMu"))
js += r"""
const sonuc = []; const ok = (ad, k) => sonuc.push([ad, !!k]);
let yazilan, bildirimler;
const ben = { uid: 'BEN' }, benimAdim = 'Semih';
const bildir = () => {};
const bildirimYaz = (...a) => bildirimler.push(a);
const ref = (y) => ({
  set: async (v) => yazilan.push(['set', y, v]),
  remove: async () => yazilan.push(['remove', y]),
  update: async (v) => yazilan.push(['update', y, v])
});
const db = { ref: (y) => ref(y || '') };
let begeniVerisi, begenmemeVerisi;
const dene = (durum, tur, sahip) => {
  yazilan = []; bildirimler = [];
  begeniVerisi = { p: durum === 'begendi' ? { BEN: true } : {} };
  begenmemeVerisi = { p: durum === 'begenmedi' ? { BEN: true } : {} };
  akisTepkiVer('p', { uid: sahip || 'O', metin: 'm' }, tur);
  return yazilan;
};
const B = 'akisBegeni/p/BEN', BM = 'akisBegenmeme/p/BEN';
let y;
y = dene('yok', 'begeni');
ok('hiçbiri → beğen: tek yol set', y.length === 1 && y[0][0] === 'set' && y[0][1] === B);
ok('beğenince sahibine bildirim', bildirimler.length === 1);
y = dene('begendi', 'begeni');
ok('beğenmiş → beğen: geri al', y.length === 1 && y[0][0] === 'remove' && y[0][1] === B);
ok('geri almada bildirim yok', bildirimler.length === 0);
y = dene('begenmedi', 'begeni');
ok('beğenmemiş → beğen: TEK atomik geçiş', y.length === 1 && y[0][0] === 'update' &&
   y[0][2][B] === true && y[0][2][BM] === null);
y = dene('yok', 'begenmeme');
ok('hiçbiri → beğenme: tek yol set', y.length === 1 && y[0][0] === 'set' && y[0][1] === BM);
ok('beğenmeme bildirim GÖNDERMİYOR', bildirimler.length === 0);
y = dene('begendi', 'begenmeme');
ok('beğenmiş → beğenme: TEK atomik geçiş', y.length === 1 && y[0][0] === 'update' &&
   y[0][2][BM] === true && y[0][2][B] === null);
ok('geçişte de bildirim yok', bildirimler.length === 0);
y = dene('begenmedi', 'begenmeme');
ok('beğenmemiş → beğenme: geri al', y.length === 1 && y[0][0] === 'remove' && y[0][1] === BM);
dene('yok', 'begeni', 'BEN');
ok('kendi gönderini beğenince bildirim yok', bildirimler.length === 0);

const kisaZaman = () => 'KISA';
const S = 1e12;
ok('30 sn → şimdi', akisZamani(S - 30000, S) === 'şimdi');
ok('3 dk', akisZamani(S - 3 * 60000 - 5000, S) === '3 dk');
ok('59 dk', akisZamani(S - 59 * 60000, S) === '59 dk');
ok('5 sa', akisZamani(S - 5 * 3600000 - 1, S) === '5 sa');
ok('1 günden eski → kisaZaman', akisZamani(S - 25 * 3600000, S) === 'KISA');
ok('saat ileride → şimdi (eksi değil)', akisZamani(S + 5000, S) === 'şimdi');
ok('zaman yok → boş', akisZamani(0, S) === '');

ok('kısa metin kesilmiyor', !gonderiMetniUzunMu('merhaba'));
ok('200 karakter kesilmiyor', !gonderiMetniUzunMu('a'.repeat(200)));
ok('400 karakter kesiliyor', gonderiMetniUzunMu('a'.repeat(400)));
ok('8 kısa satır kesiliyor', gonderiMetniUzunMu('a\nb\nc\nd\ne\nf\ng\nh'));
ok('metin yok', !gonderiMetniUzunMu(''));
console.log(JSON.stringify(sonuc));
"""
cikti = subprocess.run(["node", "-e", js], capture_output=True, text=True)
if cikti.returncode:
    sys.exit(cikti.stderr)
sonuc = json.loads(cikti.stdout)
for ad, k in sonuc:
    print(("  ✓ " if k else "  ✗ ") + ad)
kotu = [a for a, k in sonuc if not k]
print(f"\n  {len(kotu)} BAŞARISIZ" if kotu else f"\n  TUMU GECTI ({len(sonuc)})")
sys.exit(1 if kotu else 0)
