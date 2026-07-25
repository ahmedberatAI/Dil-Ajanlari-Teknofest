# Kusur-Giderme Sonrası Ölçümler — 2026-07-26

Bu belge, denetimde bulunan 17 kusurun (K1–K17) giderilmesinden **sonra** yapılan
yeniden-ölçümleri içerir. Buradaki sayılar **kanoniktir** ve daha önceki tüm
senaryo-seti rakamlarının yerine geçer.

> **Neden yeniden ölçtük:** Eski amiral rakam (`senaryo recall %98.7`) 18 pozitiften
> 8'i **donmuş tek-kare PNG** olan bir set üzerinde ölçülmüştü (bkz. K8). Ayrıca 4
> "Normal" klip aslında **güvensiz davranış** içeriyordu (K14/etiket çelişkisi).
> Set düzeltildikten sonra eski sayılar **başka bir sete** ait hale geldi.

Ortam: Qwen3-VL-8B-Instruct-FP8 · vLLM (127.0.0.1) · tek RTX 5090 Laptop (24 GB) ·
tüm oranlar **Wilson %95 güven aralığı** ile.

---

## 1. Senaryo seti — `data/eval_scenario` (25 anomali + 12 normal)

Sonuç dosyası: `benchmark/results/eval_20260726_001725.json`

| Metrik | Sonuç (Wilson %95 GA) | k/n |
|---|---|---|
| Anomali recall (≥1 olay) | **%96 [%80–%99]** | 24/25 |
| Kategori eşleşme | **%96 [%80–%99]** | 24/25 |
| Risk kalibrasyonu (≥Yüksek) | %88 [%70–%96] | 22/25 |
| Normal dar-FP (sev/risk ≥ Yüksek) | **%0 [%0–%24]** | 0/12 |
| **Normal yanlış operasyonel tetik** | **%0 [%0–%24]** | 0/12 |
| Normal risk=Düşük | %100 [%76–%100] | 12/12 |
| Gecikme (medyan) | 17.3 s | ~1.39 s/video-sn |

**Kategori kırılımı** (n küçük — GA ile okuyun):

| Kategori | recall | kategori adlandırma |
|---|---|---|
| Fire (10) | %100 [%72–%100] | %100 [%72–%100] |
| Fall (15, **gerçek video**) | %93 [%70–%99] | %93 [%70–%99] |

### Eski vs yeni (dürüstlük notu)
| | ESKİ (18 anomali, 8'i donmuş PNG) | YENİ (25 anomali, hepsi gerçek video) |
|---|---|---|
| recall | %98.7 (şişirilmiş) | **%96** |
| düşme recall | — (sentetik %100 / gerçek %67) | **%93** (gerçek video) |

Set **büyüdü ve zorlaştı** (18→25 gerçek pozitif) ama recall yalnızca ~3 puan düştü;
düşme tarafında gerçek-video performansı %67 → %93'e **yükseldi** (GMDCSA + URFD birlikte).
Yani eski rakamın fazlası sahte kolaylıktan geliyordu, sistemin kendisi sağlam.

---

## 2. 🔴 Hedef-domain seti — `data/eval_defense` (20 güvensiz + 20 güvenli)

Gerçek üretim tesisi güvenlik kamerası, 1920×1080 (Mendeley `xjmtb22pff`).
Sınıf eşlemesi: `data/industrial/CLASSES.md` (class0-3 = GÜVENSİZ).
**Projenin ilk hedef-domain ölçümü.**

| Metrik | Kurallar **KAPALI** | Kurallar **AÇIK** (`facility_rules`) |
|---|---|---|
| Anomali recall | **%25 [%11–%47]** (5/20) | **%55 [%34–%74]** (11/20) |
| Kategori eşleşme | %10 [%3–%30] (2/20) | **%35 [%18–%57]** (7/20) |
| Risk kalibrasyonu | %10 [%3–%30] | %5 [%1–%24] |
| Normal dar-FP | %5 [%1–%24] (1/20) | %15 [%5–%36] (3/20) |
| Normal yanlış tetik | %5 (1/20) | %15 (3/20) |
| Gecikme | ~1.43 s/vsn | ~1.48 s/vsn |

Sonuç dosyaları: `eval_20260726_002608.json` (kapalı) · `eval_20260726_003531.json` (açık)

### 2.1 Neden saf VLM burada %25'te kalıyor?
Senaryo setindeki olaylar **görsel olarak dramatik** (alev, yere düşen insan).
Buradakiler ise **politika ihlali** — görüntü aynı, ihlal olup olmadığı **tesis kuralına** bağlı:

| sınıf | görüntüde ne görünür | neden tek başına anlaşılamaz |
|---|---|---|
| Safe Walkway Violation | yürüyen bir insan | yürüme yolunun nerede olduğu **kurala** bağlı |
| Unauthorized Intervention | makineye dokunan biri | "yetkisiz" olduğu **kimlik/yetki** bilgisi ister |
| Opened Panel Cover | açık pano kapağı | kapalı olması gerektiği **kural** |
| Carrying Overload w/ Forklift | yük taşıyan forklift | "aşırı" olduğu **kapasite kuralı** ister |

Bu bir model kusuru değil, **bilgi eksikliğidir**: kural verilmeden bu olaylar
prensipte de çıkarılamaz. `facility_rules` mimarisi tam olarak bunun için vardır.

### 2.2 Kural enjeksiyonunun ölçülen etkisi (eşleştirilmiş McNemar, n=20)

| Metrik | Kural lehine | Kapalı lehine | McNemar exact p |
|---|---|---|---|
| Recall | **+8 klip** | +2 klip | p = 0.109 |
| Kategori adlandırma | **+5 klip** | +0 klip | p = 0.063 |
| Normal yanlış tetik (maliyet) | +2 fazla tetik | 0 | p = 0.50 |

**Dürüst yorum:** Nokta tahmininde recall **iki katına** (%25→%55), kategori adlandırma
**3.5 katına** (%10→%35) çıkıyor ve yön tutarlı (8-2 ve 5-0). **ANCAK n=20'de hiçbiri
p<0.05 eşiğini geçmiyor.** Yani şu an elimizdeki dürüst ifade:

> *"Kural enjeksiyonu bu sette recall'ı iki katına çıkardı (5/20 → 11/20); etki yönü
> tutarlı (8 klip iyileşti, 2 klip bozuldu) ancak n=20 istatistiksel anlamlılık için
> yetersizdir (p=0.11). Doğrulama için daha büyük n gereklidir."*

Bu, projenin kendi denetiminde tespit ettiği **istatistiksel güç eksikliğinin**
canlı örneğidir — ve çözümü elimizde: kaynak veri setinde **691 klip** var, bizde
şu an yalnızca 40'ı kullanılıyor.

### 2.3 Maliyet dürüstçe
Kural enjeksiyonu bedelsiz değil: normal kliplerde yanlış operasyonel tetik
%5 → %15'e çıkıyor (2 ek klip). Ayrıca risk kalibrasyonu düşüyor (%10 → %5) —
model daha çok olay buluyor ama bunları risk seviyesine **yansıtmıyor**.
Bu, `facility_rules` ile birlikte risk-eşiği ayarının gerektiğini gösteriyor.

---

## 3. Bu ölçümlerden çıkan net konumlandırma

**Sistem güçlü:** görsel olarak belirgin olaylarda (yangın, düşme, kaza) —
gerçek videoda **%96 tespit / %96 kategori**, sıfır yanlış operasyonel tetik.

**Sistem sınırlı:** tesise-özgü politika ihlallerinde — kural olmadan %25,
kuralla %55. Bu alanda **otonom alarm olarak kullanılmamalıdır**;
operatör-destek ve kayıt-triyajı olarak kullanılmalıdır.

**Sonraki adım (ölçülü):** Mendeley setindeki kalan 651 klibi indirip
`eval_defense`'i ~200 klibe çıkarmak. n=200'de McNemar gücü, gözlenen
8-2 örüntüsünü p<0.05'e taşımaya yeter; bugün taşımıyor.
