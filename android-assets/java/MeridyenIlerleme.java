package __PAKET__;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.view.Window;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * Meridyen — gönderim ilerlemesi için bildirim.
 *
 * NEDEN AYRI BİR EKLENTİ:
 * Bu iş önce @capacitor/local-notifications ile yapılmıştı ama o eklenti bu
 * amaca uygun değil, üstelik iki eksiği kendi kaynağında yazılı:
 *
 *   1) LocalNotificationManager.schedule() her çağrıda önce
 *      dismissVisibleNotification(id) çağırıyor — yani bildirimi SİLİP
 *      yeniden yayınlıyor. Sonuç: ilerleme yerinde güncellenmiyor, her
 *      yüzdede yeni bir bildirim gelmiş gibi görünüyor.
 *   2) Kaynağında "// TODO Progressbar support" yazıyor: ilerleme çubuğu
 *      desteği yok. Elde kalan tek seçenek yüzdeyi metne yazmaktı.
 *
 * Burada ikisi de doğru yapılıyor: notify() AYNI id ile, silmeden çağrılıyor
 * (Android bunu yerinde günceller) ve setProgress ile GERÇEK bir ilerleme
 * çubuğu çiziliyor.
 */
@CapacitorPlugin(name = "MeridyenIlerleme")
public class MeridyenIlerleme extends Plugin {

    private static final String KANAL = "meridyen_yukleme";
    /** Tek bir gönderim bildirimi var; sabit id yerinde güncellemenin şartı.
     *  Değer bilerek 1.9 milyarın ÜSTÜNDE: mesaj bildirimlerinin id'leri
     *  meridyen-native.js içinde `% 1900000000` ile o sınırın altına
     *  sıkıştırılıyor, böylece iki bildirim birbirinin üstüne yazamıyor. */
    private static final int BILDIRIM_ID = 2000000001;

    private void kanaliKur() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm =
            (NotificationManager) getContext().getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null || nm.getNotificationChannel(KANAL) != null) return;
        /* DÜŞÜK önem: ilerleme bildirimi ekranın üstünde belirip kullanıcıyı
           rahatsız etmemeli, ses ve titreşim de olmamalı. */
        NotificationChannel k = new NotificationChannel(
            KANAL, "Gönderim", NotificationManager.IMPORTANCE_LOW);
        k.setDescription("Dosya gönderilirken ilerlemeyi gösterir");
        k.setShowBadge(false);
        k.enableVibration(false);
        k.setSound(null, null);
        nm.createNotificationChannel(k);
    }

    /** Durum çubuğu ikonu: uygulamanın tek renk "M" ikonu, yoksa sistem ikonu. */
    private int ikon() {
        int id = getContext().getResources().getIdentifier(
            "ic_stat_meridyen", "drawable", getContext().getPackageName());
        return id != 0 ? id : android.R.drawable.stat_sys_upload;
    }

    private PendingIntent uygulamayiAcmaNiyeti() {
        Intent i = getContext().getPackageManager()
            .getLaunchIntentForPackage(getContext().getPackageName());
        if (i == null) return null;
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        int bayrak = PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE;
        return PendingIntent.getActivity(getContext(), 0, i, bayrak);
    }

    @PluginMethod
    public void goster(PluginCall call) {
        try {
            kanaliKur();
            String baslik = call.getString("baslik", "Gönderiliyor");
            String alt = call.getString("alt", "");
            Integer y = call.getInt("yuzde", 0);
            int yuzde = Math.max(0, Math.min(100, y == null ? 0 : y));
            Boolean b = call.getBoolean("belirsiz", Boolean.FALSE);
            boolean belirsiz = Boolean.TRUE.equals(b);

            NotificationCompat.Builder kur = new NotificationCompat.Builder(getContext(), KANAL)
                .setSmallIcon(ikon())
                .setContentTitle(baslik)
                .setContentText(alt)
                .setOngoing(true)                 // kaydırarak silinemesin: iş sürüyor
                .setOnlyAlertOnce(true)           // güncellemede ses/titreşim yok
                .setSilent(true)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .setProgress(100, yuzde, belirsiz);

            PendingIntent niyet = uygulamayiAcmaNiyeti();
            if (niyet != null) kur.setContentIntent(niyet);

            /* notify() AYNI id ile: Android bildirimi yerinde günceller.
               Önce iptal ETMİYORUZ — asıl arıza oydu. */
            NotificationManagerCompat.from(getContext()).notify(BILDIRIM_ID, kur.build());
            call.resolve();
        } catch (SecurityException e) {
            // Bildirim izni yoksa gönderim yine sürsün; yalnız bildirim çıkmaz.
            call.resolve();
        } catch (Exception e) {
            call.resolve();
        }
    }

    /**
     * Durum çubuğu ve gezinme çubuğu SİMGELERİNİN rengini ayarlar.
     *
     * Uygulamanın iki ayrı yüzü var: vitrin açık zeminli, sohbet paneli koyu.
     * Sistem çubuklarının simgeleri sabit kalırsa birinde görünmez oluyor —
     * açık zeminde beyaz simge, koyu zeminde siyah simge. Gerçek uygulamalar
     * bunu ekrana göre değiştirir; web tarafı hangi yüzde olduğunu bildiği
     * için kararı oradan alıp burada uyguluyoruz.
     *
     * Çubukların ZEMİN rengine dokunmuyoruz: Android 15'te (targetSdk 35)
     * statusBarColor artık yok sayılıyor, ekran zaten kenardan kenara
     * çiziliyor ve arkasını uygulamanın kendi içeriği dolduruyor.
     */
    @PluginMethod
    public void durumCubugu(PluginCall call) {
        final Boolean k = call.getBoolean("koyuSimge", Boolean.TRUE);
        final boolean koyuSimge = !Boolean.FALSE.equals(k);
        if (getActivity() == null) { call.resolve(); return; }
        getActivity().runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    Window p = getActivity().getWindow();
                    WindowInsetsControllerCompat d =
                        WindowCompat.getInsetsController(p, p.getDecorView());
                    d.setAppearanceLightStatusBars(koyuSimge);
                    d.setAppearanceLightNavigationBars(koyuSimge);
                } catch (Exception e) {}
            }
        });
        call.resolve();
    }

    @PluginMethod
    public void gizle(PluginCall call) {
        try {
            NotificationManagerCompat.from(getContext()).cancel(BILDIRIM_ID);
        } catch (Exception e) {}
        call.resolve();
    }
}
