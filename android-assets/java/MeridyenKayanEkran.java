package __PAKET__;

import android.app.Activity;
import android.app.AppOpsManager;
import android.app.PictureInPictureParams;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import android.util.Rational;

/**
 * Meridyen — görüntülü görüşmenin "kayan ekran"ı (Picture-in-Picture).
 *
 * NEDEN NATIVE: Web'in kendi Picture-in-Picture API'si Android WebView'da
 * YOK (document.pictureInPictureEnabled false döner), o yüzden uygulamada
 * düğme hiç görünmüyordu. Android'in kendi PiP'i ise Activity düzeyinde
 * çalışıyor: pencere küçülünce WebView'ın tamamı küçülüyor. Bu yüzden web
 * tarafı da haberdar ediliyor ve o kipte yalnız karşı tarafın görüntüsünü
 * çiziyor (bkz. body.kayan-ekran).
 *
 * GİRİŞ ANI ÖNEMLİ: enterPictureInPictureMode yalnız Activity HENÜZ ön
 * plandayken kabul ediliyor. JavaScript'teki visibilitychange olayı bunun
 * için geç kalıyor — o an pencere zaten arkaya geçmiş oluyor. Bu yüzden
 * karar native tarafta, Activity.onUserLeaveHint içinde veriliyor;
 * Android 12 ve üstünde ayrıca sistemin kendi otomatik girişi açılıyor.
 */
public final class MeridyenKayanEkran {

    /** Görüntülü görüşme sürüyor mu? Yalnız süruyorken kendiliğinden
     *  kayan ekrana geçiyoruz — yoksa ana ekrana dönerken vitrin küçük bir
     *  pencerede asılı kalırdı. */
    private static boolean gorusmeSuruyor = false;
    private static int en = 16, boy = 9;

    private MeridyenKayanEkran() {}

    /**
     * Kayan ekran cihazda DESTEKLENİYOR ama kullanıcı ya da üretici bu
     * uygulamaya kapatmış olabilir (Ayarlar → Uygulamalar → Özel erişim →
     * Resim içinde resim). O zaman enterPictureInPictureMode hiçbir şey
     * yapmıyor ve dışarıdan "çalışmıyor" gibi görünüyor. Ayrı ayrı
     * okuyabilmek için bu var.
     */
    public static boolean izinVarMi(Context c) {
        if (c == null) return false;
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return false;
        try {
            AppOpsManager aom = (AppOpsManager) c.getSystemService(Context.APP_OPS_SERVICE);
            if (aom == null) return true;
            int mod;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                mod = aom.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_PICTURE_IN_PICTURE,
                    android.os.Process.myUid(), c.getPackageName());
            } else {
                mod = aom.checkOpNoThrow(AppOpsManager.OPSTR_PICTURE_IN_PICTURE,
                    android.os.Process.myUid(), c.getPackageName());
            }
            return mod == AppOpsManager.MODE_ALLOWED;
        } catch (Exception e) {
            /* Okunamadıysa izin VAR sayıyoruz: okunamayan bir ayar yüzünden
               çalışan bir özelliği kapatmak, yanlış tarafa düşmek olurdu. */
            return true;
        }
    }

    public static boolean desteklenir(Context c) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return false;
        if (c == null) return false;
        try {
            return c.getPackageManager().hasSystemFeature(PackageManager.FEATURE_PICTURE_IN_PICTURE);
        } catch (Exception e) {
            return false;
        }
    }

    public static void gorusmeDurumu(Activity a, boolean suruyor, int yeniEn, int yeniBoy) {
        gorusmeSuruyor = suruyor;
        if (yeniEn > 0 && yeniBoy > 0) { en = yeniEn; boy = yeniBoy; }
        otomatikGirisiAyarla(a);
    }

    public static boolean gorusmeVarMi() { return gorusmeSuruyor; }

    /** Android 12+: sistem, ana ekrana dönüşü kendisi yakalayıp geçiriyor —
     *  jest ile çıkışta onUserLeaveHint'ten daha güvenilir. */
    private static void otomatikGirisiAyarla(Activity a) {
        if (a == null || Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return;
        try {
            a.setPictureInPictureParams(new PictureInPictureParams.Builder()
                .setAspectRatio(oran())
                .setAutoEnterEnabled(gorusmeSuruyor)
                .build());
        } catch (Exception e) {}
    }

    private static Rational oran() {
        /* Android en/boy oranını 0.42 ile 2.39 arasında istiyor; dışında
           kalan değerde çağrı hata fırlatıp görüşmeyi düşürürdü. */
        double d = (double) en / (double) boy;
        if (d < 0.45 || d > 2.35) return new Rational(16, 9);
        return new Rational(en, boy);
    }

    /** Ana ekrana dönülüyor: görüşme sürüyorsa kayan ekrana geç.
     *
     *  Android 12+'da sistemin kendi otomatik girişi de açık, ama BURADA
     *  ayrıca deniyoruz. Önce "zaten sistem hallediyor" diye atlanıyordu;
     *  oysa otomatik giriş sessizce çalışmayabiliyor (parametreler activity
     *  hazır olmadan kurulmuşsa, ya da üretici katmanı devre dışı bırakmışsa)
     *  ve o durumda kayan ekran hiç açılmıyordu. gir() zaten kipin içindeysek
     *  hiçbir şey yapmıyor, yani ikisi birlikte güvenli. */
    public static void ayrilirken(Activity a) {
        if (!gorusmeSuruyor) return;
        gir(a);
    }

    public static boolean gir(Activity a) {
        if (a == null || !desteklenir(a)) return false;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && a.isInPictureInPictureMode()) return true;
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                return a.enterPictureInPictureMode(
                    new PictureInPictureParams.Builder().setAspectRatio(oran()).build());
            }
        } catch (Exception e) {}
        return false;
    }
}
