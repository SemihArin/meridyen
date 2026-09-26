package android.webkit;

/* SAPLAMA — Android'in gerçek sınıfının yerine YALNIZ SINAMADA derleniyor;
   APK'ya girmiyor. Burada tek amaç MeridyenDirilis'in gerçek kodunu Android
   olmadan çalıştırmak. Davranış, gerçeğine SADIK kalmak zorunda: saplamayı
   üretim koduna uydurmak, sınamayı değersiz kılar. */
public class RenderProcessGoneDetail {
    private final boolean cokme;
    public RenderProcessGoneDetail(boolean cokme) { this.cokme = cokme; }
    public boolean didCrash() { return cokme; }
}
