package __PAKET__;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.WebView;

/** MeridyenDirilis'in GERÇEK kodunu Android saplamaları üstünde çalıştırır. */
public class Sinama {
    static int gecti = 0, kaldi = 0;

    static void esit(String ad, Object beklenen, Object bulunan) {
        if (beklenen == null ? bulunan == null : beklenen.equals(bulunan)) { gecti++; }
        else { kaldi++; System.out.println("KALDI: " + ad + " — beklenen " + beklenen + ", bulunan " + bulunan); }
    }
    static void dogru(String ad, boolean k) { esit(ad, Boolean.TRUE, Boolean.valueOf(k)); }

    public static void main(String[] a) throws Exception {
        pencereKurali();
        uctanSonrasiBekler();
        onGelinceDirilir();
        kayitTutulur();
        cokmeAyrimi();
        etkinlikYoksaCokmez();

        System.out.println();
        System.out.println(kaldi == 0 ? ("TUMU GECTI (" + gecti + ")")
                                      : ("BASARISIZ: " + kaldi + " / " + (gecti + kaldi)));
        if (kaldi != 0) System.exit(1);
    }

    /* 1) "Beş dakikada en çok üç" kuralı — zamanı elle veriyoruz. */
    static void pencereKurali() {
        MeridyenDirilis.Sayac s = new MeridyenDirilis.Sayac(3, 300000L);
        long t = 1000000L;
        dogru("bos sayacta yer var", s.yerVarMi(t));
        s.ekle(t);        dogru("1 kayitla yer var", s.yerVarMi(t + 1000));
        s.ekle(t + 1000); dogru("2 kayitla yer var", s.yerVarMi(t + 2000));
        s.ekle(t + 2000); dogru("3 kayitla yer YOK", !s.yerVarMi(t + 3000));

        // Pencere geçince yeniden açılıyor (301 sn sonra üçü de eskidi).
        dogru("pencere gecince yer var", s.yerVarMi(t + 301000L));
        // Sınırda: 299.9 sn sonra ilk kayıt hâlâ pencerede -> hâlâ dolu.
        dogru("sinirda hala dolu", !s.yerVarMi(t + 299000L));
        s.sifirla();
        dogru("sifirlandiktan sonra yer var", s.yerVarMi(t + 3000));

        // Halka taşması: dördüncü kayıt en eskisinin üstüne yazmalı.
        MeridyenDirilis.Sayac h = new MeridyenDirilis.Sayac(3, 300000L);
        for (int i = 0; i < 7; i++) h.ekle(t + i * 1000L);
        dogru("tasmada da dolu", !h.yerVarMi(t + 7000L));
    }

    /* 2) Uç uca: ilk üç ölüm hemen diriltiliyor, dördüncüsü ertelenıyor. */
    static void uctanSonrasiBekler() {
        MeridyenDirilis.sayac.sifirla();
        Context.depolariBosalt();
        Context c = new Context();
        Activity e = new Activity();
        WebView w = new WebView(c);
        MeridyenDirilis d = new MeridyenDirilis(e);

        for (int i = 1; i <= 3; i++) {
            boolean sonuc = d.onRenderProcessGone(w, new RenderProcessGoneDetail(false));
            dogru("olum " + i + ": true donuyor (surec oldurulmesin)", sonuc);
            esit("olum " + i + ": diriltme sayisi", Integer.valueOf(i), Integer.valueOf(e.recreateSayisi));
        }
        boolean dorduncu = d.onRenderProcessGone(w, new RenderProcessGoneDetail(false));
        dogru("4. olum: yine true donuyor", dorduncu);
        esit("4. olum: OTOMATIK diriltme YOK", Integer.valueOf(3), Integer.valueOf(e.recreateSayisi));
    }

    /* 3) Ertelenen diriltme kullanıcı öne gelince yapılıyor ve sayaç sıfırlanıyor. */
    static void onGelinceDirilir() {
        MeridyenDirilis.sayac.sifirla();
        Context.depolariBosalt();
        Context c = new Context();
        Activity e = new Activity();
        WebView w = new WebView(c);
        MeridyenDirilis d = new MeridyenDirilis(e);

        for (int i = 0; i < 4; i++) d.onRenderProcessGone(w, new RenderProcessGoneDetail(false));
        esit("4 olum sonrasi diriltme", Integer.valueOf(3), Integer.valueOf(e.recreateSayisi));

        MeridyenDirilis.onGelindi(e);
        esit("one gelince ertelenen diriltme yapiliyor", Integer.valueOf(4), Integer.valueOf(e.recreateSayisi));
        MeridyenDirilis.onGelindi(e);
        esit("ikinci cagri bir sey yapmiyor", Integer.valueOf(4), Integer.valueOf(e.recreateSayisi));

        // Sayaç sıfırlandığı için sonraki ölüm yine otomatik onarılıyor.
        d.onRenderProcessGone(w, new RenderProcessGoneDetail(false));
        esit("sifirlanan sayacla yine otomatik", Integer.valueOf(5), Integer.valueOf(e.recreateSayisi));
    }

    /* 4) Olay kalıcı olarak kaydediliyor (tanı ekranı bunu okuyor). */
    static void kayitTutulur() {
        MeridyenDirilis.sayac.sifirla();
        Context.depolariBosalt();
        Context c = new Context();
        Activity e = new Activity();
        WebView w = new WebView(c);
        MeridyenDirilis d = new MeridyenDirilis(e);

        esit("bastan sayi 0", Integer.valueOf(0), Integer.valueOf(MeridyenDirilis.sayi(c)));
        esit("bastan sure 0", Long.valueOf(0L), Long.valueOf(MeridyenDirilis.oncekiMs(c)));

        d.onRenderProcessGone(w, new RenderProcessGoneDetail(false));
        d.onRenderProcessGone(w, new RenderProcessGoneDetail(false));
        esit("iki olum kaydedildi", Integer.valueOf(2), Integer.valueOf(MeridyenDirilis.sayi(c)));
        dogru("gecen sure makul", MeridyenDirilis.oncekiMs(c) < 5000L);
        esit("sayfa tazeleme cagrildi mi (onPageLoaded ayri)", Integer.valueOf(0),
             Integer.valueOf(MeridyenIlerleme.tazelemeSayisi));
        d.onPageLoaded(w);
        esit("onPageLoaded on/arka plani tazeliyor", Integer.valueOf(1),
             Integer.valueOf(MeridyenIlerleme.tazelemeSayisi));
    }

    /* 5) Çökme mi, bellek için öldürülme mi — tanıda ayrı yazıyor. */
    static void cokmeAyrimi() {
        MeridyenDirilis.sayac.sifirla();
        Context.depolariBosalt();
        Context c = new Context();
        Activity e = new Activity();
        WebView w = new WebView(c);
        MeridyenDirilis d = new MeridyenDirilis(e);

        d.onRenderProcessGone(w, new RenderProcessGoneDetail(false));
        dogru("bellek icin oldurulme", !MeridyenDirilis.cokmeMiydi(c));
        d.onRenderProcessGone(w, new RenderProcessGoneDetail(true));
        dogru("cokme", MeridyenDirilis.cokmeMiydi(c));
        // ayrıntı gelmezse çökmemiş sayılıyor, patlamıyor
        d.onRenderProcessGone(w, null);
        dogru("ayrinti null iken cokmez", !MeridyenDirilis.cokmeMiydi(c));
    }

    /* 6) Activity yok / bitiyor / yıkıldı: diriltme denenmiyor, çökme yok. */
    static void etkinlikYoksaCokmez() {
        MeridyenDirilis.sayac.sifirla();
        Context.depolariBosalt();
        Context c = new Context();
        WebView w = new WebView(c);

        MeridyenDirilis yok = new MeridyenDirilis(null);
        dogru("etkinlik null iken true donuyor", yok.onRenderProcessGone(w, new RenderProcessGoneDetail(false)));
        esit("etkinlik null iken kayit yine tutuluyor", Integer.valueOf(1), Integer.valueOf(MeridyenDirilis.sayi(c)));

        MeridyenDirilis.sayac.sifirla();
        Activity biten = new Activity(); biten.bitiyor = true;
        new MeridyenDirilis(biten).onRenderProcessGone(w, new RenderProcessGoneDetail(false));
        esit("bitiyorsa diriltilmiyor", Integer.valueOf(0), Integer.valueOf(biten.recreateSayisi));

        MeridyenDirilis.sayac.sifirla();
        Activity yikilan = new Activity(); yikilan.yikildi = true;
        new MeridyenDirilis(yikilan).onRenderProcessGone(w, new RenderProcessGoneDetail(false));
        esit("yikildiysa diriltilmiyor", Integer.valueOf(0), Integer.valueOf(yikilan.recreateSayisi));
    }
}
