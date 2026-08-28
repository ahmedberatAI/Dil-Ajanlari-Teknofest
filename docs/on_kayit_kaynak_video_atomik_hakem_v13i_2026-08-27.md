# v13i kaynak-video atomik yeniden hakem — deney ön kaydı

Tarih: 2026-08-27

## Hipotez

Mevcut fallback atomları 2 fps örnek kareleri yeniden MP4'e kodlayarak özel
API'ye taşır. Depodaki `dogrula_video` yolu, küçük temas ve kısa zamansal geçişte
bu yeniden örneklemenin kanıt kaybettirebileceği gerekçesiyle kaynak MP4
baytlarını aynı `vlm` / `llm-large` atomik AND mimarisine doğrudan verir.

v13i yeni aile veya yeni prompt üretmez. Yalnız kanıt taşıma biçimini değiştirir.

## Sabit örneklem

Kaynak: `benchmark/results/eval_20260827_234737.json` içindeki 119 olay-sız
geliştirme klibi.

- Pozitif: kilitli v13a fiziksel haritasında ağır-yük veya kişi-destek-kaybı
  ailesine ait 8 klip.
  - 5 ağır yük: `1b1...4`, `1b1...16`, `1s2...111`, `fs...5`, `fs...6`
  - 3 destek kaybı: `87...102`, `uO...1`, `zJ...45`
- Negatif: kalan 111 olay-sız klip. Bunların her birinde iki aile de denenir;
  herhangi bir yanlış aile desteği FP sayılır. Bu, üretimde yalnız seçilmiş aynı
  aileye uygulanacak yeniden hakemden daha muhafazakâr bir FP sınamasıdır.
- v13 holdout okunmayacaktır.

## Model ve karar sözleşmesi

- Öğrenilmiş çıkarım yalnız özel API'de.
- `vlm`: görsel/varlık atomu; `llm-large`: zamansal/ilişkisel atom.
- `llm-fast` nihai yapısal/özet rolü olarak sabit kalır; bu uzman probunda çağrı
  gerektirmez.
- Yerel öğrenilmiş model ve model indirme kapalı.
- Mevcut aile spec'leri ve deterministik AND kararı değişmez.
- Hata veya boş oturum `INSUFFICIENT`tir.

## Kilitli kabul kapıları

- Semantik doğru kurtarma: en az `2/8`.
- Yeni yanlış aile/alarm: tam olarak `0/111`.
- API/oturum/ayrıştırma hatası: `0`.

Geçerse kaynak-video hakemi yalnız 2 fps atomları aynı aileyi
`REFUTED/INSUFFICIENT` verdiğinde, önceki scout seçimini genişletmeden çalışabilir.
Bu sonuç tek başına tam-dev veya holdout kabulü değildir.

