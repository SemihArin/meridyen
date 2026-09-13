package __PAKET__;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

import androidx.core.app.NotificationCompat;

/**
 * Meridyen — arka planda bağlı kalma ("nöbet").
 *
 * SORUN: Uygulama bir süre arka planda kalınca bildirimler kesiliyordu.
 * Sebebi Android'in kendi davranışı: arka plandaki uygulama bir süre sonra
 * "önbelleğe alınmış" sayılıyor, Android 14'ten beri işlem dondurulabiliyor
 * ve Doze kipinde ağ erişimi kesiliyor. WebView'daki JavaScript durunca
 * veritabanı bağlantısı da ölüyor; yeni mesaj gelse bile kimse görmüyor.
 *
 * ÇÖZÜM: Ön plan servisi. Tek işi VAR OLMAK — hiçbir şey hesaplamıyor, uyanık
 * tutma kilidi (wake lock) almıyor. Varlığı işlemi "önbelleğe alınmış"
 * olmaktan çıkarıyor: dondurulmuyor ve Doze'da ağ erişimi sürüyor, böylece
 * veritabanı bağlantısı ve onun beslediği bildirimler çalışmaya devam ediyor.
 *
 * BEDELİ dürüstçe: Android 8'den beri ön plan servisi KALICI bir bildirim
 * göstermek zorunda. Bu yüzden bildirim en düşük önemde ve sessiz —
 * bildirim gölgesinin en altında tek satır. Ayarlardan kapatılabiliyor.
 *
 * Uygulama KAPALIYKEN gelen bildirim yine sunucudan gelen FCM'e bağlı
 * (bkz. MeridyenMesajServisi); bu servis "açık ama arka planda" durumunu
 * çözüyor, o ayrı sorunu değil.
 */
public class MeridyenNobet extends Service {

    private static final String KANAL = "meridyen_nobet";
    private static final int BILDIRIM_ID = 2000000002;   // ilerleme bildiriminin komşusu

    public static boolean calisiyor = false;

    public static void baslat(Context c) {
        try {
            Intent i = new Intent(c, MeridyenNobet.class);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) c.startForegroundService(i);
            else c.startService(i);
        } catch (Exception e) {
            /* Android 12+ arka plandan ön plan servisi başlatmayı reddedebilir.
               Uygulama görünürken çağırdığımız için normalde olmaz; olursa da
               uygulamanın kalanı çalışmaya devam etmeli. */
        }
    }

    public static void durdur(Context c) {
        try { c.stopService(new Intent(c, MeridyenNobet.class)); } catch (Exception e) {}
    }

    private void kanaliKur() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null || nm.getNotificationChannel(KANAL) != null) return;
        NotificationChannel k = new NotificationChannel(
            KANAL, "Arka planda bağlı", NotificationManager.IMPORTANCE_MIN);
        k.setDescription("Mesajların gecikmeden gelmesi için açık kalan bağlantı");
        k.setShowBadge(false);
        k.enableVibration(false);
        k.setSound(null, null);
        nm.createNotificationChannel(k);
    }

    private Notification bildirim() {
        kanaliKur();
        int ikon = getResources().getIdentifier("ic_stat_meridyen", "drawable", getPackageName());
        NotificationCompat.Builder kur = new NotificationCompat.Builder(this, KANAL)
            .setSmallIcon(ikon != 0 ? ikon : android.R.drawable.stat_notify_sync)
            .setContentTitle("Meridyen")
            .setContentText("Mesajlar için bağlantı açık")
            .setOngoing(true)
            .setSilent(true)
            .setShowWhen(false)
            .setPriority(NotificationCompat.PRIORITY_MIN);
        try {
            Intent i = getPackageManager().getLaunchIntentForPackage(getPackageName());
            if (i != null) {
                i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
                kur.setContentIntent(PendingIntent.getActivity(this, 3, i,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE));
            }
        } catch (Exception e) {}
        return kur.build();
    }

    @Override
    public int onStartCommand(Intent niyet, int bayraklar, int id) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                startForeground(BILDIRIM_ID, bildirim(),
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            } else {
                startForeground(BILDIRIM_ID, bildirim());
            }
            calisiyor = true;
        } catch (Exception e) {
            calisiyor = false;
            stopSelf();
            return START_NOT_STICKY;
        }
        /* START_STICKY: sistem belleğe ihtiyaç duyup servisi kapatırsa
           yeniden başlatsın — nöbetin anlamı sürekliliği. */
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        calisiyor = false;
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent niyet) { return null; }
}
