# SynthSite Tier-1 askıdaki yük İSG benchmark raporu

**Tarih:** 2026-08-27  
**Ön kayıt:** `docs/on_kayit_synthsite_tier1_2026-08-27.md`  
**Ham sonuç:** `benchmark/results/synthsite_tier1_20260827_180131.json`

## Sonuç

Benchmark **geçmedi**. Model karar vermekten kaçınmadı ve servis hatası üretmedi;
fakat askıdaki yük ile çalışanın düşme bölgesi arasındaki fiziksel ilişkiyi yeterince
ayıramadı. Baskın hata 76 gerçek ihlalin 59'unun kaçırılmasıdır.

| ölçüt | sonuç | Wilson %95 GA | ön kayıt kapısı |
|---|---:|---:|---:|
| Katı recall | 17/76 = **%22,37** | %14,46–32,93 | ≥ %90 ❌ |
| Precision | 17/29 = **%58,62** | %40,74–74,49 | ≥ %90 ❌ |
| Güvenli klip yanlış alarmı | 12/74 = **%16,22** | %9,53–26,24 | ≤ %10 ❌ |
| Coverage | 150/150 = **%100** | %97,50–100 | ≥ %90 ✅ |
| Katı accuracy | 79/150 = **%52,67** | %44,71–60,49 | ≥ %90 ❌ |

Karışıklık matrisi: **TP 17 · FP 12 · TN 62 · FN 59**. `GORUNMUYOR`, servis
hatası ve biçim hatası sayısı sıfırdır. Ortalama gecikme 8,52 sn/klip, medyan
6,56 sn, p95 17,60 sn ve maksimum 41,56 sn'dir.

## Veri doğruluğu ve seçim

Resmî kaynak `govtech/SynthSite`, revizyon
`2904ec01c3dbf2efba09f2cb1b7bdf17841d4d39` olarak sabitlendi. Ana ölçümde
yalnız iki veya daha fazla insan değerlendiricinin tam uzlaştığı Tier-1 kullanıldı:
76 güvensiz ve 74 güvenli, toplam 150 klip. Kaynağın bu katman için raporladığı
Cohen κ ve Krippendorff α değerleri 1,00'dır. İnsan uzlaşması zayıf Tier-2, model
çıktıları görülmeden önce paydadan çıkarıldı.

İlk aday SteelBench'in açık örnek bölümünde `smoke/steam` ve
`compliant/not_worn` alanları arasında çelişkiler bulunduğu için o veri nihai ölçüme
alınmadı. Bu karar da model koşumundan önce verildi.

## Sabit çıkarım sözleşmesi

- Özel API: `https://evren-llmapi.ssyz.org.tr/v1`
- Algı: `vlm`
- Olay: `llm-large`
- Yapı/özet: `llm-fast`
- Bu dar görsel ölçümde yalnız görevine uygun algı rolü çağrıldı.
- Yerel model, yeni ağırlık veya farklı alias kullanılmadı.
- Sıcaklık 0; kapalı seçenekler `IHLAL_VAR | IHLAL_YOK | GORUNMUYOR`.

Etiketler modele verilmedi. Tam istemin SHA-256 değeri:
`9b3d7afe4243dfa22ab894dd4173de67f78bd7d81f60c2708742ed4a1866b646`.

## Üretici dilimleri

| video üreticisi | n | recall | yanlış alarm | accuracy |
|---|---:|---:|---:|---:|
| Sora 2 Pro | 4 | %0,00 | %0,00 | %50,00 |
| Veo 3.1 | 74 | %21,57 | %21,74 | %39,19 |
| Wan 2.2-14B | 61 | %40,00 | %15,22 | %73,77 |
| Wan 2.6 | 11 | %0,00 | %0,00 | %27,27 |

Küçük dilimler tek başına kıyaslanmamalıdır. Sonuçların üreticiye göre ciddi
değişmesi, görüntü üretim biçimine duyarlılığı gösterir.

## Hata denetimi

Yanlış negatif örneklerin görsel denetiminde çalışanlar çoğunlukla geniş açı veya
yüksek kamera görünümünde küçüktür. Yanlış pozitiflerde çalışan yükün yakınında
olmasına rağmen doğrudan altında değildir. Bu desen, nesne varlığından çok
**çalışan–yük ilişkisi, perspektif ve en az bir saniyelik süreklilik** ayrımının
başarısız olduğunu gösterir.

Bir sonraki geliştirme kolu model değiştirmek değil; aynı sabit `vlm` için yük ve
çalışan bölgelerini yakınlaştıran kanıt seçimi, ardından ayrı `asılı yük`, `düşme
bölgesi` ve `≥1 sn süreklilik` slotlarının deterministik AND kapısıyla birleştirilmesi
olmalıdır. Bu koşu görüldüğü için yapılacak yeni kol aynı 150 klipte bağımsız holdout
iddiası taşıyamaz; yeni bir ön kayıtla geliştirme sonucu olarak raporlanmalıdır.

## Sınırlama

SynthSite sentetiktir ve yalnız askıdaki yük kuralını ölçer. Etiket güvenilirliği
yüksek olsa da bu sonuç gerçek şantiye CCTV güvenliği veya diğer İSG olayları için
tek başına yeterli kanıt değildir.
