# Ön kayıt — iSafetyBench v12 dokunulmamış uçtan uca holdout

Tarih: 2026-08-27  
Durum: v12 davranış kodu değiştirilmeden önce kilitlendi

## Veri bölmesi

- Kaynak: yerel `data/isafety_bench` değerlendirme kopyası.
- Seed: `20260827`.
- 100 tehlike + 100 normal = 200 klip.
- Daha önce çalışma alanındaki başka değerlendirme klasörlerinde kullanılan
  iSafetyBench video adları ve eski iSafety sonuç JSON'larında geçen video
  adları aday havuzundan çıkarılacaktır.
- Betik seçimi tek sefer yapar, içerik SHA-256 değerlerini manifestte kilitler
  ve var olan hedef klasörün üzerine yazmayı reddeder.
- Lisans yalnız değerlendirmeye izin verir; eğitim/ince ayar yapılmayacaktır.

## Geliştirme/holdout sınırı

`data/eval_genelleme` içindeki mevcut 100 klip geliştirme/regresyon setidir.
Prompt, taksonomi ve kapılar yalnız bu görülen sette geliştirilebilir. Yeni
`data/eval_genelleme_holdout_v12` sonuçları ilk açılıştan sonra ayar seçmek için
kullanılmayacak; sonuç ne olursa olsun nihai rapora yazılacaktır.

## Sabit sistem

Tek uçtan uca üretim akışı ölçülür:

`vlm -> llm-large ilişki/zaman doğrulaması -> deterministik kanıt/İSG kuralları
-> llm-fast yapı/özet -> nihai olay listesi`

Özel API ve sabit alias sözleşmesi zorunludur. Yerel öğrenilmiş model ve model
indirme yasaktır.

## Ön kabul kapıları

Ana karar klip düzeyinde nihai olay var/yok üzerinden verilir:

- Kapsam en az 190/200 ve API/biçim hata oranı en fazla %5.
- Tehlike recall en az %70.
- Normal operasyonel FP en fazla %25.
- MCC en az +0,45.
- Sistem kliplerin en az %95'inde aynı kararı verirse ölçüm geçersiz.

Ek olarak olay-aile doğruluğu, normal FP aile dağılımı, kritik fonksiyon yanlış
tetiklemesi ve gecikme raporlanır. Bu ikincil ölçüler ana kapı sonuçlarından
sonra değiştirilmez.

