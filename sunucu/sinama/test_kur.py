#!/usr/bin/env python3
"""kur.sh sınaması: sunucu klasörünün geçici bir kopyasında, etkileşimsiz.

Ölçülenler: venv ve bağımlılıklar kuruluyor mu; anahtar 600 izinle doğru yere
kopyalanıyor mu; .env yazılıyor, ikinci çalıştırmada ayarlar korunuyor mu;
anahtarın JSON içeriği .env'de duruyorsa dosya yolu kazanıyor mu; bozuk anahtar
reddediliyor mu; doldurulmuş hizmet tanımı doğru mu; systemd olmayan makinede
hizmet adımı sessizce değil açıklamayla atlanıyor mu; --kontrol bozuk anahtarı
yakalıyor mu.

İnternet gerekiyor (pip). openssl gerekiyor (sahte anahtar üretmek için).
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

KAYNAK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = []


def ok(ad, k, ayrinti=''):
    T.append((ad, bool(k)))
    print(('  ✓ ' if k else '  ✗ ') + ad + ('' if k else '  — ' + str(ayrinti)[:400]))


def kos(dizin, *arg, girdi=None):
    ortam = {k: v for k, v in os.environ.items() if not k.startswith('MERIDYEN_')}
    return subprocess.run(['bash', os.path.join(dizin, 'kur.sh')] + list(arg), cwd=dizin,
                          capture_output=True, text=True, input=girdi or '', timeout=600, env=ortam)


def izin(yol):
    return stat.S_IMODE(os.stat(yol).st_mode)


def surecler(desen):
    y = subprocess.run(['pgrep', '-f', desen], capture_output=True, text=True)
    return [int(p) for p in y.stdout.split()]


def termux(dizin, gecici):
    import time
    ev = os.path.join(gecici, 'ev')
    os.makedirs(ev)
    with open(os.path.join(dizin, '.env'), 'a') as f:
        f.write('PORT=0\n')         # sağlık ucu kapalı: sahte anahtarla zaten sağlıksız olurdu
    ortam = {k: v for k, v in os.environ.items() if not k.startswith('MERIDYEN_')}
    ortam.update(TERMUX_VERSION='0.118.0', HOME=ev)
    pidd = os.path.join(dizin, '.calistir.pid')
    boot = os.path.join(ev, '.termux/boot/meridyen-bildirim')
    sunucu_deseni = '%s/venv/bin/python %s/sunucu.py' % (dizin, dizin)

    def kur(*arg):
        return subprocess.run(['bash', os.path.join(dizin, 'kur.sh')] + list(arg), cwd=dizin, env=ortam,
                              capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)

    def bekle(kosul, sure=15):
        son = time.time() + sure
        while time.time() < son:
            if kosul():
                return True
            time.sleep(0.3)
        return False

    try:
        y = kur('--kontrol-yok')
        ok('Termux yolu seçildi, systemd/sudo denenmedi', y.returncode == 0 and 'Termux: arka planda' in y.stdout
           and 'sudo' not in y.stdout + y.stderr, y.stdout[-500:] + y.stderr[-300:])
        ok('çalıştırıcı başladı', bekle(lambda: os.path.exists(pidd) and surecler(sunucu_deseni)))
        pid1 = int(open(pidd).read())
        b = open(boot).read() if os.path.exists(boot) else ''
        ok('Termux:Boot betiği yazıldı (700, doğru yol, uyanık tutma)',
           izin(boot) == 0o700 and 'exec "%s/calistir.sh"' % dizin in b and 'termux-wake-lock' in b
           and b.startswith('#!/data/data/com.termux/files/usr/bin/sh'), b)
        ok('pil/Termux:Boot uyarısı verildi', 'Termux:Boot' in y.stdout and 'Pil' in y.stdout)

        y = kur('--kontrol-yok')
        ok('ikinci kurulum yeniden başlattı', y.returncode == 0 and bekle(
            lambda: os.path.exists(pidd) and int(open(pidd).read()) != pid1 and surecler(sunucu_deseni)))
        time.sleep(1)
        ok('tek çalıştırıcı, tek sunucu (çift sunucu yok)',
           len(surecler(os.path.join(dizin, 'calistir.sh'))) == 1 and len(surecler(sunucu_deseni)) == 1,
           (surecler(os.path.join(dizin, 'calistir.sh')), surecler(sunucu_deseni)))

        eski = surecler(sunucu_deseni)[0]
        os.kill(eski, 9)
        ok('sunucu kill -9 ile ölünce çalıştırıcı yeniden başlattı',
           bekle(lambda: surecler(sunucu_deseni) and surecler(sunucu_deseni)[0] != eski, 15))
        ok('ölüm günlüğe yazıldı', 'sunucu çıktı (kod' in open(os.path.join(dizin, 'sunucu.log')).read())

        y = kur('--kaldir')
        ok('kaldır: durdu, Termux:Boot betiği silindi',
           y.returncode == 0 and bekle(lambda: not surecler(sunucu_deseni)
                                       and not surecler(os.path.join(dizin, 'calistir.sh')))
           and not os.path.exists(boot) and not os.path.exists(pidd), y.stdout + y.stderr)
    finally:
        for p in surecler(os.path.join(dizin, 'calistir.sh')) + surecler(sunucu_deseni):
            try:
                os.kill(p, 9)
            except OSError:
                pass


def main():
    gecici = tempfile.mkdtemp(prefix='meridyen-kur-')
    dizin = os.path.join(gecici, 'sunucu')
    shutil.copytree(KAYNAK, dizin, ignore=shutil.ignore_patterns(
        'venv', '.env', 'servis-hesabi.json', '.sunucu-kimligi', '__pycache__'))
    # Yapısı gerçek bir servis hesabı anahtarı gibi olan sahte anahtar
    pem = subprocess.run(['openssl', 'genrsa', '2048'], capture_output=True, text=True, check=True).stdout
    anahtar = os.path.join(gecici, 'indirilen anahtar.json')     # boşluklu yol
    with open(anahtar, 'w') as f:
        json.dump({'type': 'service_account', 'project_id': 'meridyen-830fb',
                   'private_key_id': 'x', 'private_key': pem,
                   'client_email': 'sinama@meridyen-830fb.iam.gserviceaccount.com',
                   'token_uri': 'https://oauth2.googleapis.com/token'}, f)

    print('— ilk kurulum')
    y = kos(dizin, '--anahtar', anahtar, '--kontrol-yok')
    ok('başarıyla bitti', y.returncode == 0, y.stdout[-600:] + y.stderr[-600:])
    ok('venv kuruldu, requests içinde', subprocess.run(
        [os.path.join(dizin, 'venv/bin/python'), '-c', 'import requests'],
        capture_output=True).returncode == 0)
    paketler = subprocess.run([os.path.join(dizin, 'venv/bin/python'), '-m', 'pip', 'list', '--format=freeze'],
                              capture_output=True, text=True).stdout.lower()
    # Termux'ta kurulum cryptography'yi derlemeye çalışırken çöküyordu (Rust yok).
    ok('derlenmesi gereken paket YOK (cryptography, cffi, google-auth)',
       not any(p in paketler for p in ('cryptography', 'cffi', 'google-auth')), paketler)
    hedef = os.path.join(dizin, 'servis-hesabi.json')
    ok('anahtar kopyalandı, izin 600', os.path.exists(hedef) and izin(hedef) == 0o600)
    env = open(os.path.join(dizin, '.env')).read()
    ok('.env yazıldı, anahtar yolu içinde', 'MERIDYEN_SERVIS_HESABI_DOSYASI=' + hedef in env, env[:300])
    ok('.env izni 600', izin(os.path.join(dizin, '.env')) == 0o600)
    if not os.path.isdir('/run/systemd/system'):
        ok('systemd yokken hizmet adımı AÇIKLAMAYLA atlandı (elle başlatma komutu verildi)',
           'systemd yok' in y.stdout and 'nohup' in y.stdout, y.stdout[-400:])

    print('— ikinci çalıştırma: ayarlar korunuyor')
    with open(os.path.join(dizin, '.env'), 'a') as f:
        f.write('PORT=9999\nMERIDYEN_SERVIS_HESABI={"type":"service_account"}\n')
    y = kos(dizin, '--kontrol-yok')
    env = open(os.path.join(dizin, '.env')).read()
    ok('anahtar sormadan yeniden çalıştı', y.returncode == 0, y.stderr[-400:])
    ok('kullanıcının eklediği ayar duruyor', 'PORT=9999' in env)
    ok('anahtar satırı tek kez', env.count('MERIDYEN_SERVIS_HESABI_DOSYASI=') == 1, env)
    ok('JSON içerik satırı yoruma alındı (dosya yolu kazanır)',
       '# MERIDYEN_SERVIS_HESABI={"type"' in env, env)

    print('— .env paketsiz okunuyor')
    sys.path.insert(0, dizin)
    import ortam
    o = {}
    ortam.yukle(os.path.join(dizin, '.env'), o)
    ok('sunucunun okuyucusu yolu ve portu görüyor', o.get('MERIDYEN_SERVIS_HESABI_DOSYASI') == hedef
       and o.get('PORT') == '9999' and 'MERIDYEN_SERVIS_HESABI' not in o, o)

    print('— bozuk anahtar')
    bozuk = os.path.join(gecici, 'bozuk.json')
    with open(bozuk, 'w') as f:
        json.dump({'type': 'authorized_user', 'client_id': 'x'}, f)
    y = kos(dizin, '--anahtar', bozuk, '--kontrol-yok')
    ok('servis hesabı olmayan dosya reddedildi', y.returncode != 0 and 'servis hesabı anahtarı değil' in y.stdout + y.stderr,
       y.stdout[-300:] + y.stderr[-300:])
    ok('eski (iyi) anahtar yerinde kaldı', json.load(open(hedef)).get('type') == 'service_account')
    y = kos(dizin, '--anahtar', os.path.join(gecici, 'yok.json'), '--kontrol-yok')
    ok('olmayan dosya reddedildi', y.returncode != 0)

    print('— hizmet tanımı')
    y = kos(dizin, '--hizmet-dosyasi')
    ok('doldurulmuş tanım doğru yolları gösteriyor',
       y.returncode == 0 and 'ExecStart=%s/venv/bin/python %s/sunucu.py' % (dizin, dizin) in y.stdout
       and 'WorkingDirectory=' + dizin in y.stdout and '@' not in y.stdout.replace('@KULLANICI@', ''), y.stdout)
    ok('yer tutucu kalmadı', '@DIZIN@' not in y.stdout and '@KULLANICI@' not in y.stdout)

    print('— denetim bozuk/sahte anahtarı yakalıyor')
    y = subprocess.run([os.path.join(dizin, 'venv/bin/python'), os.path.join(dizin, 'dene.py'), '--kontrol'],
                       cwd=gecici, capture_output=True, text=True, timeout=120,
                       env={k: v for k, v in os.environ.items() if not k.startswith('MERIDYEN_')})
    ok('sahte anahtarla "TAMAM" demiyor, çıkış kodu 4',
       y.returncode == 4 and 'Erişim       : ✗' in y.stdout, y.stdout[-400:] + y.stderr[-400:])

    print('— Termux (Android): arka planda çalıştırıcı + Termux:Boot')
    termux(dizin, gecici)

    shutil.rmtree(gecici, ignore_errors=True)
    kotu = [a for a, k in T if not k]
    print('\n  %d BAŞARISIZ / %d' % (len(kotu), len(T)) if kotu else '\n  TUMU GECTI (%d)' % len(T))
    sys.exit(1 if kotu else 0)


if __name__ == '__main__':
    main()
