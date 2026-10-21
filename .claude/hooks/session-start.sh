#!/bin/bash
# Meridyen — Claude Code bulut oturumu başlangıç kancası.
#
# NİÇİN: bulut kapsayıcısı oturumlar arasında yenilenebiliyor. Bir kez
# node_modules, Android SDK ve tarayıcı sınama aracı birlikte gitti; sınamalar
# "Capacitor kaynağı yok" diye düştü ve APK derlenemez oldu. Bu betik her
# oturum başında eksik olanı kuruyor. Var olana dokunmuyor (idempotent), yani
# ikinci çalıştırma birkaç saniye sürüyor.
#
# Yalnız bulutta çalışıyor: yerel makinede kimsenin SDK'sını kurcalamıyoruz.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJE="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$PROJE"

gunluk() { echo "[oturum-başlangıcı] $*" >&2; }

# ---- 1) npm bağımlılıkları (Capacitor) -------------------------------------
# Sınamalar (test_dirilis) ve native kurulum betiği Capacitor'un Java
# kaynağını node_modules içinden okuyor. `npm install` kilit dosyasına uyuyor
# ve kurulu olanı yeniden indirmiyor.
if [ ! -d node_modules/@capacitor/android/capacitor/src/main/java ]; then
  gunluk "npm bağımlılıkları kuruluyor"
  npm install --no-audit --no-fund --loglevel=error
else
  gunluk "npm bağımlılıkları zaten var"
fi

# ---- 2) Android SDK ----------------------------------------------------------
# APK'yı yerelde derleyebilmek için. Sürümler derlemenin istediğiyle aynı:
# compileSdk/targetSdk 35, AGP 8.7.x'in varsayılan build-tools'u 34.0.0.
ANDROID_HOME="${ANDROID_HOME:-$HOME/android-sdk}"
SDKMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
ARAC_SURUMU="13114758"   # commandlinetools-linux-<sürüm>_latest.zip

if [ ! -x "$SDKMANAGER" ]; then
  gunluk "Android komut satırı araçları indiriliyor"
  GECICI="$(mktemp -d)"
  curl -fsSL --retry 4 --retry-delay 2 \
    -o "$GECICI/araclar.zip" \
    "https://dl.google.com/android/repository/commandlinetools-linux-${ARAC_SURUMU}_latest.zip"
  mkdir -p "$ANDROID_HOME/cmdline-tools"
  unzip -q "$GECICI/araclar.zip" -d "$GECICI"
  rm -rf "$ANDROID_HOME/cmdline-tools/latest"
  mv "$GECICI/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
  rm -rf "$GECICI"
fi

GEREKEN=("platform-tools" "platforms;android-35" "build-tools;34.0.0")
EKSIK=()
for paket in "${GEREKEN[@]}"; do
  yol="$ANDROID_HOME/${paket//;//}"
  [ -d "$yol" ] || EKSIK+=("$paket")
done
if [ ${#EKSIK[@]} -gt 0 ]; then
  gunluk "Android paketleri kuruluyor: ${EKSIK[*]}"
  # Lisanslar kabul edilmeden sdkmanager etkileşimli soru soruyor ve kanca
  # sonsuza kadar bekliyordu.
  yes | "$SDKMANAGER" --sdk_root="$ANDROID_HOME" --licenses >/dev/null 2>&1 || true
  "$SDKMANAGER" --sdk_root="$ANDROID_HOME" "${EKSIK[@]}" >/dev/null
else
  gunluk "Android SDK paketleri zaten var"
fi

# ---- 3) Gradle: Maven Central yerine Google'ın aynası -------------------------
# Bu kapsayıcının çıkış adresi Maven Central tarafından hız sınırına takılıyor:
# Gradle'ın paralel istekleri "429 Too Many Requests" alıyor ve derleme her
# seferinde başka bir dosyada düşüyor (üç ardışık denemede de oldu). Google'ın
# Maven Central aynası BAYT BAYT aynı dosyaları veriyor (SHA-1 karşılaştırıldı),
# yani derlenen APK değişmiyor. Yalnız bu kapsayıcının ~/.gradle'ına yazılıyor;
# depoya, CI'a ve yerel makinelere dokunmuyor.
GRADLE_INIT="$HOME/.gradle/init.d/meridyen-maven-aynasi.gradle"
mkdir -p "$(dirname "$GRADLE_INIT")"
cat > "$GRADLE_INIT" <<'GRADLE'
// Meridyen bulut oturumu: Maven Central istekleri Google'ın aynasına gidiyor.
// Kaynak: .claude/hooks/session-start.sh (oturum başında yeniden yazılır).
def AYNA = 'https://maven-central.storage-download.googleapis.com/maven2/'
def yonlendir = { RepositoryHandler depolar ->
  depolar.configureEach { d ->
    if (d instanceof MavenArtifactRepository && d.url != null &&
        d.url.toString().startsWith('https://repo.maven.apache.org/maven2')) {
      d.url = AYNA
    }
  }
}
beforeSettings { ayar ->
  yonlendir(ayar.pluginManagement.repositories)
  yonlendir(ayar.buildscript.repositories)
}
allprojects { proje ->
  yonlendir(proje.buildscript.repositories)
  yonlendir(proje.repositories)
}
GRADLE

# ---- 4) Tarayıcı sınamaları için playwright-core ----------------------------
# Arayüz sınamaları önceden kurulu Chromium'u (/opt/pw-browsers) kullanıyor;
# eksik olan yalnız sürücü kitaplığı. Depoya bağımlılık olarak EKLEMİYORUZ:
# package.json Capacitor derlemesine ait, oraya giren her şey APK sürecine de
# giriyor. Ayrı bir klasöre kuruluyor; tarayıcı indirmesi kapalı.
ARACLAR="$HOME/.cache/meridyen-araclar"
if [ ! -d "$ARACLAR/node_modules/playwright-core" ]; then
  gunluk "playwright-core kuruluyor"
  mkdir -p "$ARACLAR"
  PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    npm install --prefix "$ARACLAR" --no-audit --no-fund --loglevel=error playwright-core \
    || gunluk "UYARI: playwright-core kurulamadı (yalnız arayüz sınamalarını etkiler)"
else
  gunluk "playwright-core zaten var"
fi

# Kural sınaması (scripts/test_kurallar_emulator.sh) gerçek RTDB emülatörünü
# koşturuyor: firebase-tools + rules-unit-testing aynı ayrı klasöre.
if [ ! -d "$ARACLAR/node_modules/@firebase/rules-unit-testing" ] \
   || [ ! -x "$ARACLAR/node_modules/.bin/firebase" ]; then
  gunluk "firebase emülatör araçları kuruluyor"
  npm install --prefix "$ARACLAR" --no-audit --no-fund --loglevel=error \
    firebase-tools@13 @firebase/rules-unit-testing@3 firebase@10 \
    || gunluk "UYARI: emülatör araçları kurulamadı (yalnız kural sınamasını etkiler)"
else
  gunluk "firebase emülatör araçları zaten var"
fi

# ---- 5) Oturum ortamı -------------------------------------------------------
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export ANDROID_HOME=\"$ANDROID_HOME\""
    echo "export ANDROID_SDK_ROOT=\"$ANDROID_HOME\""
    echo "export MERIDYEN_PLAYWRIGHT=\"$ARACLAR/node_modules/playwright-core\""
  } >> "$CLAUDE_ENV_FILE"
fi

gunluk "hazır"
