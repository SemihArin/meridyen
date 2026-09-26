package android.app;

/* SAPLAMA — Android'in gerçek sınıfının yerine YALNIZ SINAMADA derleniyor;
   APK'ya girmiyor. Burada tek amaç MeridyenDirilis'in gerçek kodunu Android
   olmadan çalıştırmak. Davranış, gerçeğine SADIK kalmak zorunda: saplamayı
   üretim koduna uydurmak, sınamayı değersiz kılar. */
public class Activity extends android.content.Context {
    public int recreateSayisi = 0;
    public boolean bitiyor = false, yikildi = false;
    public boolean isFinishing() { return bitiyor; }
    public boolean isDestroyed() { return yikildi; }
    public void recreate() { recreateSayisi++; }
}
