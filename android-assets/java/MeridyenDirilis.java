package __PAKET__;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.WebView;

import com.getcapacitor.WebViewListener;

/**
 * Meridyen — İŞLEYİCİ SÜRECİ ÖLÜNCE SAYFAYI DİRİLTİR.
 *
 * SORUN: Sayfayı çalıştıran Chromium işleyici süreci (renderer) uygulamanın
 * kendi süreci DEĞİL, ayrı bir sandbox süreci. Android bellek sıkıştığında
 * uygulamayı öldürmeden YALNIZ onu öldürebiliyor. O an ortaya çıkan tablo
 * kayıtlarda donmayla birebir aynı görünüyor ama bambaşka bir şey:
 *
 *   - Ön plan servisi hayatta, bildirim çubuğunda "Meridyen etkin" yazıyor,
 *   - ama sayfa yok: Firebase'i dinleyen, mesajı işleyen, bildirimi çizen
 *     hiçbir JavaScript kalmadı,
 *   - kullanıcı uygulamayı açınca beyaz ekran görüyor.
 *
 * Capacitor bu olay için bir kanca sunuyor (WebViewListener) ama ÖNTANIMLI
 * KARŞILIĞI `false` — yani "ben ilgilenmiyorum". Android'de bu cevabın anlamı
 * kesin: sistem uygulama sürecini öldürüyor. Yani şu ana dek her işleyici
 * ölümü sessiz bir çökmeyle sonuçlanıyordu.
 *
 * ÇÖZÜM: `true` dönüp toparlanmayı kendimiz yapıyoruz. Ölen WebView bir daha
 * kullanılamaz (Android bunu açıkça söylüyor), bu yüzden Activity'yi yeniden
 * yaratıyoruz: yeni yerleşim, yeni WebView, yeni işleyici süreç. Sayfa
 * sıfırdan yükleniyor ve dinlemeye kaldığı yerden devam ediyor.
 *
 * NEDEN ÖLEN WebView'ı destroy() ETMİYORUZ? Android'in tarif ettiği temizlik
 * bu, ama burada zararı faydasından çok: destroy() edilmiş bir WebView'ın
 * çağrıları İSTİSNA atıyor, ölü bir WebView'ın çağrıları ise sessizce hiçbir
 * şey yapmıyor. Diriltmeyi kullanıcının dönüşüne bıraktığımız durumda (aşağı
 * bkz.) arada gelen bir push köprüyü yoklayabiliyor; o yoklamanın çökmeye
 * dönüşmesini istemiyoruz. Activity yeniden yaratılınca eski görünüm ağacı
 * zaten gidiyor; geride en kötü durumda birkaç WebView nesnesi kalıyor.
 *
 * SONSUZ DÖNGÜ KORUMASI: bellek gerçekten tükendiyse yeni işleyici de hemen
 * ölebilir. Aynı beş dakika içinde en çok üç kez otomatik diriltiyoruz; üstüne
 * çıkarsa arka planda pili tüketmek yerine bırakıyoruz ve diriltmeyi
 * KULLANICI ÖNE GELDİĞİNDE yapıyoruz — böylece ne döngü oluyor ne de
 * kullanıcı beyaz ekran görüyor.
 */
public class MeridyenDirilis extends WebViewListener {

    private static final String DEPO = "meridyen_dirilis";
    private static final String A_SAYI = "sayi";     // toplam kaç kez oldu
    private static final String A_SON = "son";       // son olayın zamanı (ms)
    private static final String A_COKME = "cokme";   // son olay çökme miydi?

    /** Aynı pencere içinde en çok bu kadar OTOMATİK diriltme yapılır. */
    private static final int ENCOK = 3;
    private static final long PENCERE_MS = 5 * 60 * 1000L;

    /** Son diriltmelerin zamanları; süreç ömrü boyunca tutuluyor. */
    static final Sayac sayac = new Sayac(ENCOK, PENCERE_MS);

    /**
     * "Belirli bir pencerede en çok N kez" kuralı. Kendi başına duruyor ki
     * davranışı Android olmadan sınanabilsin: yanlış kurulursa iki ayrı zarar
     * veriyor — çok gevşekse bellek tükenmişken sonsuz diriltme döngüsüne
     * girip pili bitiriyor, çok sıkıysa tek seferlik bir ölümden sonra
     * kullanıcıyı ölü sayfayla bırakıyor.
     */
    static final class Sayac {
        private final long[] gecmis;
        private final long pencere;
        private int sira = 0;

        Sayac(int encok, long pencereMs) {
            this.gecmis = new long[encok];
            this.pencere = pencereMs;
        }

        /** Pencerede yer var mı — yani bir diriltme daha yapılabilir mi? */
        boolean yerVarMi(long simdi) {
            int sayi = 0;
            for (long t : gecmis) {
                if (t > 0 && simdi - t < pencere) sayi++;
            }
            return sayi < gecmis.length;
        }

        void ekle(long simdi) {
            gecmis[Math.abs(sira % gecmis.length)] = simdi;
            sira++;
        }

        /** Kullanıcı öne geldi: bellek tablosu değişti, geçmişi siliyoruz. */
        void sifirla() {
            for (int i = 0; i < gecmis.length; i++) gecmis[i] = 0L;
            sira = 0;
        }
    }

    /** Otomatik diriltmeden vazgeçildi: kullanıcı öne gelince diriltilecek. */
    private static volatile boolean bekliyor = false;

    private final Activity etkinlik;

    public MeridyenDirilis(Activity etkinlik) {
        this.etkinlik = etkinlik;
    }

    /* ---------------------------------------------------------------- */

    @Override
    public boolean onRenderProcessGone(WebView gorunum, RenderProcessGoneDetail ayrinti) {
        boolean cokme = false;
        try {
            if (ayrinti != null) cokme = ayrinti.didCrash();
        } catch (Exception e) {}

        Context baglam = (etkinlik != null) ? etkinlik
                       : ((gorunum != null) ? gorunum.getContext() : null);
        kaydet(baglam, cokme);

        long simdi = System.currentTimeMillis();
        if (sayac.yerVarMi(simdi)) {
            sayac.ekle(simdi);
            /* Diriltmeyi BU geri çağrıdan sonraya erteliyoruz: şu an yığın
               WebView'ın kendi kodunun içinde, Activity'yi oradan yeniden
               yaratmak istemiyoruz. */
            sonraDirilt();
        } else {
            bekliyor = true;
        }

        /* true = "durumu ben hallediyorum". false dönersek Android uygulama
           sürecini öldürür — öntanımlı davranış buydu. */
        return true;
    }

    /** Her sayfa yüklenişinde gerçek ön/arka plan durumunu sayfaya tazeliyor.
     *  Diriltme arka planda olduğunda sayfa sıfırdan yükleniyor ve köprü
     *  "öndeyim" varsayımıyla başlıyor; düzeltilmezse arka planda açık sohbet
     *  sanıp bildirimi yutabiliyordu. */
    @Override
    public void onPageLoaded(WebView gorunum) {
        MeridyenIlerleme.onPlanTazele();
    }

    /* ---------------------------------------------------------------- */

    /** MeridyenIlerleme.handleOnResume'dan: ertelenen diriltme varsa şimdi. */
    public static void onGelindi(Activity a) {
        if (!bekliyor) return;
        bekliyor = false;
        /* Kullanıcı geri döndü: bellek tablosu büyük olasılıkla değişti,
           sayacı sıfırlıyoruz ki bir sonraki ölüm yine otomatik onarılsın. */
        sayac.sifirla();
        dirilt(a);
    }

    private void sonraDirilt() {
        final Activity a = etkinlik;
        if (a == null) return;
        try {
            new Handler(Looper.getMainLooper()).post(new Runnable() {
                @Override
                public void run() { dirilt(a); }
            });
        } catch (Exception e) {}
    }

    private static void dirilt(Activity a) {
        if (a == null) return;
        try {
            /* minSdk 23: ikisi de her sürümde var, sürüm kontrolü gereksiz. */
            if (a.isFinishing() || a.isDestroyed()) return;
            /* recreate() Activity'yi yıkıp yeniden kuruyor: yeni yerleşim,
               yeni WebView, yeni işleyici süreç. Arka planda da çalışıyor —
               BridgeActivity sayfayı onCreate içinde yüklüyor, görünür
               olmayı beklemiyor. */
            a.recreate();
        } catch (Exception e) {}
    }

    /* ---------------------------------------------------------------- */

    private static void kaydet(Context baglam, boolean cokme) {
        if (baglam == null) return;
        try {
            SharedPreferences d = baglam.getSharedPreferences(DEPO, Context.MODE_PRIVATE);
            d.edit()
             .putInt(A_SAYI, d.getInt(A_SAYI, 0) + 1)
             .putLong(A_SON, System.currentTimeMillis())
             .putBoolean(A_COKME, cokme)
             .apply();
        } catch (Exception e) {}
    }

    /** Tanı ekranı için: kaç kez oldu. */
    public static int sayi(Context baglam) {
        try {
            return baglam.getSharedPreferences(DEPO, Context.MODE_PRIVATE).getInt(A_SAYI, 0);
        } catch (Exception e) { return 0; }
    }

    /** Tanı ekranı için: son olay kaç ms önceydi (hiç olmadıysa 0). */
    public static long oncekiMs(Context baglam) {
        try {
            long t = baglam.getSharedPreferences(DEPO, Context.MODE_PRIVATE).getLong(A_SON, 0L);
            if (t <= 0) return 0L;
            long gecen = System.currentTimeMillis() - t;
            return gecen < 0 ? 0L : gecen;
        } catch (Exception e) { return 0L; }
    }

    /** Tanı ekranı için: son olay çökme miydi (yoksa bellek için öldürülme). */
    public static boolean cokmeMiydi(Context baglam) {
        try {
            return baglam.getSharedPreferences(DEPO, Context.MODE_PRIVATE).getBoolean(A_COKME, false);
        } catch (Exception e) { return false; }
    }
}
