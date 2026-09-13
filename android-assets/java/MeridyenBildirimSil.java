package __PAKET__;

import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * Meridyen — bildirim kaydırılıp atıldığında birikenleri unutur.
 *
 * NEDEN GEREKLİ: Sohbet bildiriminde mesajlar BİRİKİYOR (bkz.
 * MeridyenBildirimler). Kullanıcı bildirimi kaydırıp attığında o birikimi
 * silmezsek, bir sonraki mesaj geldiğinde kullanıcının zaten kapattığı eski
 * satırlar geri gelir — attığı bildirim dirilmiş gibi görünür.
 *
 * Android bunun için bildirime bir "silindi" niyeti (deleteIntent)
 * bağlamamıza izin veriyor; bu alıcı onu karşılıyor.
 */
public class MeridyenBildirimSil extends BroadcastReceiver {

    private static final String EYLEM = "meridyen.BILDIRIM_SILINDI";
    private static final String EK_ID = "id";

    /** id = 0 ise grubun tamamı (özet bildirimi atıldığında). */
    public static PendingIntent niyet(Context c, int id) {
        Intent i = new Intent(c, MeridyenBildirimSil.class);
        i.setAction(EYLEM);
        i.putExtra(EK_ID, id);
        /* requestCode olarak id: hepsine 0 verilseydi FLAG_UPDATE_CURRENT
           yüzünden tüm bildirimlerin silme niyeti sonuncusununkine döner ve
           yanlış sohbetin birikimi silinirdi. */
        return PendingIntent.getBroadcast(c, 900000 + id, i,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    @Override
    public void onReceive(Context c, Intent niyet) {
        if (niyet == null || c == null) return;
        try {
            int id = niyet.getIntExtra(EK_ID, -1);
            if (id == 0) MeridyenBildirimler.hepsiniTemizle(c);
            else if (id > 0) MeridyenBildirimler.temizle(c, id);
        } catch (Exception e) {}
    }
}
