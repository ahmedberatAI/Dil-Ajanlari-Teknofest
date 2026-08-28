# v13e dar endüstriyel ikinci tarama — sonuç

Tarih: 2026-08-27

Sonuç dosyası:
`benchmark/results/dar_endustriyel_ikinci_tarama_v13e_20260827_232309.json`

## Kilitli kapılar ve sonuç

| Ölçüt | Kapı | Sonuç | Durum |
|---|---:|---:|---|
| Hedef kurtarma | en az 2/7 | 2/7 | geçti |
| Anlamsal doğruluk | tüm desteklenenler doğru | 2/2 | geçti |
| Yeni yanlış alarm | 0/112 | 1/112 | **kaldı** |
| API/ayrıştırma hatası | 0 | 0 | geçti |

Karar: **reddedildi**. v13e bu haliyle ana akışa alınmayacak.

İki doğru kurtarma `MAKINE_YAKALAMA` ve `KISI_DESTEK_KAYBI` dallarından,
tek yanlış alarm ise `ENDUSTRIYEL_ENERJI_OLAYI` dalından geldi. Bu gözlem
bağımsız bir doğrulama sonucu değil, bir sonraki geliştirme hipotezinin
kaynağıdır.

