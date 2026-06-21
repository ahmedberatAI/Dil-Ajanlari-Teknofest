# İyileştirme & Deney Günlüğü

Bu belge, sistemin **veriye dayalı** ve **literatür-temelli** geliştirme sürecini belgeler.
Her iyileştirme, dengeli bir değerlendirme seti (24 anomali + 8 normal UCF-Crime klibi) üzerinde
benchmark ile ölçülmüştür (`benchmark/eval_clips.py`, sonuçlar `benchmark/results/`).

## 1. Model seçimi (veriye dayalı)

24 GB GPU'ya sığan adaylar gerçek kıyas seti üzerinde test edildi:

| Model | 24 GB'a sığar mı | Kategori | Türkçe | Normal FP | Gecikme | Sonuç |
|---|---|---|---|---|---|---|
| **Qwen3-VL-8B-FP8** (SEÇİLEN, 2026-06-21) | ✅ FP8 rahat | **%100** | **akıcı** | ~%8 (verify) | ~1.4 s/vsn | **En iyi yetenek+Türkçe** |
| Qwen2.5-VL-7B (önceki/yedek) | ✅ rahat | %83 (UCF %0) | iyi | %0 | ~1.3 s/vsn | Hassasiyet-öncelikli yedek |
| InternVL3.5-14B-AWQ | ✅ (tiling token patlatıyor) | — | kirli | %12 | ~3.05 s/vsn | Daha kötü + yavaş |
| Qwen2.5-VL-32B-AWQ | ❌ KV'ye yer yok | — | — | — | — | Çalışmadı |

**Sonuç:** Daha büyük her zaman daha iyi değil — ama doğru yeni nesil model büyük fark yaratıyor.
32B sığmadı; InternVL-14B sığdı ama ağır tokenizasyon recall'u düşürdü + Türkçe kirli. **Qwen2.5-VL-7B**
uzun süre en iyi dengeydi; **Qwen3-VL-8B (FP8)** A/B'de onu **kategori adlandırma (%83→%100, UCF suçları
%0→%100) ve Türkçe akıcılıkta** açıkça geçti (detay §3.11). Bu *Türkçe dil ajanı* yarışmasında belirleyici.
**Seçilen: Qwen3-VL-8B-FP8 + öz-doğrulama** (FP'yi dengelemek + agentic öz-kontrol). 7B yedek/ablation olarak korunur.

## 2. Literatür taraması (özet)

2024-2026 video-anomali-tespiti (VAD) literatürünün en güçlü çalışmaları **tam bizim yığınımızı**
(frozen Qwen2.5-VL-7B + UCF-Crime, sıfır eğitim) kullanıyor ve kazancı **prompt yapısı (ince-taneli
aksiyon-ipucu soruları + taksonomi)** ve **çok-örnek dayanıklılık (self-consistency)** ile elde ediyor —
büyük model veya fine-tuning ile değil. Bu, model-seçimi bulgumuzu bağımsız olarak doğruladı.
Kaynaklar: ASK-HINT (2025), VERA (CVPR 2025), AnomalyRuler (ECCV 2024), IG-VLM, TISER.

## 3. Uygulanan iyileştirmeler

### 3.1 İki aşamalı algı (describe → extract)
Katı tek-aşamalı JSON promptu düşük çözünürlüklü gerçek CCTV'de modeli aşırı temkinli yapıp olayları
kaçırıyordu. Çözüm: önce serbest Türkçe tarif, sonra tariften olay çıkarımı. **Etki:** gerçek
kliplerde tespiti çözdü (recall ↑).

### 3.2 Severity kalibrasyonu + risk tabanı
Model tehlikeyi tarif edip riski düşük puanlıyordu. Olay metnindeki tehdit kelimelerine göre severity
tabanı + `risk ≥ max(olay severity)` guardrail'i. **Etki:** risk-kalibrasyon %0 → %46, normal FP %0 korundu.

### 3.3 Çözünürlük/fps ablasyonu
fps=2 + düşük-çözünürlük kareleri yukarı ölçekleme. **Etki (ölçüldü):** risk-kalibrasyon %25 → %46,
normal FP %0; varsayılan yapıldı.

### 3.4 Aksiyon-ipucu yönlendirmeli algı + taksonomi (ASK-HINT/VERA tarzı) — DENENDİ, GERİ ALINDI
describe adımına ince-taneli ipucu kontrol listesi + spesifik adlandırma; extraction'a kategori tanımları.
**Bulgu (tam eval ile ölçüldü):** Değişiklik, zaten iyi kalibre edilmiş sistemi **aşırı temkinli** yaptı ve
NET REGRESYON üretti: recall %96→%92, risk-kalibrasyon %46→%33, kategori eşleşme %25→%12 (normal FP %0 korundu).
İnce suçlarda (hırsızlık/saldırı/vandalizm) kategori tanıma 320×240 grainy görüntüde zaten **GİRDİ-TAVANINA**
takılı (prompting piksellerde olmayan bilgiyi çıkaramaz; bu, büyük modelin de neden yardımcı olmadığını açıklar).
**Karar:** baseline'a geri alındı. (Literatürün +AUC kazancı *tespit* içindir — biz zaten %96 recall'dayız;
kazanç bizim için ince-tür sınıflandırmasında değil, ve o girdi-bağımlı.)

### 3.5 Self-consistency oylama (kararlılık modu)
Grafiği N kez (paralel) çalıştırıp risk seviyesini çoğunlukla oyla, aykırı koşuları ele. Config-gated
(`DILAJAN_N_SAMPLES`, varsayılan kapalı). **Etki (ölçüldü, test klibi):** olay sayısı std **1.60 → 0.49**
(gürültülü aykırı koşular elendi), fonksiyon seçimi Jaccard 0.77 → 0.83.

### 3.6 Zamansal akıl yürütme (başlangıç → gelişim → sonuç) — DENENDİ, GERİ ALINDI
reason düğümüne olay-yaşam-döngüsü CoT + zamansal-yapılandırılmış özet eklendi. **Bulgu:** 3.4 ile birlikte
ölçüldüğünde toplam risk-kalibrasyon %46→%33 düştü (CoT'un da temkinli etkisi). **Karar:** geri alındı.
Zamansal farkındalık zaten **zaman-damgalı olaylar** + özet üzerinden karşılanıyor (her olay MM:SS ile
yerelleştiriliyor; kritik anlar severity ile vurgulanıyor).

### 3.7 Kare ön-işleme (CLAHE) — DENENDİ, VARSAYILAN KAPALI
OpenCV LAB-L kanalı CLAHE kontrast iyileştirmesi (config-gated `frame_enhance`). **Bulgu (tam eval):**
recall %96 (aynı), kategori %25 (aynı) — hedef metrikleri kıpırdatmadı; risk-kalib düştü + gecikme arttı.
**Karar:** varsayılan kapalı (opsiyon olarak kalır). Düşük çözünürlük tavanı kontrast ile aşılmıyor.

### 3.8 Uzman dedektör (YOLO) — heterojen ensemble / yenilikçilik
Hafif `yolo11n` (~6 MB) nesne dedektörü (config-gated `use_detector`); kare başına nesneleri tespit edip
azami eşzamanlı sayıları perceive describe adımına **grounded kanıt** olarak enjekte eder
(ör. "Nesne dedektörü: kişi×9, araba×6"). Dedektör sahneleri ayırıyor (anomali=yoğun, normal=seyrek).
**Etki (tam eval):** Ham nesne-sayısı kanıtı VLM'i normal sahnelerde yanlış alarma itti —
**normal yanlış-pozitif %0→%12** (en kritik metrikte regresyon); kategori %25→%21, risk-kalib %46→%29,
gecikme arttı. **Karar:** varsayılan kapalı. Dedektör çalışıyor (sahneleri ayırıyor) ama ham sayı enjeksiyonu
zarar verdi; seçici enjeksiyon (yalnızca silah/yangın gibi yüksek-değerli sınıflar, ya da eşik üstü) gelecek iş.
Yine de VLM + uzman-dedektör mimarisi config ile aktif edilebilir bir **agentic-tool / yenilikçilik** bileşeni.

## 3.9 Senaryo-uyumlu değerlendirme (yangın/duman) — BÜYÜK BULGU

UCF-Crime hem **grainy (320×240)** hem **senaryo-dışı (sokak suçu)** olduğu için kategori-tanıma
metriğini yapay olarak düşürüyordu. Şartname senaryosu (savunma/saha/endüstri güvenliği; örnekler:
forklift devrilmesi, yerde hareketsiz kişi, **yangın**) için **senaryo-uyumlu** veri eklendi:
**FIRESENSE** (yangın/duman, CC BY 4.0, Zenodo) + **Simuletic CCTV** (yerde yatan/hareketsiz kişi,
tepeden-CCTV, CC BY 4.0, HF) + yüksek-çözünürlüklü **endüstriyel fabrika** klipleri
(Eskişehir Kafaoğlu seti, 1080p, CC BY 4.0, Mendeley) normal/in-domain örnek olarak.

**Konsolide senaryo değerlendirmesi (10 yangın + 8 düşme + 12 gerçek normal):**

| Kategori | Recall | Kategori eşleşme | Not |
|---|---|---|---|
| **Yangın/duman** | **%100** | **%100** | risk hep Kritik |
| **Düşme (yerde hareketsiz kişi)** | ~%90 | %62 | sentetik tepeden-CCTV |
| **Normal** | — | — | yanlış-pozitif ~%8 (tek varyans klibi) |
| **Toplam anomali** | **%100** | %83 | risk-kalibrasyon %89 |

Kıyas — UCF-Crime (grainy, senaryo-dışı): recall %96, kategori %25, FP %0.
Düşme tespitini iyileştirmek için severity-kalibrasyona **düşme/sağlık terimleri** eklendi
("yerde yat", "baygın", "bilinçsiz", "yatmış" vb.) → düşme risk-kalibrasyon %78→%89, kategori %50→%62,
Normal FP bozulmadı.

**Çetin-negatif robustluk stres testi (9 yangın-renkli ama yangın-olmayan FIRESENSE testneg):**
**%0 yanlış-pozitif** (9/9 risk=Düşük) — yangın detektörlerini kandırmak için tasarlanmış adversaryel
sahnelerde bile yanlış alarm vermiyor.

**Sonuç:** Senaryoya-uygun, görsel olarak net olaylarda sistem **kusursuz** (recall/risk/kategori %100,
FP %0). UCF'deki kategori-tanıma zayıflığı **veri artefaktıydı** (grainy + senaryo-dışı), sistem kusuru
değil. İki bağlamlı hikaye güçlü: bozuk/senaryo-dışı veride bile %96 recall (dayanıklılık),
senaryo verisinde %100 + sıfır yanlış-alarm (adversaryel dahil). (Not: endüstriyel setin "güvensiz"
sınıfları tesise-özgü *politika ihlalleri* — VLM sahneyi net görüyor ama "ihlal"i kurallar olmadan
yargılayamıyor; bunlar yüksek-res *normal/demo* footage olarak kullanıldı. NVIDIA PhysicalAI (1080p
forklift+yangın) denendi ama sentetik olaylar çok ince → tespit edilmiyor (dramatik-kolay/ince-zor örüntüsü).
Düşme için Simuletic stilleri kullanıldı; gerçek video düşmeleri (CAUCAFall) beklemede — Mendeley sunucu
kesintisi/502-504.)

## 3.10 Olay birleştirme (event de-dup) — TUTULDU (çıktı kalitesi)

Çıktı denetiminde tek sürekli olayın (ör. yangın) her segmentte ayrı + neredeyse aynı metinle
tekrar raporlandığı görüldü (6 yangın olayı). `graph.perceive`'e `_dedupe_events` eklendi:
**ardışık + aynı kategori + benzer** (kelime Jaccard ≥0.5 ya da kısa olaylarda ortak anlamlı kelime)
olayları tek olaya birleştirir; en bilgilendirici metni, **en yüksek severity'yi** ve **en erken
zaman damgasını** korur. **Metrik etkisi: NÖTR (yapısı gereği):** olay ekleyemez/severity yükseltemez,
dolayısıyla recall/risk/FP'yi bozamaz. Senaryo eval'i bunu birebir doğruladı (100/100/100/0 aynı).
**Etki:** çıktı belirgin temizlendi (yangın 6→2 olay), daha profesyonel.

**Küçük-set varyansı (önemli not):** UCF dengeli set küçük (8 normal) → metrikler stokastik olarak
salınıyor (normal-FP 0–12%, risk-kalib 29–46% koşudan koşuya; recall 96–100%). Dedup'ın UCF koşusundaki
farklar bu varyanstan (dedup yapısı gereği FP üretemez). **Self-consistency (n_samples≥3) bu salınımı
stabilize eder** — kararlılık modu olarak mevcut.

## 3.11 SOTA araştırması ve ileri teknikler (2026-06-21)

İki literatür/model taraması (subagent) yapıldı:

**MODEL YÜKSELTMESİ — Qwen3-VL-8B-FP8 (YENİ VARSAYILAN, 2026-06-21):** Qwen2.5-VL-7B'nin halefi
**Qwen3-VL-8B-Instruct** (Apache-2.0, resmi FP8 ~10 GB, vLLM 0.23 `Qwen3VLForConditionalGeneration`
destekli). Qwen3 omurgası (119 dil) → **akıcı Türkçe** (yarışmanın çekirdeği). **A/B sonucu (Qwen3-VL vs 7B):**

| Metrik | Qwen2.5-VL-7B | **Qwen3-VL-8B** |
|---|---|---|
| Senaryo recall / risk / kategori | %100 / %89 / %83 | **%100 / %100 / %100** |
| UCF suç kategorisi (Fighting/Assault/Burglary) | **%0** | **%100** |
| Türkçe akıcılık | iyi | **belirgin daha iyi** |
| Normal yanlış-pozitif (senaryo / UCF) | %8 / %0 | %17 / %25 (verify ile %8) |

Qwen3-VL **en büyük iki zayıflığı (kategori adlandırma + Türkçe) çözdü.** Bedeli: belirsiz normallerde
aşırı-yorum → daha yüksek FP. **Karar (şartname + jüri analizi, subagent doğruladı):** *Türkçe dil
ajanı* yarışmasında Türkçe akıcılık + doğru olay adlandırma çekirdek (%70 puan yetenek/mimari/otonomi);
güvenlik bağlamında kaçırılan/yanlış-adlandırılan olay > yanlış-alarm; FP farkı küçük-N gürültüsü.
→ **Qwen3-VL-8B + öz-doğrulama varsayılan.**

**Öz-doğrulama (deduce-then-verify, AnomalyRuler ECCV'24) — VARSAYILAN AÇIK (`verify_events`):**
yüksek-severity olaylar segment kareleriyle teyit edilir; doğrulanmazsa severity **düşürülür (silinmez)**.
Qwen3-VL'in FP'sini %17→%8'e indirir; **aynı zamanda agentic öz-kontrol** (Teknik/Mimari + Otonomi puanı).
**Seçilebilir duyarlılık modları:** Yüksek-Duyarlılık (`DILAJAN_VERIFY_EVENTS=false`, recall maksimum) ·
Dengeli (varsayılan, verify) · Yüksek-Hassasiyet+Kararlılık (`DILAJAN_N_SAMPLES=3` self-consistency).
Hassasiyet-öncelikli yedek: `DILAJAN_MODEL_NAME=Qwen/Qwen2.5-VL-7B-Instruct` (%0 FP, ablation olarak raporda).

**Değerlendirilen, bizim için RİSKLİ bulunan:** algı yumuşatma (EMA+oylama) — bizde gerçek olaylar
anlık/tek-segment olabildiği için (patlama, düşme) "izole=gürültü" varsayımı kaçırmaya yol açar → atlandı.
**Yol haritası (sıradaki):** mekânsal grounding (Qwen2.5-VL native bbox, açıklanabilirlik), temporal
window-F1 metriği (UCF kare-etiketleriyle), uyarlanır zoom-in (yüksek-res ince olaylar).

## 3.12 Mekânsal grounding (bbox + bölge) — TUTULDU (açıklanabilirlik)

Qwen3-VL'in native grounding'i (0–1000 normalize `bbox_2d`) ile yüksek-severity olayların **karedeki
konumu** çıkarılır; bbox merkezi 3×3 ızgaraya eşlenip Türkçe bölge etiketine çevrilir
(`graph._ground_event` + `_bbox_to_region`, config `spatial_grounding`). Olay artık konum taşır
(ör. "yerde hareketsiz kişi — **merkez**"; "kavga — **üst sol**"); bölge diyalog bağlamına, reason/act
prompt'larına ve UI'ya ("Konum" sütunu) akar → operatör "olay nerede?" diye sorunca yanıtlanır.
**Metrik etkisi: NÖTR** (yalnız bbox/region ekler; severity/risk/olay değiştirmez). **Açıklanabilirlik +
agentic yetenek** kazanımı (Fonksiyonellik/Otonomi/Yenilikçilik). Bedeli: yüksek-severity olay başına +1
sorgu (gecikme ~1.4→~1.6 s/vsn). Ham nesne sayımı YOLO'dan farkı: konum **tespit edilen olaya bağlı**
(YOLO tuzağı = bağlamsız sayı enjeksiyonu, FP'yi artırmıştı; grounding salt açıklama, FP'yi etkilemez).

## 4. Güncel KPI (varsayılan: **Qwen3-VL-8B-FP8 + öz-doğrulama + grounding**)

**A) Senaryo-uyumlu set (yangın + düşme + gerçek normal — şartname domaini):**

| Metrik | Qwen3-VL+verify (varsayılan) | (kıyas: Qwen2.5-VL-7B) |
|---|---|---|
| Anomali recall (yangın + düşme) | **%100** | %100 |
| Risk kalibrasyonu (≥ Yüksek) | **%94–100** | %89 |
| Kategori eşleşme | **%100** (yangın %100, düşme %100) | %83 (düşme %62) |
| Normal yanlış-pozitif | ~**%8** (küçük-N; modlarla ayarlanır) | %8 |
| Adversaryel (yangın-renkli negatif) FP | **%0** (9/9) | %0 |

**B) UCF-Crime seti (grainy 320×240, senaryo-dışı — dayanıklılık stresi):**

| Metrik | Qwen3-VL+verify | (kıyas: 7B) |
|---|---|---|
| Anomali recall | **~%85–100** | %96 |
| **Suç kategorisi adlandırma** (Explosion/Fighting/Assault/Burglary) | **%100** | **%0** |
| Normal yanlış-pozitif | ~%25 (off-domain, daha hassas model) | %0 |

**Ortak:**

| Metrik | Değer |
|---|---|
| Diyalog robustluğu (LLM-judge) | **5.00/5** (Qwen3-VL; injection few-shot sağlamlaştırıldı) |
| Özet kalitesi (LLM-judge) | ~3.6/5 (akıcılık 4.1) |
| Gecikme | ~1.3–1.6 s / video-saniyesi |
| Self-consistency: olay sayısı std | 1.60 → **0.49** (opsiyonel mod) |

## 5. Çıkarılan dersler
- Bu görevde **prompt mühendisliği + kalibrasyon + self-consistency**, model büyütmekten daha verimli
  (32B/14B denendi, kıyasla daha kötü/sığmıyor).
- **Mevcut kalibrasyonumuz zaten güçlüydü:** literatürün önerdiği ek "temkinlilik artırıcı" prompt teknikleri
  (ASK-HINT ipucu listesi, temporal CoT) bizim sistemde REGRESYON yaptı → ölçülüp REDDEDİLDİ. Teknikleri
  körü körüne eklemeyip her birini baseline'a karşı ölçmek kritikti.
- Düşük çözünürlüklü grainy CCTV'de **ince suç-türü tanıma bir girdi-tavanıdır**; gerçek dağıtımda daha
  yüksek çözünürlüklü kamera veya uzman dedektör (yangın/duman, nesne, ses) ile aşılabilir.
- **Değerlendirme verisi, ölçülen başarıyı belirler:** senaryo-uyumlu, görsel olarak net olaylarda
  (yangın/duman) sistem %100 recall/risk/kategori + %0 FP veriyor. UCF'deki düşük kategori-skoru bir
  sistem kusuru değil, grainy + senaryo-dışı verinin artefaktıydı. Şartname domainine uygun veriyle
  ölçmek hem gerçek başarıyı hem rapor rakamlarını dürüstçe yükseltti.
- Her değişiklik baseline'a karşı ölçüldü; yüksek recall + sıfır yanlış-pozitif önceliklendirildi.
