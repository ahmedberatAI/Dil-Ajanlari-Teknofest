# Ön kayıt — v12k yük/çökme ile çarpışma aile ayrımı

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

v12j tam koşusu 40/50 recall'a ulaştı fakat 8/50 normal FP ile kendi sınırını bir
örnek aştı. Yeni FP `oeHrto1r-S4_clip0_trim_28.mp4` içinde rutin yağ varili arabası
itilirken serbest anlatının “yük devrildi” demesidir. `atomic_extended_families=0`
olduğu için yük iddiası ayrı aileye gitmemiş, geniş `çarpışma/devrilme` ailesince
yanlış desteklenmiştir. Diğer normal yük FP'si `1tuWxs8fUOk_trim_29.mp4` da aynı
ayrım problemidir.

Bu prob v12j'ye ait olay metninde açık yük/raf/platform/yapı devrilme-düşme-çökme
iddiası bulunan 15 tehlike + 2 normal klibi doğrudan `kontrolsüz yük/çökme`
atomik spekiyle ölçer. Çıktı bütçesi 40, roller `vlm` + `llm-large`, karar AND'dir.

Kabul:

- tehlikelerde en az 12/15 `SUPPORTED`,
- normallerde 0/2 `SUPPORTED`,
- API hatası 0.

Geçilirse makine ailesi açılmadan yalnız yük/çökme aile ayrımı özellik bayrağıyla
entegre edilir ve fallback açık tam 50+50 koşusu yeniden ön kaydedilir. Geçilmezse
bu yol denenmez. Holdout açılmaz.

