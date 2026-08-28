# Ön kayıt — iSafetyBench özel API satır-bazlı v2

**Tarih:** 2026-08-27  
**Durum:** v2 çıktıları görülmeden yazıldı; geliştirme ölçümüdür.

Eski `isafety_mcq.json`, atıl `guided_choice` alanı nedeniyle geçersizdir. Daha
sonraki uzak sonuç yalnız agregat tuttuğundan klip/şık sırası/tahmin denetlenemez.
Bu koşu her satırda video SHA-256, 16 şık ve sırası, GT indeks/harfi, ham cevap,
hata, gecikme ve iki kolun tahminini saklar. Başlangıçta structured-output negatif
kontrolü geçmeden hiçbir klip skorlanmaz.

Eşleştirilmiş kollar:

- A: `llm-large` videodan doğrudan kapalı MCQ.
- B: `vlm` etiketsiz/nötr kronolojik betimleme; `llm-large` yalnız bu metin ve
  aynı şıklardan kapalı MCQ.

Her sütunda klip başına ilk tekil soru alınır, sabit 2026 tohumu kullanılır. Hızlı
geliştirme koşusu hazard 20 + normal 20 kliptir. Hata başarı sayılmaz; katı accuracy,
geçerli-cevap accuracy, coverage, Wilson %95 GA ve eşleştirilmiş exact McNemar
raporlanır. Öğrenilmiş çıkarım yalnız özel API'dedir; model aliasları değişmez;
yerel model/indirme kapalıdır. Küçük ve görülmüş geliştirme dilimi final kanıt değildir.
