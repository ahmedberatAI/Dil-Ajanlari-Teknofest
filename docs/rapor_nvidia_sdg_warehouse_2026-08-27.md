# NVIDIA SDG-Warehouse pilot benchmark raporu

Tarih: 2026-08-27  
Karar: **RED**

## Kapsam ve değiştirilemezlik

Kaynak, model çıktısı görülmeden seçildi ve kurallar
`docs/on_kayit_nvidia_sdg_warehouse_2026-08-27.md` içinde sabitlendi.

- Kaynak: NVIDIA `PhysicalAI-WorldModel-Synthetic-Warehouse-Operations-Scenes`
- Sabit kaynak revizyonu: `d5b88d3abcf659f304a107f4336b71b4e2159133`
- Lisans: OpenMDW-1.1
- Seçim: dört senaryonun ilk shard'ındaki ilk 5 bağımsız run ve bu
  run'lardaki bütün RGB kameralar
- Ölçek: 20 bağımsız run, 155 kamera görünümü
- Senaryolar: yangın, forklift–raf çarpışması, forklift–insan ramak kala,
  rutin kutu alma (normal kontrol)
- Eski tesisin yelek-yetki, pano, üç-kasa ve yaya yolu kuralları kapalı
- Model: `llm-large`, sıcaklık `0.0`, örnekleme `2 FPS`, segment başına en
  fazla 12 kare, uzak API

İndirme manifesti run, seed, kamera, byte boyutu ve SHA-256 taşır. Koşumdan
önce 155/155 dosyanın varlığı ve byte boyutu doğrulandı; mukerrer içerik
elenmedi.

## Donmuş protokol sonucu

Birincil birim `run_id`'dir. Güvensiz bir run, kamera görünümlerinin en az
yarısı beklenen olay ailesini doğru adlandırırsa başarılı sayıldı.

| Senaryo | Doğru görünüm | Başarılı run | Ön kayıt eşiği | Sonuç |
|---|---:|---:|---:|---:|
| Depo yangını | 0/25, %0 [%0–%13] | 0/5, %0 [%0–%43] | en az 4/5 | Kaldı |
| Forklift–raf çarpışması | 1/30, %3 [%1–%17] | 0/5, %0 [%0–%43] | en az 4/5 | Kaldı |
| Forklift–insan ramak kala | 3/50, %6 [%2–%16] | 0/5, %0 [%0–%43] | en az 4/5 | Kaldı |
| Rutin kutu alma — doğru normal karar | 49/50, %98 [%90–%100] | 4/5, %80 [%38–%96] | — | — |

Aralıklar Wilson %95 güven aralığıdır. `n=5` nedeniyle run aralıkları geniştir;
bu bir pilot benchmarktır.

## Normal ortamda halüsinasyon

| Ölçüm | Görünüm | Run | Ön kayıt eşiği | Sonuç |
|---|---:|---:|---:|---:|
| Yüksek/kritik yanlış alarm | 1/50, %2 [%0–%11] | 1/5, %20 [%4–%62] | en fazla 1/5 run | Geçti |
| Yanlış operasyonel sevk | 1/50, %2 [%0–%11] | 1/5, %20 [%4–%62] | en fazla 1/5 run | Geçti |
| Herhangi olay veya sevk (operasyonel FP) | 6/50, %12 [%6–%24] | 4/5, %80 [%38–%96] | keşif metriği | Sorunlu |

Normal senaryoda üretilen yanlış anlatılar arasında panikle koşma, kutuya
takılıp denge kaybetme, yerde sürünme/yatarak hareket etme ve zorlukla ayağa
kalkma vardır. En ağır örnekte sistem “yerde sürünerek/yatarak hareket eden
kişi” çıkarıp sağlık ekibi, olay kaydı ve yönetici sevki tetikledi.

## Kaçırmaların niteliği

- **Yangın:** model bazı görüşlerde koşma, panik, kaçış, kaos ve parlamayı
  algıladı; fakat hiçbir görünümde alev/duman/yangın olayını adlandırmadı.
  Dolaylı tahliye davranışı yangın recall'u olarak ödüllendirilmedi.
- **Forklift–raf çarpışması:** yalnız bir kamera “forkliftin sabit iskele
  yapısına çarpıp devirmesi” dedi. Diğer bazı görüşlerde yanlış nesne ve olay
  anlatıları (otonom cihaz–merdiven, büyük yük taşıma, yolu tıkama) üretildi.
- **Ramak kala:** bazı görüşlerde doğru tehlike yakalandı; çoğunda olay yoktu
  veya olay “araca binme”, “sürücüsüz aracın kişiyi takip etmesi” gibi farklı
  bir anlatıya dönüştü. Hiçbir run kamera çoğunluğu eşiğine ulaşmadı.

Bu yeni ortamda baskın hata **güvensiz olayları kaçırma ve yanlış
adlandırma**dır. Normal kontrolde yüksek alarm seyrektir; ancak düşük/orta
seviyeli serbest anlatı halüsinasyonu 6/50 görünüm ve 4/5 run'da görülmüştür.

## Ölçüm denetiminde yakalanan kusur

Ön kayıttaki yardımcı “somut kritik iddia ailesi” sayacı ilk sonuçtan sonra
denetlendiğinde kusurlu bulundu: `düş` kökü, özetlerdeki `(Düşük)` önem
derecesini düşme iddiası sanıyor; buna karşılık “yerde sürünme” gibi bazı yanlış
iddiaları kaçırıyor. Donmuş puanlayıcı 2/50 raporlasa da bu oran **geçerli başarı
kanıtı değildir ve kabul kararında kullanılmamalıdır**.

Bu kusur sessizce düzeltilip aynı çıktı yeniden “nihai” diye adlandırılmadı.
Ana `RED` kararı değişmez: üç güvensiz senaryonun recall koşulları bağımsız
olarak kaldı. Yeni claim-family metriği gerekiyorsa ayrı ön kayıt, farklı run
kimlikleri ve kör değerlendirme gerekir.

## Sonuç ve sonraki deney tasarımı

Bu sonuçla model yeni depo ortamı için üretime hazır kabul edilemez. Aynı 20
run artık test değil, gözlenmiş audit setidir; bunların üzerinde ayar yapıp aynı
örnekleri nihai doğrulama diye kullanmak veri sızıntısı olur.

Önerilen devam sırası:

1. Bu seti değişmez audit kaydı olarak tut.
2. Farklı shard/run kimliklerinden ayrı bir geliştirme seti indir.
3. Geliştirme setinde yangın için doğrudan alev/duman kanıtını, forklift olayları
   için araç–kişi/raf ilişkisini ve normalde zamansal hareket kanıtını iyileştir.
4. Claim-family eşleştiricisini yeni bir ön kayıt altında birim testleriyle düzelt.
5. Daha önce görülmemiş run kimliklerinden kilitli holdout indirip tek seferlik
   son ölçüm yap.

## Üretilen kayıtlar

- Ham model çıktısı: `benchmark/results/eval_20260827_144252.json`
- Donmuş özel puan: `benchmark/results/nvidia_sdg_score_20260827_144259.json`
- Veri manifesti: `data/eval_nvidia_warehouse/manifest.json`
- İndirme betiği: `benchmark/hazirla_nvidia_sdg_warehouse.py`
- Donmuş puanlayıcı: `benchmark/puanla_nvidia_sdg_warehouse.py`
