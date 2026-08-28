# Ön kayıt — v12 yapılandırılmış duman/alev atomik kapısı

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

## Soru

v11 geliştirme koşusunda `Warehouse_Visible_Fire` üretilen 26 klipte mevcut
iki atomlu `yangın/duman` doğrulaması yapılandırılmış slotun yanlış önerilerini
ayırt edebiliyor mu?

## Sabit örneklem

- Kaynak sonuç: `benchmark/results/eval_20260827_194722.json`.
- Yalnız `Warehouse_Visible_Fire` olayı üretilen klipler.
- Pozitif: iSafetyBench `gt_actions` içinde `fire incident` bulunan öneriler.
- Negatif: bu etiketi taşımayan öneriler; normal ve başka tehlike etiketli
  klipler birlikte.
- Beklenen koşullu örneklem: 11 pozitif + 15 negatif = 26.
- Etiket atomik doğrulama istemine verilmez.

## Ölçülen kapı

1. `vlm`: gerçek alev veya şekil değiştiren/yükselen duman benzeri olgu.
2. `llm-large`: kronolojik olarak alev/yayılan duman mı, yoksa buhar, toz,
   parlama, sıkıştırma ya da sabit nesne mi?
3. Yalnız iki atom da `SUPPORTED` ise yapılandırılmış olay korunur.

## Kabul

- Pozitif recall en az 9/11.
- Negatiflerde en fazla 5/15 destek (`FPR <= %33,3`).
- API/biçim hatası 0.

Üç koşul birlikte sağlanmazsa kapı üretime alınmayacaktır. Bu geliştirme
probudur; yeni holdout'a bakılmaz.

