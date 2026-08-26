# ÖLÇÜM — `d-35` (Süleyman Eren Kayacılar) üç commit, ayrı ayrı

Tarih: 2026-08-26 · Düzenek: `scratchpad/dogru_rapor.py` — 8 klipli sabit panel
Her klip için **BEKLENEN** ve **YASAK** tehlike önceden yazıldı; puan **iki yönlü**.

**Neden iki yönlü:** bugün ölçüldü — prompt değişiklikleri tek yönlü eşik
kaydırıyor. Yalnız isabete bakan bir ölçüt, "her şeye kavga de" diyen kolu da
"her şeye sus" diyen kolu da ödüllendirir.

## Hüküm

| commit | ne yapıyor | hüküm |
|---|---|---|
| `a333f24` nedensel ayrım | yangın varsa panik ≠ kavga; kavga için temas şartı | **fayda** — yanlış kavga 6/6 → 4/6, risk Kritik→Orta (2 koşum) |
| `1ecae92` temperature=0 | tüm anlatı çağrıları 0,0 | **fayda** — 3/3 koşum birebir aynı (`ddd31ed61766`); main 3/3 farklı. Kritik→Yüksek, olay 3→1, silah uydurması gitti |
| `ff46622` kavga eşiği + mutlak yangın önceliği | kavga için yumruk/tekme/boğma şartı; yangın mutlak öncelik | **ZARARLI** |

## `ff46622` neden zararlı — ölçüldü

| panel | bizim main | ff46622 |
|---|---|---|
| **İSABET** | **5/6** | **3/6** |
| yanlış tehlike | 1/8 | 1/8 |

| klip | main | ff46622 |
|---|---|---|
| `Assault018` | "iterek yere devirme" ✓ | "ani ve kontrolsüz yere düşüşü" ✗ |
| `Assault038` | "sert fiziksel saldırı ve itme" ✓ | "itilerek yere düşmüştür" ✗ · risk Kritik→Yüksek |

Kavga eşiğini yükseltmek **gerçek saldırıları kaçırttı** (2/6 isabet kaybı) ve
hedef klibi **düzeltmedi** — yangın klibi her iki kolda da hâlâ "kavga".

Mutlak yangın önceliği tetiklenemiyor çünkü kural *"sahnede yangın VARSA"*
diye başlıyor ve model yangını zaten görmüyor (bugün üç bağımsız ölçümle
doğrulandı).

## Öneri

`a333f24` + `1ecae92` **alınmalı**, `ff46622` **alınmamalı**.
`1ecae92` birleştirilmeden önce üç sevk matrisinin korunduğu koşularak
doğrulanmalı — gözlem düzlemi zaten `temperature=0.0` (`gozlem.py:453`),
yani üç kuralın MCC'si etkilenmemeli, ama `category_match` anlatı
düzleminden besleniyor.

## Bugünün genel dersi (dört bağımsız ölçüm)

| deneme | yangını öne çıkardı mı |
|---|---|
| İngilizce prompt (27 klip, eşleşmiş) | hayır — sessiz kaçırma 0/9 |
| `a333f24` nedensel ayrım (6 tekrar) | hayır — 0/6 |
| tehdit merceği ablasyonu (workflow) | hayır — alev/duman 4/4 ham betimlemede yok |
| kapalı ikili panel + logprob | **kısmen** — P(yangın) 0,777 vs kontrol 0,562, ama kavga 0,990 |

Prompt düzeyindeki her müdahale **eşik kaydırıyor**, algıyı değiştirmiyor.
Tek ayrım gücü gösteren mekanizma **panel** oldu (forklift 1,000 vs 0,349).
