# Ön kayıt — v12f çok-ölçekli doğrudan yangın kanıtı

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

## Hipotez

v11'in kaçırdığı iki yangın klibinde alev tavandaki dar açıklıkta, tam kare içinde
çok küçük kalmaktadır. İnsan tepkisinden dolaylı yangın çıkarmak yerine aynı atomik
alev/duman soruları örtüşen uzamsal kırpımlarda çalıştırılır. Bu, yeni model veya
yerel öğrenilmiş çıkarım değildir; özel API'ye gönderilen kanıtın ölçeğini değiştirir.

## Kilitli yöntem

Yalnız v11 sonunda hiç olay üretmeyen kliplerde dört örtüşen görünüm kullanılır:

- üst %60,
- alt %60,
- sol %60,
- sağ %60.

Her görünüm 768 piksel uzun kenara büyütülür. `vlm` görünür alev/duman ve
`llm-large` zamansal alev/yayılan duman soruları mevcut v12 atomik spekiyle bağımsız
çalışır. En az bir görünümde iki rol de `SUPPORTED` verirse doğrudan yangın adayı
vardır. `llm-fast` ancak tam uçtan uca adayda yapı/özet rolünü sürdürür.

## Dondurulmuş geliştirme örneklemi

Karşılaştırma tabanı `benchmark/results/eval_20260827_194722.json`:

- v11'in kaçırdığı 2 adet `fire incident` klibi,
- v11'in doğru negatif bıraktığı 43 normal klip,
- toplam 45 klip.

Holdout açılmaz.

## Kabul ölçütleri

- iki yangın kaçırmasından en az 1'i geri kazanılmalı,
- 43 doğru negatif normalde yeni FP sayısı 0 olmalı,
- 45/45 örnek tamamlanmalı ve API hatası 0 olmalı.

Üç koşul birlikte sağlanmazsa kol üretime alınmaz. Sağlanırsa özellik bayrağıyla
entegre edilip tam 50+50 geliştirme koşusu ayrıca ön kaydedilir.

