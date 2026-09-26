package android.os;

/* SAPLAMA — Android'in gerçek sınıfının yerine YALNIZ SINAMADA derleniyor;
   APK'ya girmiyor. Burada tek amaç MeridyenDirilis'in gerçek kodunu Android
   olmadan çalıştırmak. Davranış, gerçeğine SADIK kalmak zorunda: saplamayı
   üretim koduna uydurmak, sınamayı değersiz kılar. */
public class Handler {
    public static int gonderilen = 0;
    public Handler(Looper l) {}
    /* Gerçekte ERTELENİYOR; sınamada hemen çalıştırıyoruz ki etkisini
       aynı adımda ölçebilelim. Ertelemenin kendisi Android'in işi. */
    public boolean post(Runnable r) { gonderilen++; r.run(); return true; }
}
