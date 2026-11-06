#!/usr/bin/env python3
"""Meridyen — biriken bildirimin kuralları doğru mu?

Bildirimler eskiden birbirinin üstüne yazıyordu: aynı sohbetin ikinci mesajı
birincinin yerine geçiyor, okunmayan mesaj sessizce kayboluyordu. Artık
sohbet başına tek bildirim var ama mesajlar İÇİNDE birikiyor.

Bu davranışın doğrudan gözlenebileceği tek yer bir telefon; burada cihaz yok.
Bu yüzden biriktirme kuralları Android'e hiç dokunmayan saf metotlara ayrıldı
(MeridyenBildirimler: depoyaEkle, depodanSil, ozetSatirlari, ozetMesajSayisi,
ozetGerekliMi) ve bu sınama onları GERÇEK kaynak dosyadan çıkarıp çalıştırıyor
— kopyasını değil.

Sınanan kurallar:
  - aynı sohbetin ikinci mesajı birincinin üstüne YAZMIYOR, ekleniyor
  - farklı sohbetler ayrı ayrı birikiyor
  - üst sınır aşılınca EN ESKİ satır atılıyor (yenisi değil)
  - sohbet açılınca yalnız o sohbetin birikimi düşüyor
  - özet yalnız birden çok sohbet varken gerekiyor
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

KAYNAK = "android-assets/java/MeridyenBildirimler.java"

# android.jar'daki org.json yalnız bir İSKELET: her metodu "Stub!" diye hata
# fırlatıyor, masaüstünde çalıştırılamıyor. Bu yüzden gerçek uygulamayı
# indiriyoruz. Sürüm sabit: sınamanın bir gün sessizce başka bir sürümle
# koşmasını istemiyoruz.
JSON_URL = "https://repo1.maven.org/maven2/org/json/json/20240303/json-20240303.jar"
JSON_ONBELLEK = os.path.join(tempfile.gettempdir(), "meridyen-org-json-20240303.jar")


def json_kavanozu():
    """org.json kavanozunu getirir; ağ takılırsa birkaç kez dener."""
    if os.path.isfile(JSON_ONBELLEK) and os.path.getsize(JSON_ONBELLEK) > 20000:
        return JSON_ONBELLEK
    son = None
    for deneme in range(4):
        try:
            with urllib.request.urlopen(JSON_URL, timeout=30) as y:
                veri = y.read()
            if len(veri) < 20000:
                raise ValueError("kavanoz beklenenden küçük: %d bayt" % len(veri))
            with open(JSON_ONBELLEK, "wb") as f:
                f.write(veri)
            return JSON_ONBELLEK
        except Exception as e:          # ağ hatası: artan beklemeyle yeniden dene
            son = e
            time.sleep(2 ** deneme)
    sys.exit("HATA: org.json kavanozu indirilemedi (%s). Sınama koşturulamadı." % son)

METOTLAR = [
    ("static String depoyaEkle(", "\n    }"),
    ("static String depodanSil(", "\n    }"),
    ("static List<String> ozetSatirlari(", "\n    }"),
    ("static int ozetMesajSayisi(", "\n    }"),
    ("static boolean ozetGerekliMi(", "\n    }"),
    ("static boolean gorulduMu(", "\n    }"),
    ("static String gorulenEkle(", "\n    }"),
    ("static String[] birikimeIsle(", "\n    }"),
    ("static boolean cagriBayatMi(", "\n    }"),
]

SURUCU = r"""
  static void esit(String ad, Object a, Object b) {
    if (a == null ? b == null : a.equals(b)) { System.out.println("OK    " + ad); }
    else { System.out.println("HATA  " + ad + " (beklenen " + b + ", gelen " + a + ")"); hata++; }
  }
  static int hata = 0;
  public static void main(String[] a) throws Exception {
    // aynı sohbete iki mesaj: ikincisi birincinin ÜSTÜNE yazmamalı
    String d = depoyaEkle("", 11, "Ayse", "UID1", "mesaj", "meridyen-UID1", "ilk", 1000);
    d = depoyaEkle(d, 11, "Ayse", "UID1", "mesaj", "meridyen-UID1", "ikinci", 2000);
    org.json.JSONObject o = new org.json.JSONObject(d);
    org.json.JSONArray s = o.getJSONObject("11").getJSONArray("satirlar");
    esit("aynı sohbette mesajlar birikiyor", s.length(), 2);
    esit("ilk mesaj duruyor", s.getJSONObject(0).getString("m"), "ilk");
    esit("ikinci mesaj sonda", s.getJSONObject(1).getString("m"), "ikinci");
    esit("tek sohbet", o.length(), 1);

    // farklı sohbet ayrı birikiyor
    d = depoyaEkle(d, 22, "Mehmet", "UID2", "mesaj", "meridyen-UID2", "selam", 3000);
    o = new org.json.JSONObject(d);
    esit("iki ayrı sohbet", o.length(), 2);
    esit("ilk sohbet etkilenmedi", o.getJSONObject("11").getJSONArray("satirlar").length(), 2);

    // üst sınır: en ESKİ atılmalı
    String u = "";
    for (int i = 1; i <= 12; i++) u = depoyaEkle(u, 33, "Cok", null, null, "e", "m" + i, i);
    org.json.JSONArray us = new org.json.JSONObject(u).getJSONObject("33").getJSONArray("satirlar");
    esit("üst sınır uygulanıyor", us.length(), ENCOK_SATIR);
    esit("en eski atıldı, en yeni duruyor",
         us.getJSONObject(us.length() - 1).getString("m"), "m12");
    esit("sınırın hemen dışındaki en eski satır gitti",
         us.getJSONObject(0).getString("m"), "m" + (12 - ENCOK_SATIR + 1));

    // özet satırları ve sayıları
    esit("özet satır sayısı sohbet kadar", ozetSatirlari(d).size(), 2);
    esit("özette son mesaj yazıyor", ozetSatirlari(d).get(0).contains("ikinci")
         || ozetSatirlari(d).get(1).contains("ikinci"), true);
    esit("toplam mesaj sayısı", ozetMesajSayisi(d), 3);
    esit("tek sohbette özet gerekmiyor", ozetGerekliMi(1), false);
    esit("iki sohbette özet gerekiyor", ozetGerekliMi(2), true);
    esit("hiç sohbet yokken özet gerekmiyor", ozetGerekliMi(0), false);

    // sohbet açılınca yalnız o sohbet düşer
    String k = depodanSil(d, 11);
    org.json.JSONObject ko = new org.json.JSONObject(k);
    esit("açılan sohbetin birikimi silindi", ko.has("11"), false);
    esit("öbür sohbet duruyor", ko.has("22"), true);
    esit("silmeden sonra özet gerekmiyor", ozetGerekliMi(ozetSatirlari(k).size()), false);

    // boş/bozuk depo çökertmemeli
    esit("boş depoya ekleme", new org.json.JSONObject(
        depoyaEkle(null, 44, "A", null, null, "e", "x", 1)).length(), 1);
    esit("boş depoda özet yok", ozetSatirlari("").size(), 0);

    // ---- TEKİLLEŞTİRME: aynı mesaj iki yoldan (uygulama + sunucu push'u) ----
    long t = 1_000_000L;
    String[] ilk = birikimeIsle("", "", 55, "Ayse", "U", "mesaj", "meridyen-U", "selam", t, "-MID1");
    esit("ilk yol mesajı gösterir", ilk != null, true);
    String[] ikinci = birikimeIsle(ilk[0], ilk[1], 55, "Ayse", "U", "mesaj", "meridyen-U", "selam", t + 300, "-MID1");
    esit("AYNI anahtarlı ikinci yol atlanır", ikinci == null, true);
    esit("birikimde tek satır kaldı",
         new org.json.JSONObject(ilk[0]).getJSONObject("55").getJSONArray("satirlar").length(), 1);
    String[] baska = birikimeIsle(ilk[0], ilk[1], 55, "Ayse", "U", "mesaj", "meridyen-U", "naber", t + 400, "-MID2");
    esit("farklı anahtarlı mesaj eklenir", baska != null
         && new org.json.JSONObject(baska[0]).getJSONObject("55").getJSONArray("satirlar").length() == 2, true);
    String[] anahtarsiz1 = birikimeIsle("", "", 66, "A", null, null, "e", "x", t, null);
    String[] anahtarsiz2 = birikimeIsle(anahtarsiz1[0], anahtarsiz1[1], 66, "A", null, null, "e", "x", t, null);
    esit("anahtarsız (eski istemci) mesaj ATLANMAZ — kaybolmasın", anahtarsiz2 != null, true);
    esit("anahtarsız mesaj görülenleri değiştirmez", anahtarsiz2[1], "");

    // Sohbet açılıp birikim silinse bile geç gelen kopya tanınmalı.
    String bosaltilmis = depodanSil(ilk[0], 55);
    esit("sohbet açıldıktan sonra geç gelen kopya yine atlanır",
         birikimeIsle(bosaltilmis, ilk[1], 55, "Ayse", "U", "mesaj", "meridyen-U", "selam", t + 9000, "-MID1") == null, true);
    esit("48 saatten eski anahtar unutulur",
         gorulduMu(ilk[1], "-MID1", t + GORULEN_OMUR_MS + 1), false);

    // Görülenler sınırsız büyümesin; en ESKİ düşsün.
    String g = "";
    for (int i = 0; i < GORULEN_SINIR + 25; i++) g = gorulenEkle(g, "k" + i, t + i);
    esit("görülenler üst sınırda", new org.json.JSONObject(g).length(), GORULEN_SINIR);
    esit("en eski düştü", gorulduMu(g, "k0", t + GORULEN_SINIR + 30), false);
    esit("en yeni duruyor", gorulduMu(g, "k" + (GORULEN_SINIR + 24), t + GORULEN_SINIR + 30), true);
    esit("bozuk/boş görülenler çökertmiyor", gorulduMu(null, "x", t), false);

    // ---- bayat çağrı push'u ----
    esit("az önceki çağrı bayat değil", cagriBayatMi(t - 20000, t), false);
    esit("2 dk önceki çağrı bayat", cagriBayatMi(t - 120000, t), true);
    esit("gönderim zamanı bilinmiyorsa çağrı kaçmasın", cagriBayatMi(0, t), false);
    esit("saat farkıyla gelecekte görünen çağrı bayat değil", cagriBayatMi(t + 5000, t), false);

    if (hata > 0) { System.out.println("\n" + hata + " BASARISIZ"); System.exit(1); }
    System.out.println("\nTUMU GECTI");
  }
"""


def main():
    if not shutil.which("javac"):
        sys.exit("HATA: bu sınama için javac gerekiyor.")
    json_jar = json_kavanozu()

    with io.open(KAYNAK, encoding="utf-8") as f:
        kaynak = f.read()

    # Sabitler de gerçek kaynaktan gelsin: sınama onları varsaymasın.
    def sabit(ad):
        i = kaynak.index(ad + " = ")
        return kaynak[i + len(ad + " = "):kaynak.index(";", i)].strip()
    encok = sabit("ENCOK_SATIR")

    govdeler = []
    for bas, son in METOTLAR:
        j = kaynak.index(bas)
        k = kaynak.index(son, j) + len(son)
        govdeler.append(kaynak[j:k])

    gecici = tempfile.mkdtemp(prefix="meridyen-biriken-")
    try:
        with io.open(os.path.join(gecici, "Bt.java"), "w", encoding="utf-8") as f:
            f.write("import org.json.JSONArray;\nimport org.json.JSONObject;\n"
                    "import java.util.ArrayList;\nimport java.util.List;\n\n"
                    "public class Bt {\n"
                    "  static final int ENCOK_SATIR = " + encok + ";\n"
                    "  static final long GORULEN_OMUR_MS = " + sabit("GORULEN_OMUR_MS") + ";\n"
                    "  static final int GORULEN_SINIR = " + sabit("GORULEN_SINIR") + ";\n"
                    + "\n".join("  " + g for g in govdeler) + "\n"
                    + SURUCU + "\n}\n")
        subprocess.check_call(["javac", "-encoding", "UTF-8", "-cp", json_jar, "Bt.java"],
                              cwd=gecici, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        cikti = subprocess.run(["java", "-cp", "." + os.pathsep + json_jar, "Bt"],
                               cwd=gecici, capture_output=True)
        print(cikti.stdout.decode().strip())
        if cikti.returncode != 0:
            hata = cikti.stderr.decode().strip()
            if hata:
                print(hata)
            sys.exit("HATA: biriken bildirim kuralları sınamayı geçmedi.")
    finally:
        shutil.rmtree(gecici, ignore_errors=True)


if __name__ == "__main__":
    main()
