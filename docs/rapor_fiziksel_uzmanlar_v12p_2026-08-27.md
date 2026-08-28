# v12p olay-sız fiziksel uzmanlar — geliştirme kapısı sonucu

Tarih: 2026-08-27  
Sonuç: **Kabul — birleşik adayda bayrak arkasında sınanacak**

Ham sonuç: `benchmark/results/fiziksel_uzmanlar_v12p_20260827_213752.json`.

- geri kazanım: 3/6,
- yeni yanlış alarm: 0/48,
- API hatası: 0,
- scout hedef-aile eşleşmesi: 3/6,
- medyan ek gecikme: 1,65 saniye.

Doğru geri kazanımlar araç içi şiddetli kaza, kenardan düşen yol silindiri ve
destek kaybı sonrası borudan sarkan kişidir. İki ağır yük olayı scout tarafından
araç ailesine yönlendirildiği, kavga klibi `OLAY_YOK` seçildiği için kaçmıştır.
Kabul yalnız bu üç fiziksel olay ve sıfır yeni FP davranışı içindir; scout'un
kaçırdığı aileleri gevşek nesirle alarm yapma yetkisi vermez.
