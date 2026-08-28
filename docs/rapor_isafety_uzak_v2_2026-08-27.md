# iSafetyBench özel API mimari raporu — 2026-08-27

## Geçerlilik

Eski `benchmark/results/isafety_mcq.json` kullanılmaz: o koşuda vLLM'nin eski
`guided_choice` alanı sessizce yok sayılmış ve serbest metnin ilk harfi seçenek
diye puanlanmıştır. `isafety_uzak_20260824_233450.json` biçimsel olarak geçerlidir
fakat yalnız agregat içerir; klip/şık sırası/tahmin denetlenemez.

Yeni koşu başlamadan önce `structured_outputs.choice` negatif kontrolü geçti.
40/40 klipte video SHA-256, 16 şık ve sırası, GT, ham tahmin, hata ve gecikme
saklandı. Hata yok, coverage %100. Öğrenilmiş çıkarım yalnız sabit özel API'dedir.

## Eşleştirilmiş geliştirme sonucu

| Kol | Toplam | Hazard | Normal | Doğrudan `llm-large` farkı | McNemar |
|---|---:|---:|---:|---:|---:|
| Doğrudan `llm-large` | 20/40 = %50 | 11/20 = %55 | 9/20 = %45 | taban | — |
| `vlm` betim → `llm-large` | 18/40 = %45 | 10/20 = %50 | 8/20 = %40 | −5 puan | p=0,754 |
| Doğrudan `vlm` | 20/40 = %50 | 12/20 = %60 | 8/20 = %40 | 0 puan | p=1,000 |
| `llm-fast` seçici ensemble | 18/40 = %45 | 10/20 = %50 | 8/20 = %40 | −5 puan | p=0,727 |

Üç kolun tanısal oracle tavanı 26/40 (%65) olsa da oracle gerçek zamanda hangi
kolun doğru olduğunu bilemez ve sevk yöntemi değildir. Denenen `llm-fast` hakemi
bu tamamlayıcılığı kullanamadı; üç doğruyu düzeltirken beş doğruyu bozdu.

## Karar

- Genel iSafety MCQ benzeri açık taksonomi sınıflamasında doğrudan `llm-large`
  korunur. Cascade, doğrudan VLM veya ensemble sevke alınmaz.
- %50 küçük geliştirme skoru “maksimum performans” değildir; model/API sabitken
  ek ajan çağrılarının bunu güvenilir biçimde yükselttiğine dair kanıt çıkmadı.
- Hazard ve normal farkları n=20 nedeniyle geniş Wilson aralıklarına sahiptir;
  bu kümede role göre gizli routing yapılmaz.
- Sonraki gerçek ilerleme, yeni prompt kolu seçmekten önce görülmemiş holdout,
  zaman aralığı/bbox alt-etiketi ve karar güveni kalibrasyonu gerektirir.

## Ürün açısından anlamı

iSafety tek-etiketli 16-sınıf MCQ, son ürünün kanıt-kapılı olay boru hattı değildir.
Yine de açık-dünya olay adlandırmanın mevcut sabit modellerle tavanının sınırlı
olduğunu gösterir. Bu nedenle üretimde kritik alarm serbest sınıf adından değil,
atomik fiziksel kanıt + yapılandırılmış kural + kaçınma mantığından doğar.
