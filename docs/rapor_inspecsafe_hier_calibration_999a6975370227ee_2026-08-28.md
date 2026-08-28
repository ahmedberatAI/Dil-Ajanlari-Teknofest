# InspecSafe-V1 hiyerarsik calibration sonucu

- Kosum anahtari: `999a6975370227ee`
- Manifest SHA-256: `1561cd7592a2e49881e502fed75c9def303172e4d6f05998512cd3bcef843fba`
- Runner SHA-256: `751c9ea8bf0eb22e331b5d4c528e1621dd9d2cab73a0a6ff419833846e1e301b`
- Tamamlanma: `2026-08-28T07:16:18.401580+00:00`
- Secili ornek: **734** inspection grubu
- Karar tanimi: `{"architecture": "hybrid", "rescue_threshold": 0.76, "veto_threshold": 0.21}`

Aranan aday: 5099; kapidan gecen: 1491.

## Birincil yuksek-performans profili

- Karar tanimi: `{"architecture": "hybrid", "rescue_threshold": 0.7, "veto_threshold": 0.21}`
- Severity ek-cagri orani: **8.4%**
- Kapi: **GECTI**

| Metrik | Duz taban | Aday |
|---|---:|---:|
| 4-sinif test-onculu accuracy | 87.2% | 88.4% |
| 4-sinif empirical accuracy | 71.5% (525/734; 95% GA 68.2%-74.7%) | 75.5% (554/734; 95% GA 72.2%-78.5%) |
| Unsafe precision (test onculu) | 86.5% | 86.8% |
| Unsafe recall | 62.7% (230/367; 95% GA 57.6%-67.5%) | 78.5% (288/367; 95% GA 74.0%-82.4%) |
| Unsafe F1 (test onculu) | 72.7% | 82.4% |
| Normal FPR | 2.5% (9/367; 95% GA 1.3%-4.6%) | 3.0% (11/367; 95% GA 1.7%-5.3%) |
| Macro recall | 45.3% | 50.0% |
| Kapsama | 100.0% (734/734; 95% GA 99.5%-100.0%) | 100.0% (734/734; 95% GA 99.5%-100.0%) |

## Ikincil kati gerilemesizlik profili

| Metrik | Duz taban | Aday |
|---|---:|---:|
| 4-sinif test-onculu accuracy | 87.2% | 88.8% |
| 4-sinif empirical accuracy | 71.5% (525/734; 95% GA 68.2%-74.7%) | 75.2% (552/734; 95% GA 72.0%-78.2%) |
| Unsafe precision (test onculu) | 86.5% | 89.6% |
| Unsafe recall | 62.7% (230/367; 95% GA 57.6%-67.5%) | 74.9% (275/367; 95% GA 70.2%-79.1%) |
| Unsafe F1 (test onculu) | 72.7% | 81.6% |
| Normal FPR | 2.5% (9/367; 95% GA 1.3%-4.6%) | 2.2% (8/367; 95% GA 1.1%-4.2%) |
| Macro recall | 45.3% | 49.4% |
| Kapsama | 100.0% (734/734; 95% GA 99.5%-100.0%) | 100.0% (734/734; 95% GA 99.5%-100.0%) |

Severity ek-cagri orani: **6.3%**.

## Kapi — GECTI

- GECTI — `at_least_one_strict_primary_gain`
- GECTI — `coverage_at_least_99pct`
- GECTI — `every_domain_fpr_non_increasing`
- GECTI — `every_domain_recall_non_decreasing`
- GECTI — `level_one_recall_non_decreasing`
- GECTI — `normal_fpr_non_increasing`
- GECTI — `unsafe_precision_non_decreasing`
- GECTI — `unsafe_recall_non_decreasing`
- GECTI — `weighted_accuracy_non_decreasing`
- GECTI — `worst_domain_fpr_non_increasing`
- GECTI — `worst_domain_recall_non_decreasing`

## Sinif recall

| Sinif | Duz | Aday | Destek |
|---|---:|---:|---:|
| LEVEL_ONE | 55.9% | 60.9% | 238 |
| LEVEL_TWO | 27.6% | 39.0% | 123 |
| LEVEL_THREE | 0.0% | 0.0% | 6 |
| NO_ABNORMALITY | 97.5% | 97.8% | 367 |

## Alan bazinda binary

| Alan | Recall duz | Recall aday | FPR duz | FPR aday |
|---|---:|---:|---:|---:|
| coal_conveyor | 59.0% | 80.7% | 8.4% | 8.4% |
| metallurgy | 50.0% | 75.0% | 0.0% | 0.0% |
| oil_gas_chemical | 68.7% | 77.1% | 0.0% | 0.0% |
| power | 51.1% | 61.7% | 0.0% | 0.0% |
| tunnel | 63.7% | 73.5% | 2.0% | 1.0% |

## Yurutme

- Observe/direct/flat/binary/severity hata: `0` / `11` / `0` / `0` / `0`
- Logprob hard-choice fallback: `0`
- Retry alan cagri: `0`; azami retry: `0`
