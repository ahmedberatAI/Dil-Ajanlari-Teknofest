# v12q doğrudan ağır yük + kavga rescue — sonuç

Tarih: 2026-08-27  
Sonuç: **Reddedildi — mimariye bağlanmadı**

Ham sonuç: `benchmark/results/dogrudan_fiziksel_rescue_v12q_20260827_214017.json`.

- geri kazanım: 1/3,
- doğru hedef aile desteği: 1/3,
- yeni yanlış alarm: 3/48,
- API hatası: 0.

Yalnız gerçek kavga yakalandı. Aynı kavga atomu üç rutin normal klibi de kavga olarak
destekledi. İki ağır yük klibi ise `KONTROLLU_TASIMA` diye reddedildi. Bu nedenle
scout olmadan bütün kliplerde doğrudan çoklu uzman çalıştırma yaklaşımı kullanılmaz.
