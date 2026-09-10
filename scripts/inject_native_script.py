#!/usr/bin/env python3
"""Meridyen — bildirim köprüsünü DERLENEN index.html'e ekler.

`www/index.html` bilerek canlı sitedekiyle BİREBİR aynı tutuluyor; siteyi
güncellediğinde dosyayı olduğu gibi kopyalayabilmen için. Bu yüzden köprü
(`meridyen-native.js`) oraya elle eklenmiyor — `npx cap sync` web içeriğini
android/app/src/main/assets/public altına kopyaladıktan SONRA, yalnızca o
kopyaya bir <script> satırı ekleniyor.

Böylece: depodaki index.html el değmemiş kalıyor, APK'daki kopya ise köprüyü
yüklüyor. Betik idempotent — satır zaten varsa tekrar eklemiyor.
"""
import sys

HEDEF = sys.argv[1] if len(sys.argv) > 1 else "android/app/src/main/assets/public/index.html"
BETIK = "meridyen-native.js"
SATIR = '<script src="%s"></script>\n' % BETIK

with open(HEDEF, encoding="utf-8") as f:
    html = f.read()

if BETIK in html:
    print("köprü zaten ekli, dokunulmadı.")
    sys.exit(0)

# Köprü, uygulamanın kendi kodundan ÖNCE çalışmalı: `Notification` sınıfını
# o kod ilk kez sorgulamadan yerine koymuş olması gerekiyor. </head> bunun
# için en güvenli yer — sayfadaki tek <script> gövdede, çok daha sonra.
if "</head>" not in html:
    sys.exit("HATA: index.html içinde </head> bulunamadı, köprü eklenemedi.")

html = html.replace("</head>", SATIR + "</head>", 1)

with open(HEDEF, "w", encoding="utf-8") as f:
    f.write(html)

print("köprü eklendi:", SATIR.strip())
