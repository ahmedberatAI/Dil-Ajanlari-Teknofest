# Ön kayıt — SynthSite Tier-1 askıdaki yük İSG benchmarkı

**Tarih:** 2026-08-27  
**Durum:** Model çıktıları görülmeden yazıldı. Sonuç alındıktan sonra bu dosya değiştirilmez.

## Veri ve etiket uygunluğu

- Kaynak: `govtech/SynthSite`
- Sabit revizyon: `2904ec01c3dbf2efba09f2cb1b7bdf17841d4d39`
- Lisans: GovTech Singapore Open Source Software Licence
- Ana küme yalnız `tier == 1`: **150 video**
- Dağılım: **76 güvensiz**, **74 güvenli**
- Her videoda en az iki insan değerlendirici vardır ve tüm etiketler uzlaşır.
- Kaynağın raporladığı Tier-1 uyumu: Cohen κ **1,00**, Krippendorff α **1,00**.
- İnsanların uzlaşamadığı Tier-2 (77 video; κ −0,24, α −0,33) ana skora alınmaz.
- Klipler mevcut UCF-Crime, FIRESENSE, iSafetyBench, Eskişehir OSB ve NVIDIA
  SDG-Warehouse kümelerinden farklıdır.

## Dondurulmuş kural

`IHLAL_VAR` yalnız üç koşul birlikte görünüyorsa doğrudur:

1. Yük vinçle gerçekten havada asılıdır.
2. Çalışan yükün doğrudan altındaki düşme bölgesindedir.
3. Bu ilişki en az 1 saniye sürer.

Yakında bulunma, bariyer arkasında kalma, perspektif yanılsaması, yerdeki yük ve
1 saniyeden kısa geçiş `IHLAL_YOK` kabul edilir. Üç koşuldan biri güvenilir biçimde
ölçülemiyorsa `GORUNMUYOR` seçilir. Etiket hiçbir isteme eklenmez.

Tam istem ve kapalı cevap kümesi `benchmark/synthsite_tier1.py` içinde sabittir.
İstem veya puanlayıcı değişirse yeni ön kayıt ve yeni koşum kimliği gerekir.

## Model ve servis sözleşmesi

- Öğrenilmiş çıkarım yalnız `https://evren-llmapi.ssyz.org.tr/v1` üzerinden yapılır.
- Model rolleri değişmez: algı `vlm`, olay `llm-large`, yapı/özet `llm-fast`.
- Bu görsel ölçüm yalnız algı rolünü (`vlm`) kullanır; başka model indirilmez veya
  yerelde çalıştırılmaz.
- Sıcaklık `0`, cevap seçenekleri `IHLAL_VAR | IHLAL_YOK | GORUNMUYOR`.

## Önceden belirlenmiş metrikler ve kabul kapısı

`GORUNMUYOR` ile servis/ayrıştırma hataları başarı sayılmaz. Katı recall ve katı
accuracy paydasında hata olarak kalır; ayrıca coverage ile ayrı raporlanır.

- Katı recall ≥ **0,90**
- Precision ≥ **0,90**
- Güvenli klip yanlış alarm oranı ≤ **0,10**
- Karar coverage ≥ **0,90**
- Katı accuracy ≥ **0,90**

Beş koşulun tamamı sağlanmadan benchmark geçmez. Ham TP/FP/TN/FN, kaçınma/hata,
Wilson %95 güven aralıkları ve video üreticisi dilimleri birlikte raporlanır.

## Sınırlama

Veri insan uzlaşılı olsa da sentetiktir ve tek bir İSG kuralını ölçer. Başarılı sonuç,
gerçek şantiye/depo CCTV üretim güvenliği kanıtı değildir; başarısız sonuç ise bu dar
fiziksel ilişki için doğrudan bir model/kullanım kusurudur.
