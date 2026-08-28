# Ön kayıt — v10 yapılandırılmış İSG olay gölgelemesi

**Tarih:** 2026-08-27  
**Kaynak bulgu:** v9 tam koşusu üç kodda da recall/FP kabulünü geçti; yalnız
`nearmiss run_13 eye_04` satırında yapılandırılmış near-miss olayına ek olarak serbest
anlatı aynı fiziksel olayı ikinci kez, kritik önemle yazdı.

## Değişiklik

Model, API, prompt, slot, eşik ve karar kuralları değişmez. `isg_grounded` politikasında,
yapılandırılmış İSG koduyla aynı fiziksel ailede ve en fazla 5 saniye uzaktaki kodsuz
serbest anlatı kopyası deterministik olarak kaldırılır. Farklı tehlike ailesi korunur.
Near-miss yanında gerçek bir çarpışma kaybolmasın diye çarpışma ailesi yalnız
`risk/ramak/yakın/kaçınma` niteleyicisi taşıyorsa near-miss kopyası sayılır.

## Kabul

- birim testte near-miss kopyası silinir, ayrı gerçek çarpışma korunur;
- hedef `run_13/eye_04` yeniden koşusunda yalnız yapılandırılmış near-miss olayı kalır;
- v9 tam koşu eşikleri değişmez: yangın 2/2, çarpışma 3/3, near-miss 20/20 ve kod FP 0;
- normal 0/20 korunur;
- tüm öğrenilmiş çıkarım sabit özel API'dedir; yerel model yoktur.

Sonuçtan sonra bu ön kayıt değiştirilmeyecektir.
