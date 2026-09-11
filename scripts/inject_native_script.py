#!/usr/bin/env python3
"""Meridyen — bildirim köprüsünü DERLENEN index.html'e ekler.

`www/index.html` bilerek canlı sitedekiyle aynı tutuluyor; köprü oraya elle
eklenmiyor. `npx cap sync` web içeriğini android/app/src/main/assets/public
altına kopyaladıktan SONRA, yalnızca o kopyaya bir <script> satırı ekleniyor.

DİKKAT — BURADA BİR KEZ HATA YAPILDI, TEKRARLAMASIN:
Eskiden "zaten ekli mi?" denetimi dosya ADINI arıyordu (`if 'meridyen-native.js'
in html`). index.html içine o adı anan bir YORUM satırı eklenince betik
"zaten ekli" sanıp etiketi hiç koymadı. Köprü APK'ya giriyor ama sayfaya hiç
yüklenmiyordu: window.Notification tanımsız kalıyor, uygulama "Tarayıcın
desteklemiyor" diyor ve BÜTÜN bildirimler sessizce kayboluyordu.

Bu yüzden artık:
  1) Denetim dosya adını değil ETİKETİN KENDİSİNİ arıyor (düzenli ifadeyle).
  2) Var olan etiketler önce temizlenip tam bir tane ekleniyor — yani işlem
     tanım gereği idempotent, kaç kez çalıştırılırsa çalıştırılsın.
  3) İşin sonunda etiketin gerçekten orada olduğu DOĞRULANIYOR; değilse betik
     hata koduyla çıkıyor ve derleme kırılıyor. Sessiz başarısızlık yok.
"""
import re
import sys

HEDEF = sys.argv[1] if len(sys.argv) > 1 else "android/app/src/main/assets/public/index.html"
BETIK = "meridyen-native.js"
SATIR = '<script src="%s"></script>\n' % BETIK

# Tırnak türü, ek nitelikler ve boşluklar değişebilir; hepsini yakalayalım.
ETIKET_DESENI = re.compile(
    r'[ \t]*<script\b[^>]*\bsrc\s*=\s*["\']%s["\'][^>]*>\s*</script>[ \t]*\n?'
    % re.escape(BETIK),
    re.IGNORECASE,
)


def enjekte_et(html):
    """Köprü etiketini tam bir kez içeren HTML'i döndürür."""
    if "</head>" not in html:
        raise ValueError("index.html içinde </head> bulunamadı, köprü eklenemedi.")
    # Önce varsa eskileri temizle: böylece tekrar çalıştırmak etiketi çoğaltmaz.
    temiz = ETIKET_DESENI.sub("", html)
    # Köprü, uygulamanın kendi kodundan ÖNCE çalışmalı: `Notification` sınıfını
    # o kod ilk kez sorgulamadan yerine koymuş olması gerekiyor. Sayfadaki tek
    # <script> gövdede, çok daha sonra.
    return temiz.replace("</head>", SATIR + "</head>", 1)


def main():
    with open(HEDEF, encoding="utf-8") as f:
        html = f.read()

    onceki = len(ETIKET_DESENI.findall(html))
    yeni = enjekte_et(html)

    # DOĞRULAMA: etiket gerçekten ve tam bir kez orada mı?
    adet = len(ETIKET_DESENI.findall(yeni))
    if adet != 1:
        sys.exit("HATA: köprü etiketi %d kez bulundu (1 olmalıydı)." % adet)

    with open(HEDEF, "w", encoding="utf-8") as f:
        f.write(yeni)

    if onceki:
        print("köprü etiketi yenilendi (%d eski etiket temizlendi)." % onceki)
    else:
        print("köprü eklendi:", SATIR.strip())


if __name__ == "__main__":
    main()
