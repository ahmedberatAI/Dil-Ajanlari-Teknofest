# Ön kayıt — v13c saflaştırılmış endüstriyel scout allowlist tekrarı

Tarih: 2026-08-27  
Durum: Yeni API sonucu görülmeden kilitlendi

v13a/v13b geliştirme analizi sonucunda yalnız üç scout dalı ayrıştırılabildi:

- `MAKINE_YAKALAMA` → üçüncü gerçek fiziksel bağ atomlu aktif sıkışma,
- `MAKINE_ARIZASI` → dar/yanlış parça iddiası yerine ani kontrolsüz endüstriyel
  enerji/ekipman olayı,
- `KISI_DESTEK_KAYBI` → kişi destek kaybı/düşme.

`DUSEN_AGIR_YUK`, `ALEV_DUMAN_GAZ` ve `ARAC_KONTROL_KAYBI` scout seçimleri bu
katmanda alarm üretemez. Aynı 22 fiziksel pozitif + 109 negatifte yeni bağımsız özel
API tekrarı yapılır. Geniş endüstriyel aileyle olgusal olarak uyumlu on geliştirme
örneğinin dal eşlemesi sonuçtan önce betikte kilitlidir.

Kabul: en az 8/22 geri kazanım, desteklenen bütün pozitiflerde kilitli semantik dal
uyumu, en fazla 1/109 yeni FP, 0 API hatası. Geçilirse özellik bayrağı arkasında tam
v13 geliştirme E2E adayına bağlanır; v13 holdout açılmaz.
