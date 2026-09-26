package android.content;

/* SAPLAMA — Android'in gerçek sınıfının yerine YALNIZ SINAMADA derleniyor;
   APK'ya girmiyor. Burada tek amaç MeridyenDirilis'in gerçek kodunu Android
   olmadan çalıştırmak. Davranış, gerçeğine SADIK kalmak zorunda: saplamayı
   üretim koduna uydurmak, sınamayı değersiz kılar. */
import java.util.HashMap;
import java.util.Map;
public class SharedPreferences {
    public final Map<String, Object> veri = new HashMap<String, Object>();
    public int getInt(String a, int y) { Object v = veri.get(a); return v == null ? y : (Integer) v; }
    public long getLong(String a, long y) { Object v = veri.get(a); return v == null ? y : (Long) v; }
    public boolean getBoolean(String a, boolean y) { Object v = veri.get(a); return v == null ? y : (Boolean) v; }
    public Editor edit() { return new Editor(this); }
    public static class Editor {
        private final SharedPreferences d;
        Editor(SharedPreferences d) { this.d = d; }
        public Editor putInt(String a, int v) { d.veri.put(a, v); return this; }
        public Editor putLong(String a, long v) { d.veri.put(a, v); return this; }
        public Editor putBoolean(String a, boolean v) { d.veri.put(a, v); return this; }
        public void apply() {}
    }
}
