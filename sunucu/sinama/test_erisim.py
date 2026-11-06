#!/usr/bin/env python3
"""erisim.py sınaması: saf Python RSA imzası OpenSSL'e karşı.

Kendi yazdığımız imza kodu yanlışsa Google belirteci vermez ve sunucu hiç
bildirim gönderemez; üstelik bu ancak gerçek anahtarla, cihazda görünür.
Burada OpenSSL'in ürettiği anahtarlarla imzalayıp OpenSSL'e doğrulatıyoruz;
belirteç akışını da imzayı OpenSSL ile denetleyen sahte bir belirteç
sunucusuna karşı koşturuyoruz. (openssl gerekli.)
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import erisim as E  # noqa: E402

T = []
GECICI = tempfile.mkdtemp(prefix='meridyen-erisim-')


def ok(ad, k, ayrinti=''):
    T.append((ad, bool(k)))
    print(('  ✓ ' if k else '  ✗ ') + ad + ('' if k else '  — ' + str(ayrinti)[:300]))


def openssl(*arg, girdi=None):
    return subprocess.run(['openssl'] + list(arg), capture_output=True, input=girdi, check=True).stdout


def anahtar_uret(bit, pkcs1=False):
    pem = openssl('genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:%d' % bit)
    if pkcs1:
        pem = openssl('rsa', '-traditional', girdi=pem)
    yol = os.path.join(GECICI, 'k%d%s.pem' % (bit, '1' if pkcs1 else '8'))
    with open(yol, 'wb') as f:
        f.write(pem)
    pub = yol + '.pub'
    openssl('pkey', '-in', yol, '-pubout', '-out', pub)
    return pem.decode(), pub


def openssl_dogrula(pub, mesaj: bytes, imza: bytes) -> bool:
    m, s = os.path.join(GECICI, 'm.bin'), os.path.join(GECICI, 's.bin')
    with open(m, 'wb') as f:
        f.write(mesaj)
    with open(s, 'wb') as f:
        f.write(imza)
    y = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', pub, '-signature', s, m],
                       capture_output=True, text=True)
    return y.returncode == 0 and 'Verified OK' in y.stdout


def b64c(s):
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def main():
    print('— RS256 imzası OpenSSL ile doğrulanıyor')
    for bit, pkcs1 in ((2048, False), (2048, True), (3072, False), (4096, False)):
        pem, pub = anahtar_uret(bit, pkcs1)
        a = E.ozel_anahtar_coz(pem)
        imzalar = [(m, E.rs256_imzala(m, a)) for m in (b'', b'merhaba', os.urandom(5000))]
        ok('%d bit %s: 3 iletinin imzası geçerli' % (bit, 'PKCS#1' if pkcs1 else 'PKCS#8'),
           all(openssl_dogrula(pub, m, s) for m, s in imzalar))
    ok('başka iletiye ait imza REDDEDİLİYOR (doğrulama gerçekten çalışıyor)',
       not openssl_dogrula(pub, b'baska', imzalar[1][1]))

    print('— bozuk anahtar')
    for ad, pem in (('boş', ''), ('rastgele', '-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----'),
                    ('genel anahtar', open(pub).read())):
        try:
            E.ozel_anahtar_coz(pem)
            ok(ad + ' reddedildi', False)
        except E.AnahtarHatasi:
            ok(ad + ' reddedildi', True)

    print('— belirteç akışı (imzayı OpenSSL ile denetleyen sahte belirteç sunucusu)')
    pem, pub = anahtar_uret(2048)
    istekler = []
    durum = {'hata': None}

    class Isleyici(BaseHTTPRequestHandler):
        def do_POST(self):
            form = parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode())
            jwt = form['assertion'][0]
            h, g, s = jwt.split('.')
            gecerli = openssl_dogrula(pub, (h + '.' + g).encode(), b64c(s))
            istekler.append((form['grant_type'][0], json.loads(b64c(h)), json.loads(b64c(g)), gecerli))
            if durum['hata']:
                kod, govde = 400, {'error': 'invalid_grant', 'error_description': durum['hata']}
            elif not gecerli:
                kod, govde = 400, {'error': 'invalid_grant', 'error_description': 'Invalid JWT Signature.'}
            else:
                kod, govde = 200, {'access_token': 'ya29.sahte-%d' % len(istekler), 'expires_in': 3599}
            veri = json.dumps(govde).encode()
            self.send_response(kod)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(veri)))
            self.end_headers()
            self.wfile.write(veri)

        def log_message(self, *a):
            pass

    sunucu = ThreadingHTTPServer(('127.0.0.1', 0), Isleyici)
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    hesap = {'type': 'service_account', 'client_email': 'bildirim@meridyen-830fb.iam.gserviceaccount.com',
             'private_key': pem, 'private_key_id': 'abc123',
             'token_uri': 'http://127.0.0.1:%d/token' % sunucu.server_address[1]}
    sh = E.ServisHesabi(hesap, ['k1', 'k2'])
    b1, b2 = sh.belirtec(), sh.belirtec()
    ok('belirteç alındı', b1 == 'ya29.sahte-1')
    ok('ikinci çağrı önbellekten (tek istek)', b2 == b1 and len(istekler) == 1)
    tur, baslik, govde, gecerli = istekler[0]
    ok('JWT imzası belirteç sunucusunda doğrulandı', gecerli)
    ok('JWT alanları doğru', tur == 'urn:ietf:params:oauth:grant-type:jwt-bearer'
       and baslik == {'alg': 'RS256', 'typ': 'JWT', 'kid': 'abc123'}
       and govde['iss'] == hesap['client_email'] and govde['aud'] == hesap['token_uri']
       and govde['scope'] == 'k1 k2' and govde['exp'] - govde['iat'] == 3600, (baslik, govde))
    ok('zorla yenileme yeni belirteç alıyor', sh.belirtec(zorla=True) == 'ya29.sahte-2')
    durum['hata'] = 'Invalid JWT: Token must be a short-lived token (60 minutes) and in a reasonable timeframe.'
    try:
        sh.belirtec(zorla=True)
        ok('saat hatası açıklanıyor', False)
    except E.ErisimHatasi as e:
        ok('saat hatası açıklanıyor ("SAATİ yanlış")', 'SAATİ' in str(e), e)
    durum['hata'] = 'Invalid JWT Signature.'
    try:
        sh.belirtec(zorla=True)
        ok('iptal edilmiş anahtar açıklanıyor', False)
    except E.ErisimHatasi as e:
        ok('iptal edilmiş anahtar açıklanıyor', 'iptal' in str(e), e)
    sunucu.shutdown()

    kotu = [a for a, k in T if not k]
    print('\n  %d BAŞARISIZ / %d' % (len(kotu), len(T)) if kotu else '\n  TUMU GECTI (%d)' % len(T))
    sys.exit(1 if kotu else 0)


if __name__ == '__main__':
    main()
