# v13j rota-kilitli kaynak-video hakemi — deney ön kaydı

Tarih: 2026-08-28

## Sabit akış

Yalnız v13f dar scout tam olarak `KISI_DESTEK_KAYBI` seçerse:

1. Mevcut 2 fps kare atomları aynı `kişi destek kaybı/düşme` ailesini doğrular.
2. Kare atomları desteklerse mevcut davranış korunur.
3. Kare atomları desteklemezse kaynak MP4 aynı değişmez aile spec'iyle
   `dogrula_video` üzerinden yeniden hakemlenir.
4. Kaynak-video atomlarının tamamı AND ile desteklenirse olay adayı oluşur;
   aksi halde olay yoktur.

Scout başka etiket seçerse kaynak-video çağrısı yapılmaz. Kaynak-video yolu yeni
aile tarayamaz.

## Örneklem ve sözleşme

- Kaynak: v13f sonucundaki 119 olay-sız geliştirme klibi.
- Pozitif: 3 kayıtlı kişi-destek-kaybı klibi (`87...102`, `uO...1`, `zJ...45`).
- Negatif: kalan 116 klip (23 anomali karşıtı + 93 normal).
- Öğrenilmiş çıkarım yalnız özel API; modeller `vlm`, `llm-large`, `llm-fast`.
- Yerel öğrenilmiş çıkarım ve model indirme kapalı.
- v13 holdout okunmaz.

## Kilitli kabul kapıları

- Kaynak-video yolunun ilave kurtarması: en az `1/3`.
- Nihai semantik kurtarma: kaynak hedefli bütün desteklenen pozitifler doğru aile.
- Nihai yeni yanlış alarm: tam olarak `0/116`.
- API/oturum/ayrıştırma hatası: `0`.

Geçiş yalnız opt-in entegrasyon iznidir. Tam-dev kapıları ayrıca uygulanacaktır.

