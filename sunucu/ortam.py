"""`.env` dosyasını okur — paketsiz.

Sunucu ayarlarını ortam değişkenlerinden alıyor. Bu dosya, sunucunun yanındaki
`.env`'i (ya da MERIDYEN_ENV_DOSYASI'nın gösterdiğini) okuyup eksik
değişkenleri dolduruyor; böylece elle çalıştırırken `set -a; . ./.env` ile
uğraşmak gerekmiyor ve systemd de aynı dosyayı aynı kurallarla okumuş oluyor.

Kurallar bilerek basit:
  - `AD=değer` satırları; boş satırlar ve `#` ile başlayanlar atlanır;
    başta `export ` olabilir.
  - Değer tek ya da çift tırnak içindeyse tırnaklar atılır; içi OLDUĞU GİBİ
    kalır (kaçış, `$DEĞİŞKEN` açılımı yok).
  - Tırnaksız değer de olduğu gibi alınır. Kabuk bunu yapmıyor: anahtarın
    JSON içeriğini tek satır yazınca kabuk tırnakları yutup JSON'u
    bozuyordu; burada `MERIDYEN_SERVIS_HESABI={"type": ...}` bozulmadan gelir.
  - Ortamda ZATEN tanımlı bir değişkenin üstüne yazılmaz: komut satırından ya
    da hizmet tanımından verilen değer her zaman kazanır.
"""
from __future__ import annotations

import os
import re

_SATIR = re.compile(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$')


def coz(metin: str) -> dict:
    """`.env` metnini {ad: değer} sözlüğüne çevirir."""
    cikti = {}
    for satir in metin.splitlines():
        if not satir.strip() or satir.lstrip().startswith('#'):
            continue
        m = _SATIR.match(satir)
        if not m:
            continue
        ad, deger = m.group(1), m.group(2)
        if len(deger) >= 2 and deger[0] == deger[-1] and deger[0] in ('"', "'"):
            deger = deger[1:-1]
        cikti[ad] = deger
    return cikti


def yukle(yol: str | None = None, ortam=None) -> str | None:
    """Dosyayı okuyup ortamda OLMAYAN değişkenleri ekler.

    Okunan dosyanın yolunu döndürür; dosya yoksa None (hata değil: ayarlar
    doğrudan ortamdan da verilebilir)."""
    ortam = os.environ if ortam is None else ortam
    yol = yol or ortam.get('MERIDYEN_ENV_DOSYASI') or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '.env')
    try:
        with open(yol, encoding='utf-8-sig') as f:
            degerler = coz(f.read())
    except FileNotFoundError:
        return None
    for ad, deger in degerler.items():
        if ad not in ortam:
            ortam[ad] = deger
    return yol
