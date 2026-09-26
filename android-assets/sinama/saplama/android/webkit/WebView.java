package android.webkit;

/* SAPLAMA — Android'in gerçek sınıfının yerine YALNIZ SINAMADA derleniyor;
   APK'ya girmiyor. Burada tek amaç MeridyenDirilis'in gerçek kodunu Android
   olmadan çalıştırmak. Davranış, gerçeğine SADIK kalmak zorunda: saplamayı
   üretim koduna uydurmak, sınamayı değersiz kılar. */
import android.content.Context;
public class WebView {
    private final Context baglam;
    public WebView(Context b) { this.baglam = b; }
    public Context getContext() { return baglam; }
}
