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
import androidx.core.app.Person;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
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
    /** Grubun "özet" bildirimi: birden çok sohbet varken üstte duran satır.
     *  Mesaj id'leri 1.9 milyarın altına sıkıştırıldığı için bu değerler
     *  onlarla asla çakışmıyor. */
    private static final int OZET_ID = 2000000003;
    /** Bir sohbette en fazla kaç satır biriksin. Daha fazlası ne ekrana
     *  sığıyor ne de işe yarıyor; Android zaten "N yeni mesaj" diyor. */
    private static final int ENCOK_SATIR = 8;
    private static final String DEPO = "meridyen_bildirim";
    private static final String ANAHTAR = "birikenler";
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

    /* ================= BİRİKEN BİLDİRİMLER =================
     *
     * ESKİ DAVRANIŞ VE NEDEN YANLIŞTI: Aynı sohbetin bildirimi hep aynı
     * id'ye yazılıyordu, yani ikinci mesaj birincinin ÜSTÜNE yazıyordu.
     * Amaç "her mesaj için ayrı bildirim yığılmasın" idi ama sonucu, gelen
     * mesajı okumadan kaybetmek oldu: bildirime bakan kişi yalnız SONUNCU
     * mesajı görüyordu.
     *
     * YENİ DAVRANIŞ (WhatsApp'taki gibi): sohbet başına TEK bildirim var ama
     * içinde mesajlar BİRİKİYOR. Satırlar MessagingStyle ile yazılıyor;
     * Android açılmamış hâlde "N yeni mesaj" diyor, açılınca hepsini alt alta
     * gösteriyor. Birden çok sohbetten mesaj varsa hepsi tek bir "Meridyen"
     * başlığı altında toplanıyor.
     *
     * NEDEN DİSKTE: Biriken satırlar SharedPreferences'ta tutuluyor, bellekte
     * değil. Uygulama kapalıyken gelen bildirimi FCM servisi çiziyor ve o
     * servis işlem öldükten sonra sıfırdan başlayabiliyor — bellekte tutsaydık
     * her uyanışta önceki mesajlar kaybolurdu.
     */

    /* ---- SAF ÇEKİRDEK ----
       Biriktirme kuralları (üst sınır, en eskiyi atma, özetin ne zaman
       gerektiği) Android'e HİÇ dokunmayan metotlarda duruyor. Böylece
       elimizde cihaz olmadan da sınanabiliyorlar; bildirim davranışının
       doğrudan gözlenemeyen tek yeri burası. */

    /** Yeni mesajı depoya ekler, güncel depoyu JSON metni olarak döndürür. */
    static String depoyaEkle(String hamDepo, int id, String baslik, String gonderen,
                             String tur, String etiket, String metin, long ts) throws Exception {
        JSONObject depo = (hamDepo == null || hamDepo.length() == 0)
            ? new JSONObject() : new JSONObject(hamDepo);
        JSONObject sohbet = depo.optJSONObject(String.valueOf(id));
        if (sohbet == null) sohbet = new JSONObject();
        sohbet.put("baslik", baslik == null || baslik.length() == 0 ? "Meridyen" : baslik);
        if (gonderen != null) sohbet.put("gonderen", gonderen);
        if (tur != null) sohbet.put("tur", tur);
        sohbet.put("etiket", etiket == null ? "" : etiket);

        JSONArray satirlar = sohbet.optJSONArray("satirlar");
        if (satirlar == null) satirlar = new JSONArray();
        JSONObject satir = new JSONObject();
        satir.put("m", metin == null ? "" : metin);
        satir.put("t", ts);
        satirlar.put(satir);

        /* Üst sınırı aşınca EN ESKİ satırlar atılıyor. JSONArray.remove
           Android'in eski sürümlerinde yok, bu yüzden yeniden kuruyoruz. */
        if (satirlar.length() > ENCOK_SATIR) {
            JSONArray kirpik = new JSONArray();
            for (int i = satirlar.length() - ENCOK_SATIR; i < satirlar.length(); i++) {
                kirpik.put(satirlar.get(i));
            }
            satirlar = kirpik;
        }
        sohbet.put("satirlar", satirlar);
        depo.put(String.valueOf(id), sohbet);
        return depo.toString();
    }

    /** Bir sohbeti depodan düşürür. */
    static String depodanSil(String hamDepo, int id) throws Exception {
        JSONObject depo = (hamDepo == null || hamDepo.length() == 0)
            ? new JSONObject() : new JSONObject(hamDepo);
        depo.remove(String.valueOf(id));
        return depo.toString();
    }

    /** Özet bildiriminin satırları: her sohbet için "Ad: son mesaj". */
    static List<String> ozetSatirlari(String hamDepo) throws Exception {
        List<String> cikti = new ArrayList<>();
        JSONObject depo = (hamDepo == null || hamDepo.length() == 0)
            ? new JSONObject() : new JSONObject(hamDepo);
        JSONArray anahtarlar = depo.names();
        if (anahtarlar == null) return cikti;
        for (int i = 0; i < anahtarlar.length(); i++) {
            JSONObject s = depo.optJSONObject(anahtarlar.optString(i));
            if (s == null) continue;
            JSONArray satirlar = s.optJSONArray("satirlar");
            if (satirlar == null || satirlar.length() == 0) continue;
            JSONObject sonuncu = satirlar.optJSONObject(satirlar.length() - 1);
            cikti.add(s.optString("baslik", "Meridyen") + ": "
                + (sonuncu == null ? "" : sonuncu.optString("m", "")));
        }
        return cikti;
    }

    /** Depodaki toplam mesaj sayısı. */
    static int ozetMesajSayisi(String hamDepo) throws Exception {
        int toplam = 0;
        JSONObject depo = (hamDepo == null || hamDepo.length() == 0)
            ? new JSONObject() : new JSONObject(hamDepo);
        JSONArray anahtarlar = depo.names();
        if (anahtarlar == null) return 0;
        for (int i = 0; i < anahtarlar.length(); i++) {
            JSONObject s = depo.optJSONObject(anahtarlar.optString(i));
            if (s == null) continue;
            JSONArray satirlar = s.optJSONArray("satirlar");
            if (satirlar != null) toplam += satirlar.length();
        }
        return toplam;
    }

    /** Özet YALNIZ birden çok sohbet varken çizilmeli: Android tek çocuklu
     *  bir grubu özetin kendisiyle gösteriyor ve kullanıcı mesajı değil
     *  "1 sohbet" yazısını görürdü. */
    static boolean ozetGerekliMi(int sohbetSayisi) {
        return sohbetSayisi >= 2;
    }

    /* ---- Android'e dokunan taraf ---- */

    private static String depoyuOku(Context c) {
        try {
            String ham = c.getSharedPreferences(DEPO, Context.MODE_PRIVATE).getString(ANAHTAR, null);
            if (ham != null) return ham;
        } catch (Exception e) {}
        return "";
    }

    private static void depoyuYaz(Context c, String ham) {
        try {
            c.getSharedPreferences(DEPO, Context.MODE_PRIVATE)
                .edit().putString(ANAHTAR, ham).apply();
        } catch (Exception e) {}
    }

    /** Tek mesaj bildirimi yayınlar; aynı sohbetin önceki mesajları korunur. */
    public static void mesaj(Context c, String baslik, String govde,
                             String etiket, String gonderen, String tur) {
        try {
            mesajKanaliniKur(c);
            int id = etiketId(etiket);
            String yeni = depoyaEkle(depoyuOku(c), id, baslik, gonderen, tur,
                                     etiket, govde, System.currentTimeMillis());
            depoyuYaz(c, yeni);
            yayinla(c, id, new JSONObject(yeni).optJSONObject(String.valueOf(id)));
            ozetiTazele(c, yeni);
        } catch (SecurityException e) {
            // POST_NOTIFICATIONS izni yok: sessizce geç, uygulama çalışmaya devam etsin.
        } catch (Exception e) {}
    }

    /** Bir sohbetin biriken bildirimini çizer (ya da yerinde günceller). */
    private static void yayinla(Context c, int id, JSONObject sohbet) {
        try {
            String b = sohbet.optString("baslik", "Meridyen");
            String gonderen = sohbet.has("gonderen") ? sohbet.optString("gonderen") : null;
            String tur = sohbet.has("tur") ? sohbet.optString("tur") : null;
            JSONArray satirlar = sohbet.optJSONArray("satirlar");
            if (satirlar == null || satirlar.length() == 0) return;

            /* MessagingStyle: kapalıyken son mesajı ve "N yeni mesaj"ı,
               açılınca hepsini alt alta gösteriyor — sohbet bildiriminin
               Android'deki doğru biçimi bu. */
            Person karsi = new Person.Builder().setName(b).build();
            NotificationCompat.MessagingStyle stil =
                new NotificationCompat.MessagingStyle(new Person.Builder().setName("Sen").build());
            stil.setGroupConversation(false);
            for (int i = 0; i < satirlar.length(); i++) {
                JSONObject s = satirlar.optJSONObject(i);
                if (s == null) continue;
                stil.addMessage(s.optString("m", ""), s.optLong("t", System.currentTimeMillis()), karsi);
            }

            JSONObject sonSatir = satirlar.optJSONObject(satirlar.length() - 1);
            String sonMetin = sonSatir == null ? "" : sonSatir.optString("m", "");

            NotificationCompat.Builder kur = new NotificationCompat.Builder(c, KANAL_MESAJ)
                .setSmallIcon(ikon(c))
                .setContentTitle(b)
                .setContentText(sonMetin)
                .setStyle(stil)
                .setAutoCancel(true)
                .setCategory(NotificationCompat.CATEGORY_MESSAGE)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setDefaults(NotificationCompat.DEFAULT_ALL)
                .setGroup(GRUP)
                /* Biriken mesajın her satırında yeniden ses çıkarmasın diye
                   DEĞİL — burada bilerek her yeni mesajda uyarıyor; susturmak
                   istenirse kanal ayarından yapılır. */
                .setNumber(satirlar.length());

            int r = renk(c);
            if (r != 0) kur.setColor(r);

            PendingIntent niyet = acmaNiyeti(c, id, gonderen, tur);
            if (niyet != null) kur.setContentIntent(niyet);
            /* Kullanıcı bildirimi kaydırıp attıysa birikenleri de unutuyoruz;
               yoksa bir sonraki mesajda okunmuş satırlar geri gelirdi. */
            kur.setDeleteIntent(MeridyenBildirimSil.niyet(c, id));

            NotificationManagerCompat.from(c).notify(id, kur.build());
        } catch (SecurityException e) {
        } catch (Exception e) {}
    }

    /**
     * Grup özeti: birden çok sohbetten bildirim varken üstte duran satır.
     *
     * Tek sohbet varken bilerek ÇİZİLMİYOR: Android tek çocuklu bir grubu
     * özetin kendisiyle gösteriyor ve kullanıcı mesajı değil "2 sohbet"
     * yazısını görüyor.
     */
    private static void ozetiTazele(Context c, String hamDepo) {
        try {
            NotificationManagerCompat nm = NotificationManagerCompat.from(c);
            List<String> basliklar = ozetSatirlari(hamDepo);
            if (!ozetGerekliMi(basliklar.size())) { nm.cancel(OZET_ID); return; }
            int toplam = ozetMesajSayisi(hamDepo);

            NotificationCompat.InboxStyle stil = new NotificationCompat.InboxStyle();
            for (String satir : basliklar) stil.addLine(satir);
            stil.setSummaryText(toplam + " mesaj · " + basliklar.size() + " sohbet");

            NotificationCompat.Builder kur = new NotificationCompat.Builder(c, KANAL_MESAJ)
                .setSmallIcon(ikon(c))
                .setContentTitle("Meridyen")
                .setContentText(toplam + " yeni mesaj")
                .setStyle(stil)
                .setGroup(GRUP)
                .setGroupSummary(true)
                .setAutoCancel(true)
                .setCategory(NotificationCompat.CATEGORY_MESSAGE)
                /* Özet sessiz: ses ve titreşimi asıl sohbet bildirimi veriyor,
                   ikisi birden uyarsaydı her mesajda çift titreşim olurdu. */
                .setSilent(true)
                .setNumber(toplam);
            int r = renk(c);
            if (r != 0) kur.setColor(r);
            PendingIntent niyet = acmaNiyeti(c, OZET_ID, null, null);
            if (niyet != null) kur.setContentIntent(niyet);
            kur.setDeleteIntent(MeridyenBildirimSil.niyet(c, 0));   // 0 = hepsi

            nm.notify(OZET_ID, kur.build());
        } catch (SecurityException e) {
        } catch (Exception e) {}
    }

    /** Bir sohbetin bildirimini ve biriken satırlarını siler.
     *  Sohbet uygulamada açıldığında çağrılıyor: okunan mesaj bildirimde
     *  durmamalı. */
    public static void temizle(Context c, int id) {
        try {
            String yeni = depodanSil(depoyuOku(c), id);
            depoyuYaz(c, yeni);
            NotificationManagerCompat.from(c).cancel(id);
            ozetiTazele(c, yeni);
        } catch (Exception e) {}
    }

    public static void temizle(Context c, String etiket) {
        temizle(c, etiketId(etiket));
    }

    public static void hepsiniTemizle(Context c) {
        try {
            String ham = depoyuOku(c);
            JSONObject depo = (ham == null || ham.length() == 0)
                ? new JSONObject() : new JSONObject(ham);
            NotificationManagerCompat nm = NotificationManagerCompat.from(c);
            JSONArray anahtarlar = depo.names();
            if (anahtarlar != null) {
                for (int i = 0; i < anahtarlar.length(); i++) {
                    try { nm.cancel(Integer.parseInt(anahtarlar.optString(i))); } catch (Exception e) {}
                }
            }
            nm.cancel(OZET_ID);
            depoyuYaz(c, "");
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
