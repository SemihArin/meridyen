#!/usr/bin/env python3
"""Meridyen — index.html'deki kural kopyası ile database.rules.json aynı mı?

index.html'in başındaki yorum bloğu, veritabanı kurallarının kopyala-yapıştır
kopyasını taşıyor. Dosyanın kendisi bunun neden tehlikeli olduğunu yazıyor:
ikisi birbirinden saparsa, biri oradaki ESKİ ve gevşek kuralları konsola
yapıştırıp daha önce kapatılmış bir açığı kendi eliyle yeniden açabilir.

Uyarı yazmak yeterli değil — unutmak bedava, hatırlamak değil. Bu sınama
ikisini de ayrıştırıp (yorumdaki metni JSON olarak okuyup) karşılaştırıyor ve
saptıklarında derlemeyi kırıyor. Karşılaştırma ANLAM düzeyinde: boşluk,
girinti ve anahtar sırası önemsiz, içerik önemli.
"""
import io
import json
import re
import sys

HTML = "www/index.html"
KURAL = "database.rules.json"


def yorumdan_cikar(html):
    """Yorum bloğundaki `{ "rules": { ... } }` gövdesini bulur.

    Blok dengeli süslü parantezlerle sınırlı; başlangıçtan itibaren sayarak
    sonunu buluyoruz (regex bunu güvenilir yapamaz).
    """
    i = html.find('"rules"')
    if i < 0:
        sys.exit("HATA: index.html içinde kural kopyası bulunamadı.")
    bas = html.rfind("{", 0, i)
    if bas < 0:
        sys.exit("HATA: kural kopyasının açılış parantezi bulunamadı.")
    derinlik = 0
    for j in range(bas, len(html)):
        if html[j] == "{":
            derinlik += 1
        elif html[j] == "}":
            derinlik -= 1
            if derinlik == 0:
                return html[bas:j + 1]
    sys.exit("HATA: kural kopyasının kapanış parantezi bulunamadı.")


def farklari_yaz(a, b, yol=""):
    """İki kural ağacını karşılaştırır, insanın okuyabileceği farklar üretir."""
    farklar = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            alt = yol + "/" + k
            if k not in a:
                farklar.append("yalnız database.rules.json'da: " + alt)
            elif k not in b:
                farklar.append("yalnız index.html'de: " + alt)
            else:
                farklar += farklari_yaz(a[k], b[k], alt)
    elif a != b:
        farklar.append("farklı değer: %s\n      rules.json: %r\n      index.html: %r" % (yol, a, b))
    return farklar


def main():
    with io.open(HTML, encoding="utf-8") as f:
        html = f.read()
    with io.open(KURAL, encoding="utf-8") as f:
        dosya = json.load(f)

    ham = yorumdan_cikar(html)
    try:
        yorum = json.loads(ham)
    except ValueError as e:
        sys.exit("HATA: index.html'deki kural kopyası geçerli JSON değil: %s" % e)

    if "rules" not in yorum:
        sys.exit("HATA: index.html'deki kopyada 'rules' anahtarı yok.")

    farklar = farklari_yaz(dosya["rules"], yorum["rules"])
    if farklar:
        print("index.html'deki kural kopyası database.rules.json ile AYNI DEĞİL:")
        for f2 in farklar:
            print("  - " + f2)
        sys.exit("HATA: %d fark var. İkisini birden güncelle." % len(farklar))

    print("kural kopyası database.rules.json ile birebir aynı (%d düğüm)."
          % len(dosya["rules"]))


if __name__ == "__main__":
    main()
