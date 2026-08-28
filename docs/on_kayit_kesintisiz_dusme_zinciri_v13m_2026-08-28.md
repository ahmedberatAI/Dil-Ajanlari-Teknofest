# v13m kesintisiz kişi-düşme zinciri — deney ön kaydı

Tarih: 2026-08-28

## Hipotez

v13l, üç hafızasız atomun aynı kişiye ve aynı kesintisiz olaya ait olduğunu
güvenceye alamadığı için üç anomali karşıtında yanlış destek üretmiştir. Mevcut
üç atom korunup dördüncü bir bütünsel kimlik ve süreklilik atomu eklenirse açık
`zJq...45` düşüşü korunurken yük/platform, önceden yerde bulunan kişi, kalabalık
müdahale ve rutin oturma/eğilme karşıtları elenebilir.

Bu yalnız geliştirme hipotezidir; önceki denemelerden sonra aynı dev setinde
tasarlandığı için bağımsız genelleme kanıtı sayılmaz.

## Sabit dört atom

1. `vlm` — olay boyunca izlenebilir gerçek kişi ve beden görünür.
2. `llm-large` — aynı kişi destekli/dik durumdan istemsiz, kontrolsüz aşağı geçer.
3. `llm-large` — aynı geçiş görünür fiziksel sonuçla tamamlanır: beden teması,
   asılı kalma veya temas sonrası toparlanma.
4. `llm-large` — **tek kesintisiz zincir**: aynı kişi başlangıçta destekli/dik,
   sonra açık destek kaybı yaşar ve sonuçta daha aşağıda zemine/sert yüzeye temas
   eder ya da kaybedilen destekten asılı kalır. Sahne kesimi, farklı kişi,
   başlangıçtan beri oturan/yerde/örtülü kişi, rutin eğilme-çömelme, platformda
   yük taşıma, yalnız nesne hareketi ve önceden başlamış kalabalık müdahale
   `A` değildir.

Dört atom da açıklamasız `A/B/C/D` kapalı seçimi kullanır. Dördü de `A` olmadan
destek yoktur. Kaynak MP4 tek oturumda taşınır; her soru `hatirla=False` çalışır.

## Örneklem ve sözleşme

- Kaynak: v13f sonucundaki 119 olay-sız geliştirme klibi.
- Pozitif: önceden kayıtlı 3 kişi-destek-kaybı klibi.
- Negatif: kalan 116; bunun 23'ü anomali karşıtı, 93'ü normaldir.
- Öğrenilmiş çıkarım yalnız `https://evren-llmapi.ssyz.org.tr/v1` özel API'si.
- Sabit roller: `vlm`, `llm-large`, `llm-fast`; model indirme veya yerel
  öğrenilmiş çıkarım yoktur.
- v13 holdout açılmayacak ve okunmayacaktır.

## Kilitli kabul kapıları

- Semantik kurtarma: en az `1/3`.
- Yeni yanlış destek: tam olarak `0/116`.
- API/oturum/ayrıştırma hatası: `0`.

Kapı geçilirse dahi yalnız opt-in entegrasyon ve tek tam-dev ölçümüne izin verir.
Geçilmezse prompt tekrarı yapılmadan aday reddedilir.
