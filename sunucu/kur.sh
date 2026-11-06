#!/usr/bin/env bash
# Meridyen bildirim sunucusu — KURULUM.
#
# Sunucunun çalışacağı makinede (Raspberry Pi, Linux bilgisayar, VPS) sunucu/
# klasörünün içinden çalıştır:
#
#   ./kur.sh                          her şeyi sorarak kurar
#   ./kur.sh --anahtar ~/indir/meridyen-830fb-xxxx.json
#
# Yaptıkları (her adım yeniden çalıştırılabilir; ikinci kez çalıştırmak
# güncelleme yapar, ayarları silmez):
#   1. Python 3.9+ ve venv var mı bakar (yoksa nasıl kurulacağını söyler)
#   2. venv/ oluşturur, bağımlılıkları kurar
#   3. Servis hesabı anahtarını servis-hesabi.json olarak yerleştirir (izin 600)
#   4. .env'i yazar (izin 600)
#   5. Kurulumu doğrular: anahtar, veritabanı, FCM izni (bildirim GÖNDERMEDEN)
#   6. systemd hizmetini kurar, açılışta başlatır, çalıştığını denetler
#
# Seçenekler:
#   --anahtar YOL        servis hesabı JSON dosyası (kopyalanır)
#   --hizmet-yok         systemd hizmeti kurma (yalnız ortamı hazırla)
#   --kontrol-yok        bağlantı denetimini atla
#   --hizmet-dosyasi     doldurulmuş hizmet tanımını ekrana yaz ve çık
#   --kaldir             hizmeti durdur ve kaldır (ayarlar ve venv kalır)
#   -h, --yardim
set -euo pipefail

HIZMET=meridyen-bildirim
DIZIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$DIZIN"

ANAHTAR_KAYNAGI=""
HIZMET_KUR=1
KONTROL=1
ETKILESIMLI=0
[ -t 0 ] && [ -t 1 ] && ETKILESIMLI=1

if [ -t 1 ]; then Y=$'\e[32m'; S=$'\e[33m'; K=$'\e[31m'; N=$'\e[0m'; else Y=""; S=""; K=""; N=""; fi
adim()  { printf '\n%s==>%s %s\n' "$Y" "$N" "$*"; }
uyari() { printf '%s!%s %s\n' "$S" "$N" "$*"; }
olum()  { printf '\n%sHATA:%s %s\n' "$K" "$N" "$*" >&2; exit 1; }
sor() {  # sor "soru" varsayılan(e/h) → 0 evet, 1 hayır
  local yanit varsayilan="$2"
  if [ "$ETKILESIMLI" != 1 ]; then [ "$varsayilan" = e ]; return; fi
  read -r -p "$1 [$( [ "$varsayilan" = e ] && echo E/h || echo e/H )] " yanit || true
  yanit="${yanit:-$varsayilan}"
  [[ "$yanit" =~ ^[eEyY] ]]
}

KULLANICI="${SUDO_USER:-$(id -un)}"
yetkili() {   # root değilsek sudo ile
  if [ "$(id -u)" = 0 ]; then "$@"; else sudo "$@"; fi
}

hizmet_dosyasi() {
  sed -e "s|@KULLANICI@|$KULLANICI|g" -e "s|@DIZIN@|$DIZIN|g" "$DIZIN/meridyen-bildirim.service"
}

systemd_var() {
  command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]
}

while [ $# -gt 0 ]; do
  case "$1" in
    --anahtar) [ $# -ge 2 ] || olum "--anahtar bir dosya yolu ister"; ANAHTAR_KAYNAGI="$2"; shift 2 ;;
    --anahtar=*) ANAHTAR_KAYNAGI="${1#*=}"; shift ;;
    --hizmet-yok) HIZMET_KUR=0; shift ;;
    --kontrol-yok) KONTROL=0; shift ;;
    --hizmet-dosyasi) hizmet_dosyasi; exit 0 ;;
    --kaldir)
      systemd_var || olum "Bu makinede systemd yok."
      yetkili systemctl disable --now "$HIZMET" 2>/dev/null || true
      yetkili rm -f "/etc/systemd/system/$HIZMET.service"
      yetkili systemctl daemon-reload
      echo "Hizmet kaldırıldı. Ayarlar (.env), anahtar ve venv/ yerinde duruyor."
      exit 0 ;;
    -h|--yardim) sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) olum "bilinmeyen seçenek: $1 (yardım: ./kur.sh --yardim)" ;;
  esac
done

# ---------------------------------------------------------------- 1) Python
adim "Python denetleniyor"
PY="$(command -v python3 || true)"
[ -n "$PY" ] || olum "python3 yok. Debian/Raspberry Pi OS: sudo apt install python3 python3-venv"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
  || olum "Python 3.9 ya da daha yenisi gerekli; bu makinede: $("$PY" --version 2>&1)"
echo "$("$PY" --version)"
# Debian'da venv modülü ayrı pakette; ensurepip yoksa venv yarım kalıyor.
if ! "$PY" -c 'import venv, ensurepip' >/dev/null 2>&1; then
  uyari "Python'un venv modülü eksik."
  if command -v apt-get >/dev/null 2>&1 && sor "python3-venv şimdi kurulsun mu (sudo apt)?" e; then
    yetkili apt-get update -qq && yetkili apt-get install -y -qq python3-venv
  else
    olum "Önce şunu çalıştır: sudo apt install python3-venv"
  fi
fi

# ---------------------------------------------------------------- 2) venv
adim "Sanal ortam ve bağımlılıklar (venv/)"
if [ ! -x venv/bin/python ] || ! venv/bin/python -c 'import sys' >/dev/null 2>&1; then
  rm -rf venv
  "$PY" -m venv venv
fi
venv/bin/python -m pip install --quiet --disable-pip-version-check --upgrade pip >/dev/null 2>&1 || true
venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt \
  || olum "Bağımlılıklar kurulamadı (internet var mı?)"
echo "requests ve google-auth kurulu."

# ---------------------------------------------------------------- 3) anahtar
adim "Servis hesabı anahtarı"
anahtar_dogrula() {   # $1 = dosya; geçerliyse proje adını yazar
  venv/bin/python - "$1" <<'PYEOF'
import json, sys
try:
    with open(sys.argv[1], encoding='utf-8') as f:
        d = json.load(f)
except Exception as e:
    sys.exit('okunamadı: %s' % e)
if d.get('type') != 'service_account' or not d.get('private_key') or not d.get('client_email'):
    sys.exit('bu bir servis hesabı anahtarı değil (type=%s)' % d.get('type'))
print(d.get('project_id', '?'))
PYEOF
}

HEDEF_ANAHTAR="$DIZIN/servis-hesabi.json"
# .env'de başka bir yer gösteriliyorsa onu kullan
if [ -z "$ANAHTAR_KAYNAGI" ] && [ -f .env ]; then
  ENVDEKI="$(sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}MERIDYEN_SERVIS_HESABI_DOSYASI[[:space:]]*=[[:space:]]*//p' .env | tail -n1 | sed "s/^[\"']//; s/[\"']$//")"
  if [ -n "$ENVDEKI" ] && [ -f "$ENVDEKI" ]; then HEDEF_ANAHTAR="$ENVDEKI"; fi
fi

if [ -n "$ANAHTAR_KAYNAGI" ]; then
  [ -f "$ANAHTAR_KAYNAGI" ] || olum "anahtar dosyası yok: $ANAHTAR_KAYNAGI"
elif [ ! -f "$HEDEF_ANAHTAR" ]; then
  if [ "$ETKILESIMLI" = 1 ]; then
    echo "Firebase konsolu → Proje ayarları → Servis hesapları → \"Yeni özel anahtar oluştur\""
    echo "ile indirdiğin JSON dosyasının yolunu yaz (sürükleyip bırakabilirsin)."
    while :; do
      read -r -p "Anahtar dosyası: " ANAHTAR_KAYNAGI || olum "anahtar verilmedi"
      ANAHTAR_KAYNAGI="${ANAHTAR_KAYNAGI%\'}"; ANAHTAR_KAYNAGI="${ANAHTAR_KAYNAGI#\'}"
      ANAHTAR_KAYNAGI="${ANAHTAR_KAYNAGI/#\~/$HOME}"
      [ -f "$ANAHTAR_KAYNAGI" ] && break
      uyari "dosya bulunamadı: $ANAHTAR_KAYNAGI"
    done
  else
    olum "Anahtar yok. ./kur.sh --anahtar /yol/anahtar.json ile ver."
  fi
fi

if [ -n "$ANAHTAR_KAYNAGI" ]; then
  PROJE="$(anahtar_dogrula "$ANAHTAR_KAYNAGI")" || olum "anahtar geçersiz: $ANAHTAR_KAYNAGI"
  HEDEF_ANAHTAR="$DIZIN/servis-hesabi.json"
  if [ "$(cd "$(dirname "$ANAHTAR_KAYNAGI")" && pwd -P)/$(basename "$ANAHTAR_KAYNAGI")" != "$HEDEF_ANAHTAR" ]; then
    install -m 600 "$ANAHTAR_KAYNAGI" "$HEDEF_ANAHTAR"
  fi
else
  PROJE="$(anahtar_dogrula "$HEDEF_ANAHTAR")" || olum "kayıtlı anahtar geçersiz: $HEDEF_ANAHTAR"
fi
chmod 600 "$HEDEF_ANAHTAR"
echo "Anahtar: $HEDEF_ANAHTAR (proje: $PROJE)"
if [ "$PROJE" != "meridyen-830fb" ]; then
  uyari "Bu anahtar \"$PROJE\" projesinin; Meridyen'in projesi \"meridyen-830fb\"."
  sor "Yine de devam edilsin mi?" h || olum "durduruldu"
fi
[ "$KULLANICI" != "$(id -un)" ] && chown "$KULLANICI" "$HEDEF_ANAHTAR" 2>/dev/null || true

# ---------------------------------------------------------------- 4) .env
adim "Ayar dosyası (.env)"
if [ ! -f .env ]; then
  cp ornek.env .env
  echo ".env oluşturuldu (ornek.env'den)."
fi
# Anahtar satırını yaz/güncelle; dosyadaki diğer ayarlara dokunma.
venv/bin/python - .env "$HEDEF_ANAHTAR" <<'PYEOF'
import re, sys
yol, anahtar = sys.argv[1], sys.argv[2]
satirlar = open(yol, encoding='utf-8').read().splitlines()
yeni, yazildi = [], False
for s in satirlar:
    if re.match(r'^\s*(export\s+)?MERIDYEN_SERVIS_HESABI_DOSYASI\s*=', s):
        if not yazildi:
            yeni.append('MERIDYEN_SERVIS_HESABI_DOSYASI=' + anahtar)
            yazildi = True
        continue
    # Anahtarın JSON içeriği de yazılmışsa dosya yolu kazansın diye yoruma al.
    if re.match(r'^\s*(export\s+)?MERIDYEN_SERVIS_HESABI\s*=', s):
        yeni.append('# ' + s + '   # (kur.sh: dosya yolu kullanılıyor)')
        continue
    yeni.append(s)
if not yazildi:
    yeni.insert(0, 'MERIDYEN_SERVIS_HESABI_DOSYASI=' + anahtar)
open(yol, 'w', encoding='utf-8').write('\n'.join(yeni) + '\n')
PYEOF
chmod 600 .env
[ "$KULLANICI" != "$(id -un)" ] && chown "$KULLANICI" .env venv -R 2>/dev/null || true
echo "MERIDYEN_SERVIS_HESABI_DOSYASI=$HEDEF_ANAHTAR"

# ---------------------------------------------------------------- 5) denetim
if [ "$KONTROL" = 1 ]; then
  adim "Kurulum denetleniyor (bildirim gönderilmiyor)"
  if ! venv/bin/python dene.py --kontrol; then
    olum "Denetim geçmedi; yukarıdaki ✗ satırına bak. Düzeltip ./kur.sh'ı yeniden çalıştır."
  fi
fi

# ---------------------------------------------------------------- eski Node sunucusu
if command -v pm2 >/dev/null 2>&1 && pm2 jlist 2>/dev/null | grep -q '"name":"meridyen'; then
  uyari "pm2'de ESKİ (Node) Meridyen sunucusu kayıtlı. İkisi birlikte çalışırsa çift bildirim olur."
  if sor "Eski sunucu durdurulup pm2'den silinsin mi?" e; then
    for ad in $(pm2 jlist | grep -o '"name":"meridyen[^"]*"' | cut -d'"' -f4 | sort -u); do
      pm2 delete "$ad" >/dev/null && echo "pm2: $ad silindi"
    done
    pm2 save >/dev/null 2>&1 || true
  fi
fi

# ---------------------------------------------------------------- 6) hizmet
if [ "$HIZMET_KUR" = 1 ] && ! systemd_var; then
  uyari "Bu makinede systemd yok; hizmet kurulmadı. Elle başlatmak için:"
  echo "    cd $DIZIN && nohup venv/bin/python sunucu.py >> sunucu.log 2>&1 &"
  HIZMET_KUR=0
fi
if [ "$HIZMET_KUR" = 1 ] && sor "Sunucu açılışta kendiliğinden başlayan bir hizmet olarak kurulsun mu?" e; then
  adim "systemd hizmeti ($HIZMET, kullanıcı: $KULLANICI)"
  GECICI="$(mktemp)"
  hizmet_dosyasi > "$GECICI"
  yetkili install -m 644 "$GECICI" "/etc/systemd/system/$HIZMET.service"
  rm -f "$GECICI"
  yetkili systemctl daemon-reload
  yetkili systemctl enable "$HIZMET" >/dev/null 2>&1
  yetkili systemctl restart "$HIZMET"
  # Sağlık ucundan çalıştığını gör (port .env'den, yoksa 8080)
  PORT="$(venv/bin/python -c 'import ortam,os; ortam.yukle(); print(os.environ.get("PORT","8080"))')"
  echo -n "Sunucu ayağa kalkıyor"
  for _ in $(seq 1 20); do
    if venv/bin/python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:$PORT/', timeout=2)" >/dev/null 2>&1; then
      echo " — çalışıyor."
      venv/bin/python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:$PORT/', timeout=2)); print('  akış bağlı: %s | saat farkı: %s ms' % (d['akisBagli'], d['saatFarkiMs']))" 2>/dev/null || true
      break
    fi
    if [ "$PORT" = 0 ]; then echo " (sağlık ucu kapalı)"; break; fi
    echo -n "."; sleep 1
  done
  yetkili systemctl --no-pager --lines=0 status "$HIZMET" | sed -n '1,3p' || true
  echo
  echo "Günlük:        journalctl -u $HIZMET -f"
  echo "Yeniden başlat: sudo systemctl restart $HIZMET"
  echo "Kaldır:        ./kur.sh --kaldir"
fi

adim "Bitti"
echo "Uygulamada Ayarlar → Bildirimler tanısı birkaç saniye içinde \"bildirim sunucusu: çalışıyor\" demeli."
echo "Deneme bildirimi: venv/bin/python dene.py <kullanıcıUid> \"merhaba\""
