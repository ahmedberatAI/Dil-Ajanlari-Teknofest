# v13g çift-scout çelişki kurtarma — deney ön kaydı

Tarih: 2026-08-27

## Hipotez ve geliştirme verisi notu

v13f tam-dev koşusunda recall `%74` kaldı. İz incelemesinde bir geliştirme FN'si
(`zJqzjDX-XFU_trim_45.mp4`) için iki farklı kapalı scout istemi de
`KISI_DESTEK_KAYBI` seçti; iki zamansal atom da destek kaybı/düşme/asilma
geçişini doğruladı. Görsel atom ise `KISI_YOK` veya `GORUNMUYOR` değil,
`RUTIN_ZEMIN_HAREKETI` diyerek veto etti. Aynı çift-scout deseni v13f'deki
sessiz normal örneklerde görülmedi.

Bu gözlem geliştirme verisinden türetildi; bağımsız doğrulama iddiası yoktur.
v13g yalnız bu açık çelişki biçimini ölçer ve v13 holdout'u açmaz.

## Sabit karar kuralı

Olay-sız klipte:

1. v13c geniş scout ve v13f dar scout birbirinden farklı sabit istemlerle
   çalışır.
2. İkisi de tam olarak `KISI_DESTEK_KAYBI` seçmelidir.
3. Aynı `kişi destek kaybı/düşme` ailesi iki kez mevcut atomik mimariyle
   doğrulanır.
4. Her iki tekrarda görsel atom tam olarak `RUTIN_ZEMIN_HAREKETI`, zamansal atom
   tam olarak `DESTEK_KAYBI_DUSME_ASILMA` olmalıdır.
5. Hata, boşluk, `KISI_YOK`, `GORUNMUYOR` veya scout uyuşmazlığında olay yoktur.

Bu kural hiçbir diğer aileyi ve hiçbir geniş enerji dalını kurtaramaz.

## Sözleşme ve örneklem

- Özel API: `vlm`, `llm-large`, `llm-fast`; modeller değişmez.
- Yerel öğrenilmiş çıkarım ve model indirme kapalı.
- Kaynak: `benchmark/results/eval_20260827_234737.json` içindeki 119 olay-sız klip.
- 7 kayıtlı hedef pozitif, 112 karşıt negatif; karşıtların 19'u anomali sınıfındadır.

## Kilitli kabul kapıları

- Çelişki kurtarma: en az `1/7`.
- Kurtarılan her pozitifin kayıtlı hedefi `KISI_DESTEK_KAYBI` olmalı.
- Yeni yanlış alarm: tam olarak `0/112`.
- API/ayrıştırma hatası: `0`.

Geçiş yalnız birleşik fallback entegrasyonuna izin verir. Tam-dev, regresyon ve
holdout kapıları ayrıca uygulanacaktır; başarısız aday şans için tekrarlanmaz.

