#!/usr/bin/env python3
"""Meridyen — mesaj bildirimi id'si iki tarafta da AYNI mı?

Bir mesaj bildirimi iki ayrı yerden çıkabiliyor:
  - uygulama açıkken  : web tarafı (meridyen-native.js, `etiketId`)
  - uygulama kapalıyken: native taraf (MeridyenBildirimler.java, `etiketId`)

İkisi aynı etiket için aynı sayıyı üretmezse Android bunları AYRI bildirim
sayar ve aynı mesaj için iki bildirim görünür. İki ayrı dilde elle yazılmış
iki karma fonksiyonu olduğu için bu sessizce ayrışmaya çok açık — bu yüzden
sınanıyor.

Yöntem: iki fonksiyon da GERÇEK kaynak dosyalardan çıkarılıp çalıştırılıyor,
kopyaları sınanmıyor. Girdi, kod birimi listesi olarak veriliyor: JVM'in
komut satırı argümanlarını platform kodlamasıyla çözmesi (ASCII ortamlarda
Türkçe harfleri bozuyor) sonucu etkilemesin.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile

JAVA_KAYNAK = "android-assets/java/MeridyenBildirimler.java"
JS_KAYNAK = "www/meridyen-native.js"

ETIKETLER = [
    "meridyen-abc123",
    "meridyen-",
    "meridyen-sinama",
    "meridyen-ZzYyXx000111",
    "meridyen-ünlüğüşç",
    "",
    "meridyen-msg-0:1699999999999999%abcdef",
    "meridyen-9999999999999999999999999999",
    "meridyen-😀emoji",
    "meridyen-ÇĞİÖŞÜçğıöşü",
    "meridyen-" + "x" * 500,
]


def govde_cikar(yol, bas, son_isaret):
    with io.open(yol, encoding="utf-8") as f:
        kaynak = f.read()
    i = kaynak.index(bas)
    j = kaynak.index(son_isaret, i) + len(son_isaret)
    return kaynak[i:j]


def main():
    if not shutil.which("javac") or not shutil.which("node"):
        sys.exit("HATA: bu sınama için javac ve node gerekiyor.")

    java_govde = govde_cikar(JAVA_KAYNAK, "public static int etiketId(String etiket) {", "\n    }")
    js_govde = govde_cikar(JS_KAYNAK, "function etiketId(etiket) {", "\n  }")

    kodlu = [",".join(str(ord(c)) for c in e) for e in ETIKETLER]

    gecici = tempfile.mkdtemp(prefix="meridyen-id-")
    try:
        with io.open(os.path.join(gecici, "Idt.java"), "w", encoding="utf-8") as f:
            f.write(
                "public class Idt {\n" + java_govde + "\n"
                "  public static void main(String[] a) {\n"
                "    for (String satir : a) {\n"
                "      StringBuilder sb = new StringBuilder();\n"
                "      if (satir.length() > 0) for (String p : satir.split(\",\")) "
                "sb.append((char) Integer.parseInt(p));\n"
                "      System.out.println(etiketId(sb.toString()));\n"
                "    }\n"
                "  }\n"
                "}\n"
            )
        with io.open(os.path.join(gecici, "idt.js"), "w", encoding="utf-8") as f:
            f.write(
                js_govde + "\n"
                "process.argv.slice(2).forEach(function (satir) {\n"
                "  var s = satir === '' ? '' : satir.split(',').map(function (p) "
                "{ return String.fromCharCode(+p); }).join('');\n"
                "  console.log(etiketId(s));\n"
                "});\n"
            )

        subprocess.check_call(
            ["javac", "-encoding", "UTF-8", "Idt.java"], cwd=gecici,
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        j = subprocess.check_output(["java", "Idt"] + kodlu, cwd=gecici,
                                    stderr=subprocess.DEVNULL).decode().split()
        n = subprocess.check_output(["node", "idt.js"] + kodlu, cwd=gecici).decode().split()
    finally:
        shutil.rmtree(gecici, ignore_errors=True)

    if len(j) != len(ETIKETLER) or len(n) != len(ETIKETLER):
        sys.exit("HATA: sonuç sayısı beklenenden farklı (java=%d js=%d)" % (len(j), len(n)))

    hata = 0
    for etiket, a, b in zip(ETIKETLER, j, n):
        kisa = etiket if len(etiket) <= 40 else etiket[:37] + "..."
        if a == b:
            print("  eşit   %-12s <- %s" % (a, kisa))
        else:
            print("  FARKLI java=%s js=%s <- %s" % (a, b, kisa))
            hata += 1

    if hata:
        sys.exit("HATA: %d etikette native ve web id'leri ayrışıyor." % hata)

    # Mesaj id'leri, gönderim ilerleme bildiriminin bandına (1.9 milyar ve
    # üstü, bkz. MeridyenIlerleme.BILDIRIM_ID) ASLA girmemeli: girerse
    # gönderim bildirimi bir mesaj bildirimini ezer ya da tersi.
    for etiket, a in zip(ETIKETLER, j):
        if not (0 < int(a) < 1900000000):
            sys.exit("HATA: id bandın dışında (%s <- %s)" % (a, etiket))
    print("bildirim id'leri iki tarafta da aynı (%d/%d)." % (len(ETIKETLER), len(ETIKETLER)))


if __name__ == "__main__":
    main()
