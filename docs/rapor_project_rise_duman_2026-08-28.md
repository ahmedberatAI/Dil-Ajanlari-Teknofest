# Project RISE dengeli endüstriyel duman benchmarkı — sonuç raporu

Tarih: 2026-08-28  
Sonuç dosyası: `benchmark/results/deep_smoke_balanced_20260828_023444.json`  
Ön kayıt: `docs/on_kayit_project_rise_duman_2026-08-28.md`

## Karar

Mevcut v13o kodu ve v13n opt-in zinciri bu yeni dış veride **başarısızdır**.
İkili duman recall `12/28`, duman FP `6/28`, MCC `0,229` çıkmıştır. Daha önemlisi,
yanlış pozitiflerin tamamı Kritik risk ve gerçek fonksiyon çağrısına dönüşmüştür.

Bu sonuç bir “VLM dumanı hiç görmüyor” vakası değildir. İlk yapılandırılmış görsel
slot dumanlı videoların `24/28`'inde plüm görmüştür. Kaybın büyük kısmı sonraki
buhar/toz vetosunda, yanlış alarmın büyük kısmı ise alan-kapsamı olmayan depo slotu
ve çelişkili hakem semantiğinde oluşmaktadır.

## Veri sözleşmesi

- Kaynak: CMU CREATE Lab, Project RISE / Deep Smoke Machine.
- Repo revizyonu: `e796bf36988226b8bc657872bdc83c6cbad791cd`.
- Metadata SHA256: `cc85ad6db07557ae4afacc4f12f443b6e68ae0d88e30869fcf031f4c7dc7ee18`.
- Lisans: veri CC0; kod BSD-3-Clause.
- Daha önce projede kullanılmamış kaynak; yerel aramada kaynak/kimlik eşleşmesi yoktur.
- Sabit seçim: camera `0`, view `0`, tarih `2019-02-02`, güçlü araştırmacı etiketi
  `23=duman`, `16=dumansız`; filtreye uyan kayıtların tamamı.
- Denge: `28 + 28 = 56`; aynı tesis, kamera, görüş, gün ve çözünürlük.
- Medya: 56/56 H.264, 320×320, 36 kare, 12 fps, 3,0 s, sessiz; SHA256 mükerrer yok.
- Dosya/dizin adları etiketi taşımaz; altın etiket modele verilmemiştir.

SteelBench daha geniş İSG adayı olarak incelenmiş; yayınlanan 50-klip örneğinde genel
KKD uyumu, kişi düzeyi KKD ve açık ihlal metinleri çeliştiği için sonuç görülmeden
ana ölçümden çıkarılmıştır.

## Koşum sözleşmesi

- Özel API: `https://evren-llmapi.ssyz.org.tr/v1`.
- Sabit roller birlikte: `vlm` + `llm-large` + `llm-fast`.
- Pipeline: `2026-08-28-isg-evidence-v13o-policy-bound-ppe`.
- v13n'in yedi fallback/veto bayrağı açık; sıcaklık `0`; dört işçi.
- Yerel öğrenilmiş çıkarım ve model indirme kapalı.
- Kapsama `56/56`, API/ayrıştırma hatası `0`.
- Kilitli v13 holdout açılmadı/okunmadı.

## Birincil sonuçlar

Karışıklık matrisi: `TP=12, FN=16, FP=6, TN=22`.

| Ölçüt | Sonuç | Wilson %95 GA |
|---|---:|---:|
| Duman recall | **12/28 = %43** | %27–%61 |
| Duman FP | **6/28 = %21** | %10–%40 |
| Precision | **12/18 = %67** | %44–%84 |
| Specificity | **22/28 = %79** | %60–%90 |
| Accuracy / balanced accuracy | %60,7 / %60,7 | — |
| F1 | 0,522 | — |
| MCC | **0,229** | — |

## Operasyonel sonuçlar

| Ölçüt | Sonuç | Wilson %95 GA |
|---|---:|---:|
| Dumanlı klipte herhangi olay | 12/28 = %43 | %27–%61 |
| Dumansız klipte operasyonel FP | **6/28 = %21** | %10–%40 |
| Dumansız klipte yüksek/kritik FP | **6/28 = %21** | %10–%40 |
| Dumansız klipte dispatch FP | **6/28 = %21** | %10–%40 |
| Kapsama | 56/56 = %100 | %93,6–%100 |
| Medyan gecikme | 18,2 s/klip | min 10,1; maks 27,9 |

Üretilen 18 olayın **18'i de Kritik**, 18'inin tamamı dispatch üretmiştir. Dolayısıyla
bu testte algısal “plüm olabilir” belirsizliği ile acil ekip sevki arasında güvenli
bir ayrım yoktur.

## Kök neden ayrıştırması

### 1. Algı plümü görüyor; nihai kapı dumanı siliyor

İlk `depo_gorunur_yangin` slotu:

| Altın etiket | Slot `VAR` | Nihai duman |
|---|---:|---:|
| Duman | **24/28** | 12/28 |
| Dumansız | 16/28 | 6/28 |

Yani ham slot hassas fakat özgül değildir. Sonraki buhar/toz vetosu dumansızlardaki
10 slot alarmını doğru bastırırken, dumanlılardaki **13 doğru etiketi de bastırmıştır**.
Toplam 16 FN'nin 13'ü açıkça `BUHAR_TOZ_PARLAMA -> olay silindi`; kalan üçü ilk
slotta `YOK` olmuştur.

Arşivden yapılan tanısal karşı-olguda (yeni model çağrısı yok), yalnız slot `VAR`
tahmin sayılsaydı recall `24/28 = %86`, fakat FP `16/28 = %57` olurdu. Veto bu nedenle
gerekli, ancak mevcut ayrım duman ile buharı güvenilir ayıramamaktadır.

### 2. Hakem `REFUTED` diyor, olay yine korunuyor

18 nihai pozitifin 17'si yapılandırılmış depo-yangın olayıdır:

- 6 olay atomik hakemde `SUPPORTED`;
- **11 olay atomik hakemde `REFUTED` olduğu hâlde korunmuştur**;
- 1 olay serbest anlatıdır.

Mevcut kural yalnız açık `BUHAR_TOZ_PARLAMA` sonucunu veto ediyor; `ALEV_DUMAN_YOK`,
`SABIT_GOLGE_NESNE` veya `BELIRTI_YOK` ile gelen diğer `REFUTED` sonuçları olayı
koruyor. Böylece “hakem reddetti” durumu semantik olarak tek anlam taşımıyor. Altı
FP'nin dördü bu `REFUTED fakat korundu` yolundan gelmiştir.

### 3. Depo-özel slot genel sanayi sahnesine taşmış

18 alarmın 17'si `Warehouse_Visible_Fire:depo_gorunur_yangin` kaynağındadır. Görüntü
bir depo değil, uzaktan izlenen tesis bacasıdır. Alan kilidi olmadan depo-özel gözlem
genel sahneye uygulanmış, olay metni her seferinde “Depo alanında duman/alev” diye
üretilmiş ve yangın kaynağı varsayılmıştır.

### 4. Duman varlığı ile yangın/acil durum aynı karara bağlanmış

Veri etiketi yalnız **endüstriyel duman emisyonu var/yok** bilgisidir. Model ise her
pozitifi “yangın riski”, Kritik önem ve dört fonksiyon çağrısına çevirmiştir. Doğru
duman tespiti bile otomatik olarak yangın, basınç artışı, sızıntı veya tahliye kanıtı
değildir. `rise_18032` doğru duman pozitifidir; buna rağmen serbest anlatı “ani basınç
artışı veya sızıntı” ve acil tahliye/itfaiye sonuçlarını görüntüden uydurmuştur.

## Sonuçtan sonra yapılmayanlar

- Aynı 56 klip yeniden koşturulmadı.
- Prompt, eşik, eşleştirici veya veri seçimi sonuca göre değiştirilmedi.
- Başarısız örnekler geliştirme setine çevrilmedi.
- Yerel model indirilmedi/çalıştırılmadı.

## Bir sonraki geliştirme için kilit öneriler

1. `depo_*` slotlarını depo/warehouse bağlamı doğrulanmadan çalıştırmayan alan kapısı.
2. Genel bir `endustriyel_plum` gözlemi: `smoke / steam / dust / cloud-fog / unknown`,
   kaynakla bağlılık, renk-opaklık, kalıcılık ve zamansal yayılımı ayrı alanlarda üretme.
3. `REFUTED` semantiğini tekleştirme; olayın korunması gerekiyorsa durum `INCONCLUSIVE`
   olmalı, `REFUTED` değil.
4. Duman gözlemini yangın ve dispatch'ten ayırma. Alev, hızla büyüyen koyu duman,
   tesis sensörü/politikası veya ikinci bağımsız kanıt yoksa otomatik Kritik sevk yok.
5. Aynı 56 test klibinde ayar yapmama. Project RISE'ın başka gün/görüşlerinden ayrı
   geliştirme seti, başka kamera/görüşten yeni kilitli test seti oluşturma.

Bu benchmark dar bir endüstriyel duman/emisyon testidir; genel İSG başarısının tamamını
ölçmez. Ancak duman–buhar ayrımı, alan-kapsamı ve alarm–dispatch kalibrasyonunda gerçek
bir genelleme kusurunu bağımsız veride açıkça göstermektedir.
