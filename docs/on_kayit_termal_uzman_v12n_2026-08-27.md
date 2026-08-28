# Ön kayıt — v12n termal aşırı ısınma uzmanı

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

v12m'nin v12j'ye göre kaybettiği üç klibin ikisi farklı tehlikelerin sahte yangın
etiketiyle sayılmasıydı. Üçüncü klip `1s2Tcqr3Rgg_trim_19.mp4`: makine yüzeylerinin
kızarıp tehlikeli ısınma göstermesi, `fire incident` etiketi. Genel yangın kapısı
gevşetilmez; ayrı bir termal fiziksel aile ölçülür.

Atomlar:

- `vlm`: geniş makine/metal yüzeyde boya/lamba/yansıma olmayan kızgın kırmızı-
  turuncu kor görünümü,
- `llm-large`: normal/koyu yüzeyden kızarma geçişi veya sürdürülen kor ışıması,
- deterministik AND, hata/belirsizlik fail-closed.

Örneklem:

- 1 gerçek termal tehlike (`1s2Tcqr3Rgg_trim_19.mp4`),
- v12m'de doğru negatif kalan 47 normal klip,
- toplam 48; holdout açılmaz.

Kabul: 1/1 TP, 0/47 FP, 0 API hatası. Geçilirse yalnız tüm diğer kanallar olay-sız
kaldığında çalışan özellik bayraklı termal uzman eklenir ve v12m tam 50+50 koşusu
yeniden ön kaydedilir. Geçilmezse aile üretime alınmaz.

