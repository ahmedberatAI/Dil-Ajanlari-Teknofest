# v13h ani patlama/parlama uzmanı — deney ön kaydı

Tarih: 2026-08-27

## Gerekçe

v13f geliştirme FN'lerinin yalnız geliştirme verisinde yapılan 2 fps storyboard
denetiminde `1gx7OURLLBs_trim_6.mp4` ve `1gx7OURLLBs_trim_8.mp4` kliplerinde
ani, lokal ve genişleyen yoğun parlama/bulut geçişi açıkça görülmüştür. Mevcut
yangın atomu bu klipleri `BUHAR_TOZ_PARLAMA` diye veto ettiği için gerçek ani
enerji/patlama olayı ayrı bir fiziksel aile olarak ölçülecektir.

Bu iki klip geliştirme etiketidir; holdout açılmamıştır. Aile “yangın” iddiası
üretmez ve yalnız ışık sonrası insan hareketini kanıt saymaz.

## Sabit üç atom

1. `vlm`: lokal patlama çekirdeği ile yeni oluşan yoğun parlak bulut/parçacık
   birlikte görünür; far, el feneri, sabit lamba, yansıma ve pozlama reddedilir.
2. `llm-large`: sıradan durumdan ani başlangıç + hızlı genişleme/şiddetlenme +
   sönme/dağılma geçişi vardır; hareketli ışık huzmesi reddedilir.
3. `llm-large`: tepe sonrası aynı bölgede duman/bulut/parçacık izi kalır veya
   yakındaki kişi doğrudan geri çekilir/irkilir; önceden başlayan rutin hareket
   reddedilir.

Yalnız üç atomun da kapalı seçimde `A` olması alarm adayıdır. Hata ve belirsizlik
fail-closed'dur.

## Sözleşme ve örneklem

- Öğrenilmiş çıkarım yalnız özel API'de.
- Sabit modeller: `vlm`, `llm-large`, `llm-fast`; indirme ve yerel öğrenilmiş
  çıkarım yok.
- Kaynak: v13f sonucundaki 119 olay-sız klip.
- Pozitif: 2; negatif: 117 (24 anomali karşıtı + 93 normal).

## Kilitli kabul kapıları

- Kurtarma: `2/2`.
- Yeni yanlış alarm: `0/117`.
- API/ayrıştırma hatası: `0`.
- Desteklenen her örnekte üç atom da tam olarak `A`.

Geçiş yalnız opt-in uzman entegrasyonuna izin verir; tam-dev ve holdout kabulü
değildir.

