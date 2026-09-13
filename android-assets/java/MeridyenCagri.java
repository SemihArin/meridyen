package __PAKET__;

import android.app.Activity;
import android.app.KeyguardManager;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.media.AudioAttributes;
import android.media.RingtoneManager;
import android.os.Build;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.app.Person;

/**
 * Meridyen — gelen çağrı: uygulamayı öne çıkarır ve tam ekran çağrı gösterir.
 *
 * SORUN: Gelen çağrıyı web tarafı veritabanı dinleyicisinden öğreniyor ve
 * çağrı ekranını açıyor — ama bu yalnız uygulama zaten ÖNDEYSE işe yarıyor.
 * Uygulama arka plandaysa ya da ekran kilitliyse kimse bir şey görmüyordu.
 * Android 10'dan beri arka plandaki bir uygulama kendi kendine ekrana
 * gelemiyor: "startActivity" sessizce yok sayılıyor.
 *
 * ÇÖZÜM: Android'in bu iş için ayırdığı tek kapı, TAM EKRAN NİYETİ olan bir
 * bildirim (setFullScreenIntent). Sistem, telefon boştayken ya da kilitliyken
 * o niyeti doğrudan açıyor — yani çağrı ekranı tam ekran geliyor; kullanıcı
 * telefonu aktif kullanıyorsa üstte bir çağrı şeridi olarak beliriyor.
 * WhatsApp'takinin aynısı bu.
 *
 * Bildirim ayrı bir kanalda: mesaj kanalının sesi kısa bir "ding", çağrının
 * ise ZİL sesi olmalı ve telefonun zil ayarına uymalı. Android'de ses kanal
 * başına ayarlandığı için bu ayrı kanal şart.
 */
public final class MeridyenCagri {

    public static final String KANAL = "meridyen_cagri";
    private static final int BILDIRIM_ID = 2000000004;

    public static final String EK_CAGRI = "meridyen_cagri";
    public static final String EK_EYLEM = "meridyen_cagri_eylem";

    private MeridyenCagri() {}

    public static void kanaliKur(Context c) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm =
            (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null || nm.getNotificationChannel(KANAL) != null) return;
        NotificationChannel k = new NotificationChannel(
            KANAL, "Gelen çağrı", NotificationManager.IMPORTANCE_HIGH);
        k.setDescription("Görüntülü ve sesli aramalar");
        k.setShowBadge(false);
        /* Telefonun KENDİ zil sesi: kullanıcı neyi duymaya alışkınsa o.
           USAGE_NOTIFICATION_RINGTONE, sesin zil ses düzeyine bağlanmasını
           ve sessiz kipte susmasını sağlıyor. */
        try {
            k.setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE),
                new AudioAttributes.Builder()
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                    .build());
        } catch (Exception e) {}
        k.enableVibration(true);
        k.setVibrationPattern(new long[]{0, 700, 600, 700, 600});
        nm.createNotificationChannel(k);
    }

    private static PendingIntent niyet(Context c, String gonderen, String eylem, int kod) {
        Intent i = c.getPackageManager().getLaunchIntentForPackage(c.getPackageName());
        if (i == null) return null;
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        if (gonderen != null) i.putExtra(EK_CAGRI, gonderen);
        i.putExtra(EK_EYLEM, eylem == null ? "" : eylem);
        return PendingIntent.getActivity(c, kod, i,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    /**
     * Gelen çağrı bildirimini yayınlar.
     *
     * @return tam ekran niyetinin kabul edilip edilmediği. Reddedilmişse
     *         (Android 14'te ayrı bir izin) bildirim yine çıkıyor ama
     *         uygulama kendiliğinden öne GELMİYOR; web tarafı bunu bilmeli.
     */
    public static boolean goster(Context c, String ad, String gonderen, String tur) {
        try {
            kanaliKur(c);
            String baslik = (ad == null || ad.length() == 0) ? "Bilinmeyen" : ad;
            String alt = "goruntu".equals(tur) ? "Görüntülü arama" : "Sesli arama";

            PendingIntent tamEkran = niyet(c, gonderen, "", 4001);
            PendingIntent kabul = niyet(c, gonderen, "kabul", 4002);
            PendingIntent reddet = niyet(c, gonderen, "reddet", 4003);

            NotificationCompat.Builder kur = new NotificationCompat.Builder(c, KANAL)
                .setSmallIcon(MeridyenBildirimler.ikon(c))
                .setContentTitle(baslik)
                .setContentText(alt)
                .setCategory(NotificationCompat.CATEGORY_CALL)
                .setPriority(NotificationCompat.PRIORITY_MAX)
                /* Kaydırarak atılamasın: çağrı sürerken bildirim kaybolursa
                   kullanıcının cevaplama yolu kalmıyor. */
                .setOngoing(true)
                .setAutoCancel(false)
                /* İkinci parametre "yüksek öncelikli": telefon boştaysa ya da
                   kilitliyse sistem bu niyeti doğrudan AÇIYOR. Uygulamanın
                   arka plandan öne gelmesinin Android'deki tek meşru yolu. */
                .setFullScreenIntent(tamEkran, true);

            int r = MeridyenBildirimler.renk(c);
            if (r != 0) kur.setColor(r);

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                /* CallStyle: Android'in kendi çağrı görünümü — büyük "Cevapla"
                   ve "Reddet" düğmeleriyle. */
                Person kisi = new Person.Builder().setName(baslik).setImportant(true).build();
                kur.setStyle(NotificationCompat.CallStyle.forIncomingCall(kisi, reddet, kabul));
            } else {
                kur.addAction(0, "Reddet", reddet);
                kur.addAction(0, "Cevapla", kabul);
                kur.setContentIntent(tamEkran);
            }

            NotificationManagerCompat.from(c).notify(BILDIRIM_ID, kur.build());
            return tamEkranIzniVarMi(c);
        } catch (SecurityException e) {
            return false;
        } catch (Exception e) {
            return false;
        }
    }

    public static void kapat(Context c) {
        try { NotificationManagerCompat.from(c).cancel(BILDIRIM_ID); } catch (Exception e) {}
    }

    /**
     * Android 14'ten beri tam ekran niyeti AYRI bir izin. Verilmemişse
     * bildirim yalnız üstte bir şerit olarak çıkıyor, uygulama öne gelmiyor —
     * ve bu dışarıdan "çağrı gelmiyor" gibi görünüyor. Ayrı okuyabilmek için.
     */
    public static boolean tamEkranIzniVarMi(Context c) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.UPSIDE_DOWN_CAKE) return true;
        try {
            NotificationManager nm =
                (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            return nm == null || nm.canUseFullScreenIntent();
        } catch (Exception e) {
            return true;
        }
    }

    /**
     * Çağrı ekranı KİLİT EKRANININ ÜSTÜNDE görünsün ve ekranı uyandırsın.
     *
     * Bilerek yalnız çağrı geldiğinde açılıyor, kalıcı değil: uygulamanın
     * kendi kilit kodu var ve her açılışta kilit ekranını aşmak gizliliği
     * bozardı. Çağrı bitince geri alınıyor.
     */
    public static void kilitUstunde(Activity a, boolean acik) {
        if (a == null) return;
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
                a.setShowWhenLocked(acik);
                a.setTurnScreenOn(acik);
                if (acik) {
                    KeyguardManager km =
                        (KeyguardManager) a.getSystemService(Context.KEYGUARD_SERVICE);
                    if (km != null) km.requestDismissKeyguard(a, null);
                }
            }
        } catch (Exception e) {}
    }
}
