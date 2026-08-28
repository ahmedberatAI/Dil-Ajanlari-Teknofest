# Ön kayıt — özel API v8 ortak çarpışma doğrulama sabiti

**Tarih:** 2026-08-27  
**Önceki kol:** v7 ön tanısında üretim doğrulayıcısı destekli `cam_00` için
`YANINDAN_GECIS` üretti; v7 kabul edilmedi.

## Tek değişiklik

v7 incelemesinde benchmark probunun başarılı fiziksel soru metni ile üretim slotunun metni
arasında drift bulundu. v8, daha önce pozitif/negatif çiftte ölçülen metni üretim
`Slot.soru` sabiti yapar; prob da ayrı metin kopyası tutmak yerine doğrudan bu sabiti okur.
Kapalı semantik etiketler ve deterministik parser v7 ile aynıdır.

Model/alias, özel API endpoint'i, video baytları ve iki-kanıt karar kuralı değişmez.

## Kabul

v6 ile aynı 14 kliplik dondurulmuş dilim:

- destekli görünürlük recall `3/3`;
- kanıtsız/belirsiz aynı-senaryo çarpışma alarmı `0/9`;
- çapraz zor negatif çarpışma alarmı `0/2`;
- API/slot hatası `0`;
- çelişki karar izinde `INSUFFICIENT`.

Öğrenilmiş çıkarım yalnız sabit özel API'de; model indirme/yerel model yoktur. Sonuçtan
sonra bu belge değiştirilmeyecektir.
