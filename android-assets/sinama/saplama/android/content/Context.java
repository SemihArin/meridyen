package android.content;

/* SAPLAMA — Android'in gerçek sınıfının yerine YALNIZ SINAMADA derleniyor;
   APK'ya girmiyor. Burada tek amaç MeridyenDirilis'in gerçek kodunu Android
   olmadan çalıştırmak. Davranış, gerçeğine SADIK kalmak zorunda: saplamayı
   üretim koduna uydurmak, sınamayı değersiz kılar. */
import java.util.HashMap;
import java.util.Map;
public class Context {
    public static final int MODE_PRIVATE = 0;
    /* Uygulama genelinde tek depo kümesi: Activity'den yazıp uygulama
       bağlamından okumak gerçekte de aynı dosyayı veriyor. */
    private static final Map<String, SharedPreferences> DEPOLAR = new HashMap<String, SharedPreferences>();
    public static void depolariBosalt() { DEPOLAR.clear(); }
    public SharedPreferences getSharedPreferences(String ad, int kip) {
        SharedPreferences d = DEPOLAR.get(ad);
        if (d == null) { d = new SharedPreferences(); DEPOLAR.put(ad, d); }
        return d;
    }
}
