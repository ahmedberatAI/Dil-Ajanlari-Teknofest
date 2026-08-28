# v13f dar kişi/makine ikinci tarama — deney ön kaydı

Tarih: 2026-08-27

## Hipotez ve dürüstlük notu

v13e, iki doğru kurtarmaya karşılık yalnız geniş enerji/ekipman dalında bir
yanlış alarm üreterek kilitli kapıyı geçemedi. v13f yeni ve bağımsız veri iddiası
değildir; aynı geliştirme kümesinde yapılan açık bir güvenlik ablasyonudur.
Scout seçenekleri değişmez, fakat ikinci taramadan yalnız aşağıdaki iki dar dal
alarm üretmeye yetkilidir:

- `MAKINE_YAKALAMA` -> `aktif makine yakalama/sıkışma`
- `KISI_DESTEK_KAYBI` -> `kişi destek kaybı/düşme`

`ENDUSTRIYEL_ENERJI_OLAYI` seçimi dahil diğer bütün seçimler olay üretmez.
İki izinli dal da mevcut bağımsız atomik AND kapısından geçmek zorundadır.

## Sabit sözleşme ve örneklem

- Özel API modelleri: `vlm`, `llm-large`, `llm-fast`; model değişikliği yok.
- Yerel öğrenilmiş model ve model indirme kapalı.
- Kaynak sonuç: `benchmark/results/eval_20260827_231802.json`.
- 7 hedef pozitif, 112 sessiz karşıt negatif; v13 holdout açılmayacak.

## Kilitli kabul kapıları

- Hedef kurtarma: en az `2/7`.
- Desteklenen her pozitifin etiketi kayıtlı hedefle aynı.
- Yeni yanlış alarm: tam olarak `0/112`.
- API/ayrıştırma hatası: `0`.

Geçerse bu yalnız uzman-seviye entegrasyon iznidir. Nihai kabul için ayrıca
önceden kaydedilecek v13f tam-dev kapıları, tüm regresyonlar ve en son tek seferlik
kilitli v13 holdout koşusu gerekecektir.

