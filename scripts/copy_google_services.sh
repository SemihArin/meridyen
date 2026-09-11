#!/usr/bin/env bash
# Meridyen — Firebase yapılandırmasını taze üretilen android/ projesine koyar.
#
# Capacitor'un kendi app/build.gradle şablonu bu dosyayı ARIYOR: varsa
# google-services eklentisini uyguluyor (yani FCM/push çalışıyor), yoksa
# sessizce atlıyor. Dolayısıyla Gradle'a elle dokunmaya gerek yok, dosyayı
# doğru yere koymak yeterli.
set -euo pipefail

KAYNAK="google-services.json"
HEDEF="android/app/google-services.json"

if [ ! -f "$KAYNAK" ]; then
  echo "HATA: $KAYNAK bulunamadı — push bildirimleri bu dosya olmadan çalışmaz." >&2
  exit 1
fi

# Yanlış projenin dosyasıyla derlemek, derlemeyi bozmaz ama bildirimleri
# SESSİZCE çalışmaz hale getirir (belirteçler başka projeden gelir, sunucu
# gönderemez). Bu yüzden burada bir kez doğruluyoruz.
python3 - "$KAYNAK" <<'PYEOF'
import json, sys
BEKLENEN_PROJE = "meridyen-830fb"
BEKLENEN_GONDEREN = "628310759714"
BEKLENEN_PAKET = "com.meridyen.app"

d = json.load(open(sys.argv[1], encoding="utf-8"))
proje = d["project_info"]["project_id"]
gonderen = d["project_info"]["project_number"]
paketler = [
    i["client_info"]["android_client_info"]["package_name"] for i in d.get("client", [])
]

if proje != BEKLENEN_PROJE or gonderen != BEKLENEN_GONDEREN:
    sys.exit(
        "HATA: google-services.json yanlış Firebase projesine ait.\n"
        "  beklenen: %s / %s\n  gelen:    %s / %s"
        % (BEKLENEN_PROJE, BEKLENEN_GONDEREN, proje, gonderen)
    )

if BEKLENEN_PAKET not in paketler:
    sys.exit(
        "HATA: google-services.json içinde %s paketi yok (bulunanlar: %s)"
        % (BEKLENEN_PAKET, ", ".join(paketler) or "yok")
    )

print("google-services.json doğrulandı: %s / %s / %s" % (proje, gonderen, BEKLENEN_PAKET))
PYEOF

mkdir -p "$(dirname "$HEDEF")"
cp "$KAYNAK" "$HEDEF"
echo "Firebase yapılandırması kopyalandı."
