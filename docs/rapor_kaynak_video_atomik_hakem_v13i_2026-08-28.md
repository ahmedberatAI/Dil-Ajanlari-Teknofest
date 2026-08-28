# v13i kaynak-video atomik yeniden hakem — sonuç

Tarih: 2026-08-28

Sonuç: `benchmark/results/kaynak_video_atomik_v13i_20260828_000649.json`

| Ölçüt | Kapı | Sonuç | Durum |
|---|---:|---:|---|
| Semantik kurtarma | en az 2/8 | 3/8 | geçti |
| Yeni yanlış aile/alarm | 0/111 | 2/111 | **kaldı** |
| API/oturum hatası | 0 | 0 | geçti |

Karar: **doğrudan kullanım reddedildi**. Üç destek-kaybı pozitifini kurtardı;
ancak bir anomali karşıtında ve bir normal klipte aynı aileyi yanlış destekledi.

İki FP'nin hiçbirinde mevcut dar scout bu aileyi seçmemiştir. Bu nedenle sonraki
deney doğrudan tarama yapmayacak; yalnız aynı aileyi önceden seçen scout sonrası
2 fps atomu reddedilirse kaynak-video hakemini çalıştıracaktır.

