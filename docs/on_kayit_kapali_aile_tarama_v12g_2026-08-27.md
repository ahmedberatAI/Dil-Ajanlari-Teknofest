# Ön kayıt — v12g kapalı aile tarama + atomik doğrulama

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

## Hipotez

Açık-uçlu olay nesri bazı küçük fakat gerçek İSG olaylarında hiç aday üretmiyor.
Olay üretmeyen kliplerde tek bir kapalı-uzay aile taraması yapılır; seçilen aile
mevcut bağımsız atomik kanıt kapısından geçmeden alarm olmaz. Böylece aday recall'ı
ile kanıt precision'ı ayrılır.

## Kilitli yöntem

`llm-large` videodan yalnız bir sınıf seçer:

`YANGIN_DUMAN, KISI_DUSME, SIDDET_SILAH, ARAC_KAZA, YUK_COKME,
MAKINE_SIKISMA, ASKIDA_YUK, SINIR_IHLALI, KKD_EKSIK, OLAY_YOK, GORUNMUYOR`.

Seçim alarm değildir. Seçilen aile `vlm` varlık/olgu ve `llm-large` ilişki/zaman
sorularından oluşan v12 atomik spekle yeniden, önceki cevabı göstermeden doğrulanır.
Yalnız `SUPPORTED` alarm adayıdır. `YUK_COKME` ve `MAKINE_SIKISMA` için eklenmiş
fakat varsayılanı kapalı iki spek bu probda doğrudan kullanılacaktır.

## Dondurulmuş geliştirme örneklemi

`benchmark/results/eval_20260827_194722.json` sonunda olay üretmeyen:

- 17 tehlike klibi,
- 43 doğru-negatif normal klip,
- toplam 60 klip.

Holdout açılmaz.

## Kabul ölçütleri

- 17 kaçırmadan en az 3'ü atomik destekle geri kazanılmalı,
- 43 doğru negatifte yeni FP sayısı 0 olmalı,
- 60/60 tamamlanmalı ve API hatası 0 olmalı.

Geçilirse özellik bayrağıyla entegre edilip tam 50+50 geliştirme koşusu ayrıca ön
kaydedilir. Geçilmezse üretime alınmaz.

