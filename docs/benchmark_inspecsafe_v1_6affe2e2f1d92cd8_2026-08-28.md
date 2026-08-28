# InspecSafe-V1 gercek test sonucu

- Tamamlanma (UTC): `2026-08-28T02:43:03.034603+00:00`
- Test: **1250 / 1250** resmî ornek
- Veri manifest SHA-256: `13721d4b691312a21953da2ad9780a05d0feda9c8bd035c9cc5eed6a531dc766`
- Kosum anahtari: `6affe2e2f1d92cd8`
- Ogrenilmis cikarim: yalniz ozel API; yerel model/model indirme yok

## Ana sonuclar

| Kol | 4-sinif strict accuracy | Kapsama | Unsafe precision | Unsafe recall | Unsafe F1 | Normal FPR | MCC |
|---|---:|---:|---:|---:|---:|---:|---:|
| direct VLM | 62.5% (781/1250; 95% GA 59.8%–65.1%) | 96.9% | 41.6% | 92.0% | 57.3% | 32.4% | 0.480 |
| ara karar (vlm + llm-large) | 83.7% (1046/1250; 95% GA 81.5%–85.6%) | 100.0% | 71.3% | 61.4% | 66.0% | 6.2% | 0.584 |
| tam sistem (3 model) | 83.5% (1044/1250; 95% GA 81.4%–85.5%) | 99.8% | 70.6% | 61.4% | 65.7% | 6.4% | 0.580 |

## Eslesik karsilastirma

Sistem dogrudan kolun **312** hatasini duzeltti; **49** dogrusunu bozdu. Accuracy farki +21.0 puan, exact McNemar p=`5.67266e-48`.

On-kayitli gerilemesizlik kapisi: **KALDI**.

- GECTI — `four_class_accuracy_non_decreasing`
- GECTI — `unsafe_precision_non_decreasing`
- KALDI — `unsafe_recall_non_decreasing`
- GECTI — `normal_fpr_non_increasing`
- GECTI — `end_to_end_coverage_at_least_99pct`

## Yayimlanmis dogrudan VLM referansi

Yalniz `direct VLM` kolu, resmi tek-goruntu + standart prompt protokolune yakindir. Ozel API `image_url` kabul etmedigi icin ayni tek kare iki ozdes kareli kayipsiza-yakin MP4'e sarilmistir; tam uc-modelli sistem skoru bu tek-model siralamasiyla dogrudan kiyaslanamaz. Resmi betik T=0.1, bu kosum T=0.0 kullandigi icin yayin karsilastirmasi yalniz yon gostericidir.

Yayimlanan 15 modelin accuracy araligi `41.7%`–`81.3%`. Bizim direct kol nokta degerinden daha yuksek 12/15 yayim satiri vardir.

| Yayin modeli | Accuracy |
|---|---:|
| doubao-seed-1-6-vision-250815 | 81.3% |
| qwen3-vl-32b-thinking | 76.9% |
| qwen3-vl-235b-a22b-thinking | 75.4% |
| grok-4.1-fast | 73.0% |
| qwen3-vl-235b-a22b-instruct | 72.4% |
| glm-4.5v | 72.0% |
| claude-opus-4-5-20251101 | 71.7% |
| qwen3-vl-8b-thinking | 70.2% |
| qwen3-vl-8b-instruct | 69.4% |
| gemini-3-flash-preview | 68.9% |
| GLM-4.1V-Thinking-Flash | 68.6% |
| qwen3-vl-32b-instruct | 68.2% |
| gpt-5.2 | 62.5% |
| yi-vision | 61.2% |
| glm-4.6 | 41.7% |

## Dort-sinif confusion matrix

### direct VLM

| Gercek \ Tahmin | Level I | Level II | Level III | Normal | Invalid |
|---|---:|---:|---:|---:|---:|
| Level I | 52 | 93 | 15 | 9 | 0 |
| Level II | 2 | 54 | 9 | 10 | 0 |
| Level III | 0 | 6 | 0 | 1 | 0 |
| Level IV / normal | 59 | 128 | 98 | 675 | 39 |

### ara karar (vlm + llm-large)

| Gercek \ Tahmin | Level I | Level II | Level III | Normal | Invalid |
|---|---:|---:|---:|---:|---:|
| Level I | 82 | 21 | 13 | 53 | 0 |
| Level II | 7 | 26 | 2 | 40 | 0 |
| Level III | 0 | 2 | 1 | 4 | 0 |
| Level IV / normal | 48 | 6 | 8 | 937 | 0 |

### tam sistem (3 model)

| Gercek \ Tahmin | Level I | Level II | Level III | Normal | Invalid |
|---|---:|---:|---:|---:|---:|
| Level I | 82 | 21 | 13 | 53 | 0 |
| Level II | 7 | 26 | 2 | 40 | 0 |
| Level III | 0 | 2 | 1 | 4 | 0 |
| Level IV / normal | 48 | 6 | 8 | 935 | 2 |

## Alan bazinda strict accuracy

| Alan | Direct | System | Uctan uca |
|---|---:|---:|---:|
| coal_conveyor | 35.4% | 78.3% | 78.3% |
| metallurgy | 63.8% | 81.4% | 81.4% |
| oil_gas_chemical | 69.4% | 81.2% | 80.4% |
| power | 93.4% | 92.5% | 92.5% |
| tunnel | 61.1% | 86.1% | 86.1% |

## Kosum ve yorum siniri

Cagri gecikmesi p50/p95: `2.886` / `5.341` sn; satir gecikmesi p50/p95: `11.874` / `15.731` sn.

Semantik betim benzerligi raporlanmadi; resmi BGE-M3 degerlendiricisi sabit model sozlesmesi disinda oldugu icin calistirilmadi. InspecSafe-V1 tek kareli ve agirlikla normal bir robot-denetim testidir; sonuc video zamansalligini veya butun ISG dagilimlarini tek basina kanitlamaz.
