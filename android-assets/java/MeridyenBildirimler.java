package __PAKET__;

import android.app.ActivityManager;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

import java.util.List;

/**
 * Meridyen — mesaj bildirimlerinin ORTAK tarafı.
 *
 * Bildirim üç ayrı yerden çıkabiliyor ve üçünün de AYNI görünmesi, aynı
 * kanalı kullanması, aynı id ile birbirinin üstüne yazması gerekiyor:
 *
 *   1) Uygulama açıkken  : web tarafı `new Notification(...)` çağırıyor
 *                          (meridyen-native.js köprüsü üzerinden).
 *   2) Uygulama kapalıyken: sunucudan gelen FCM verisi — MeridyenMesajServisi.
 *   3) Ayarlar'daki sınama düğmesi.
 *
 * id'ler bu yüzden burada, index.html'in `tag` mantığıyla BİREBİR aynı
 * karmadan üretiliyor: aynı kişiden gelen ikinci bildirim yenisini eklemek
 * yerine öncekini güncelliyor ve iki yol aynı anda çalışsa bile ekranda tek
 * bildirim kalıyor.
 */
public final class MeridyenBildirimler {

    /** Mesajlar için AYRI kanal: yükleme ilerlemesi sessiz ve düşük önemli,
     *  mesaj ise ekranın üstünde belirmeli, ses ve titreşim vermeli. Tek
     *  kanalda ikisi birden olamıyor — Android'de önem kanal başına. */
    public static final String KANAL_MESAJ = "meridyen_mesaj";
    public static final String GRUP = "meridyen_mesajlar";
    public static final String EK_GONDEREN = "meridyen_gonderen";
    public static final String EK_TUR = "meridyen_tur";

    private MeridyenBildirimler() {}

    public static void mesajKanaliniKur(Context c) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm =
            (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null || nm.getNotificationChannel(KANAL_MESAJ) != null) return;
        NotificationChannel k = new NotificationChannel(
            KANAL_MESAJ, "Mesajlar", NotificationManager.IMPORTANCE_HIGH);
        k.setDescription("Yeni mesaj ve çağrı bildirimleri");
        k.enableVibration(true);
        k.setShowBadge(true);
        /* Kilit ekranı görünürlüğüne BİLEREK dokunulmuyor: varsayılan
           (VISIBILITY_PRIVATE) kullanıcının sistem ayarına uyuyor. Burada
           sabitleseydik uygulamanın kendi "bildirimde mesajı göster"
           tercihini ezerdik. */
        nm.createNotificationChannel(k);
    }

    /**
     * index.html'in `tag` değerini Android'in sayısal bildirim id'sine çevirir.
     *
     * meridyen-native.js içindeki `etiketId` ile BİREBİR aynı olmak zorunda:
     * aynı sohbetin bildirimi hangi yoldan gelirse gelsin aynı id'ye düşmeli,
     * yoksa aynı mesaj için iki bildirim görünür.
     */
    public static int etiketId(String etiket) {
        int h = 0;
        String s = etiket == null ? "" : etiket;
        for (int i = 0; i < s.length(); i++) {
            h = h * 31 + s.charAt(i);   // JS'teki `| 0` ile aynı: int taşması
        }
        /* JS'te Math.abs(-2147483648) = 2147483648 (sayı int32'ye sıkışmıyor),
           Java'da Math.abs(Integer.MIN_VALUE) NEGATİF döner. İki taraf aynı
           sonucu versin diye long'a genişletiyoruz. */
        long m = Math.abs((long) h) % 1900000000L;
        return m == 0 ? 1 : (int) m;
    }

    /** Durum çubuğu ikonu: uygulamanın tek renk "M" ikonu, yoksa sistem ikonu. */
    static int ikon(Context c) {
        int id = c.getResources().getIdentifier(
            "ic_stat_meridyen", "drawable", c.getPackageName());
        return id != 0 ? id : android.R.drawable.stat_notify_chat;
    }

    static int renk(Context c) {
        int id = c.getResources().getIdentifier(
            "meridyen_vurgu", "color", c.getPackageName());
        if (id == 0) return 0;
        try {
            return androidx.core.content.ContextCompat.getColor(c, id);
        } catch (Exception e) {
            return 0;
        }
    }

    private static PendingIntent acmaNiyeti(Context c, int id, String gonderen, String tur) {
        Intent i = c.getPackageManager().getLaunchIntentForPackage(c.getPackageName());
        if (i == null) return null;
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        if (gonderen != null) i.putExtra(EK_GONDEREN, gonderen);
        if (tur != null) i.putExtra(EK_TUR, tur);
        /* requestCode olarak bildirim id'si veriliyor. Hepsine 0 verilseydi
           FLAG_UPDATE_CURRENT yüzünden AÇIK olan tüm bildirimlerin niyeti
           sonuncusununkiyle değişir ve her biri yanlış sohbeti açardı. */
        int bayrak = PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE;
        return PendingIntent.getActivity(c, id, i, bayrak);
    }

    /** Tek mesaj bildirimi yayınlar (ya da aynı etiketlisini günceller). */
    public static void mesaj(Context c, String baslik, String govde,
                             String etiket, String gonderen, String tur) {
        try {
            mesajKanaliniKur(c);
            int id = etiketId(etiket);
            String b = (baslik == null || baslik.length() == 0) ? "Meridyen" : baslik;
            String g = govde == null ? "" : govde;

            NotificationCompat.Builder kur = new NotificationCompat.Builder(c, KANAL_MESAJ)
                .setSmallIcon(ikon(c))
                .setContentTitle(b)
                .setContentText(g)
                // Kilit ekranında tek satıra sığmayan metin açılabilsin.
                .setStyle(new NotificationCompat.BigTextStyle().bigText(g))
                .setAutoCancel(true)
                .setCategory(NotificationCompat.CATEGORY_MESSAGE)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                // Android 8 ÖNCESİ için: orada önem kanaldan değil buradan geliyor.
                .setDefaults(NotificationCompat.DEFAULT_ALL)
                .setGroup(GRUP);

            int r = renk(c);
            if (r != 0) kur.setColor(r);

            PendingIntent niyet = acmaNiyeti(c, id, gonderen, tur);
            if (niyet != null) kur.setContentIntent(niyet);

            NotificationManagerCompat.from(c).notify(id, kur.build());
        } catch (SecurityException e) {
            // POST_NOTIFICATIONS izni yok: sessizce geç, uygulama çalışmaya devam etsin.
        } catch (Exception e) {}
    }

    /**
     * Uygulama ŞU AN önde mi?
     *
     * Öndeyse bildirimi biz çizmiyoruz: web tarafı zaten veritabanı
     * dinleyicisinden kendi bildirimini gösteriyor ve ekranda açık olan
     * sohbet için hiç göstermiyor. İkisi birden çalışsa aynı mesaj iki kez
     * görünürdü.
     */
    public static boolean ondeMi(Context c) {
        try {
            ActivityManager am = (ActivityManager) c.getSystemService(Context.ACTIVITY_SERVICE);
            if (am == null) return false;
            List<ActivityManager.RunningAppProcessInfo> liste = am.getRunningAppProcesses();
            if (liste == null) return false;
            int pid = android.os.Process.myPid();
            for (ActivityManager.RunningAppProcessInfo p : liste) {
                if (p.pid == pid) {
                    return p.importance == ActivityManager.RunningAppProcessInfo.IMPORTANCE_FOREGROUND;
                }
            }
        } catch (Exception e) {}
        return false;
    }
}
