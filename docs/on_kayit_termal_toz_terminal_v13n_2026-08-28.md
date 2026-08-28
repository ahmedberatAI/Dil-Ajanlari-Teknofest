# v13n termal–toz çapraz-aile terminal abstain — mikro-prob ön kaydı

Tarih: 2026-08-28

## Hipotez

Yapılandırılmış yangın atomu `BUHAR_TOZ_PARLAMA` diyerek bir olayı açıkça veto
ettiğinde, aynı sahneyi termal destek üzerinden başka bir kritik aileye çevirmek
fiziksel yorum çelişkisidir. Termal atomlar yine destek verirse olay üretmek veya
cascade'e devam etmek yerine segment terminal abstain olmalıdır. Termal atomlar
reddedilirse sonraki fiziksel/endüstriyel uzmanlar çalışmaya devam etmelidir.

## Sabit örneklem

- Çelişki negatifi: `Normal/Normal/ZQVQZdOgDlQ_trim_1.mp4`.
- Korunacak anomali kontrolleri:
  - `Anomali/Hazard/1s2Tcqr3Rgg_trim_84.mp4`
  - `Anomali/Hazard/6fhnKhZQE4o_trim_3.mp4`
  - `Anomali/Hazard/7QFdUqCdML8_trim_1.mp4`
  - `Anomali/Hazard/qJLf_5RJFG8_trim_3.mp4`

Bu dört anomali önceki tam-dev koşusunda termal atom reddinden sonra sonraki
kanallarca kurtarılmıştır; global toz-veto terminali bunları yanlışlıkla silerdi.

## Sabit koşul

- Özel API ve sabit `vlm` / `llm-large` / `llm-fast` rolleri.
- `closed_family=1`, `structured_fire_dust_veto=1`, `thermal=1`,
  `physical=1`, `industrial=1`, `narrow=1`, `continuous_fall=1`.
- Yerel öğrenilmiş çıkarım ve model indirme kapalı.
- v13 holdout açılmaz.

## Kabul kapıları

- `ZQV...1`: `0` olay ve terminal-abstain izi.
- Dört anomali kontrolünün her biri: en az `1` olay.
- Tamamlanan örnek: `5/5`; API/ayrıştırma hatası: `0`.

Kapı geçilmezse tam-dev koşusu yapılmaz. Aynı mikro-prob şans için tekrarlanmaz.
