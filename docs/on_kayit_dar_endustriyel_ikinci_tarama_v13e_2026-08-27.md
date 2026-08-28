# v13e dar endüstriyel ikinci tarama — deney ön kaydı

Tarih: 2026-08-27

## Amaç

v13d tam geliştirme koşusu, önceden kilitlenen `%75` recall eşiğini `%74`
ile bir örnek farkla kaçırdı. Bu deney v13d sonucunu yeniden koşturmaz ve v13
holdout bölümünü açmaz. Yalnız v13 geliştirme bölümünde, önceki bütün kanallar
ve v13c geniş endüstriyel scout olay üretmediyse çalışan dar bir ikinci taramayı
ölçer.

## Değişmez model sözleşmesi

- Görsel/varlık algısı: özel API `vlm`
- Olay ve zaman ilişkisi: özel API `llm-large`
- Yapı ve özet: özel API `llm-fast`
- Yerel öğrenilmiş model: yasak
- Model indirme: yasak

İkinci scout `llm-large` rolünü kullanır. Seçilen aday, mevcut atomik kanıt
mimarisinde görsel atom için `vlm`, zamansal/ilişkisel atom için `llm-large`
ile bağımsız doğrulanır. Karar deterministik AND kapısıdır.

## Kilitli örneklem

Kaynak sonuç: `benchmark/results/eval_20260827_231802.json`.

- Pozitif: v13d'de olay-sız kalan ve mevcut saflaştırılmış üç aileden birine ait
  7 geliştirme klibi.
- Negatif: v13d'de olay-sız kalan diğer 112 geliştirme klibi. Buna normal doğru
  negatifler ve üç hedef aile dışındaki anomali karşıtları birlikte dahildir.
- Holdout klipleri bu deneyde okunmayacaktır.

İzin verilen scout etiketleri:

- `MAKINE_YAKALAMA`
- `KISI_DESTEK_KAYBI`
- `ENDUSTRIYEL_ENERJI_OLAYI`
- `OLAY_YOK`
- `GORUNMUYOR`

Scout tek başına olay üretemez. Yalnız ilk üç etiket kendi sabit atomik ailesine
eşlenip bütün atomlar `SUPPORTED` ise olay adayı kabul edilir.

## Önceden kilitlenen kabul kapıları

- Hedef kurtarma: en az `2/7`.
- Anlamsal doğruluk: desteklenen her pozitif, kayıtlı hedef ailesiyle aynı olmalı.
- Yeni yanlış alarm: tam olarak `0/112`.
- API/ayrıştırma hatası: `0`.

Bu kapıların tamamı geçilmeden kod ana akışa alınmayacak ve v13 tam geliştirme
koşusu çalıştırılmayacaktır. Geçerse özellik yine opt-in kalacak; entegrasyon
testleri ve yeni bir v13e tam-dev ön kaydı tamamlandıktan sonra tek tam geliştirme
koşusu yapılacaktır.

