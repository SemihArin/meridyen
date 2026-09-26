package __PAKET__;

import android.content.Context;
import android.util.AttributeSet;
import android.view.View;

import com.getcapacitor.CapacitorWebView;

/**
 * Meridyen — arka planda ÇALIŞMAYA DEVAM EDEN WebView.
 *
 * SORUN (tanı günlüğüyle kanıtlandı): uygulama arka plana düşünce sayfa bir
 * süre sonra TAMAMEN duruyordu. Günlükte "zamanlayıcı 135 sn durmuş" satırı
 * var: iki dakikadan uzun süre hiçbir JavaScript çalışmamış. Bu sürede gelen
 * mesaj işlenmiyor, bildirim çizilmiyor, yükleme ilerlemiyor.
 *
 * SEBEP: Chromium, sayfayı GİZLİ gördüğü anda kendi kurallarını uyguluyor —
 * zamanlayıcıları seyreltiyor, bir süre sonra sayfayı tamamen donduruyor. Bu
 * karar işletim sisteminin değil, tarayıcı motorunun kendi kararı; ön plan
 * servisi, uyanık tutma kilidi ve işleyici süreç önceliği bunu DEĞİŞTİRMİYOR
 * (üçünü de eklemiştik, yine donuyordu).
 *
 * Sayfanın gizli sayılması, WebView'ın pencere görünürlüğünden geliyor.
 * Burada o sinyali sabitliyoruz: arka plan kipi açıkken pencere görünürlüğü
 * her zaman VISIBLE bildiriliyor, böylece motor sayfayı "açık sekme" gibi
 * çalıştırmaya devam ediyor.
 *
 * PEKİ SAYFA ARTIK ARKA PLANDA OLDUĞUNU NEREDEN BİLECEK? document.hidden bu
 * yalandan sonra hep false olurdu ve "sohbet açıkken bildirim gösterme",
 * "arka planda kilit iste" gibi mantıklar bozulurdu. Bu yüzden gerçek ön/arka
 * plan bilgisi YERLİ taraftan (Activity yaşam döngüsü) sayfaya iletiliyor ve
 * köprü document.hidden'ı ona göre yeniden tanımlıyor: motor sayfayı açık
 * sanıyor, sayfa gerçeği biliyor.
 *
 * Kullanıcı "Arka planda bağlı kal" ayarını kapatırsa bayrak düşüyor ve
 * WebView varsayılan davranışına dönüyor (pil).
 */
public class MeridyenWebView extends CapacitorWebView {

    /** Arka planda çalışmaya devam edilsin mi? Ayardan yönetiliyor. */
    public static volatile boolean arkaPlandaCalis = true;

    public MeridyenWebView(Context baglam, AttributeSet ozellikler) {
        super(baglam, ozellikler);
    }

    @Override
    protected void onWindowVisibilityChanged(int gorunurluk) {
        super.onWindowVisibilityChanged(arkaPlandaCalis ? View.VISIBLE : gorunurluk);
    }

    @Override
    protected void onVisibilityChanged(View degisen, int gorunurluk) {
        super.onVisibilityChanged(degisen, arkaPlandaCalis ? View.VISIBLE : gorunurluk);
    }
}
