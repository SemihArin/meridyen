#!/usr/bin/env sh
# Sunucuyu arka planda çalıştırır; çıkarsa ya da çökerse 5 sn sonra yeniden
# başlatır. systemd'nin olmadığı yerler için (Android'de Termux): kur.sh bunu
# başlatıyor, telefon açılınca da Termux:Boot ile kendiliğinden başlıyor.
#
#   ./calistir.sh            (zaten çalışıyorsa ikinci bir kopya açmaz)
#   kill "$(cat .calistir.pid)"   durdurur (ya da ./kur.sh --kaldir)
#
# Günlük: sunucu.log (5 MB'ı geçince sunucu.log.1'e taşınır).
DIZIN=$(cd "$(dirname "$0")" && pwd -P)
cd "$DIZIN" || exit 1
PIDDOSYASI="$DIZIN/.calistir.pid"

if [ -f "$PIDDOSYASI" ] && kill -0 "$(cat "$PIDDOSYASI")" 2>/dev/null; then
  echo "zaten çalışıyor (pid $(cat "$PIDDOSYASI"))"
  exit 0
fi
echo $$ > "$PIDDOSYASI"

# Android ekran kapanınca işlemciyi uyutuyor ve ağı kesiyor; Termux'un uyanık
# tutma kilidi olmadan sunucu dakikalar içinde susar.
if command -v termux-wake-lock >/dev/null 2>&1; then termux-wake-lock; fi

COCUK=""
bitir() {
  [ -n "$COCUK" ] && kill "$COCUK" 2>/dev/null
  rm -f "$PIDDOSYASI"
  exit 0
}
trap bitir TERM INT
# Terminal kapanınca (HUP) durmasın; sunucu da bu yoksaymayı devralıyor.
trap '' HUP

while :; do
  if [ -f sunucu.log ] && [ "$(wc -c < sunucu.log)" -gt 5242880 ]; then
    mv -f sunucu.log sunucu.log.1
  fi
  # Tam yollar: kur.sh durdururken yalnız BU klasörün sunucusunu tanısın.
  "$DIZIN/venv/bin/python" "$DIZIN/sunucu.py" >> sunucu.log 2>&1 &
  COCUK=$!
  wait "$COCUK"
  KOD=$?
  COCUK=""
  echo "$(date '+%Y-%m-%d %H:%M:%S') sunucu çıktı (kod $KOD); 5 sn sonra yeniden başlıyor" >> sunucu.log
  sleep 5
done
