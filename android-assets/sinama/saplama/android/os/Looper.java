package android.os;

/* SAPLAMA — Android'in gerçek sınıfının yerine YALNIZ SINAMADA derleniyor;
   APK'ya girmiyor. Burada tek amaç MeridyenDirilis'in gerçek kodunu Android
   olmadan çalıştırmak. Davranış, gerçeğine SADIK kalmak zorunda: saplamayı
   üretim koduna uydurmak, sınamayı değersiz kılar. */
public class Looper { private static final Looper ana = new Looper(); public static Looper getMainLooper() { return ana; } }
