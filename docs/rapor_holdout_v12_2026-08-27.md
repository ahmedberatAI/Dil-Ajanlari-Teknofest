# v12 dokunulmamış iSafetyBench holdout sonucu

Tarih: 2026-08-27  
Sonuç: **Reddedildi — recall kabul kapısını geçmedi**

Ham tek-sefer sonuç: `benchmark/results/eval_20260827_221706.json`.

Önceden kilitli 100 tehlike + 100 normal klibin tamamı bir kez işlendi:

- TP 64/100, FN 36/100, recall %64 [%54,2–%72,7],
- FP 8/100, TN 92/100, normal operasyonel FP %8 [%4,1–%15,0],
- MCC +0,5833,
- kapsam 200/200, işleme/API hata izi 0,
- medyan gecikme 20,5 saniye,
- sıkı olay-aile eşleşmesi 24/100 (%24).

Ön kayıt kapılarından kapsam, hata, FP, MCC ve dejenere-olmama geçti; recall için
gerekli %70 geçilmedi. Sonuç ayar seçmek veya prompt değiştirmek için
kullanılmayacak ve bu holdout tekrar koşulmayacaktır.

Sekiz normal yanlış alarmın olay kategorisi dağılımı: 4 Kaza, 3 Güvenlik, 1 Sağlık.
Üçünde `Warehouse_Visible_Fire` yapılandırılmış yangın kodu vardı; beşinde serbest/
diğer olay kodu vardı. Yanlış alarmlar 8 olay kaydı + yönetici bildirimi, 6 alan
güvenliği, 5 güvenlik ekibi, 2 acil durdurma ve 2 sağlık ekibi tetiklemesine yol
açtı. Bu dağılım yalnız rapordur; v12 holdout'a göre yeni kural ayarlanmayacaktır.
