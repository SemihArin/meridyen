#!/usr/bin/env bash
# Meridyen — hazırlanmış uygulama ikonlarını taze üretilen android/ projesine kopyalar.
set -euo pipefail
KAYNAK="android-assets"
HEDEF="android/app/src/main/res"

for d in mipmap-mdpi mipmap-hdpi mipmap-xhdpi mipmap-xxhdpi mipmap-xxxhdpi; do
  cp "$KAYNAK/$d/ic_launcher.png" "$HEDEF/$d/ic_launcher.png"
  cp "$KAYNAK/$d/ic_launcher_round.png" "$HEDEF/$d/ic_launcher_round.png"
  cp "$KAYNAK/$d/ic_launcher_foreground.png" "$HEDEF/$d/ic_launcher_foreground.png"
done

mkdir -p "$HEDEF/mipmap-anydpi-v26"
cp "$KAYNAK/mipmap-anydpi-v26/ic_launcher.xml" "$HEDEF/mipmap-anydpi-v26/ic_launcher.xml"
cp "$KAYNAK/mipmap-anydpi-v26/ic_launcher_round.xml" "$HEDEF/mipmap-anydpi-v26/ic_launcher_round.xml"

mkdir -p "$HEDEF/values"
cp "$KAYNAK/values/ic_launcher_background.xml" "$HEDEF/values/ic_launcher_background.xml"

echo "ikonlar kopyalandı."

# Bildirim (durum çubuğu) ikonu: launcher ikonundan AYRI bir dosya, çünkü
# Android bunu yalnız siluet olarak çiziyor — renkli ikon burada beyaz leke
# olarak görünürdü. Üretimi: scripts/make_notification_icon.py
for d in drawable-mdpi drawable-hdpi drawable-xhdpi drawable-xxhdpi drawable-xxxhdpi; do
  mkdir -p "$HEDEF/$d"
  cp "$KAYNAK/$d/ic_stat_meridyen.png" "$HEDEF/$d/ic_stat_meridyen.png"
done

echo "bildirim ikonu kopyalandı."
