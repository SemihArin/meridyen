#!/bin/bash
# Kural sınamasını RTDB emülatöründe koşturur (bkz. test_kurallar_emulator.js).
# Araçlar depoya bağımlılık olarak girmiyor; MERIDYEN_ARACLAR klasörüne
# kurulu firebase-tools + @firebase/rules-unit-testing kullanılıyor.
set -euo pipefail
cd "$(dirname "$0")/.."
ARACLAR="${MERIDYEN_ARACLAR:-$HOME/.cache/meridyen-araclar}"
export MERIDYEN_RUT="$ARACLAR/node_modules/@firebase/rules-unit-testing"
exec "$ARACLAR/node_modules/.bin/firebase" --config scripts/kural-emulator.json \
  emulators:exec --only database --project demo-meridyen \
  "node scripts/test_kurallar_emulator.js database.rules.json"
