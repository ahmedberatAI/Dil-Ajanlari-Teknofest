# v13m kesintisiz kişi-düşme zinciri — deney raporu

Tarih: 2026-08-28

Sonuç dosyası:
`benchmark/results/kesintisiz_dusme_zinciri_v13m_20260828_002752.json`.

## Ön kayıt sonucu

| Ölçüt | Kapı | Sonuç | Durum |
|---|---:|---:|---|
| Semantik kurtarma | en az 1/3 | 1/3 | geçti |
| Yeni yanlış destek | 0/116 | 0/116 | geçti |
| API/oturum/ayrıştırma hatası | 0 | 0 | geçti |

Kurtarılan tek pozitif `zJqzjDX-XFU_trim_45.mp4`'tür. Bu klipte koşma,
kontrolsüz destek kaybı, bedenin zemine teması ve toparlanma aynı kesintisiz
planda görünür; dört atom da `A` vermiştir.

v13l'nin üç yanlış desteği dördüncü atomda açık `B` ile elenmiştir:

- `1b1NOLpwCz8_trim_16.mp4`: platform/yük sahnesi.
- `9XXineiOxSo_trim_5.mp4`: kalabalık müdahale/makine sahnesi.
- `J9WlxhcRAPo_trim_4.mp4`: oturma/eğilme sahnesi.

Normal sınıfta da destek yoktur (`0/93`). Diğer anomali aileleri kişi düşmesi
sayılmadığından katı semantik karşıt olarak korunmuş ve hiçbirinde dört atom
birlikte geçmemiştir (`0/23`).

## Karar

Ön kayıt geçmiştir; yalnız opt-in `continuous_fall_fallback` olarak entegrasyon
ve tek tam-dev koşusuna izin verilmiştir. Bu sonuç aynı geliştirme setinde önceki
yanlışların incelenmesinden sonra elde edildiği için bağımsız genelleme kanıtı
değildir. Üretim varsayılanı kapalı kalacak; tam-dev ve regresyonlar geçmeden v13
holdout açılmayacaktır.
