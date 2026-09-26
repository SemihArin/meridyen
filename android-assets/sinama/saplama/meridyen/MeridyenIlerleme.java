package __PAKET__;

/* SAPLAMA — yalnız sınamada derleniyor, APK'ya GİRMİYOR.
   Gerçek MeridyenIlerleme bütün Capacitor ve Android bildirim yığınını
   çekiyor; MeridyenDirilis ondan tek bir şey çağırıyor. Sınamada o tek
   çağrının yapıldığını görebilmek için yerine bu geçiyor. */
public class MeridyenIlerleme {
    public static int tazelemeSayisi = 0;
    public static void onPlanTazele() { tazelemeSayisi++; }
}
