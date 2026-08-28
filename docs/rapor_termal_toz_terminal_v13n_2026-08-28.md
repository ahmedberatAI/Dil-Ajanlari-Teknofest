# v13n termal–toz terminal abstain — mikro-prob sonucu

Tarih: 2026-08-28

Sonuç: `benchmark/results/termal_toz_terminal_v13n_20260828_005733.json`.

| Ölçüt | Kapı | Sonuç | Durum |
|---|---:|---:|---|
| `ZQV...1` olay | 0 | 0 | geçti |
| Terminal abstain izi | zorunlu | var | geçti |
| Korunan anomali | 4/4 | 4/4 | geçti |
| API/ayrıştırma hatası | 0 | 0 | geçti |
| Ölçüm arızası | 0 | 0 | geçti |

Karar: **kabul**. Toz/buhar vetosu tek başına segmenti durdurmamaktadır;
yalnız termal atomlar da aynı sahnede destek verirse yorum çelişkisi terminal
abstain olur. Termal atom reddinde sonraki uzmanlar çalışmaya devam eder. Böylece
global veto nedeniyle recall kaybı yaratmadan ölçülen `ZQV...1` cascade FP'si
engellenmiştir.

Bu yalnız mikro-prob kabulüdür; üretim varsayılanını değiştirmez. Tam-dev ve
regresyon geçmeden v13 holdout açılmaz.
