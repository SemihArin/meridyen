package __PAKET__;

import androidx.annotation.NonNull;

import com.capacitorjs.plugins.pushnotifications.MessagingService;
import com.google.firebase.messaging.RemoteMessage;

import java.util.Map;

/**
 * Meridyen — sunucudan gelen push'u UYGULAMA KAPALIYKEN DE ekrana çıkarır.
 *
 * ARIZANIN KÖKÜ: Capacitor'un push eklentisi gelen mesajı yalnızca
 * JavaScript'e İLETİYOR (PushNotificationsPlugin.sendRemoteMessage), kendisi
 * hiçbir bildirim çizmiyor. Uygulama kapalıyken çalışan bir WebView yok, o
 * yüzden mesaj `lastMessage` alanında bekletiliyor ve kullanıcı hiçbir şey
 * görmüyor. Yani bildirim, yalnızca sunucu yükü içine bir `notification`
 * bloğu koyduğunda çıkıyordu — onu da FCM'in kendi SDK'sı çiziyordu. Sunucu
 * yalnız `data` gönderirse bildirim SESSİZCE kayboluyordu.
 *
 * ÇÖZÜM: Kendi servisimiz. Capacitor'unkini MİRAS ALIYOR — yani JS tarafına
 * iletim ve belirteç yenileme (onNewToken) aynen sürüyor — ama üstüne,
 * uygulama önde DEĞİLSE bildirimi kendimiz çiziyoruz. Böylece sunucunun ne
 * gönderdiğinden bağımsız olarak bildirim görünüyor.
 *
 * Manifestte Capacitor'un servisi KALDIRILIYOR (bkz. patch_manifest.py):
 * aynı intent-filter'a sahip iki servis olursa FCM hangisine teslim edeceğini
 * belirsiz bir sırayla seçer. Tek servis bırakmak bunu kesinleştiriyor.
 */
public class MeridyenMesajServisi extends MessagingService {

    @Override
    public void onMessageReceived(@NonNull RemoteMessage mesaj) {
        // Önce Capacitor'un kendi işi: uygulama çalışıyorsa JS'e ilet.
        super.onMessageReceived(mesaj);

        try {
            /* Öndeyse karışma: index.html zaten veritabanı dinleyicisinden
               kendi bildirimini gösteriyor (ve açık sohbet için hiç
               göstermiyor). İkisi birden çizerse mesaj iki kez görünür. */
            if (MeridyenBildirimler.ondeMi(this)) return;

            Map<String, String> d = mesaj.getData();
            RemoteMessage.Notification n = mesaj.getNotification();

            /* Sunucu yükünün alan adları için hem Türkçe hem yaygın İngilizce
               karşılıkları kabul ediyoruz: sunucu tarafı bu yüzden hiç
               değişmek zorunda kalmasın. */
            String baslik = ilk(d.get("baslik"), d.get("title"),
                                n == null ? null : n.getTitle());
            String govde = ilk(d.get("metin"), d.get("govde"), d.get("body"),
                               n == null ? null : n.getBody());
            String gonderen = ilk(d.get("gonderen"), d.get("uid"), d.get("sender"));
            String tur = ilk(d.get("tur"), d.get("type"));

            if (baslik == null && govde == null) return;   // gösterilecek bir şey yok

            /* Etiket = hangi bildirimin hangisinin üstüne yazacağı. Web tarafı
               'meridyen-<gonderenUid>' kullanıyor; aynısını üretiyoruz ki iki
               yol aynı id'ye düşsün. Gönderen bilinmiyorsa mesaj kimliğine
               düşüyoruz: o zaman her bildirim ayrı kalır (üst üste yazmaktansa
               fazladan bildirim yeğdir — mesaj kaybolmasın). */
            String etiket = d.get("etiket");
            if (etiket == null) {
                etiket = gonderen != null
                    ? "meridyen-" + gonderen
                    : "meridyen-msg-" + mesaj.getMessageId();
            }

            MeridyenBildirimler.mesaj(this, baslik, govde, etiket, gonderen, tur);
        } catch (Exception e) {
            // Bildirim çizilemese bile servis çökmesin.
        }
    }

    private static String ilk(String... adaylar) {
        for (String a : adaylar) {
            if (a != null && a.length() > 0) return a;
        }
        return null;
    }
}
