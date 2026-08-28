# Ön kayıt — iSafetyBench v13 yeni geliştirme ve ikinci donmuş doğrulama bölmeleri

Tarih: 2026-08-27  
Durum: Bölmeler oluşturulmadan önce kilitlendi

Yerel lisanslı değerlendirme kopyasındaki video dosyaları kullanılır; eğitim veya
ince ayar yapılmaz. Aşağıdaki adlar aday havuzundan çıkarılır:

- mevcut bütün `data/eval*` klasörlerindeki video adları,
- `benchmark/results/**/*.json` içinde daha önce geçen bütün `.mp4` adları.

Sabit seed `2026082713` ile önce tehlike ve normal havuzları ayrı ayrı sıralanır,
sonra deterministik olarak karıştırılır. Her sınıftan ilk 100 v13 geliştirme,
sonraki 100 v13 donmuş holdout olur:

- `data/eval_genelleme_v13_dev`: 100 tehlike + 100 normal,
- `data/eval_genelleme_holdout_v13`: 100 tehlike + 100 normal.

Her dosyanın kaynak yolu, hedefi, SHA-256 değeri, seed ve dışlanan ad sayısı tek
manifestte kilitlenir. Hedef klasörlerden biri varsa betik üzerine yazmayı reddeder.

v13 geliştirme seti prompt/kapı geliştirmesinde kullanılabilir. v13 holdout video
içeriği, açıklaması ve model sonucu geliştirme adayının ön kayıtlı kapısı geçene
kadar açılmaz. Açıldıktan sonra ayar seçmek için kullanılmaz ve tek sefer raporlanır.
