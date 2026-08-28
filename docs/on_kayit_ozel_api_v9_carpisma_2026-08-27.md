# Ön kayıt — özel API v9 bayt-eş fiziksel kanıt sorusu

**Tarih:** 2026-08-27  
**Önceki kol:** v8 ön tanısında `cam_00` yine `YANINDAN_GECIS` verdi. Arşivlenmiş
başarılı prob sorusuyla karşılaştırmada tek fark son yönergeydi:
`Yalnız etiketi yaz.` yerine `Yalnız bu dört etiketten birini yaz.` kullanılmıştı.

## Tek değişiklik

Üretim `Slot.soru`, daha önce pozitif `cam_00` için `DOGRUDAN_ETKILESIM`, zor negatif
`run_12/cam_02` için `YANINDAN_GECIS` veren arşivlenmiş soru metniyle bayt düzeyinde aynı
hale getirilir. Prob doğrudan bu üretim sabitini okur. Model, endpoint, video speki,
semantik seçenekler, parser ve iki-kanıt karar kuralı değişmez.

## Ön tanı ve kabul sırası

1. Aynı pozitif-negatif çiftte doğrulama iki kez tekrarlanır; iki tekrarda da pozitif
   `DOGRUDAN_ETKILESIM`, negatif `YANINDAN_GECIS/ARAC_YOK` olmalıdır.
2. Geçerse v6 ile aynı 14 kliplik odak dilimi koşulur.

Odak kabulü: destekli recall `3/3`; kanıtsız/belirsiz aynı-senaryo alarmı `0/9`;
çapraz zor negatif alarmı `0/2`; API/slot hatası `0`; çelişki izi `INSUFFICIENT`.

Tüm öğrenilmiş çıkarım sabit özel API'dedir; model indirme/yerel model yoktur. Bu belge
sonuçtan sonra değiştirilmez.
