#!/usr/bin/env python3
"""Bildirim sunucusu — saf mantık sınamaları (ağ yok, Firebase yok)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bildirim as B  # noqa: E402

SIMDI = 1_800_000_000_000
KAYIT = {'hedef': 'AYSE', 'gonderen': 'SEMIH', 'gonderenAd': 'Semih', 'tur': 'mesaj',
         'baslik': 'Semih', 'metin': 'gizli metin', 'ts': SIMDI, 'mid': '-Nabc123', 'sid': 'S1'}
ACIK = {'belirtec': 'T' * 30, 'icerikGoster': True, 'ts': 5}
KAPALI = {'belirtec': 'K' * 30, 'icerikGoster': False, 'ts': 5}


class Mesaj(unittest.TestCase):
    def test_yalniz_data(self):
        m = B.mesaj_kur(KAYIT, ACIK, 'q1')
        self.assertNotIn('notification', m)
        self.assertEqual(m['android']['priority'], 'HIGH')
        self.assertEqual(m['android']['ttl'], '86400s')
        self.assertEqual(m['webpush']['headers']['Urgency'], 'high')
        self.assertTrue(all(isinstance(v, str) for v in m['data'].values()))

    def test_iki_platformun_anahtarlari(self):
        d = B.mesaj_kur(KAYIT, ACIK, 'q1')['data']
        self.assertEqual((d['baslik'], d['metin']), ('Semih', 'gizli metin'))
        self.assertEqual((d['title'], d['body']), ('Semih', 'gizli metin'))
        self.assertEqual(d['etiket'], 'meridyen-SEMIH')
        self.assertEqual(d['tag'], d['etiket'])

    def test_mid_tasiniyor(self):
        self.assertEqual(B.mesaj_kur(KAYIT, ACIK, 'q1')['data']['mid'], '-Nabc123')

    def test_mid_yoksa_kuyruk_anahtari(self):
        k = dict(KAYIT); del k['mid']
        self.assertEqual(B.mesaj_kur(k, ACIK, 'q9')['data']['mid'], 'k-q9')

    def test_bozuk_mid_kullanilmiyor(self):
        k = dict(KAYIT, mid='a/b' * 40)
        self.assertEqual(B.mesaj_kur(k, ACIK, 'q9')['data']['mid'], 'k-q9')

    def test_icerik_kapali_metin_hic_gitmiyor(self):
        m = B.mesaj_kur(KAYIT, KAPALI, 'q1')
        self.assertNotIn('gizli metin', str(m))
        self.assertEqual(m['data']['title'], 'Meridyen')

    def test_cagri(self):
        c = dict(KAYIT, tur='arama', metin='Görüntülü arıyor')
        m = B.mesaj_kur(c, KAPALI, 'q1')
        self.assertEqual(m['data']['tur'], 'arama')
        self.assertEqual(m['data']['aramaTuru'], 'goruntu')
        self.assertEqual(m['android']['ttl'], '45s')
        self.assertEqual(m['data']['baslik'], 'Semih', 'çağrıda arayanın adı gizlenmiyor')
        self.assertEqual(m['data']['metin'], 'Arıyor')
        # Web'de çağrı, aynı kişinin okunmamış MESAJ bildiriminin üstüne yazmasın.
        self.assertEqual(m['data']['tag'], 'meridyen-cagri-SEMIH')


class Cihazlar(unittest.TestCase):
    def test_bozuk_cihazlar_atlaniyor(self):
        isler, _ = B.mesajlari_kur(KAYIT, {'a': ACIK, 'b': {'belirtec': 'kisa'}, 'c': {}, 'd': None}, 'q')
        self.assertEqual([a for a, _ in isler], ['a'])

    def test_ayni_belirtec_iki_kayitta_tek_gonderim(self):
        isler, _ = B.mesajlari_kur(KAYIT, {'a': ACIK, 'b': dict(ACIK)}, 'q')
        self.assertEqual(len(isler), 1)

    def test_yeniden_denemede_yalniz_kalanlar(self):
        isler, _ = B.mesajlari_kur(KAYIT, {'a': ACIK, 'b': KAPALI}, 'q', yalniz={'b'})
        self.assertEqual([a for a, _ in isler], ['b'])

    def test_hesap_degisen_telefon(self):
        """Aynı belirteç YENİ hesapta daha yeni kayıtlı: eski hesaba gitmemeli."""
        tum = {'ESKI': {'x': {'belirtec': 'Z' * 30, 'ts': 100}},
               'YENI': {'y': {'belirtec': 'Z' * 30, 'ts': 200}}}
        harita = B.sahiplik_haritasi(tum)
        isler, devredilen = B.mesajlari_kur(dict(KAYIT, hedef='ESKI'), tum['ESKI'], 'q', harita)
        self.assertEqual((isler, devredilen), ([], ['x']))
        isler, devredilen = B.mesajlari_kur(dict(KAYIT, hedef='YENI'), tum['YENI'], 'q', harita)
        self.assertEqual((len(isler), devredilen), (1, []))

    def test_esit_zamanda_silinmiyor(self):
        tum = {'A': {'x': {'belirtec': 'Z' * 30, 'ts': 100}}, 'B': {'y': {'belirtec': 'Z' * 30, 'ts': 100}}}
        _, devredilen = B.mesajlari_kur(dict(KAYIT, hedef='A'), tum['A'], 'q', B.sahiplik_haritasi(tum))
        self.assertEqual(devredilen, [])


class Kayit(unittest.TestCase):
    def test_gecersiz(self):
        for k in (None, {}, {'hedef': 'x'}, {'hedef': 'x', 'gonderen': ''}, [1]):
            self.assertFalse(B.kayit_gecerli_mi(k))

    def test_kendine_bildirim_yok(self):
        self.assertFalse(B.kayit_gecerli_mi({'hedef': 'A', 'gonderen': 'A'}))

    def test_bayat(self):
        self.assertIsNone(B.bayat_mi(dict(KAYIT, ts=SIMDI - 29 * 60_000), SIMDI))
        self.assertIsNotNone(B.bayat_mi(dict(KAYIT, ts=SIMDI - 31 * 60_000), SIMDI))
        cagri = dict(KAYIT, tur='arama')
        self.assertIsNone(B.bayat_mi(dict(cagri, ts=SIMDI - 30_000), SIMDI))
        self.assertIsNotNone(B.bayat_mi(dict(cagri, ts=SIMDI - 90_000), SIMDI), 'bitmiş çağrının zili çalmasın')
        self.assertIsNone(B.bayat_mi(dict(KAYIT, ts=None), SIMDI))


class Hatalar(unittest.TestCase):
    def tur(self, http, govde, basari=False):
        return B.hata_turu(*B.fcm_hatasi_coz(http, govde), basari)

    @staticmethod
    def hata(status, kod=None, mesaj=''):
        d = [{'@type': 'type.googleapis.com/google.firebase.fcm.v1.FcmError', 'errorCode': kod}] if kod else []
        return {'error': {'status': status, 'message': mesaj, 'details': d}}

    def test_olu(self):
        self.assertEqual(self.tur(404, self.hata('NOT_FOUND', 'UNREGISTERED')), 'olu')
        self.assertEqual(self.tur(400, self.hata('INVALID_ARGUMENT', 'INVALID_ARGUMENT',
                                                 'The registration token is not a valid FCM registration token')), 'olu')

    def test_yuk_hatasi_olu_degil(self):
        self.assertEqual(self.tur(400, self.hata('INVALID_ARGUMENT', 'INVALID_ARGUMENT',
                                                 'Invalid value at message.data')), 'diger')

    def test_gecici(self):
        self.assertEqual(self.tur(503, self.hata('UNAVAILABLE', 'UNAVAILABLE')), 'gecici')
        self.assertEqual(self.tur(500, None), 'gecici')
        self.assertEqual(self.tur(429, self.hata('RESOURCE_EXHAUSTED', 'QUOTA_EXCEEDED')), 'gecici')
        self.assertEqual(B.hata_turu('AG', '', 'Connection reset', False), 'gecici')

    def test_kurulum_belirteci_silmiyor(self):
        self.assertEqual(self.tur(401, self.hata('UNAUTHENTICATED', 'THIRD_PARTY_AUTH_ERROR')), 'kurulum')
        self.assertEqual(self.tur(401, self.hata('UNAUTHENTICATED')), 'kurulum')
        self.assertEqual(self.tur(403, self.hata('PERMISSION_DENIED', 'SENDER_ID_MISMATCH')), 'kurulum')

    def test_sender_id_mismatch_basaridan_sonra_olu(self):
        self.assertEqual(self.tur(403, self.hata('PERMISSION_DENIED', 'SENDER_ID_MISMATCH'), basari=True), 'olu')

    def test_geri_cekilme(self):
        self.assertEqual([B.geri_cekilme_sn(n) for n in (1, 2, 3, 4, 5, 9)], [2, 4, 8, 16, 30, 30])


class Sinir(unittest.TestCase):
    def test_patlama_sonra_saniyede_bir(self):
        h = B.HizSiniri(kapasite=3, saniyede=1)
        self.assertEqual([h.izin_ver('a', 0) for _ in range(4)], [True, True, True, False])
        self.assertTrue(h.izin_ver('b', 0), 'başka gönderen etkilenmiyor')
        self.assertTrue(h.izin_ver('a', 1.0))
        self.assertFalse(h.izin_ver('a', 1.0))


class Sahiplenme(unittest.TestCase):
    def test(self):
        self.assertTrue(B.sahiplenilebilir_mi({'hedef': 'x'}, 'BEN', SIMDI))
        self.assertTrue(B.sahiplenilebilir_mi({'isleyen': {'kimlik': 'BEN', 'bitis': SIMDI + 9}}, 'BEN', SIMDI))
        self.assertFalse(B.sahiplenilebilir_mi({'isleyen': {'kimlik': 'O', 'bitis': SIMDI + 9}}, 'BEN', SIMDI))
        self.assertTrue(B.sahiplenilebilir_mi({'isleyen': {'kimlik': 'O', 'bitis': SIMDI - 1}}, 'BEN', SIMDI),
                        'kirası dolmuş kayıt devralınır')
        self.assertFalse(B.sahiplenilebilir_mi(None, 'BEN', SIMDI))


if __name__ == '__main__':
    unittest.main(verbosity=1)
