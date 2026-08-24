# ÖN-KAYIT — Yaya yolu geofence'i (D39-B)

**Tarih:** 2026-08-18 · **Sonuçlara bakılmadan önce yazıldı.**

## Neden bu hamle

Üç bağımsız kanıt hattı aynı yeri gösterdi:

1. **Yetenek envanteri:** `restricted_zones` geofence'i kodda **çalışır durumda**
   (`detector.py:162-189`), savunma setinde **recall %88 / precision %100** ölçülmüş,
   ve İSG setinde **hiç koşulmamış**.
2. **Literatür:** yaya yolu ihlali için baskın kalıp *dedektör → takip → yer temas
   noktası → poligon-içi testi → durum makinesi*. Uçtan uca VLM neredeyse hiç
   kullanılmıyor. (Sensors 23(20):8371, 2023 — PMC10610944)
3. **Kendi ölçümümüz:** VLM'in `isg_özgül` isabeti %4-6; `tespit MCC` üç özdeş
   koşumda ±0,18 salınıyor. VLM bu sınıfta karar verecek durumda değil.

## Sahne bulguları (ölçüldü, varsayılmadı)

| bulgu | ölçüm |
|---|---|
| Klip sayısı | ihlal 25 · normal 23 = **48** |
| Çözünürlük | **48/48 → 1920×1080** |
| Kamera sabit mi | **HAYIR** — referansa göre kare farkı medyan 26, maks 50 |
| Yürüme yolu | **sarı çizgili yeşil boya** — renk maskesi görsel denetimde temiz |
| Yeşil alan oranı | ihlal %2,74 · normal %3,60 (**örtüşüyor** — tek başına ayırmaz) |

Kamera sabit olmadığı için **elle poligon çizmek işe yaramaz**; renk maskesi her
karede kendini kalibre eder. Bu, literatürün önerdiği elle-poligondan **daha iyi**
bir uyarlama ve etiketleme emeği gerektirmez.

## Bilinen komplikasyon

Makinede çalışan işçiler **her iki sınıfta da** var (`0_tr123` ve `4_tr12`). Yani
*"yeşilin dışında = ihlal"* tek başına yanlış pozitif üretir. Literatür bunun için
**takip + geçiş durum makinesi** diyor (geçen kişi ≠ tezgâhta duran kişi).

## Yığın ve lisans

- Dedektör: **RT-DETRv2** (`PekingU/rtdetr_v2_r50vd`, **Apache-2.0**, transformers yerleşik)
- **ultralytics KULLANILMAZ** — 8.4.72 = AGPL-3.0, depomuz Apache-2.0 (bkz. D39-A)
- Yer temas noktası: kutu üstünden **α = 0,914** aşağı (PMC10610944)

## Ön-kayıtlı kural ailesi — SONUÇLARA BAKMADAN sabitlendi

| # | kural |
|---|---|
| R1 | Hiçbir kişinin ayağı yeşilde değil → **ihlal** |
| R2 | En az bir kişinin ayağı yeşil dışında → **ihlal** |
| R3 | R2 + o kişinin yeşile mesafesi < D (koridorda, makine bölgesinde değil) |
| R4 | En çok yer değiştiren kişinin ayağı yeşilde değil → **ihlal** |
| R5 | (yeşildeki kişi-kare / toplam kişi-kare) < τ → **ihlal** |
| R6 | R1 **ve** koridorda en az bir kişi var (mesafe < D) → **ihlal** |

Eşikler `D ∈ {150, 250, 400, 600} px`, `τ ∈ {0,05 0,10 0,20 0,35}` ızgarasından
seçilir. **Izgara dışına çıkılmayacak.**

## Seçim ölçütü — önceden sabit

1. 48 klipte **MCC** en yüksek olan kural seçilir; beraberlikte **FP azlığı** bozar.
2. Seçilen kural **MCC ≥ 0,40** eşiğini geçmezse → **RET**, yayımlanmaz.

## Gerçek sınav — geliştirme setinde DEĞİL

48 klip **geliştirme setidir**; orada iyi çıkması kanıt sayılmaz. Kabul için ayrıca:

3. Tam **197 klipte** koşulur. Diğer **149 klipte** (yaya yolu dışı sınıflar)
   yanlış pozitif artışı **≤ 5 klip** olmalı.
4. Karar metriği **`isg_özgül` TP/FP** — koşumlar arası birebir kararlı olan sütun.
   **`recall` ve `tespit MCC` KULLANILMAZ** (üç özdeş koşumda ±12 puan / ±0,18 salınıyor).

## Geri çekilme sözü

Kural bu eşiklerden herhangi birini geçemezse **reddedilir ve belgelenir**;
eşikler sonradan gevşetilmez. İSG merceğinde (D37) olduğu gibi, kendi önerim de
ölçüme tabidir.

---

# EK-1 — İlk koşum sonucu ve maske düzeltmesinin metodolojik durumu

**Tarih:** 2026-08-18, ön-kayıttan sonra · Sonuçlar aşağıda **olduğu gibi** duruyor.

## Ön-kayıtlı ölçüt geçildi, ama kural dağıtılabilir değil

RT-DETRv2 (Apache-2.0) · 48 klip · 16 kare · α=0,914

| kural | MCC | TP | FP | FN | TN | kesinlik | duyarlılık |
|---|---|---|---|---|---|---|---|
| **R6 (her D) ≡ R1** | **+0,506** | 24 | **12** | 1 | 11 | 0,667 | 0,960 |
| R5 τ=0,05 | +0,431 | 25 | 16 | 0 | 7 | 0,610 | 1,000 |
| R4 en hareketli | +0,394 | 24 | 15 | 1 | 8 | 0,615 | 0,960 |
| R2 · R3 (her D) | **0,000** | 25 | 23 | 0 | 0 | 0,521 | 1,000 |

Üç dürüstlük notu:

1. **R6, R1'e çöküyor.** Dört D eşiği birebir aynı sayıyı veriyor — mesafe terimi hiç
   bağlamıyor. Seçilen kural aslında **R1: "kimsenin ayağı yeşilde değil"**.
   D parametresi rapor edilirken süs olarak taşınmayacak.
2. **R2 ve R3 dejenere** — 48 klibin 48'ine "ihlal" diyor. MCC 0,000 bunu doğru gösterdi.
   (D37'de MCC'nin dejenere sınıflandırıcıyı gizlediği tuzağın tersi: burada recall=1,000
   ile birlikte okununca ele veriyor. **İki metrik birlikte okundu.**)
3. **Kesinlik 0,667** — 23 normal klibin **12'si yanlış alarm**. Ön-kayıtlı MCC eşiği
   geçilmiş olsa da bu haliyle **dağıtılamaz**.

## Yanlış pozitiflerin sebebi: maske kusuru (etiketten bağımsız bulgu)

Görsel + sayısal teşhis:

| klip | tip | maske oranı | ayağın yeşile en yakın mesafesi |
|---|---|---|---|
| `4_te19` | FP | %1,30 | **2 px** |
| `4_tr37` | FP | %1,31 | **3 px** |
| `4_tr3` | FP | %3,60 | 15 px |
| `4_te15` | FP | %1,44 | 24 px |
| `4_tr35` | TN | %2,96 | 0 |
| `4_tr7` | TN | %3,27 | 0 |

Görsel denetimde (`yol_tani.jpg`) net: FP kliplerinde maske koridorun yalnızca sağ-alt
köşesini yakalıyor, koridorun gövdesi **maskesiz kalıyor**. Sebep, eşiklerin **mutlak**
olması (`g−r>12, g−b>6, g>55`); o kliplerde boya farklı pozlamada soluk çıkıyor.

**Bu bir algı kusurudur, etiket meselesi değil.**

## Düzeltmenin metodolojik statüsü — açıkça yazıyorum

Maske düzeltmesi **etiketlere bakılarak yapılmayacak**. Yürüme yolu 48 klipte fiziksel
olarak aynı koridordur; dolayısıyla maskelenen alan oranı kabaca sabit olmalıdır.
Optimize edilen ölçüt **etiket içermez**:

- (a) 48 klipte maske oranının **varyasyon katsayısı** düşük olmalı
- (b) hiçbir klipte oran **< %1,5** olmamalı (yol kayboldu)
- (c) hiçbir klipte oran **> %8** olmamalı (taşma)

Metrik oyunu riski bu yüzden yapısal olarak yoktur: ölçüt sınıf etiketini görmez.
Üç aday yaklaşım bağımsız üretilip bu ölçütle hakemlenecek; hakem ayrıca üretilen
**görselleri açıp bakacak** ve ölçütü kandıran adayı (ör. maskeyi sabit dikdörtgen yapmak)
eleyecek.

## Ama şu kabul ediliyor

**48 klip artık geliştirme verisidir.** Üstünde kural ailesi denendi, kusur teşhis edildi,
maske düzeltilecek. Buradan çıkacak sayı **kanıt değildir**.

Kabul kararı **yalnızca ön-kayıtta ilan edilen tam 197 klip koşumundan** verilecek:
diğer **149 klipte** yanlış pozitif artışı **≤ 5**, karar metriği **`isg_özgül` TP/FP**.
Bu eşikler **değiştirilmedi ve değiştirilmeyecek.**

---

# EK-2 — Ölçeğe duyarlı ayak toleransı (POST-HOC, çalışmadı)

12 yanlış pozitifin **12'sinin de** görsel denetimi yapıldı (`fp_denetim.jpg`).
**Hepsinde** yolun üstünde veya kılpayı kenarında bir kişi var. Yani `Safe_Walkway`
etiketi gerçekten *"biri yolu doğru kullanıyor"* demek — **R1'in polaritesi doğru**,
kusur tamamen geometrik.

Fiziksel gerekçeli düzeltme denendi: ayak noktası belirsizliği kişinin görüntüdeki
boyuyla ölçeklenir → `ayak_mesafe < β × kutu_yüksekliği`. Eşik, yanlış pozitiflerin
mesafelerine (2, 3, 15, 24 px) **bakılarak seçilmedi**.

| β | MCC | TP | FP | FN | TN | kesinlik | duyarlılık | duyarlılık %95 GA |
|---|---|---|---|---|---|---|---|---|
| **0,00** (R1) | +0,506 | 24 | 12 | 1 | 11 | 0,667 | 0,960 | [0,80 · 0,99] |
| 0,02 | +0,523 | 23 | 10 | 2 | 13 | 0,697 | 0,920 | [0,75 · 0,98] |
| 0,05 | +0,549 | 22 | 8 | 3 | 15 | 0,733 | 0,880 | [0,70 · 0,96] |
| 0,10 | +0,415 | 19 | 8 | 6 | 15 | 0,704 | 0,760 | [0,57 · 0,89] |
| 0,15 | +0,499 | 19 | 6 | 6 | 17 | 0,760 | 0,760 | [0,57 · 0,89] |
| 0,20 | +0,419 | 17 | 6 | 8 | 17 | 0,739 | 0,680 | [0,48 · 0,83] |
| 0,30 | +0,435 | 15 | 4 | 10 | 19 | 0,789 | 0,600 | [0,41 · 0,77] |

## Karar: **tolerans TEK BAŞINA işe yaramıyor**

- En iyi β kazancı **+0,043 MCC** — 48 klipte gürültü seviyesinde.
- Wilson aralıkları tamamen örtüşüyor.
- 7 β değeri arasından en iyiyi seçmek **çoklu-karşılaştırma alışverişidir**;
  düzeltilirse kazanç kalmaz.
- Yanlış pozitif 12→8 **düşüyor ama** duyarlılık 24→22 **düşerek**. Takas, kazanç değil.

**Hiçbir β, β=0'ı açıkça yenmiyor.** Tolerans tek başına dağıtılmayacak.

Asıl darboğaz maskede: yanlış pozitif kliplerde maske oranı **%1,2-1,7**, doğru
kliplerde **%3,0-3,6** — maske yolun yaklaşık yarısını kaçırıyor. Düzeltme oraya
uygulanacak ve **etiketsiz ölçütle** (EK-1) hakemlenecek.

---

# EK-3 — DÜZELTME: EK-1'deki iki iddiam yanlış çıktı

İki bağımsız ajan, ölçerek çürüttü. Düzeltmeleri kayda geçiriyorum; EK-1'deki
yanlış cümleler **silinmedi**, aşağıda düzeltiliyor.

## Yanlış iddia 1 — "48 klip aynı sabit kamera"

**Gerçek:** iki farklı kamera çerçevesi var.

| grup | n | maske oranı (eski maske) |
|---|---|---|
| A_GENİŞ (geniş açı) | ~30 | ort %1,48 · maks %1,78 |
| B_YAKIN (yakın plan) | ~18 | ort %3,59 · min %2,56 |

**Örtüşme yok.** Alan oranı **B/A = 2,10×**, ve bu tam olarak
genişlik 1,29× × uzunluk 1,62× = **2,09×** çarpımına ayrışıyor — geometrik kanıt,
tahmin değil.

**Sonucu:** EK-1'deki (a) ölçütü — "maske oranı klipler arası sabit olmalı" —
**hatalı temele dayanıyordu**. Küresel varyasyonun büyük kısmı maske kalitesinden
değil, çerçeve farkından geliyor. Bir ajan küresel CV'nin kuramsal tabanını 0,4267
olarak hesapladı; yani (a) ölçütünde oynayacak alan neredeyse yoktu.
**Anlamlı ölçüt grup-içi CV'dir.**

Ayrıca EK-1'de "başarısız" saydığım `4_te15`/`4_te19` ile "iyi" saydığım
`4_tr35`/`4_tr7` ayrımı da maske kalitesi değil, **çerçeve farkıydı** —
ilk ikisi geniş, son ikisi yakın plan.

## Yanlış iddia 2 — "boya soluk kalıyor, eşiğin altına düşüyor"

**Gerçek:** uzlaşı yol bölgesinde en düşük 5 ve en yüksek 5 klip karşılaştırıldı:

| ölçüm | düşük | yüksek | yorum |
|---|---|---|---|
| `g − r` | 36,8 | 37,6 | **fark yok** |
| `(g−r)/s` | 0,125 | 0,120 | **fark yok** |
| `g − b` | 9,8 | 16,3 | **%40 düşüş ← suçlu** |

41/48 klipte yol çekirdeğinin **%0,0'ı** `g−r>12` eşiğinin altında — eşiğin
**4 kat marjı** var. Kayan eksen yeşil-mavi, yani **beyaz dengesi**; pozlama değil.
Büyüklük sınaması da tutuyor (b≈100'de %6,5 oran kayması → Δ(g−b)≈6,5; ölçülen −6,5).

## Bunun geofence sonucuna etkisi — AÇIK SORU

Çerçeve tipi sınıf etiketiyle **korelasyonluysa**, çerçeveye duyarlı herhangi bir
öznitelik sınıfları **sahte** olarak ayırır. R1'in MCC +0,506'sı bu yüzden kısayol
olabilir. Bu şu an ölçülüyor: her çerçeve grubu **içinde** ayrı ayrı
TP/FP/FN/TN + MCC, artı Fisher exact bağımsızlık testi.

Sonuç grup içinde de ayırıyorsa geofence **hayatta**; MCC ~0'a çöküyorsa
**kısayoldu ve reddedilecek**.

## Seçilen maske

Jüri **sarı-sınır çıkarımlı histerezis** maskesini seçti (`maske_sari_sinir.py`).
Jüri üç adayın sayılarını **kendi betiğiyle bağımsız yeniden üretti** (hepsi birebir
tuttu), kandırma denetimi yaptı (sabit dikdörtgen/ROI yok) ve **kendi ürettiği
görsellerle** birlikte görsel denetimi tamamladı.

| ölçüt | eski | yeni |
|---|---|---|
| `<%1,5` ihlali | 16 klip | **0 klip** |
| `>%8` ihlali | 0 | 0 |
| kamera-içi CV | 0,127 | **0,053** |
| `4_te15` | %1,29 | %2,27 |
| `4_te19` | %1,18 | %2,45 |
| `4_tr35` (zaten iyiydi) | %2,80 | %4,22 |

Maliyet: 233 ms/kare (CPU) — eski ham maske 10 ms.

**Dürüstlük notu (aday kendisi bildirdi):** ham eski maske küresel CV'de daha *iyi*
(0,290) görünüyor, çünkü yakın-plan grubunda **eksik tespit** edip aralığı yapay
sıkıştırıyor. Yani (a) ölçütü **"daha az tespit et" ile oynanabilir**. Bu yüzden
karar grup-içi CV ve uzlaşı IoU ile verildi.

---

# KARAR — **RET.** Yaya yolu geofence'i kısayoldu.

**Tarih:** 2026-08-18 · Ön-kayıtlı ölçüt (MCC ≥ 0,40) *geçilmişti*; buna rağmen **reddediliyor**,
çünkü ön-kayıtta öngörmediğim bir karıştırıcı ölçüldü ve sonucu açıkladığı kanıtlandı.

## 1. Kamera çerçevesi sınıf etiketiyle korelasyonlu

Kümeleme iki bağımsız yöntemle (medyan-arkaplan korelasyonu + yeşil maske geometrisi)
**%100 aynı** bölmeyi verdi: **A_GENİŞ n=30 · B_YAKIN n=18**.

- küme-içi korelasyon **+0,938** · küme-arası **+0,175** → dağılımlar **hiç örtüşmüyor**
- silhouette **+0,929**, negatif klip **0/48**
- 200/200 önyükleme birebir aynı bölme · önceki ajanın bölmesiyle **48/48** aynı

| | İHLAL | NORMAL | ihlal oranı |
|---|---|---|---|
| A_GENİŞ | 21 | 9 | **%70,0** |
| B_YAKIN | 4 | 14 | **%22,2** |

**Fisher exact (iki yönlü) p = 2,4×10⁻³ · OR = 8,17.** Çerçeve ile etiket bağımsız değil.

## 2. Kural, verinin çoğunluğunu oluşturan grupta çöküyor

| kesit | n | TP | FP | FN | TN | MCC | p |
|---|---|---|---|---|---|---|---|
| tüm veri | 48 | 24 | 12 | 1 | 11 | **+0,506** | — |
| **A_GENİŞ içinde** | **30** | 20 | 8 | 1 | 1 | **+0,117** | **0,52** |
| B_YAKIN içinde | 18 | 4 | 4 | 0 | 10 | +0,598 | 0,023 |

- A_GENİŞ'te önyükleme %95 GA **[−0,201 · +0,484] — sıfırı içeriyor**
- A_GENİŞ'te kural **dejenere**: 30 klibin **28'ine** (%93) "ihlal" diyor;
  doğruluğu **0,700**, hep-ihlal diyen önemsiz sınıflandırıcıyla **tam eşit** → **sıfır kazanç**
- B_YAKIN'de sadece **4 pozitif** var; iki grup-içi test yapıldığı için Bonferroni eşiği
  0,025 ve p kıl payı geçiyor; oradaki doğruluk da (0,778) çoğunluk tabanına eşit
- **Cochran-Mantel-Haenszel** (çerçeveye göre katmanlı): **χ² = 3,695 · p = 0,0546** → 0,05'te anlamlı **değil**

## 3. Kısayolun tavanı — belirleyici sayı

Çerçeve tipini **tek başına** sınıflandırıcı olarak kullan (A_GENİŞ→ihlal, B_YAKIN→normal):
**35/48 = %72,9 doğruluk · MCC +0,463.**

**R1'in doğruluğu da tam %72,9.** Yani R1 ham doğrulukta saf çerçeve kısayolunu **hiç geçmiyor**;
yalnızca MCC'de +0,463 → +0,506 kadar oynuyor. R1 ile çerçeve tahmini **38/48 (%79,2)** örtüşüyor.
R1'in 11 doğru "normal" kararının **10'u tek bir çerçeve grubundan**.

**Mekanizma:** A_GENİŞ'te yol uzak ve küçük; yeşil-ayak oranının medyanı **tam 0,0000**.
Kural orada içerik değil, **çerçeve ölçüyor**.

## 4. Maske gerçekten düzeldi — ama kural düzelmedi

| kural-bağımsız maske ölçümü | eski | yeni |
|---|---|---|
| ortalama kapsama | 0,0227 | **0,0338** (+%49) |
| `<%1,5` kapsamalı klip | 14 | **0** |
| kamera-içi CV | 0,059 | **0,038** |

Ama aynı kuralda (R1) maske değişiminin etkisi:

**McNemar exact: b=4 · c=4 → p = 1,0000.** ΔMCC %95 GA **[−0,266 · +0,167]**.
Uyumsuz çiftler **mükemmel simetrik** — eski 4 İHLAL klibi kazanıyor, yeni 4 NORMAL klibi.
Sinyal yok, sadece **duyarlılık↔özgüllük takası**.

## 5. Kendi ızgara tasarımımdaki kusur

D ızgarası **atıl**: R6 dört D değerinde de R1 ile **birebir aynı**, R3 dört D değerinde de
R2 ile aynı. 1080p'de en küçük D=150 px her klipte sağlanıyor. **15 "ön-kayıtlı yapılandırma"nın
gerçekte yalnızca 7'si ayırt edilebilir.** Çoklu-karşılaştırma düzeltmesi 7 üzerinden yapılmalıydı.

Ayrıca yeni maskede "en iyi" çıkan R5 τ=0,05 (+0,501), 7 yapılandırma üzerinden **maksimum
alınarak** seçildi; +0,070'lik kazanımı gerçek saymıyoruz.

## Sonuç

Fikir yanlış değil — literatürde yaya yolu ihlali böyle çözülüyor ve savunma setinde
%88/%100 vermişti. **Bu veri setinde ölçülemiyor**, çünkü iki kamera çerçevesi etiketle
korelasyonlu ve çerçeveye duyarlı her öznitelik sahte ayırt etme gücü kazanıyor.

**Dağıtılmayacak.** Ölçekten arındırılmış bir ölçüt veya çerçeve-başına kalibrasyon
denenebilir, ama o da grup-içi raporlanmak zorunda ve A_GENİŞ'te yalnızca 30 klip var.

## Bu bulgunun kapsamı — veri seti özelliği

Bu, yaya yolu sınıfına özgü bir kaza değil: **`data/eval_defense` içinde çerçeveye duyarlı
herhangi bir öznitelik bu iki sınıfı sahte ayırabilir.** Diğer sınıf çiftlerinde de
çerçeve homojenliği doğrulanmadan sonuç raporlanmamalı.
(Pano sınıflarında kamera **sabit** doğrulandı — orası temiz.)
