# Ön kayıt — v12e zamansal yangın şüphesi kolu

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

## Hipotez

Doğrudan alev/duman kapısının yerine geçmeyen ikinci bir aday üretici ölçülecek.
Videoda önce yokken sonradan oluşan yerel ışık/alev veya bulutumsu bulanıklığın
ardından insanların aynı kaynağa yönelmesi, uzaklaşması, koşması ya da müdahale
etmesi **yangın şüphesi** adayı üretebilir. Tek başına ışık, bulanıklık veya insan
hareketi olay değildir.

## Kilitli karar kuralı

Bir aday yalnız şu iki bağımsız özel-API ölçümü birlikte destek verirse pozitiftir:

1. `vlm`: `YENI_ISIK_BULUT` — belirti önce yokken sonra belirip büyümüş/yayılmıştır.
2. `llm-large`: `KAYNAKLA_BAGLANTILI_TEPKI` — insanlar belirtiden sonra aynı
   kaynağa yönelmiş, uzaklaşmış, koşmuş veya müdahale etmiştir.

`BUHAR_TOZ_PARLAMA`, kamera pozlaması, far/kaynak ışığı, rutin hareket ve belirsiz
yanıtlar destek değildir. Bir rolün hatası fail-closed sonuç verir. Bu kol doğrudan
“yangın var” demez; yalnız “zamansal yangın şüphesi” üretir.

## Dondurulmuş geliştirme örneklemi

- `data/eval_genelleme` içindeki iSafetyBench geliştirme kümesi,
- 13 adet `fire incident` etiketli tehlike klibi,
- 50 adet normal klip,
- karşılaştırma tabanı: `benchmark/results/eval_20260827_194722.json`.

Bu ölçüm holdout değildir; dondurulmuş `data/eval_genelleme_holdout_v12` açılmaz.

## Kabul ölçütleri

Kol ancak aşağıdakilerin **tamamını** sağlarsa tam geliştirme adayına dönüşür:

- v11'in kaçırdığı 2 yangın klibinden en az 1'ini geri kazanır,
- v11'de doğru negatif olan 43 normal klipte yeni FP sayısı 0'dır,
- 50 normalin tamamında şüphe tetikleme sayısı en fazla 2'dir,
- 63/63 örnek tamamlanır ve API hatası 0'dır.

Eşik geçilmezse üretim koduna alınmaz. Geçilirse önce tam 50+50 geliştirme koşusu
ön kaydedilir; o da geçmeden holdout açılmaz.

