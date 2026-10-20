/* SAHTE firebase-admin — yalnız sınama için (NODE_PATH ile yükleniyor; klasör adı bilerek
   node_modules DEĞİL: kök .gitignore onu dışlıyordu).
   index.js'i GERÇEK dosya olarak çalıştırıp davranışını gözlüyoruz: ağ yok,
   gerçek anahtar yok. Yapılan her iş sinama/kayit.json'a yazılıyor. */
'use strict';
const fs = require('fs');
const path = require('path');
const KAYIT = process.env.SINAMA_KAYIT || path.join(__dirname, '..', '..', 'kayit.json');

const durum = { gonderilen: [], silinen: [], kuyruktanSilinen: [], baslatma: null,
                /* PATLA belirteçli hedefe kaç kez gönderim DENENDİ. Yeniden
                   deneme sınırının gerçekten işlediğini ölçmek için. */
                patlayanDeneme: 0 };
function yaz() { fs.writeFileSync(KAYIT, JSON.stringify(durum, null, 1)); }

/* Sınama verisi: kuyruk + cihazlar */
const veri = JSON.parse(fs.readFileSync(process.env.SINAMA_VERI, 'utf8'));

function dugumAl(yol) {
  return yol.split('/').filter(Boolean).reduce((o, p) => (o == null ? o : o[p]), veri);
}

function ref(yol) {
  return {
    on(olay, geri, hata) {
      if (olay === 'child_added') {
        const cocuklar = dugumAl(yol) || {};
        Object.keys(cocuklar).forEach((k) => {
          setTimeout(() => geri({ key: k, val: () => cocuklar[k] }), 5);
        });
      } else if (olay === 'value' && yol === '.info/connected') {
        setTimeout(() => geri({ val: () => true }), 1);
      }
    },
    off() {},
    once(olay) {
      return Promise.resolve({ val: () => dugumAl(yol) });
    },
    remove() {
      if (yol.indexOf('cihazlar/') === 0) durum.silinen.push(yol);
      else durum.kuyruktanSilinen.push(yol);
      yaz();
      return Promise.resolve();
    }
  };
}

module.exports = {
  credential: {
    cert: (o) => ({ tur: 'cert', proje: o && o.project_id }),
    applicationDefault: () => ({ tur: 'varsayilan' })
  },
  initializeApp(ayar) { durum.baslatma = { veritabani: ayar.databaseURL }; yaz(); },
  app: () => ({ delete: () => Promise.resolve() }),
  database: () => ({ ref }),
  messaging: () => ({
    sendEach(mesajlar) {
      /* PATLA: sendEach'in KENDİSİ reddediyor (mesaj başına hata değil).
         Yeniden deneme yolu yalnız böyle tetikleniyor — kalıcı bir geçici
         hatanın sonsuza kadar denenmediğini bu sınıyor. */
      if (mesajlar.some((m) => /PATLA/.test(m.token))) {
        durum.patlayanDeneme++;
        yaz();
        const h = new Error('sunucu geçici olarak meşgul');
        h.code = 'messaging/server-unavailable';
        return Promise.reject(h);
      }
      durum.gonderilen.push(mesajlar);
      yaz();
      const yanitlar = mesajlar.map((m) => {
        if (/OLU/.test(m.token)) {
          const h = new Error('token yok');
          h.code = 'messaging/registration-token-not-registered';
          return { success: false, error: h };
        }
        if (/YANLISANAHTAR/.test(m.token)) {
          /* Servis hesabı yanlış projeye ait: belirteçle ilgisi YOK.
             Sunucu bu hatada cihaz kaydını SİLMEMELİ. */
          const h = new Error('SenderId mismatch');
          h.code = 'messaging/mismatched-credential';
          return { success: false, error: h };
        }
        if (/GECICI/.test(m.token)) {
          const h = new Error('sunucu meşgul');
          h.code = 'messaging/server-unavailable';
          return { success: false, error: h };
        }
        return { success: true, messageId: 'id-' + m.token.slice(0, 6) };
      });
      return Promise.resolve({
        successCount: yanitlar.filter((y) => y.success).length,
        failureCount: yanitlar.filter((y) => !y.success).length,
        responses: yanitlar
      });
    }
  })
};
