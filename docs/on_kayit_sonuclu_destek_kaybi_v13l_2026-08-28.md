# v13l sonuç atomlu kişi destek-kaybı — deney ön kaydı

Tarih: 2026-08-28

## Hipotez

Kaynak-video iki atomu üç kayıtlı destek-kaybı pozitifini kurtarmış, fakat rutin
yürüme/taşıma içeren iki karşıtta yanlış destek vermiştir. Görsel denetim bu iki
yanlış desteğin tamamlanmış fiziksel sonuç taşımadığını göstermiştir. v13l,
mevcut iki koşulu üç ayrı ve zorunlu kapıya böler.

## Sabit üç atom

1. `vlm` — gerçek kişi ve bedeni izlenebilir biçimde görünür; nesne/gölge kişi
   sayılmaz.
2. `llm-large` — aynı kişi destekli/dik konumdan istemsiz ve kontrolsüz aşağı
   geçer; rutin eğilme, çömelme, yük kaldırma, planlı iniş ve sahne kesimi reddedilir.
3. `llm-large` — geçişin fiziksel sonucu vardır: beden zemine/sert yüzeye temas
   eder, kişi asılı kalır veya düşme sonrası toparlanır; yalnız yürüme/koşma,
   nesne düşürme ve farklı kişiye/sahneye geçiş reddedilir.

Üç atom da `A` olmadan olay yoktur. Kaynak MP4 tek oturumda taşınır; sorular
`hatirla=False` ile birbirinin cevabını görmez.

## Örneklem ve sözleşme

- Kaynak: v13f sonucundaki 119 olay-sız geliştirme klibi.
- Pozitif: 3 kayıtlı kişi-destek-kaybı klibi.
- Negatif: kalan 116 (23 anomali karşıtı + 93 normal).
- Öğrenilmiş çıkarım yalnız özel API; sabit `vlm`, `llm-large`, `llm-fast`.
- Yerel öğrenilmiş çıkarım/model indirme yok; v13 holdout okunmaz.

## Kilitli kabul kapıları

- Semantik kurtarma: en az `1/3`.
- Yeni yanlış alarm: tam olarak `0/116`.
- API/oturum/ayrıştırma hatası: `0`.

Bu doğrudan uzman kapısını geçerse bile yalnız opt-in entegrasyon ve tam-dev
ölçümüne izin verir.

