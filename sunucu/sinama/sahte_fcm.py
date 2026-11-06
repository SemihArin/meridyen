"""Sahte FCM HTTP v1 sunucusu — yalnız sınama için.

Gerçek sunucu kodunun HTTP yolu (istek kurma, hata yanıtı ayrıştırma) olduğu
gibi çalışsın diye FCM'i taklit ediyor. Belirtecin içindeki sözcük yanıtı
belirliyor:

  OLU            404 UNREGISTERED             (belirteç ölü)
  GECERSIZ       400 "not a valid FCM registration token"
  YUKHATASI      400 INVALID_ARGUMENT, yük hatası (belirteç ölü DEĞİL)
  GECICI<n>      ilk n denemede 503, sonra başarı
  HEP_GECICI     hep 503
  YANLISANAHTAR  403 SENDER_ID_MISMATCH
  UCUNCU         401 THIRD_PARTY_AUTH_ERROR
  (diğer)        200
"""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class SahteFcm:
    def __init__(self):
        self.kilit = threading.Lock()
        self.denemeler = []         # her istek: (belirteç, data)
        self.basarilar = []         # yalnız başarılı olanlar
        self._sayac = {}
        self.dogrulamalar = 0
        sahte = self

        class Isleyici(BaseHTTPRequestHandler):
            def do_POST(self):
                govde = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)))
                m = govde['message']
                if govde.get('validate_only'):      # dene.py --kontrol: hiçbir şey gönderilmez
                    with sahte.kilit:
                        sahte.dogrulamalar += 1
                    kod, yanit = 200, {'name': 'projects/demo/messages/fake_message_id'}
                else:
                    kod, yanit = sahte._karar(m)
                veri = json.dumps(yanit).encode()
                self.send_response(kod)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(veri)))
                self.end_headers()
                self.wfile.write(veri)

            def log_message(self, *a):
                pass

        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Isleyici)
        self.port = self.http.server_address[1]
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    @staticmethod
    def _hata(http, status, kod, mesaj=''):
        d = [{'@type': 'type.googleapis.com/google.firebase.fcm.v1.FcmError', 'errorCode': kod}] if kod else []
        return http, {'error': {'code': http, 'status': status, 'message': mesaj, 'details': d}}

    def _karar(self, m):
        t = m['token']
        with self.kilit:
            self.denemeler.append((t, m['data']))
            n = self._sayac[t] = self._sayac.get(t, 0) + 1
        if 'OLU' in t:
            return self._hata(404, 'NOT_FOUND', 'UNREGISTERED', 'Requested entity was not found.')
        if 'GECERSIZ' in t:
            return self._hata(400, 'INVALID_ARGUMENT', 'INVALID_ARGUMENT',
                              'The registration token is not a valid FCM registration token')
        if 'YUKHATASI' in t:
            return self._hata(400, 'INVALID_ARGUMENT', 'INVALID_ARGUMENT', 'Invalid value at message.data')
        if 'HEP_GECICI' in t:
            return self._hata(503, 'UNAVAILABLE', 'UNAVAILABLE')
        g = re.search(r'GECICI(\d)', t)
        if g and n <= int(g.group(1)):
            return self._hata(503, 'UNAVAILABLE', 'UNAVAILABLE')
        if 'YANLISANAHTAR' in t:
            return self._hata(403, 'PERMISSION_DENIED', 'SENDER_ID_MISMATCH')
        if 'UCUNCU' in t:
            return self._hata(401, 'UNAUTHENTICATED', 'THIRD_PARTY_AUTH_ERROR')
        with self.kilit:
            self.basarilar.append((t, m['data']))
        return 200, {'name': 'projects/demo/messages/%d' % len(self.basarilar)}

    def sifirla(self):
        with self.kilit:
            self.denemeler.clear()
            self.basarilar.clear()
            self._sayac.clear()

    def kopya(self):
        with self.kilit:
            return list(self.denemeler), list(self.basarilar)

    def kapat(self):
        self.http.shutdown()
