# Pano dedektörü — **ÇALIŞIYOR** (D39-E)

**Tarih:** 2026-08-18 · Karar: **KABUL, sert kontrollerden geçti.**

## Başlangıç noktası: benim "algı sınırı" sonucum eksikti

D33 ve bugünkü kırpma probum şunu ölçmüştü:

| kol | 12 açık pano klibinde doğru |
|---|---|
| VLM, tam kare @768 | **0/12** |
| VLM, panoya kırpılmış @768 (2,5× detay) | **1/12** |
| Qwen3.8-27B (3× büyük model) | **0/99** |

Sonuç doğruydu: **VLM bunu göremiyor.** Ama eksikti — *"kimse göremez"* demiyordu.

## Mekanizma: "açık kapak = karanlık oyuk"

Dar pano ROI'si `(0,08 · 0,55 · 0,21 · 0,73)` üzerinde, **kareler boyunca minimum
ortalama parlaklık**. Tek skaler, **model yok, eğitim yok**.

## Ama tek başına güvenlik kuralı değil

| görev | doğruluk | MCC | TP | FP | FN | TN |
|---|---|---|---|---|---|---|
| (i) class2 vs class6 — **algı** | 0,959 | — | 23 | 1 | 1 | 24 |
| (ii) class2 vs class5 — **yetki** | 0,571 | +0,241 | 23 | **20** | 1 | 5 |
| (iii) class2 vs class6+class5 — **gerçek güvenlik** | 0,703 | +0,513 | 23 | **21** | 1 | 29 |

`Authorized_Intervention` (class5) kliplerinde pano da **fiziksel olarak açık**.
**"Pano açık" görünür; "yetkili mi" görünmez.**

## Çözüm: konum terimi — "başında kimse var mı"

Ham sinyal, pano kutusuyla örtüşen kişi oranı:

| sınıf | oran |
|---|---|
| class2 `Opened_Panel_Cover` (ihlal) | **0,12** |
| class5 `Authorized_Intervention` (normal) | **0,88** |
| class6 `Closed_Panel_Cover` (normal) | 0,20 |

Hipotez doğrulandı: **class5 = biri panonun başında çalışıyor · class2 = pano başıboş açık.**

### Bileşik kural: *pano karanlık* **VE** *başında kişi yok* → ihlal

| görev | kural | doğruluk | MCC | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|
| (ii) yetki | luma tek başına | 0,571 | +0,241 | 23 | 20 | 1 | 5 |
| (ii) yetki | **bileşik** | **0,898** | **+0,801** | 20 | **1** | 4 | 24 |
| (iii) güvenlik | luma tek başına | 0,703 | +0,513 | 23 | 21 | 1 | 29 |
| (iii) güvenlik | **bileşik** | **0,932** | **+0,845** | 20 | **1** | 4 | 49 |
| (iii) güvenlik | **bileşik, TUTMA kümesi (n=26)** | **0,962** | **+0,799** | 2 | **0** | 1 | 23 |

**Yanlış pozitif 21 → 1.** class5 sorunu çözüldü.

## Sonucu ayakta tutan üç kontrol

**1. Çoklu-karşılaştırma — maks-istatistiği permütasyonu.** 8 varyantlık ızgara,
n=2000, **tüm boru hattı her permütasyonda yeniden koşuldu**: gözlenen maks MCC **+0,845**,
boş dağılımın %95 kuantili **+0,360**, **p = 0,0005**. Izgara seçimi düzeltildikten sonra da gerçek.

**2. Mekânsal plasebo.** Bu ortamda **gerçek bir oturum izi olduğu ölçülmüştü**
(SigLIP ile panodan uzak aynı-boyut kutu 0,776 / MCC 0,577 · p=0,003), bu yüzden zorunlu:

| kutu | görev (ii) MCC | görev (iii) MCC |
|---|---|---|
| **PANO** | **+0,755** | **+0,845** |
| AYNA (yaya yolu, aynı boyut) | +0,212 | +0,539 *(luma tabanı +0,513'ün üstüne ~hiçbir şey)* |
| GENİŞ (pano çevresi) | +0,549 | +0,571 |
| ORTA | +0,059 | +0,254 |
| ÜST | −0,202 *(dejenere)* | — |

Sinyal **panoya yerel**. Oturum izi bunu açıklayamıyor.

**3. Dış geçerlilik.** "Hiçbir kapalı klipte görülmeyen kadar karanlık" eşiği (=87,6):
class2 **%75** · class6 **%0** · class5 **%76**. class5 **ayrı bir oturum** ama pano-yerel
ölçüm onu açık sınıfıyla aynı yere koyuyor → özellik gerçekten **panoyu** görüyor.

## Çekinceler

- n=49 (görev i) / n=74 (görev iii) **küçük**. Tutma kümesinde yalnızca 3 pozitif var.
- Etiket klip düzeyi, pano klip **içinde** açılabiliyor (ör. `2_te12` orta karede kapalı)
  → 4 kare yetersizdi, **16 kare** kullanıldı. Kare sayısı/toplama seçimi sonucu ciddi etkiliyor.
- Veride **gerçek oturum izi var**; SigLIP tabanlı herhangi bir manşet sayısı kısmen şişkin.
  **Yalnızca dar/mekanizma-temelli ölçümlere güvenilecek.**
- ROI sabit; kamera bu sınıflarda sabit doğrulandı (1920×1080, aynı görüntü).
  **Başka tesise taşınırsa ROI yeniden tanımlanmalı.**

## Lisans

Luma yolu: yalnızca **numpy** — bağımlılık yok. Kişi tespiti: **RT-DETRv2**
(`PekingU/rtdetr_v2_r50vd`, **Apache-2.0**, transformers yerleşik). **ultralytics kullanılmadı.**

## Neden bu, projenin kendi tezini doğruluyor

§6.2: *"ince görsel durum VLM işi değildir."* Şimdi sayıyla:
VLM kırpılmış görüntüde **1/12**; iki satırlık deterministik ölçüm **0,932**.
**VLM anlatsın, deterministik dedektörler karar versin.**

---

# GERÇEK SINAV — tam 197 klip, üretim kod yolu

**Tarih:** 2026-08-18 · `benchmark/pano_197.py` · `dilajan.pano.pano_durumu`
**doğrudan** çağrılır, kareler `dilajan.video.extract_timestamped_frames` ile üretilir
— yani ölçülen şey **üretimde koşacak kodun aynısıdır**, yeniden yazımı değil.

## Bulgu 1 — kural kalibre edildiği kamera görüşü DIŞINDA çöküyor

Yukarıdaki 74 klipllik ölçüm yalnızca pano sınıflarını kapsıyordu. Diğer 123 klip
eklenince:

| sınıf | n | ateşledi | oran |
|---|---|---|---|
| `Opened_Panel_Cover` **(hedef)** | 24 | 15 | 0,62 |
| **`Safe_Walkway_Violation`** | 25 | **17** | **0,68** |
| **`Unauthorized_Intervention`** | 25 | **13** | 0,52 |
| **`Normal/Safe_Walkway`** | 23 | **12** | 0,52 |
| `Closed_Panel_Cover` | 25 | 0 | 0,00 |
| `Authorized_Intervention` | 25 | 1 | 0,04 |
| `Safe_Carrying` · `Carrying_Overload` | 50 | 0 | 0,00 |

**MCC +0,845 → +0,270 · kesinlik 0,259.**

Desen belirleyici: pano sınıflarının **kamera görüşünde kural temiz**; gürültünün
tamamı **öteki çerçeveden** geliyor — bugün yaya yolu geofence'ini de öldüren
aynı iki-çerçeve olgusu. Sabit ROI orada panoya değil, başka bir karanlık makine
yüzeyine düşüyor.

Modül belgesine *"ROI tesise özgüdür"* yazmıştım. **Hafife almışım:** ROI **aynı
tesisin farklı kamera çerçevesinde bile** geçersiz.

## Bulgu 2 — çözünürlük önemli değil (doğrulandı, varsayılmadı)

Eşik tam çözünürlükte kalibre edilmişti; üretim kareleri `frame_max_side=768`
ile küçültüyor.

| kol | TP | FP |
|---|---|---|
| üretim (768) | 15 | 43 |
| tam çözünürlük (4096) | 15 | 47 |

Ortalama parlaklık küçültme altında korunuyor. **Üretim küçültmesi zarar vermiyor.**

## Düzeltme — GÖRÜŞ KİLİDİ

Bir ROI kuralı, kalibre edildiği kamera görüşü için tanımlıdır. Kilit bunu
zorunlu kılar: sahnenin kaba yapı imzası (16×9 medyan gri, z-normalize) ile
Pearson korelasyonu eşiğin altındaysa **kural hiç çalışmaz**.

Ölçülmüş ayrım (48 klip, iki çerçeve): görüş-içi **+0,938** · görüş-arası **+0,175**
→ 0,60 eşiği geniş marjla ayırıyor. Kalibrasyonda kapalı-pano kliplerinin imzaya
korelasyonu **min 0,949**.

Kalibrasyon: `scripts/pano_kalibre.py` → `panel_roi` · `panel_luma_esik` ·
`panel_gorus_imza`.

## Kilitli sonuç

| | kilitsiz | **kilitli** |
|---|---|---|
| TP | 15 | **15** |
| FP | 43 | **5** |
| FN | 9 | 9 |
| TN | 130 | **168** |
| kesinlik | 0,259 | **0,750** |
| duyarlılık | 0,625 | 0,625 |
| **MCC** | +0,270 | **+0,646** |
| Normal klipte yanlış alarm | 13/98 | **4/98** |

| sınıf | kilitsiz | kilitli |
|---|---|---|
| `Safe_Walkway_Violation` | 17/25 | **0/25** |
| `Unauthorized_Intervention` | 13/25 | **1/25** |
| `Normal/Safe_Walkway` | 12/23 | **3/23** |
| `Opened_Panel_Cover` (hedef) | 15/24 | **15/24** |

**Doğru tespitler hiç azalmadı** — kilit yalnızca sahte ateşlemeleri sildi.

Ön-kayıtlı kabul eşiği *"hedef dışı kliplerde yanlış pozitif artışı ≤ 5"* idi:
**5. Geçti.**

## Dürüstlük kayıtları

**1. Kalibrasyon verisi test kümesinin içinde.** Eşik (87,3) ve görüş imzası
25 `Closed_Panel_Cover` klibinden üretildi ve o klipler 197'nin içinde. Yani o
sınıftaki **0/25** kısmen inşa gereğidir. Kesinlik (0,750) bundan **etkilenmiyor**:
5 yanlış pozitifin hiçbiri o sınıftan değil. Ve görüş imzası, kalibrasyonda
kullanılmayan `Opened_Panel_Cover` kliplerini **doğru kabul ediyor** (15 ateşleme)
— yani görüş-içi genelleme kanıtı var.

**2. Duyarlılık 0,625, önceki 74-klip ölçümünden düşük.** Sebep ayarlanmadı,
açıklanıyor: eşik burada kalibrasyondan geldi (87,3), öncekinde kat-dışı LOO ile
(~89,2); ve üretim ~12 kare kullanıyor, önceki ölçüm 16. **Test kümesine bakarak
eşik veya kare sayısı ayarlanmadı** — bu, ölçülmemiş bir başlık üretirdi.

**3. Kalan 4 yanlış pozitif.** 3'ü `Safe_Walkway` (luma 75-81), 1'i
`Authorized_Intervention` (84,8). İlk üçü görüş kilidini **geçiyor** — yani o klipler
pano kamerasının görüşüne yeterince yakın. Görüş eşiğini yükseltmek bunları
kesebilir ama **test kümesine bakarak eşik seçilmeyecek**; bu, yeni veriyle
doğrulanması gereken bir pay olarak bırakılıyor.

## Dağıtım ayarı (tesisimiz)

```
DILAJAN_PANEL_ROI=0.08,0.55,0.21,0.73
DILAJAN_PANEL_LUMA_ESIK=87.3
DILAJAN_PANEL_GORUS_IMZA=<scripts/pano_kalibre.py çıktısı>
```

Varsayılan **boş = kapalı** (K2). Başka bir kamerada **yeniden kalibrasyon şart**.
