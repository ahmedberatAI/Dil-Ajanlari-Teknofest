# Ön kayıt — NVIDIA SDG-Warehouse dış veri benchmarkı

Tarih: 2026-08-27  
Model kodu: `4e9c3a3`  
Veri revizyonu: `d5b88d3abcf659f304a107f4336b71b4e2159133`

## Veri seçimi

Kaynak: `nvidia/PhysicalAI-WorldModel-Synthetic-Warehouse-Operations-Scenes`
(Hugging Face, OpenMDW-1.1).

Bu veri proje geliştirmesinde daha önce kullanılmadı. Dört senaryo aynı NVIDIA
Isaac Sim depo ortamı/layout ailesinde üretilir. Ortam, raf ve depo semantiği
ortaktır; ışık, varlık, kamera pozu ve olay zamanı seed ile çeşitlenir. Veri
sentetiktir; gerçek tesis başarısı iddiası kurulmayacaktır.

Model sonucu görülmeden sabitlenen seçim:

- Her senaryonun ilk RGB shard'ı.
- Tar sırasındaki ilk 5 bağımsız simülasyon run'ı.
- Seçilen run'lardaki bütün RGB kamera görüşleri.
- Birincil istatistik birimi `run_id`; çoklu kameralar bağımsız örnek gibi
  sayılmayacak. Klip/görüş metriği ikincil olarak ayrıca verilecek.
- Dosya SHA-256, run, seed ve kamera manifestte tutulacak.

## Bu depo için sabitlenen İSG kuralları

1. **Yangın:** görünür alev ve/veya dumanla depo yangını `Kritik` olaydır;
   çalışanların çıkışa yönelmesi tahliyedir.
2. **Forklift–raf çarpışması:** forkliftin rafa temas edip rafı/devrilen
   malzemeyi harekete geçirmesi `Kritik` kazadır.
3. **Forklift–insan ramak kala:** forklift ile çalışanın aynı yol uzamında
   tehlikeli yakınlaşması veya doğrudan temas `Yüksek/Kritik` olaydır.
4. **Rutin kutu alma:** çalışanın kutuyu alıp taşıması tek başına İSG olayı
   değildir; bağımsız yangın, çarpışma, düşme, yaralı, şiddet, yetkisiz erişim
   veya KKD eksikliği uydurulmamalıdır.

Bu benchmarkta eski üretim tesisine ait pano koyuluğu, yeşil yelek-yetki,
üç-kasa ve yaya çizgisi eşikleri **kapalıdır**; yeni depoda bunların sözleşmesi
yoktur.

## Puanlama — sonuçtan önce kilitli

Görüş-düzeyi doğru eşleşme:

- `fire`: Event/summary metninde yangın, alev, ateş, tutuş veya duman.
- `forklift_collision`: forklift/araç ile çarpışma, çarpma, raf devrilmesi.
- `nearmiss`: forklift/araç ile kişi arasında ramak kala, tehlikeli yakınlık,
  çarpma/temas veya kaçınma.
- `box_pickup`: yüksek/kritik olay yok ve operasyon fonksiyonu tetiklenmiyor.

Anahtar sözcüğün yalnızca olumsuz bir ifadede geçmesi (ör. “yangın tespit
edilmedi”, “çarpışma yok”) doğru eşleşme sayılmaz. Eşleştirici bunu cümle/parça
düzeyinde eler. Bu olumsuzlama kuralı da ilk model çıktısı görülmeden kilitlendi.

Run-düzeyi karar:

- Güvensiz run `başarılı`: kamera görüşlerinin en az yarısı beklenen aileyi
  doğru adlandırır.
- Normal run `yüksek FP`: kamera görüşlerinden en az biri yüksek/kritik yanlış
  olay veya yüksek/kritik genel risk üretir. Ayrıca daha yumuşak çoğunluk-FP
  metriği ayrı raporlanır.
- Bir kamera görünmüyorsa `yanlış` sayılır; örnek sonuçtan sonra elenmez.

## Önceden belirlenen kabul kuralları

Pilot, aşağıdakilerin hepsini sağlarsa `KABUL`:

- Her üç güvensiz senaryoda run-recall en az `4/5`.
- Rutin kutu run'larında katı yüksek-FP en fazla `1/5`.
- Rutin kutu görüşlerinde somut kritik iddia ailesi oranı en fazla `%10`.
- Yanlış operasyon tetiklenen normal run en fazla `1/5`.

Wilson `%95` güven aralıkları hem run hem görüş düzeyinde verilecek. `n=5`
küçük olduğu için bu bir pilot benchmarktır; başarılı olsa bile daha büyük
run örneklemi gerektirir.

## Değiştirilemezlik

İndirme seçimi, kurallar, eşikler ve puanlama model çıktısı görülmeden bu
dosyada sabitlendi. İlk sonuçtan sonra prompt/regex/eşik değiştirerek aynı
koşu `nihai` diye yeniden adlandırılmayacaktır; yapılırsa yeni bir ön kayıt ve
ayrı sonuç dosyası gerekir.
