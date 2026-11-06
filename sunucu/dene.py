#!/usr/bin/env python3
"""Kurulumu DOĞRULAMA aracı.

Gerçek bir mesaj beklemeden seçtiğin kullanıcıya deneme bildirimi gönderir:
"servis hesabı doğru mu, cihaz belirteci kayıtlı mı, push geliyor mu"
soruları tek komutta yanıtlanıyor. Sunucuyla aynı ortam değişkenlerini okur.

  python3 dene.py <hedefUid> [mesaj]
  python3 dene.py --cihazlar <hedefUid>     kayıtlı cihazları listeler
  python3 dene.py --durum                   çalışan sunucunun nabzını gösterir
  python3 dene.py --kontrol                 kurulumu doğrular: anahtar, veritabanı, FCM izni
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bildirim as B  # noqa: E402
import ortam  # noqa: E402
import sunucu as S  # noqa: E402


def kontrol(ayar, db, fcm):
    """Kurulumu bildirim GÖNDERMEDEN doğrular. Her adım ayrı söylüyor ki
    sorun çıkarsa nerede olduğu belli olsun. Başarıda 0, sorunda 4 döner."""
    sorun = 0
    h = ayar.servis_hesabi or {}
    print('Anahtar      : %s (proje: %s)' % (h.get('client_email', '— emülatör —'), h.get('project_id', ayar.proje)))
    if h and h.get('project_id') != S.VARSAYILAN_PROJE:
        print('  ! Bu anahtar "%s" projesinin; Meridyen "%s". Yanlış dosya olabilir.'
              % (h.get('project_id'), S.VARSAYILAN_PROJE))
    # 1) Google'dan erişim belirteci: anahtarın kendisi geçerli mi
    try:
        db.erisim.baslik()
        print('Erişim       : ✓ anahtar geçerli')
    except Exception as e:
        print('Erişim       : ✗ anahtarla oturum açılamadı — dosya bozuk ya da anahtar iptal edilmiş (%s)'
              % type(e).__name__)
        return 4
    # 2) Veritabanı: bu anahtar bu veritabanını okuyabiliyor mu
    try:
        n = db.oku(S.NABIZ_YOLU)
        print('Veritabanı   : ✓ %s' % db.taban)
        if isinstance(n, dict) and n.get('nabiz'):
            yas = (time.time() * 1000 - n['nabiz']) / 1000
            print('               son sunucu nabzı %d sn önce (%s)' % (yas, n.get('dil') or 'node'))
    except Exception as e:
        sorun += 1
        print('Veritabanı   : ✗ okunamadı — %s' % str(e)[:160])
    # 3) FCM: gönderme izni var mı. validate_only: hiçbir şey gönderilmiyor;
    #    sahte belirteç için "geçersiz belirteç" yanıtı, izinlerin TAMAM
    #    olduğunu gösteriyor (izin yoksa ondan önce 401/403 dönüyor).
    try:
        y = S.requests.post(fcm.url, headers=fcm.erisim.baslik(), timeout=S.ZAMAN_ASIMI, json={
            'validate_only': True,
            'message': {'token': 'meridyen-kurulum-kontrolu-' + 'x' * 20, 'data': {'k': 'v'}}})
        if y.status_code in (200, 400):
            print('FCM          : ✓ gönderme izni var (%s)' % ayar.proje)
        else:
            sorun += 1
            try:
                durum, kod, metin = B.fcm_hatasi_coz(y.status_code, y.json())
            except ValueError:
                durum, kod, metin = 'HTTP_%d' % y.status_code, '', ''
            print('FCM          : ✗ %s %s — %s' % (durum, kod, metin[:120]))
            print('               Firebase konsolunda "Cloud Messaging API (V1)" açık mı, anahtar bu projenin mi?')
    except S.requests.RequestException as e:
        sorun += 1
        print('FCM          : ✗ ulaşılamadı — %s' % type(e).__name__)
    print('\nKurulum %s.' % ('TAMAM' if not sorun else 'SORUNLU'))
    return 4 if sorun else 0


def main():
    arg = sys.argv[1:]
    if not arg:
        print(__doc__)
        return 1
    ortam.yukle()
    ayar, db, fcm = S.kur()

    if arg[0] == '--kontrol':
        return kontrol(ayar, db, fcm)

    if arg[0] == '--durum':
        n = db.oku(S.NABIZ_YOLU) or {}
        if not n:
            print('Hiç nabız yok: sunucu bu veritabanına hiç bağlanmamış.')
            return 2
        yas = (time.time() * 1000 - (n.get('nabiz') or 0)) / 1000
        print('Son nabız: %d sn önce | kip: %s | dil: %s | kimlik: %s' % (
            yas, n.get('kip'), n.get('dil') or 'node', n.get('kimlik') or '-'))
        print('Gönderilen: %s | başarısız: %s | kurulum hatası: %s | başka sunucu: %s' % (
            n.get('gonderilen'), n.get('basarisiz'), n.get('kurulumHatasi'), n.get('cakisma')))
        return 0

    liste = arg[0] == '--cihazlar'
    hedef = arg[1] if liste and len(arg) > 1 else (None if liste else arg[0])
    if not hedef:
        print(__doc__)
        return 1
    metin = ' '.join(arg[1:]) or 'Deneme bildirimi — her şey çalışıyor.'

    cihazlar = db.oku('cihazlar/' + hedef) or {}
    print('Hedef:', hedef)
    print('Kayıtlı cihaz:', len(cihazlar))
    for a, c in sorted(cihazlar.items()):
        c = c or {}
        print('  - %s | içerik: %s | belirteç: %s… | %s' % (
            a, 'açık' if c.get('icerikGoster') else 'kapalı',
            str(c.get('belirtec') or '')[:18], str(c.get('tarayici') or '')[:40]))
    if not cihazlar:
        print('\nHiç cihaz yok. Kullanıcı uygulamayı açıp bildirim iznini vermiş olmalı;')
        print('web tarafında ayrıca firebase-messaging-sw.js sitenin kökünde bulunmalı.')
        return 2
    if liste:
        return 0

    kayit = {'hedef': hedef, 'gonderen': 'DENEME', 'gonderenAd': 'Meridyen', 'tur': 'mesaj',
             'baslik': 'Meridyen', 'metin': metin, 'mid': 'deneme-%d' % time.time()}
    isler, _ = B.mesajlari_kur(kayit, cihazlar, 'deneme')
    basarisiz = 0
    print()
    for anahtar, mesaj in isler:
        tamam, hata = fcm.gonder(mesaj)
        if tamam:
            print('  ✓', anahtar)
        else:
            basarisiz += 1
            tur = B.hata_turu(hata[0], hata[1], hata[2], False)
            print('  ✗ %s  %s %s (%s) %s' % (anahtar, hata[0], hata[1], tur, hata[2][:80]))
    print('\nGönderildi: %d / %d' % (len(isler) - basarisiz, len(isler)))
    return 3 if basarisiz else 0


if __name__ == '__main__':
    sys.exit(main())
