"""Servis hesabı anahtarıyla Google erişim belirteci almak — saf Python.

NEDEN google-auth DEĞİL: güncel google-auth `cryptography` paketini zorunlu
istiyor. cryptography derlenmiş bir paket; Android/Termux (32 bit ARM) gibi
hazır sürümü olmayan yerlerde kaynaktan derlenmesi Rust istiyor ve Rust o
işlemciyi desteklemiyor — kurulum hiç bitmiyordu. Burada yaptığımız iş küçük
ve standart (Google'ın "servis hesabı için OAuth 2.0" akışı):

  1. Anahtardaki RSA özel anahtarını çöz (PEM → DER → sayılar),
  2. kısa ömürlü bir JWT kur ve RS256 (RSASSA-PKCS1-v1_5 + SHA-256) ile imzala,
  3. token_uri'ye gönderip erişim belirtecini al.

Yalnız standart kütüphane ve `requests`. İmza doğruluğu sınamada OpenSSL'e
karşı denetleniyor (sinama/test_erisim.py).
"""
from __future__ import annotations

import base64
import hashlib
import json
import threading
import time

# ---------------------------------------------------------------- DER

def _der_oku(veri: bytes, i: int):
    """i konumundaki DER öğesi: (etiket, içerik, sonraki_konum)."""
    etiket = veri[i]
    uzunluk = veri[i + 1]
    i += 2
    if uzunluk & 0x80:
        k = uzunluk & 0x7F
        uzunluk = int.from_bytes(veri[i:i + k], 'big')
        i += k
    return etiket, veri[i:i + uzunluk], i + uzunluk


def _ogeler(icerik: bytes):
    cikti, i = [], 0
    while i < len(icerik):
        etiket, deger, i = _der_oku(icerik, i)
        cikti.append((etiket, deger))
    return cikti


class AnahtarHatasi(ValueError):
    pass


def ozel_anahtar_coz(pem: str) -> dict:
    """PKCS#8 ("BEGIN PRIVATE KEY", Google'ın verdiği) ya da PKCS#1
    ("BEGIN RSA PRIVATE KEY") RSA özel anahtarını sayılarına ayırır."""
    try:
        govde = ''.join(s.strip() for s in pem.strip().splitlines() if not s.startswith('-----'))
        der = base64.b64decode(govde)
        etiket, icerik, _ = _der_oku(der, 0)
        if etiket != 0x30:
            raise AnahtarHatasi('DER dizisi değil')
        ogeler = _ogeler(icerik)
        # PKCS#8: [sürüm, algoritma DİZİSİ, OCTET STRING(PKCS#1)]
        if len(ogeler) >= 3 and ogeler[1][0] == 0x30 and ogeler[2][0] == 0x04:
            if b'\x2a\x86\x48\x86\xf7\x0d\x01\x01\x01' not in ogeler[1][1]:   # rsaEncryption OID
                raise AnahtarHatasi('RSA anahtarı değil')
            etiket, icerik, _ = _der_oku(ogeler[2][1], 0)
            ogeler = _ogeler(icerik)
        sayilar = [int.from_bytes(d, 'big') for t, d in ogeler if t == 0x02]
        if len(sayilar) < 9:
            raise AnahtarHatasi('eksik RSA alanları')
        _, n, e, d, p, q, dp, dq, qinv = sayilar[:9]
        return {'n': n, 'e': e, 'd': d, 'p': p, 'q': q, 'dp': dp, 'dq': dq, 'qinv': qinv}
    except AnahtarHatasi:
        raise
    except Exception as e:
        raise AnahtarHatasi('özel anahtar çözülemedi: %s' % e) from e


# SHA-256 için DigestInfo öneki (RFC 8017, 9.2 notu 1)
_SHA256_ONEK = bytes.fromhex('3031300d060960864801650304020105000420')


def rs256_imzala(mesaj: bytes, a: dict) -> bytes:
    """RSASSA-PKCS1-v1_5, SHA-256 (JWT'nin RS256'sı)."""
    k = (a['n'].bit_length() + 7) // 8
    t = _SHA256_ONEK + hashlib.sha256(mesaj).digest()
    if k < len(t) + 11:
        raise AnahtarHatasi('anahtar çok kısa')
    em = b'\x00\x01' + b'\xff' * (k - len(t) - 3) + b'\x00' + t
    m = int.from_bytes(em, 'big')
    # Çin kalan teoremi: doğrudan pow(m, d, n)'den ~4 kat hızlı (eski ARM'de fark ediyor)
    m1 = pow(m, a['dp'], a['p'])
    m2 = pow(m, a['dq'], a['q'])
    h = (a['qinv'] * (m1 - m2)) % a['p']
    s = m2 + h * a['q']
    return s.to_bytes(k, 'big')


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode('ascii')


def jwt_kur(hesap: dict, kapsamlar, simdi: float, a: dict) -> str:
    baslik = {'alg': 'RS256', 'typ': 'JWT'}
    if hesap.get('private_key_id'):
        baslik['kid'] = hesap['private_key_id']
    iat = int(simdi)
    govde = {'iss': hesap['client_email'], 'scope': ' '.join(kapsamlar),
             'aud': hesap.get('token_uri') or 'https://oauth2.googleapis.com/token',
             'iat': iat, 'exp': iat + 3600}
    girdi = _b64(json.dumps(baslik, separators=(',', ':')).encode()) + '.' + \
        _b64(json.dumps(govde, separators=(',', ':')).encode())
    return girdi + '.' + _b64(rs256_imzala(girdi.encode('ascii'), a))


# ---------------------------------------------------------------- belirteç

class ErisimHatasi(Exception):
    pass


class ServisHesabi:
    """Erişim belirtecini alır, süresi dolmadan yeniler. İş parçacığı güvenli."""

    def __init__(self, hesap: dict, kapsamlar, oturum=None):
        for alan in ('client_email', 'private_key'):
            if not hesap.get(alan):
                raise AnahtarHatasi('servis hesabında "%s" yok' % alan)
        self.hesap = hesap
        self.kapsamlar = list(kapsamlar)
        self._anahtar = ozel_anahtar_coz(hesap['private_key'])
        self._kilit = threading.Lock()
        self._belirtec = None
        self._bitis = 0.0
        self._oturum = oturum

    def belirtec(self, zorla: bool = False) -> str:
        with self._kilit:
            if zorla or self._belirtec is None or time.time() > self._bitis - 300:
                self._yenile()
            return self._belirtec

    def _yenile(self):
        import requests
        oturum = self._oturum or requests
        url = self.hesap.get('token_uri') or 'https://oauth2.googleapis.com/token'
        simdi = time.time()
        try:
            y = oturum.post(url, timeout=(10, 30), data={
                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'assertion': jwt_kur(self.hesap, self.kapsamlar, simdi, self._anahtar)})
        except requests.RequestException as e:
            raise ErisimHatasi('belirteç sunucusuna ulaşılamadı: %s' % type(e).__name__) from e
        try:
            veri = y.json()
        except ValueError:
            veri = {}
        if y.status_code != 200 or 'access_token' not in veri:
            neden = '%s %s' % (veri.get('error', 'HTTP %d' % y.status_code), veri.get('error_description', ''))
            if 'short-lived' in neden or 'iat' in neden or 'exp' in neden:
                neden += ' — bu makinenin SAATİ yanlış olabilir'
            elif 'invalid_grant' in neden:
                neden += ' — anahtar iptal edilmiş ya da başka projenin olabilir'
            raise ErisimHatasi(neden.strip())
        self._belirtec = veri['access_token']
        self._bitis = simdi + float(veri.get('expires_in', 3600))
