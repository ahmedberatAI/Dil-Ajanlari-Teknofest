# v13m düşme kanıt v2 modülü — ön kayıt

Tarih: 2026-08-28

## Amaç ve kapsam kilidi

`dilajan/dusme_kanit_v2.py`, kişi düşmesi/destek kaybını dört zorunlu atomla
ölçen izole bir aday modüldür. Bu ön kayıt sırasında `agent/graph.py` veya
`config.py` modülü içe aktarmayacak; özellik anahtarı eklenmeyecektir. Bu nedenle
mevcut üretim ve değerlendirme davranışına etkisi tanım gereği sıfırdır.

Modül model yüklemez veya indirmez; yerel öğrenilmiş çıkarım çalıştırmaz. Sabit
özel API sözleşmesi şöyledir:

- `algi=vlm`
- `olay=llm-large`
- `yapi=llm-fast`
- `ozet=llm-fast`

Kapı yalnız `algi` ve `olay` rollerini çağırır. API koşusu bu uygulama adımının
dışındadır.

## Kilitli karar

Aynı kaynak MP4, cevap belleği kapalı dört soruda ölçülür:

1. `person / algi`: olay boyunca izlenebilir gerçek kişi ve beden/destek ilişkisi.
2. `transition / olay`: destekli/dik durumdan istemsiz kontrolsüz aşağı geçiş.
3. `outcome / olay`: aynı kişide beden teması, asılı kalma veya temas sonrası
   toparlanma gibi görünür fiziksel sonuç.
4. `continuous_chain / olay`: önceki üç olgunun aynı kişiye ve sahne kesintisi
   olmayan tek görsel zincire ait olması.

Her atom `A/B/C/D` kapalı uzayındadır. Yalnız `A+A+A+A` `SUPPORTED` üretir.
`B/C` açık karşı kanıt, `D`, eksik veya izin dışı cevap yetersiz kanıttır. API,
oturum, rol veya ayrıştırma hatası daima fail-closed `INSUFFICIENT` döndürür.
Çoğunluk, OR, serbest metin ve aynı koşuda şans tekrarı yoktur.

## Geliştirme örneklemi

Yalnız `eval_20260827_234737.json` içindeki olay-sız v13 geliştirme satırları
kullanılacaktır:

- Pozitif: `87O1pBSGtR0_trim_102`, `uOAJL-g4Y_w_trim_1`,
  `zJqzjDX-XFU_trim_45`.
- Negatif: kalan 116 satır; 23 anomali karşıtı ve 93 normal.
- Sert karşıtlar: `1b1...trim_4/16`, `J9...trim_4`, `9XX...trim_5`,
  `2JY...trim_5/8/9`, `oyRn...trim_43/50/63/65`.

`data/eval_genelleme_holdout_v13` bu geliştirme ve modül testi kapsamında
açılmayacak, listelenmeyecek veya okunmayacaktır.

## Uzman-seviye kabul kapıları

API probu ileride ayrı ve tek kilitli koşu olarak yapıldığında:

- Recall kapısı: `zJq...trim_45` zorunlu olmak üzere en az `1/3` semantik doğru
  kurtarma.
- Precision kapısı: tam `0/116` yeni yanlış destek; on bir sert karşıtın tamamı
  reddedilmiş olmalı.
- Güvenilirlik: API/oturum/ayrıştırma hatası `0`.

Bu koşullar yalnız opt-in tam-dev entegrasyon adaylığı verir.

## Gelecekteki entegrasyon için ayrı non-regression koşulları

Entegrasyon ayrıca önceden kaydedilmiş tek tam-dev koşusunda iki bağımsız kapıyı
birlikte geçmelidir:

1. **Recall non-regression:** v13 geliştirme anomali TP sayısı `74/100` altına
   düşmez; daha önce TP olan hiçbir anomali FN'ye dönmez ve yeni kapı en az bir
   kayıtlı destek-kaybı FN'sini semantik doğru kurtarır.
2. **Precision non-regression:** operasyonel normal FP `7/100` üzerine çıkmaz;
   yeni modül daha önce doğru negatif olan hiçbir normalde düşme olayı üretmez.

Her iki kapı, hata `0` ve sabit model sözleşmesi birlikte sağlanmadan özellik
varsayılan açılamaz. Aynı geliştirme verisine göre prompt ayarı veya başarısız
adayı şans için yeniden çalıştırma yapılmaz.
