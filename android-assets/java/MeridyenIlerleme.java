package __PAKET__;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.PowerManager;
import android.provider.Settings;
import android.view.Window;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.JSObject;
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

    /** MainActivity'nin Activity geri çağrıları (onUserLeaveHint,
     *  onPictureInPictureModeChanged) Capacitor'un Plugin sınıfında YOK;
     *  oradan buraya ulaşabilmek için tek örneği tutuyoruz. */
    private static MeridyenIlerleme ornek = null;

    /** Bildirime dokunularak açıldıysa, hangi sohbetin açılacağı.
     *  JS dinleyicisi köprü yüklenmeden ÖNCE gelebildiği için (soğuk açılış)
     *  değeri saklıyoruz; web tarafı hazır olunca `bekleyenAcilis` ile alıyor. */
    private String bekleyenGonderen = null;

    @Override
    public void load() {
        ornek = this;
        /* Kanallar uygulama daha ilk kez açılırken kurulmalı: bildirim
           geldiğinde kanal yoksa Android bildirimi hiç göstermez. */
        try { MeridyenBildirimler.mesajKanaliniKur(getContext()); } catch (Exception e) {}
        try { kanaliKur(); } catch (Exception e) {}
        if (getActivity() != null) niyetiIsle(getActivity().getIntent());
    }

    /** Uygulama zaten açıkken bildirime dokunulursa buraya düşer. */
    @Override
    protected void handleOnNewIntent(Intent niyet) {
        super.handleOnNewIntent(niyet);
        niyetiIsle(niyet);
    }

    private void niyetiIsle(Intent niyet) {
        if (niyet == null) return;
        String g;
        try {
            g = niyet.getStringExtra(MeridyenBildirimler.EK_GONDEREN);
        } catch (Exception e) {
            return;
        }
        if (g == null || g.length() == 0) return;
        /* Aynı niyet Activity yeniden yaratıldığında tekrar okunabiliyor;
           bir kez işlendikten sonra temizliyoruz ki her dönüşte sohbet
           kendiliğinden açılmasın. */
        try { niyet.removeExtra(MeridyenBildirimler.EK_GONDEREN); } catch (Exception e) {}
        bekleyenGonderen = g;
        JSObject veri = new JSObject();
        veri.put("gonderen", g);
        notifyListeners("bildirimAcildi", veri, true);
    }

    /** Soğuk açılışta kaçırılan "bildirime dokunuldu" olayını web tarafına verir. */
    @PluginMethod
    public void bekleyenAcilis(PluginCall call) {
        JSObject sonuc = new JSObject();
        sonuc.put("gonderen", bekleyenGonderen == null ? "" : bekleyenGonderen);
        bekleyenGonderen = null;
        call.resolve(sonuc);
    }

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

    /**
     * Bildirimlerin neden çıkmadığını SÖYLER.
     *
     * Bildirimin sessizce kaybolmasının birkaç ayrı sebebi var ve dışarıdan
     * hepsi birbirine benziyor ("bildirim gelmiyor"). Burada her birini ayrı
     * ayrı okuyup web tarafına veriyoruz; Ayarlar ekranı bunu insan diline
     * çeviriyor. Kullanıcının ekran görüntüsü göndermesine gerek kalmadan
     * hangi ayarın kapalı olduğu görülebiliyor.
     */
    @PluginMethod
    public void tani(PluginCall call) {
        JSObject s = new JSObject();
        try {
            s.put("surum", Build.VERSION.SDK_INT);
            s.put("bildirimAcik", NotificationManagerCompat.from(getContext()).areNotificationsEnabled());

            int onem = -1;      // -1: kanal henüz yok
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                NotificationManager nm = (NotificationManager)
                    getContext().getSystemService(Context.NOTIFICATION_SERVICE);
                if (nm != null) {
                    NotificationChannel k =
                        nm.getNotificationChannel(MeridyenBildirimler.KANAL_MESAJ);
                    if (k != null) onem = k.getImportance();
                }
            } else {
                onem = 3;       // Android 8 öncesi: kanal kavramı yok
            }
            /* 0 = IMPORTANCE_NONE: kullanıcı KANALI kapatmış. Uygulama izni
               açık göründüğü hâlde tek bir bildirim bile çıkmaz — en çok
               yanıltan durum bu. */
            s.put("kanalOnem", onem);

            boolean pilSerbest = true;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                PowerManager pm = (PowerManager) getContext().getSystemService(Context.POWER_SERVICE);
                if (pm != null) {
                    pilSerbest = pm.isIgnoringBatteryOptimizations(getContext().getPackageName());
                }
            }
            /* Pil iyileştirmesi açıkken üretici katmanları (Xiaomi, Huawei,
               Samsung...) uygulamayı uyutup push teslimini geciktirebiliyor. */
            s.put("pilSerbest", pilSerbest);
            s.put("nobet", MeridyenNobet.calisiyor);
            s.put("kayanEkran", MeridyenKayanEkran.desteklenir(getContext()));
        } catch (Exception e) {
            s.put("hata", String.valueOf(e.getMessage()));
        }
        call.resolve(s);
    }

    /* ================= MESAJ BİLDİRİMİ =================
     *
     * Uygulama açıkken bildirimi eskiden Capacitor'un yerel bildirim eklentisi
     * çiziyordu; o eklenti her çağrıda aynı id'yi silip yeniden yayınladığı
     * için aynı sohbetin ikinci mesajı birincinin ÜSTÜNE yazıyordu — okunmadan
     * kaybolan mesajın sebebi buydu. Artık açıkken de kapalıyken de bildirim
     * TEK yoldan geçiyor (MeridyenBildirimler): mesajlar birikiyor ve
     * bildirimler tek başlık altında gruplanıyor.
     */
    @PluginMethod
    public void mesajBildirimi(PluginCall call) {
        MeridyenBildirimler.mesaj(
            getContext(),
            call.getString("baslik", "Meridyen"),
            call.getString("govde", ""),
            call.getString("etiket", "meridyen"),
            call.getString("gonderen", null),
            call.getString("tur", null));
        call.resolve();
    }

    /** Sohbet uygulamada açıldığında çağrılıyor: okunan mesaj bildirimde
     *  durmamalı, biriken satırlar da unutulmalı. */
    @PluginMethod
    public void bildirimTemizle(PluginCall call) {
        String etiket = call.getString("etiket", null);
        if (etiket == null || etiket.length() == 0) MeridyenBildirimler.hepsiniTemizle(getContext());
        else MeridyenBildirimler.temizle(getContext(), etiket);
        call.resolve();
    }

    /**
     * Sınama bildirimi — GERÇEK mesaj bildirimiyle aynı yoldan.
     *
     * Bilerek MeridyenBildirimler.mesaj() çağrılıyor: sınama görünüyorsa
     * kanal, izin, ikon ve dokunma niyeti çalışıyor demektir. Ayrı bir
     * "sınama bildirimi" kodu yazsaydık gerçek yolu değil kendisini sınardı.
     */
    @PluginMethod
    public void sina(PluginCall call) {
        MeridyenBildirimler.mesaj(
            getContext(),
            "Meridyen",
            "Sınama bildirimi — bunu gördüysen bildirimler çalışıyor.",
            "meridyen-sinama",
            null,
            "sinama");
        call.resolve();
    }

    /* ================= ARKA PLANDA BAĞLI KALMA ================= */

    /** Web tarafı "oturum açık ve ayar açık" dediğinde nöbeti başlatıyor.
     *  Bilerek uygulama GÖRÜNÜRKEN çağrılıyor: Android 12'den beri arka
     *  plandan ön plan servisi başlatmak reddediliyor. */
    @PluginMethod
    public void nobet(PluginCall call) {
        boolean acik = Boolean.TRUE.equals(call.getBoolean("acik", Boolean.FALSE));
        try {
            if (acik) MeridyenNobet.baslat(getContext());
            else MeridyenNobet.durdur(getContext());
        } catch (Exception e) {}
        JSObject s = new JSObject();
        s.put("calisiyor", MeridyenNobet.calisiyor);
        call.resolve(s);
    }

    /** Pil iyileştirmesinden muafiyet penceresi. Muafiyet olmadan üretici
     *  katmanları (Xiaomi, Huawei, Samsung...) uygulamayı arka planda
     *  uyutup bildirimleri geciktirebiliyor. */
    @PluginMethod
    public void pilIzniIste(PluginCall call) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                PowerManager pm = (PowerManager) getContext().getSystemService(Context.POWER_SERVICE);
                String paket = getContext().getPackageName();
                if (pm != null && !pm.isIgnoringBatteryOptimizations(paket)) {
                    Intent i = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
                    i.setData(Uri.parse("package:" + paket));
                    i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    getContext().startActivity(i);
                }
            }
        } catch (Exception e) {
            /* Bazı cihazlarda bu niyet hiç yok; kullanıcı ayarlardan elle
               yapabilir, uygulama çalışmaya devam etmeli. */
        }
        call.resolve();
    }

    /* ================= KAYAN EKRAN (Picture-in-Picture) ================= */

    /** Görüntülü görüşme başladı/bitti. Yalnız sürerken kendiliğinden kayan
     *  ekrana geçiliyor; yoksa ana ekrana dönerken vitrin küçük bir pencerede
     *  asılı kalırdı. */
    @PluginMethod
    public void kayanEkranDurumu(PluginCall call) {
        final boolean suruyor = Boolean.TRUE.equals(call.getBoolean("gorusme", Boolean.FALSE));
        final Integer e = call.getInt("en", 16);
        final Integer b = call.getInt("boy", 9);
        if (getActivity() != null) {
            getActivity().runOnUiThread(() -> MeridyenKayanEkran.gorusmeDurumu(
                getActivity(), suruyor, e == null ? 16 : e, b == null ? 9 : b));
        }
        JSObject s = new JSObject();
        s.put("destek", MeridyenKayanEkran.desteklenir(getContext()));
        call.resolve(s);
    }

    /** Düğmeyle elle geçiş. */
    @PluginMethod
    public void kayanEkranaGec(PluginCall call) {
        final JSObject s = new JSObject();
        if (getActivity() == null) { s.put("oldu", false); call.resolve(s); return; }
        getActivity().runOnUiThread(() -> {
            boolean oldu = MeridyenKayanEkran.gir(getActivity());
            s.put("oldu", oldu);
            call.resolve(s);
        });
    }

    /** MainActivity'den: ana ekrana dönülüyor. */
    public static void ayrilirken(android.app.Activity a) {
        try { MeridyenKayanEkran.ayrilirken(a); } catch (Exception e) {}
    }

    /** MainActivity'den: kayan ekran kipine girildi/çıkıldı. Web tarafı bu
     *  kipte yalnız karşı tarafın görüntüsünü çiziyor — küçük pencerede
     *  tüm arayüzü göstermenin anlamı yok. */
    public static void kayanEkranDegisti(boolean icinde) {
        if (ornek == null) return;
        try {
            JSObject v = new JSObject();
            v.put("icinde", icinde);
            ornek.notifyListeners("kayanEkranDegisti", v, true);
        } catch (Exception e) {}
    }

    /** Sistemin bildirim ayarlarını açar: tanı bir şeyin kapalı olduğunu
     *  söylediğinde kullanıcı tek dokunuşla düzeltebilsin. */
    @PluginMethod
    public void bildirimAyarlariniAc(PluginCall call) {
        try {
            Intent i;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                i = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS);
                i.putExtra(Settings.EXTRA_APP_PACKAGE, getContext().getPackageName());
            } else {
                i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
                i.setData(Uri.parse("package:" + getContext().getPackageName()));
            }
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(i);
        } catch (Exception e) {}
        call.resolve();
    }
}
