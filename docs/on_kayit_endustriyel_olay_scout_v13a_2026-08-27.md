# Ön kayıt — v13a dar endüstriyel olay scout + atomik kapı

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

Yalnız v13 geliştirme tabanındaki 35 FN ve 96 doğru normal kullanılır. Doğru
iSafety açıklamalarına göre 22 FN doğrudan ölçülebilir altı fizik ailesine ayrıldı:

- aktif makine yakalama/sıkışma,
- üstten düşen ağır yük/platform/pres,
- kişi destek kaybı/düşme/asılma,
- yangın, yayılan duman veya basınçlı gaz salımı,
- araç/iş makinesi kontrol kaybı,
- ani makine arızası, kırılma veya parça fırlaması.

Niyet/süpheli hareket, polis araması/tutuklama, güvenli rutin çalışma gibi kalan 13
FN özellikle karşıt negatif yapılır. Bunlara ek olarak tabandaki 96 doğru normal
vardır: toplam 22 pozitif + 109 negatif.

`llm-large` tek kapalı aile scout'u çalıştırır. Seçilen aile `vlm` varlık/geometri
atomu ve `llm-large` ilişki/zaman atomunun bağımsız kapalı çağrılarıyla doğrulanır;
deterministik AND dışında alarm yoktur. Sabit model sözleşmesi değişmez, yerel model
ve indirme yoktur.

Kabul: en az 8/22 geri kazanım, en az 8 doğru hedef-aile desteği, en fazla 1/109
yeni yanlış alarm ve 0 API hatası. Geçilirse yalnız olay-sız segmentte özellik
bayrağı arkasında E2E adaya bağlanır. v13 holdout açılmaz.
