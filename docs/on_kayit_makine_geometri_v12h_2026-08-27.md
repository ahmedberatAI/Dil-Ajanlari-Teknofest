# Ön kayıt — v12h makine sıkışma geometrisi

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

v12g düzeltilmiş koşusu sekiz tehlikeyi geri kazandı fakat aynı ailede bir gerçek
pozitif ve bir normal pozitife izin verdi:

- pozitif: `_a46_s5WViY_trim_0.mp4` — kişi kapanan iki makine yüzeyi arasında,
- negatif: `YE7VTtHbtQA_trim_0.mp4` — kişi kelepçe söküp boru takıyor.

Mevcut kişi-var ve sıkışma/çekilme ilişki atomlarına üçüncü, bağımsız `vlm`
geometri atomu eklenir. Yalnız kişi daralan iki büyük yüzey arasındaysa veya
uzuv/giysi hareketli mekanizmanın içindeyse destek verir. Rutin boru/kelepçe/vana/
el-aleti işi açık çürütmedir.

Kabul: 1/1 pozitif `SUPPORTED`, 0/1 negatif destek, 0 API hatası. Geçmezse bu
sıkılaştırma ve v12g üretime alınmaz. Geçerse v12g'nin 60 klibinin tamamı yeni
spek ile tekrar doğrulanır; holdout açılmaz.

