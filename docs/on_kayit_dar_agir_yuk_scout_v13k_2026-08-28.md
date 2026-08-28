# v13k dar ağır-yük scout — deney ön kaydı

Tarih: 2026-08-28

## Hipotez

v13f olay-sız geliştirme örneklerinin en büyük kayıtlı fiziksel FN kümesi beş
ağır-yük olayıdır. Geniş scout sekiz sınıf arasında yönlendirme yaparken bu
örnekleri çoğunlukla `OLAY_YOK/GORUNMUYOR` seçmiştir. v13k yalnız ağır-yük
kararını daraltır; doğrudan aile taraması yapmaz.

## Sabit akış

1. `llm-large` kapalı scout seçenekleri:
   `KONTROLSUZ_AGIR_YUK`, `KONTROLLU_TASIMA`, `OLAY_YOK`, `GORUNMUYOR`.
2. Yalnız `KONTROLSUZ_AGIR_YUK` seçilirse mevcut `dengesini kaybeden ağır yük`
   ailesi `vlm` varlık atomu + `llm-large` zamansal atomla doğrulanır.
3. İki atom da desteklemeden olay üretilemez; hata fail-closed'dur.

## Örneklem ve sözleşme

- Kaynak: v13f sonucundaki 119 olay-sız klip.
- Pozitif: kilitli v13a haritasındaki 5 ağır-yük klibi.
- Negatif: kalan 114 klip (21 anomali karşıtı + 93 normal).
- Öğrenilmiş çıkarım yalnız özel API; sabit modeller `vlm`, `llm-large`,
  `llm-fast`; yerel öğrenilmiş model/indirme yok.
- v13 holdout okunmaz.

## Kilitli kabul kapıları

- Semantik kurtarma: en az `2/5`.
- Yeni yanlış alarm: tam olarak `0/114`.
- API/ayrıştırma hatası: `0`.

Geçiş yalnız opt-in entegrasyon iznidir; tam-dev ayrıca ölçülür.

