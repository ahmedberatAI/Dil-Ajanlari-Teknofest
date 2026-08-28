# Ön kayıt — v12c atomik iddia ayrıştırma ve genişletilmiş İSG aileleri

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

## Değişiklik

Tek bir model cümlesindeki her fiziksel iddia ailesi bağımsız doğrulanır.
Mevcut v11 bütün ailelerin desteklenmesini istiyor ve örneğin düşme
`SUPPORTED`, çarpışma `REFUTED` olduğunda kanıtlı düşmeyi de siliyor. Aday:

- tüm aileler destekliyse özgün olay korunur,
- yalnız bazı aileler destekliyse özgün nesir atılır ve her destekli aile için
  sabit, dar bir olay şablonu üretilir,
- hiçbir aile desteklenmiyorsa olay silinir.

İki yeni kapalı aile eklenir:

1. `kontrolsüz yük/çökme`: gerçek yük/yapı + düşme, devrilme, kopma veya çökme
   geçişi; rutin indirme/taşıma açık negatiftir.
2. `makineye sıkışma/ezilme`: gerçek kişi ve makine/araç + beden/giysi
   sıkışması, çekilmesi veya ezilmesi; rutin yakın çalışma açık negatiftir.

## Geliştirme ölçümü

- Veri: görülen `data/eval_genelleme`, 50 tehlike + 50 normal.
- Tüm üretim hattı birlikte çalışır; yalnız
  `DILAJAN_ATOMIC_CLAIM_DECOMPOSITION=1` adayı açar.
- v11 referansı: TP33 FP7 FN17 TN43, recall %66, normal operasyonel FP %14,
  MCC +0,531.

## Kabul

- Recall en az 36/50 (%72).
- Normal operasyonel FP en fazla 8/50 (%16).
- MCC en az +0,56.
- Kapsam 100/100 ve hata 0.

Tümü sağlanmazsa özellik varsayılan açılmaz. Aynı geliştirme kümesinde kabul
edilse bile genel başarı iddiası değildir; nihai karar daha önce kilitlenen
200 kliplik holdout'ta verilir.
