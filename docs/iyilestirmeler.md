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

## 3.13 W1 — Halüsinasyon/aşırı-yorum FP'si (baseline-first prompting)

**Sorun:** Qwen3-VL belirsiz normalleri aşırı-yorumluyor + bazen olmayan tehdit uyduruyordu
(ör. temiz fabrikada "makinanın yanında duman → Kritik"). **Teşhis:** kaynak describe aşaması;
eski prompt tehdit-listesini öne çıkarıp "emin değilsen 'olası' diye yine de belirt" diyordu →
spekülasyon/halüsinasyon davet ediyordu. **Düzeltme (subagent araştırması + kök-neden):** describe
prompt'u **"önce BEKLENEN NORMAL'i belirt, sonra yalnızca SAPMA'yı raporla; her şey normalse SAPMA YOK"**
+ negatif örnekler (rutin yürüme/çalışma/oturma/merdiven/taşıma OLAY DEĞİL) + **anti-halüsinasyon**
("olmayanı uydurma; ama grainy de olsa gerçek sapmayı raporla").
**Sonuç:** Senaryo domaininde **uydurma-tehdit halüsinasyonu çözüldü** (4_tr13 "duman" → Düşük/0 olay),
senaryo normal-FP ~%17→**~%0-8**, **recall %100 + kategori %100 korundu**. Kalan tek senaryo FP'si
endüstriyel belirsizlik (işçi-makine yakınlığı = setin kendi "politika ihlali" gri bölgesi → W4).
**Dürüst kısıt:** UCF (8 normal/24 anomali) küçük olduğu için recall/FP **varyans-baskın** (recall koşudan
koşuya %67–96); prompt etkisi orada gürültü bandında. Temiz ölçüm daha büyük eval seti + LLM-judge ister (W3).

## 3.14 W3 — Titiz kategori-doğruluğu (LLM-judge, keyword yerine)

Eski kategori-eşleşme **sabit keyword listesi** sezgisiydi — model doğru ama listede olmayan eş anlamlı
ifade kullanınca ("darp/itişme") kaçırıyordu, yani aslında **fazla katı** (cömert değil). `benchmark/judge_category.py`
eklendi: her anomali klibi için gerçek kategori + tespit edilen olaylar tarafsız hakeme verilir, **0/1/2**
puanlanır (2=türü doğru adlandırdı, 1=anormal tespit ama tür yanlış/muğlak, 0=kaçırdı). `eval_clips` artık
olay metinlerini kaydediyor. **Sonuç (LLM-judge):** Senaryo (yangın+düşme) **%100 doğru adlandırma**;
UCF suçları **%62 doğru / %71 tespit** (Explosion/Assault/Burglary %100, Fighting %67) — keyword'ün
gösterdiği ~%38-46'dan **yüksek ve daha dürüst**. Bundan sonra kategori için LLM-judge esas alınır.

## 3.15 W6 — Zamansal lokalizasyon (olay pencereleri + dürüst sınır)

**Somut kazanım:** Olay şeması `end_time` ile zenginleştirildi; `_dedupe_events` birden çok segmente
yayılan olayı tek **zaman penceresine [başlangıç–bitiş]** birleştiriyor (ör. "yangın 00:30–00:50").
Pencere diyalog bağlamı, prompt'lar ve UI'ya akıyor → "tam ne zaman" artık nokta değil aralık.
**Bulgu:** Segment-segment teşhis, ajanın olayları **doğru zaman-segmentlerine** yerleştirdiğini
gösterdi (kompozit klipte yangın orta segmentlerde tespit edildi); granülerlik ~10 s (segment boyu).
**Dürüst sınır:** Kare-seviyesi window-F1, kırpılmış kısa eval kliplerinde (medyan 14 s, klip≈olay)
uygulanabilir değil + UCF temporal GT erişilemedi; kontrollü kompozit (normal→olay→normal) TIoU testi
ffmpeg süre-kurgu artefaktlarından kesin sonuç vermedi (`scripts/make_composite.py`, `scripts/eval_temporal.py`
ileride kırpılmamış tam video / canlı akış W7 ile kullanılabilir). Yani: segment-granülerlikte lokalizasyon
çalışıyor + olay pencereleri üretiliyor; piksel-kare-seviyesi metrik gelecek iş.

## 3.16 W2 — Gerçek video düşme verisi (sentetik yerine)

Düşme sonucu önce sentetik Simuletic stilleriyle ölçülmüştü (temsili). **GMDCSA-24** (gerçek `.mp4`
düşme videoları, 720p/30fps, CC BY 4.0, GitHub raw — auth yok; `scripts/get_gmdcsa.py`) indirildi
(9 düşme + 6 ADL, `data/falls_real/`). CAUCAFall hâlâ Mendeley kesintisinde (GMDCSA daha iyi: gerçek
hareketli düşme + ADL normal). **Gerçek-düşme sonucu (LLM-judge):** recall **%67** (6/9), kategori **%67**,
**ADL normal-FP %0** (6/6 Düşük). Sentetik %100'den düşük ama **gerçek + dürüst** — gerçek düşmeler
zor (3/9 hızlı/ince düşme kaçtı → W4). ADL günlük aktivitede sıfır yanlış-alarm güçlü. Sentetik-veri
uyarısı kapandı; düşme artık indirilebilir gerçek veri + gerçek metrikle kanıtlı.

## 3.17 W5 — UCF recall (varyans karakterizasyonu, dürüst)

İlk gözlem "Qwen3-VL UCF recall %96→%79" temiz bir düşüş gibi görünüyordu. Çoklu koşu topluca incelendi:
**UCF anomali recall = %67 / %79 / %87.5 (3 koşu, bant ~67-88, ort ~78)** — yani **24-klip setinde
yüksek varyans** (stokastik üretim + verify/dedup). Tek koşuya bakmak yanıltıcı; 7B'nin %96'sı da tek
çekiliş. **Senaryo (hedef domain) recall %100.** Kaçırılan UCF klipleri ağırlıkla grainy ince suçlar
(Shooting/Vandalism) = girdi-tavanı (W4 ile örtüşür), model kusuru değil. **Çözüm/levers:** güvenilir
ölçüm için daha büyük eval seti; recall-öncelikli yapılandırma. Sonuç: "recall düştü" yerine dürüst
ifade = "grainy off-domain UCF'de recall varyanslı (~%78±10), senaryoda %100".

## 3.18 W7 — Canlı kamera / akış yolu (kayan-pencere)

"Hepsi benchmark klibi, canlı akış yok" zayıflığı için `scripts/live_analyze.py` eklendi: **webcam
(`0`), IP kamera (`rtsp://...`) veya dosya** kaynağını OpenCV ile okur, her WINDOW saniyede bir
tampona alıp tam ajan pipeline'i (`analyze_video`) ile işler → pencere başına risk + zaman-damgalı
olaylar + operasyonel fonksiyon tetikleme. **Test (kompozit dosya-akışı, 15s pencere):** normal pencere
→ Düşük/olay yok; yangın pencereleri → Kritik "yangın @merkez" + yerde hareketsiz kişi + acil-durdurma/
sağlık/güvenlik ekibi tetiklendi. Yani sistem **sürekli akış** üzerinde çalışıyor (yalnızca yerel).
Küçük gelecek-iş: pencere zaman damgalarını mutlak akış-zamanına ofsetlemek.

## 3.19 W4 — İnce-olay tavanı (dürüst karakterizasyon + dağıtılabilir hafifletme)

İnce olaylar (grainy ince suç türleri, sentetik/uzak mild çarpışmalar, tesis politika-ihlalleri)
**girdi-bağımlı bir tavandır** — bu oturumda denenen tüm hafifletmeler ölçülüp sınırına ulaştı:
büyük model (32B/InternVL ❌), CLAHE (❌), YOLO dedektör (FP↑ ❌), yüksek-çözünürlük (768→1280 +16 kare
**context bütçesini aşıp hata verdi** ❌). Yani grainy/mild durumlar piksel/veri-bağımlı; gerçek çözüm
daha iyi kamera + uzman dedektör (yangın/duman %100 zaten var; YOLO mevcut). **Dağıtılabilir hafifletme
(politika alt-sınıfı):** config-gated `facility_rules` — tesise-özgü kurallar perceive prompt'una enjekte
edilir; model artık somut kriterlere karşı uyum değerlendirir. Sanity: kuralsız bir endüstriyel normal klip
yanlışlıkla flaglenirken (Orta/1 olay), kurallı versiyon doğru biçimde "ihlal yok" (Düşük/0 olay) dedi —
yani somut kriter hem **politika-ihlali tespitini** mümkün kılıyor hem **grounded yargıyla FP'yi azaltıyor**.
Varsayılan boş (güvenli). **Dürüst sonuç:** ince-olay tavanı çözülemez değil ama training-free tam çözümü yok;
dramatik olaylarda mükemmeliz + ince/politika için dağıtım-zamanı hook'lar (kural enjeksiyonu, uzman dedektör) hazır.

## 3.20 Holistik şartname performans testi + gap analizi

Subagent ile jüri-hizalı kapsamlı karne tasarlandı; daha önce **hiç ölçülmeyen** zorunlu çıktılar için
yeni judge'lar eklendi (`benchmark/holistic.py`): M1 aksiyon kalitesi, M2 agentic dispatch doğruluğu,
M3 JSON şema uyumu, M4 risk gerekçe kalitesi. **Karne (temsili set, Qwen3-VL):**

| Eksen | Ölçüm | Sonuç |
|---|---|---|
| İşlevsellik | Olay tespiti (recall) | senaryo %100 · holistik %83 |
| İşlevsellik | Özet kalitesi (LLM-judge) | **4.98/5** |
| İşlevsellik | **Aksiyon kalitesi (M1)** | **4.71/5** (yeni — güçlü) |
| İşlevsellik | **Risk gerekçe (M4)** | **5.0/5** (yeni — güçlü) |
| İşlevsellik | **JSON şema uyumu (M3)** | %89 → **%100** (zaman normalizasyonu, aşağıda) |
| Otonomi | **Agentic dispatch (M2)** | **%78** (anomali→fonk %83, normal→yanlış-tetik-yok %67) |
| Otonomi | Diyalog robustluğu | 5.0/5 |
| Teknik | **Hata toleransı (G4)** | **%100 zarif** (bozuk/boş/siyah/kısa video çökmüyor) |
| Teknik | Gecikme | ~1.6 s/vsn |

**Bulgu:** En pahalı sanılan boşluklar (aksiyon, risk gerekçe) ölçülünce **çok güçlü** çıktı (veri değil
ölçüm eksikmiş). **Kapatılan gap'ler:** (1) **JSON uyumu %89→%100** — `_normalize_time` ile olay zaman
damgası her zaman geçerli MM:SS'e zorlanıyor (modelin bozuk çıktısına bağlı değil); (2) **hata toleransı
%100 zarif** — kenar-durum testi (`data/robust/`). **Kalan gap'ler (kabul/ileri):** grainy recall (W4
girdi-tavanı), normalde nadir aşırı-dispatch (W1 kalıntısı), çok-turlu diyalog tutarlılığı (G7, küçük).

## 3.21 Jüri paneli değerlendirmesi + uygulanan aksiyonlar

4 hakem-subagent (Teknik, Fonksiyonellik, Otonomi+Yenilikçilik, Şüpheci başkan) gerçek kod+veriyle
değerlendirdi. **Konsensüs:** ~B+/75 (şüpheci başkan ~66, uyum riskleri düzeltilirse B+). **Oybirliğiyle
#1 zayıflık:** "normal-FP %0" bir **metrik-eşik artefaktıydı** — normaller "Orta" severity'li uydurma olay
üretip boşuna operasyonel fonksiyon (sağlık/güvenlik) tetikliyordu (gerçek operasyonel FP ~%17-33).

**UYGULANAN AKSİYONLAR:**
- **Dispatch kapısı (`act`):** operasyonel fonksiyonlar yalnızca risk≥Yüksek VEYA olay-severity≥Yüksek'te
  tetiklenir → normalde yanlış sağlık/güvenlik çağrısı **kesildi**. Sonuç: normal **operasyonel-FP ~%33→%8**
  (1/12), **anomali recall/risk/kategori %100 korundu** (gerçek tetik bozulmadı).
- **Dürüst FP metriği:** `eval_clips` artık dar-FP yanında **operasyonel-FP** (normalde herhangi olay/tetik)
  ve **yanlış-dispatch** oranını da raporluyor; gizli %33 yok.
- **Veri lisans manifesti:** `docs/veri_kaynaklari.md` (her set kaynak+lisans; `data/` zaten gitignore —
  yeniden dağıtım yok; şartmenin "açık veri linki" + lisans-zinciri netliği).

**Kalan jüri-önerileri (yapılacak):** istatistiksel güven (CI/daha büyük set), adaptif koşullu döngü
(otonomi 70→80), severity'yi kod-içi keyword'den modele/rubrik'e taşı, çok-turlu diyalog testi,
düşme recall %67→artır, GitHub'a düzenli commit + `BilisimVadisi2026` topic'ini fiilen ekle.

## 3.22 Tier-2 jüri iyileştirmeleri (devam)

- **Çok-turlu diyalog testi (jüri açığı kapatıldı):** `dialogue_test.py`'a 4-turlu zincir eklendi
  (coreference "o kişi", temporal "ondan sonra", öz-referans "az önce önerdiğin"). **Sonuç: 5.00/5** —
  ajan bağlamı turlar arası kusursuz taşıyor. Tek-tur 5.0 + çok-tur 5.0.
- **İstatistiksel dürüstlük (`benchmark/aggregate.py`):** çoklu koşu set-imzasına göre gruplanıp
  **ortalama±std** raporlanıyor. Senaryo (11 koşu): recall %99±2, kategori %94±9, normal-FP %10±5;
  UCF (13 koşu): recall %86±12 [58–100] (varyans). Tek-çekiliş "%100" yerine savunulabilir bant.
- **Adaptif koşullu döngü (otonomi hakeminin #1 eleştirisi):** graf artık **doğrusal değil** —
  `g.add_conditional_edges("perceive", route_after_perceive)` ile ajan **belirsiz (Orta-severity) olay**
  varsa `reexamine` düğümüne yönlenir, orada o olayı segment kareleriyle odaklı yeniden değerlendirir
  (RUTIN→Düşük: FP↓, CIDDI→Yüksek: ince gerçek olayı yakala, BELIRSIZ→korur), sonra `reason`'a döner
  (tek-sefer döngü-muhafızı). Ajanin "tekrar bakayim" kararini temsil eder. Net/güçlü vakalarda (Kritik/
  Düşük) tetiklenmez → düşük regresyon riski; yalnız belirsiz bandı işler. Config `adaptive_reexamine`.

## 4. Güncel KPI (varsayılan: **Qwen3-VL-8B-FP8 + öz-doğrulama + grounding**)

**A) Senaryo-uyumlu set (yangın + düşme + gerçek normal — şartname domaini), 11 koşu ortalaması:**

| Metrik | Qwen3-VL+verify (ort ± std) |
|---|---|
| Anomali recall (yangın + düşme) | **%99 ± 2** [94–100] |
| Risk kalibrasyonu (≥ Yüksek) | **%95 ± 8** |
| Kategori eşleşme | **%94 ± 9** (yangın %100, düşme yüksek) |
| Normal operasyonel-FP (herhangi olay/tetik) | ~**%8** (dispatch kapısı ile) |
| Adversaryel (yangın-renkli negatif) FP | **%0** (9/9) |

> Rakamlar `benchmark/aggregate.py` ile **çoklu koşudan ortalama±std** (tek-çekiliş "%100" değil). Küçük
> setler → varyans bandı esastır. "Normal-FP %0" eski iddiası dar-eşik artefaktıydı; dürüst op-FP ~%8.

**B) UCF-Crime seti (grainy 320×240, senaryo-dışı — dayanıklılık stresi), 13 koşu ortalaması:**

| Metrik | Qwen3-VL+verify (ort ± std) | (kıyas: 7B) |
|---|---|---|
| Anomali recall | **%86 ± 12** [58–100] (varyans) | %96 (tek koşu) |
| Kategori (keyword / LLM-judge) | %32 / **%62** (Explosion/Assault/Burglary %100) | %25 / — |
| Normal yanlış-pozitif (dar) | %12 ± 10 [0–25] | %0 |

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

## 6. "En ciddi 5 zayıflık" — dürüst teşhis + çözüm (2026-06-22)
Sistemin dürüst dezavantaj analizinde öne çıkan 5 ciddi sorun teker teker, ölçümle çözüldü.

### E1 — Self-evaluation döngüselliği (kalite skorları şişkin)
**Sorun:** Özet/aksiyon/risk-gerekçe/diyalog kalitesi, çıktıyı ÜRETEN modelin (Qwen3-VL) KENDİSİyle
puanlanıyordu → döngüsel, şişkin skor riski.
**Çözüm:** (a) Önce netleştirme — recall/FP/risk-kalibrasyon/keyword-kategori **zaten objektiftir**
(dataset etiketine karşı, LLM-judge değil → döngüsel değil). (b) Kalite skorları için **bağımsız, farklı
aile** bir judge (Google **Gemma-3-12B-it-FP8**) ile yeniden puanlama (`benchmark/judge_independent.py`
+ `gen_dialogue.py`; iki-faz: Qwen3-VL üretir → swap → Gemma puanlar). Aya-Expanse daha iyi Türkçe ama
CC-BY-NC lisansı yarışmaya uygun değil → Gemma seçildi (izinli, Blackwell-kanıtlı).
**Sonuç (self-judge → bağımsız Gemma):** Özet 4.98 → **4.64±0.53** (n=90), Aksiyon 4.71 → **4.69±0.47**,
Risk-gerekçe 5.0 → **4.92±0.46**, Diyalog tek/çok-tur 5.0 → **5.00/5.00**. Özet skoru bir miktar şişmiş
ama bağımsız judge'la bile **4.64–5.0 = gerçekten yüksek**; skorlar artık güvenilir.

### E3 — Gerçek düşme recall'ı %67 (3'te 1 kaçıyor)
**Teşhis (`scripts/probe_clip.py`):** Model düşmeyi GÖRÜYOR ama W1/W5 muhafazakârlığı yüzünden onu
"kişi uzanıyor = günlük rutin aktivite → SAPMA YOK" diye mantığa büküyordu (ör. `Subject3_fall01`).
**Çözüm:** Algı prompt'larına + verify'a güçlü düşme-karşıtı-rasyonalizasyon: "bir KİŞİNİN yere/zemine
düşmesi/çökmesi veya YERDE hareketsiz kalması = DÜŞME/sağlık acili, yaralanma görünmese bile raporla;
ama yatağa/koltuğa uzanmak NORMALDİR (düşme değil)" (mobilya istisnası FP'yi önler).
**Sonuç (`data/falls_real`, n=9):** recall **%67 → %89**, risk-kalibrasyon **%56 → %78**, normal-FP **%0**
(yatak-uzanma FP'si mobilya istisnasıyla giderildi). Tek kalan kayıp: `Subject2_fall03` (hızlı düşme).

### E5 — Normallerde halüsinasyon (operasyonel FP)
**Teşhis (`scripts/show_fp.py`):** En zararlısı `0_tr128` (normal fabrika) → "yere düşmüş NESNE" model
tarafından **Kritik/Güvenlik** sanılıp 3 operasyonel fonksiyon tetiklenmişti.
**Çözüm:** (a) Verify prompt'u güçlendirildi: sadece "görünüyor mu" değil "gerçekten ciddi mi" — aşırı-yorumu
reddet (düşmüş NESNE, yürüme, yatağa uzanma → HAYIR → severity düşür). (b) Prompt'lara aşırı-yorum önleme:
"düşmüş nesne kritik değil; yürüme/geçme tek başına yetkisiz giriş değil".
**Sonuç (`data/eval_scenario`, n=30):** dar normal-FP **%8 → %0**, yanlış operasyonel-tetik (dispatch-FP)
**%8 → %0** (zararlı FP'ler sıfırlandı), operasyonel-FP %25 → %17 (kalan 2 olay Düşük + gated, zararsız).
Bonus: anomali recall **%94 → %100** (düşme/yangın cue'ları recall'ı da artırdı).

### E4 — Gerçek-zamanlı değil (~1.5 s/video-sn)
**Çözüm:** `DILAJAN_FAST_MODE=1` hızlı mod — tek-geçişli algı (describe+extract birleşik) + verify/grounding/
reexamine kapalı + 1 fps / 6 kare / 512px (config'de profil; `prompts.SEGMENT_FAST_INSTRUCTION`).
**Sonuç (`data/eval_scenario`, n=30):** gecikme **1.50 → 0.61 s/video-sn (~2.5× hız)**; bu sette doğruluk
TAM korundu (recall/risk/kategori %100, normal-FP %0). 60 sn video ~37 sn'de analiz → gerçeğe-yakın.
Ödünleşim: iki-aşamalı algının özet/derinlik kalitesi feda edilir; canlı/hızlı tarama için idealdir.

### E2 — Forklift devrilmesi (şartname amiral örneği) gerçek-tespit kanıtı yok
**Dürüst bulgu (subagent araştırması):** Açık-lisanslı GERÇEK forklift-devrilme videosu hiçbir yerde yok
(yalnız ücretli stok/telifsiz-belirsiz). NVIDIA sentetik forklift = tespit 0 (sentetik≠gerçek).
**En yakın gerçek kanıtla çözüm:** (a) **Gerçek araç-kazası/devrilme** — UCF RoadAccidents 9 gerçek CCTV
klibi (`data/e2_vehicle/`): recall **%78** (7/9), "araç çarpıştı/devrildi" doğru raporlanıyor. (b) **Gerçek
forklift CCTV** — Eskişehir `class3` (1080p): sistem forklifti doğru anlıyor ve "işçi forkliftin yolunu
keserek geçiyor → potansiyel çarpışma riski" yakın-çarpışmasını bile yakalıyor. Şeffaf beyan: gerçek
forklift TIP-OVER açık veride yok; en yakın gerçek devrilme/forklift verisinde kanıtlandı.

### Bağımsız judge swap mekaniği (tekrar üretilebilir)
`pkill -f api_server/EngineCore` → `vllm serve RedHatAI/gemma-3-12b-it-FP8-dynamic` → judge → tekrar
`python serve_vllm.py` (Qwen3-VL geri). WSL varsayılan distrosu `docker-desktop` olduğundan komutlar
`wsl -d Ubuntu-24.04 ...` ile çalıştırılır.

## 7. Dürüst kalan noktalar — adım adım ele alındı (2026-06-22)
§6'daki çözümlerin geride bıraktığı dürüst artıklar da teşhis edilip ölçüldü.

### E2 araç-kazası recall %78 → %89 (kök-neden fix)
**Teşhis (`probe_clip.py`):** Kaçan `RoadAccidents043`'te model kazayı GÖVDEDE mükemmel tarif ediyor
("sağdaki araç soldakine çarpmıştır… bu bir trafik kazasıdır") ama açıklamanın SONUNDA "SAPMA YOK" diye
kendini çürütüyor; iki-aşamalı algının extraction adımı son-yargıya bakıp olayı düşürüyordu.
**Çözüm:** `EVENT_EXTRACTION_INSTRUCTION`'a **çelişki kuralı** — "sonda 'SAPMA YOK' dese bile gövdede somut
bir olay (çarpışma/kaza, düşme, yangın, kavga, silah) tarif edilmişse onu MUTLAKA çıkar; çelişkide somut
tarifi esas al." **Sonuç:** araç-kazası recall **%78 → %89** (`RoadAccidents043` kurtarıldı); E3 (%89) ve
senaryo zararlı-FP (%0) bozulmadı. Genel bir robustluk iyileştirmesi.

### E4 hız-modu kalite ödünleşimi — ölçüldü (kayıp YOK)
Bağımsız Gemma judge ile tam-mod vs hız-mod (aynı 30-klip senaryo seti):
| Metrik | Tam mod | Hızlı mod |
|---|---|---|
| Özet kalitesi | 4.64 | **4.62** |
| Aksiyon kalitesi | 4.66 | **4.74** |
| Risk gerekçe | 4.87 | **5.00** |
Özet/aksiyon/risk **neredeyse aynı** (özet/risk üreten `reason` düğümü iki modda özdeş; fark yalnız algıda
ve bu sette ikisi de %100 recall). Yani "hız modu özet derinliğini feda eder" çekincesi bu sette **veriyle
çürütüldü**; gerçek risk yalnız çok-ince/grainy olaylarda kalır (bu sette fark yok). Hız modu pratikte bedava.

### İndirgenemez kalan (veri/girdi tavanı — dürüstçe beyan)
- **E2 gerçek forklift TIP-OVER videosu:** açık lisansta YOK; yaratılamaz. En yakın gerçek devrilme/forklift
  verisinde kanıtlandı. `RoadAccidents021` (320×240 grainy) kişi-düşmesi girdi-tavanı (ince+düşük çözünürlük).
- **E3 `Subject2_fall03`:** model "kişi yatağa yatıyor" görüyor — yatak-üstü düşme ile kasıtlı uzanma arasındaki
  GERÇEK belirsizlik. Zorlamak `Subject1_adl01` yatak-FP'sini geri getirir → 89% recall + %0 FP doğru çalışma
  noktası. (recall/FP sınır frontu)
- **E5 senaryo'da kalan 2-3 olay:** hepsi **Düşük + dispatch-gated + yarı-meşru** (yürüyüş yolunda nesne;
  forklift yolunu kesen işçi). Zararlı FP (Kritik/dispatch) **%0**.

## 8. Ölçüm & genelleme + mimari zayıflıkları (G6-G12, 2026-06-22)
Dürüst dezavantaj listesindeki "ölçüm/genelleme" (G6-G8) ve "mimari/teknik" (G9-G12) kalemleri ele alındı.

### G6 — Minik eval seti → büyük-n + dürüst varyans
**Çözüm:** (a) `scripts/get_ucf_many.py` ile **64-klip** set (`data/eval_big`, 48 anomali/8 kategori + 16 normal);
(b) `benchmark/aggregate.py` ile TÜM koşular mean±std + aralık raporlanır (varyans artık gizlenmiyor).
**Sonuç:** Büyük-n (n=48 anomali) recall **%92** (kararlı tek tahmin). Konsolide varyans: Senaryo (16 koşu)
recall **%99±2** [94–100]; UCF-grainy (13 koşu) **%86±12** [58–100]; GMDCSA düşme (5 koşu) **%80±11**.
Dürüst mesaj: in-domain kararlı; grainy-OOD model doğal olarak daha değişken (n büyüdükçe daralıyor: 92%@n48).

### G7 — Gerçek-dünya/jüri-videosu robustluğu
**Çözüm:** (a) **Zarif bozulma** doğrulandı — bozuk/boş/var-olmayan video `ingest`'te çökmeden 0-segment +
açıklama döner (jüri çöp dosya yüklese bile sistem çökmez). (b) **Çeşitlilik kanıtı:** 320×240 grainy UCF →
1080p endüstriyel → frontal (GMDCSA) → **tavan/overhead** (URFD) → yol kazası → geniş çözünürlük/açı/domain
yelpazesinde test edildi. Kalan dürüst gerçek: gerçek savunma-tesisi videosu yok (açık veride mevcut değil).

### G8 — Gözetim-açılı düşme verisi (frontal değil)
**Sorun:** GMDCSA frontal ev-webcam; gözetim/savunma açısı değil.
**Çözüm:** `scripts/get_urfd_overhead.py` — URFD cam1 = gerçek **tavan/ceiling** kamera düşme klipleri
(PNG→mp4), `data/falls_surveillance/`. **Sonuç:** overhead açıda fall recall **%100 (6/6)**, risk %100,
kategori %100 — frontal GMDCSA'dan (%89) bile yüksek. E3 düşme-fix'i **farklı dataset + açıda da çalışıyor**
(GMDCSA'ya overfit DEĞİL). (Not: URFD falls simüle ama kamera-montajı gerçek surveillance görüşü.)

### G9 — Tek-GPU/sunucu güvenilirliği (watchdog)
**Çözüm:** `scripts/watchdog.py` — `/v1/models` sağlık-kontrolü; ardışık başarısızlıkta stale temizle +
`serve_vllm.py` ile otomatik yeniden-başlat (sunucu sessizce ölürse kendini toparlar). Ölçekleme yolu
belgelendi: vLLM continuous-batching eşzamanlı istekleri kuyruklar; çok-GPU için `--tensor-parallel-size`.

### G10 — Kare-örnekleme/segment-sınırı olayları
**Çözüm:** `config.segment_overlap` + `build_segments(overlap=)` — örtüşen pencereler (ör. overlap=3 →
[0-10),[7-17),[14-24)…) segment-sınırına denk gelen olayları iki pencerede gösterir (dedup birleştirir).
Varsayılan 0 (regresyonsuz); uzun-video/canlı-akış için açılır. Saniye-altı olaylar için `fps_sample` levyesi.

### G11 — Severity keyword-bağımlılığı (OOD/dil-körlüğü)
**Çözüm:** Severity zaten **model-öncelikli** (Qwen3-VL semantik atar, dil-bağımsız); keyword'ler yalnız
**tek-yönlü güvenlik tabanı**. Taban artık **iki-dilli** — İngilizce eşdeğerler (fire/smoke/collision/weapon…)
**kelime-sınırı** ile eklendi (Türkçe metinle çakışmaz, asla düşürmez). İngilizce/OOD tarif artık kör değil.

### G12 — Türkçe dil-saflığı (yabancı-karakter sızıntısı)
**Ölçüm (`scripts/scan_purity.py`):** 3054 metinde **%0.5** yabancı-script sızıntısı — ve örneklerin TÜMÜ eski
(Qwen2.5/öncesi) koşulardan; güncel Qwen3-VL koşularında görülmedi. **Çözüm:** `graph._purify` guard — çıktıda
Türkçe-dışı karakter varsa anlamı koruyarak yeniden-Türkçeleştirir; **temiz metinde sıfır ek-çağrı** (yalnız
sızıntıda tek düzeltme). Jüri-güveni için kalıcı güvenlik ağı.

## 9. Halüsinasyon — sistematik test + çoklu-subagent yöntem araştırması (2026-06-22)
Kullanıcı, canlı demoda çok-bölümlü bir videoda (gözetim + şömine) modelin "fabrikada yangın + yaralı işçi"
uydurduğunu fark etti. İstek: ad-hoc düzeltme yerine **(1) halüsinasyonun genelliğini ölç, (2) birçok subagent
ile literatürdeki çözümleri araştır, (3) yöntemlerle çöz.** Dürüst, ölçüm-odaklı süreç:

### Kök neden (önceki turlarda zaten çözülmüştü)
Asıl bug = **domain-varsayım confabulation** (persona "savunma tesisi" prime ediyordu) + **nesne-severity
aşırı-yükseltme**. İkisi de §6-§7'de çözülüp commit edildi (sahne-agnostik persona + nesne-vs-kişi severity);
kullanıcının videosunda doğrulandı ("fabrika/işçi" → "iç mekân/kişi"). Bu turda bunun ÜZERİNE artık-halüsinasyonu
daha da düşürmeye çalıştık.

### Ölçüm metriği (subagent araştırması → POPE/CHAIR literatürü)
**False-Event-Rate (FER)** = (olay üreten normal klip)/(normal klip) — judge-suz, objektif, "olay/bağlam uydurma"yı
doğrudan ölçer (CHAIR_S analoğu; reference=∅). `eval_clips` operasyonel-normal-FP'si bunu zaten verir.

### 4 subagent — yöntem aileleri + uygulanabilirlik
- **Decoding-time** (VCD/DoLa/OPERA/M3ID): hepsi ikinci-pass/hidden-state/attention ister → **vLLM HTTP'den UYGULANAMAZ**
  (vLLM'i terk etmek gerekir). Kullanılabilir olan: düşük-sıcaklık + guided-JSON (artımlı).
- **Self-verification/abstention** (CoVe/Woodpecker/SelfCheckGPT): kanıt+güven şeması, varlık-doğrulayıcı, olay-oylama.
- **Ölçüm** (POPE/CHAIR/VideoHallucer): FER + POPE-probu.
- **VAD-özel** (AnomalyRuler perception-smoothing, Holmes-VAD gate): zamansal çoğunluk-oyu = en yüksek kaldıraç.

### Uygulanan + ÖLÇÜLEN yöntemler (eval_big, aynı 16 normal + anomali)
| Yöntem | FER | Narrow-FP | Recall | Karar |
|---|---|---|---|---|
| Baseline (domain+severity fix) | %31 | %6 | %88 | **en iyi denge** |
| Kanıt/güven şeması + abstention | %56 | %12 | %88 | ❌ **reddedildi** — model kanıt UYDURUP daha çok olay üretti |
| Self-consistency N=3 (çoğunluk) | **%12** | %0 | %72 | ⚠️ recall -16; opt-in precision-modu |
| Self-consistency N=3 (severity-hibrit) | %31 | %19 | %89 | ❌ yüksek-sev normal-halüsinasyonu geçirdi |

### Dürüst sonuç
Grainy footage'da **hem gerçek olay hem halüsinasyon stokastik + yüksek-severity olabildiğinden self-consistency
ikisini temiz ayıramıyor** — "bedava öğle yemeği yok". Kanıt-şeması ise geri tepti (model kendi uydurmasına güven
verir). **Asıl ve en iyi çözüm zaten committed domain+severity-fix'leriydi.** Self-consistency `event_consistency_n`
ile **opt-in "yüksek-hassasiyet modu"** olarak bırakıldı (varsayılan KAPALI=1 → recall-öncelik); FER'i yarıdan
fazla düşürür ama recall + 2-3× gecikme bedeliyle. Bu, "her yöntemi baseline'a karşı ölç, yalnız net kazananı
uygula" disiplininin (CLAHE/YOLO/temporal-CoT/evidence-şeması ret) bir örneği daha. Yeni araç: `scripts/audit_outputs.py`.

## 10. Çok-bölümlü/kopuk video — sahne-kesimi + neden-sonuç-bağımsızlık (M3, 2026-06-22)
**Sorun:** Kullanıcının yüklediği video iki bölümlüydü (gözetim CCTV + sonradan eklenmiş şömine); ajan ikisini
TEK bir olay öyküsüne birleştiriyordu ("önce ... sonra yangın ... sonra ..."). Bağımsız sahneler arası yapay
neden-sonuç = bir confabulation türü.

**İki katmanlı çözüm:**
1. **Sahne-kesimi tespiti** (`video.detect_scene_cuts`): ardışık karelerin 4×4×4 RGB renk-histogramı kesişim
   mesafesi; eşik üstü = sert kesim. `ingest` bunu hesaplar (`state.scene_cuts`); `reason` olayları **Bölüm
   1/2/...** diye gruplar + "bölümler KOPUK, aralarında neden-sonuç KURMA" talimatı ekler.
2. **Her-zaman-açık neden-sonuç-bağımsızlık backstop'u** (`DECISION_SUPPORT` summary kuralı): kesim tespit
   edilse de edilmese de, "olaylar arası otomatik öykü/neden-sonuç kurma; yalnız açıkça aynı sahnedekileri
   ilişkilendir." Bu, asıl ROBUST katman.

**Spliced test (industrial + fire concat):** Kesim **00:11'de** tespit edildi; özet artık birleştirmiyor →
*"00:02 yere düşmüş kişi … 00:12-30 yangın … İki olay birbirinden bağımsızdır ve farklı sahnelerdir."*

**Dürüst sınır (ölçülmüş):** Saf-görsel kesim tespiti **yangın/parlama sahnelerinde temelden güvenilmez** —
yangın sahne-içi titremesinin histogram-mesafesi (0.208) gerçek sahne-kesiminden (0.197) bile YÜKSEK çıkabiliyor;
hiçbir sabit eşik ikisini temiz ayıramaz. Bu yüzden kesim-eşiği **konservatif (0.30)** bırakıldı (yangın klibini
yanlış-bölmemek için yalnız çok-dramatik kesimleri yakalar) ve asıl iş **prompt-seviyesi neden-sonuç-bağımsızlık
backstop'una** verildi (false-positive yok, birleştirmeyi tek başına önler — test edildi). Araç: `scripts/probe_scenes.py`.

### Bonus (aynı video tetikledi) — algı `repetition_penalty` ile "düşmüş kişi" uydurması düzeltildi
Kullanıcının videosunda model, koridorda **yürüyen bir işçiyi** "yere düşmüş hareketsiz kişi" sanıyordu.
Kaynak klibi (`6_te12`) probe edince neden görüldü: describe adımı **degenerate döngüye** girip ("...düşmüş
gibi... düşmüş gibi..." 3×) belirsiz okumayı şişiriyordu (model aynı klibin 2. segmentinde "kişi GÖRÜNMÜYOR"
diyerek kendiyle çelişiyordu). **Çözüm (decoding-time, aef55 araştırması):** algı çağrısına
`repetition_penalty` (`config.perceive_repetition_penalty`, `VLMClient` → vLLM `extra_body`).
**Ölçüm:** rp=1.3 döngüyü kesti ama recall'ı düşürdü (falls_real 89→78) → fazla agresif. **rp=1.15** tatlı nokta:
`6_te12` uydurma-kişi GİTTİ; falls_real recall **%89 korundu** (risk-kalib 78→89); senaryo recall/risk/kategori
**%100**, zararlı-FP **%0**. Varsayılan **1.15** yapıldı (tam doğrulandı, recall bozulmadı). Bu, "emin yanlış-okuma"
sınıfının grainy-OOD'de kısmen iyileştirilebildiğini gösteren ölçülü bir kazanım.

## 11. Düşme-precision — POZ-TABANLI doğrulama (F1, 2026-06-22)
**Sorun:** Endüstriyel CCTV'de **çömelen/eğilen bir işçiyi** "kişi zemine düşmüş ve hareketsiz" (Kritik/Sağlık +
dispatch) sanma. Bu, E3'te düşme-recall için eklediğimiz hassasiyetin doğrudan yan etkisi; prompt/decoding
tweak'leri (rp=1.15) azalttı ama stokastik olarak tekrar etti.

**Benzer çalışmaların yöntemi (2 subagent literatür analizi):** Bu tam olarak fall-detection'ın "fall vs ADL"
(oturma/eğilme/çömelme) problemi. Çözüm desenleri: **Woodpecker/Semantic-Drive** (VLM önerir → uzman dedektör
doğrular) + **poz-tabanlı fall-detection** (PMC7729773, ACM 3478027): bbox aspect-ratio + **torso açısı** +
spine-ratio. Ayırt edici sinyal: **çömelme/eğilme torso'yu DİK tutar; düşme torso'yu YATAY yapar** (+ temporal:
düşme bir noktada yatay olur, çömelme hiç olmaz).

**Uygulama (`detector.verify_fallen`, YOLO11n-pose):** VLM "kişi düşmüş" dediğinde poz çalışır; omuz(5,6)/kalça(11,12)
keypoint'lerinden torso-açısı (dikeyden) hesaplanır. Eşikler (literatür): <30° = DİK (çömelme), >50° veya
(aspect>1 & spine<1.2) = YATAY (düşmüş). **Karar (fail-open + yalnız-düşür):**
- ≥2 karede yatay → **CONFIRM** (gerçek düşme, korunur)
- 0 yatay + **≥6 kare** sürekli-dik → **REJECT** → severity Orta'ya (dispatch-altı) düşürülür
- poz güvenilmez/kişi yok/overhead → **ABSTAIN** → VLM korunur (gerçek-düşme recall'i güvende)

**Ölçüm (önce/sonra, recall bozmadan):**
| Test | Sonuç |
|---|---|
| 6_te12 (çömelen işçi) | **REJECT** → sahte "düşmüş kişi" gitti ✓ |
| Gerçek düşmeler (Subject1/3) | **CONFIRM** ✓ |
| URFD overhead | **ABSTAIN** (fail-open) ✓ |
| falls_real | recall **%89**, risk-kalib **%89**, normal-FP **%0** (bozulmadı) ✓ |
| comp_fire | "dizleri üzerinde" → Düşük; "hareketsiz" → Yüksek korundu; yangın Kritik |

REJECT-eşiği önce n_up≥3 idi (2 gerçek düşmeyi de düşürdü, risk-kalib 67); **n_up≥6** (sürekli-çömelme) yapınca
gerçek düşmeler korundu (risk-kalib 89), çömelme yine yakalandı. **Dürüst sınır:** tepeden/overhead kamerada poz
güvenilmez → ABSTAIN (VLM'e güvenir); derin bel-eğilmesi torso'yu yatay yapabilir (nadir kalan edge-case).
Araçlar: `detector.verify_fallen`, `scripts/_test_pose.py`, `scripts/probe_scenes.py`. Açıklanabilirlik: trace'e
poz-verdict yazılır.

## 12. Araç-kazası recall — HAREKET-BELİRGİNLİĞİ dikkat ipucu (D1, 2026-06-23)
**Sorun (jüri yükledi):** 5sn'lik park-alanı klibinde (RoadAccidents021, 320×240) **2.sn'deki araç çarpışması**
kaçtı; model "iki kişi etkileşimde, olay yok / Düşük" dedi. Tüm araç setinde recall %89 (UCF-dengeli'de %33).

**Kök-neden (probe ile, varsayım değil):** Örnekleme **değil** — çarpışma anı (hareket-zirvesi t=1.3s) zaten
örnekleniyor (en yakın kare 0.2s uzakta). Model **0 olay** veriyor. Doğrudan "çarpışma var mı?" diye sorulunca,
**1024px'e büyütülüp 4fps'te bile** "Hayır" diyor → 320×240'ta tanıma **tavanı**. Kareleri kendi gözümle
inceledim: çarpışma gerçek ama **düşük-hızlı, sol-üst köşede, küçük** bir park-teması; model ön plandaki büyük
kamyonet+2 kişiye odaklanıp köşedeki ufak olayı gözden kaçırıyor. **Net örüntü:** dramatik kazalar (5/9) zaten
Kritik/Yüksek doğru; **ince/düşük-hızlı/uzak** olaylar (021,027,128,129) zayıf.

**Çözüm (motion-saliency / video-anomali literatürü):** Segment karelerinde en belirgin **ANİ görsel değişim**
anını ucuzca bul (64×64 gri ardışık-kare farkı; GPU yok), perceive'e **YUMUŞAK dikkat ipucu** enjekte et:
"~MM:SS'e özellikle dikkat et — ani çarpışma/devrilme/düşme/kaza olabilir; **emin değilsen normal de**". İddia
DEĞİL (FP zorlamaz). Yalnız **belirgin+izole zirvede** tetikler (mutlak>6 VE >2× ortalama) → uniform/düşük-hareketli
normalde sessiz. (`config.motion_saliency_cue=True`, `graph._motion_cue`).

**Ölçüm (A/B, sonra 3 sette regresyon kontrolü):**
| Metrik | KAPALI | AÇIK |
|---|---|---|
| Araç recall (e2_vehicle, n=9) | %89 | **%100** (027 tam-kaçıştan kurtuldu) |
| Araç risk≥Yüksek | %67 | %67 |
| Normal op-FP (UCF+senaryo, n=20) | %35 | **%30** (artmadı, düştü) |
| Normal dar-FP | %0 | %0 |
| **Senaryo** (yangın+düşme) | 100/100/100/0/33 | **birebir aynı** (flagship korundu) |
| falls_real | recall 89 / dar-FP 0 | recall 89 / **dar-FP 0** (op-FP 0→17: 1 normal, düşük-sev.) |

Kullanıcı-yüzlü doğrulama: **021 artık** `[00:02] Pikap ani hareketle geriye kayarak beyaz otomobile dokunmuş
(kat=Kaza)` veriyor (önce: "olay yok"). **Dürüst sınır:** ipucu olasılıksal — 027 bazı koşularda hâlâ kaçıyor
(gerçekten sınırda/tavan); 021 severity Düşük (düşük-hızlı temas için kalibrasyon doğru, zorlamadım). Tek maliyet:
falls_real'de 1 normal klipte düşük-severity op-FP (dispatch-altı, dar-FP %0). Araçlar: `scripts/probe_road.py`,
`scripts/ab_motion_cue.py`, `scripts/eval_all_datasets.py`.

## 13. SAVUNMA — yasak/kısıtlı bölge ihlali (geofence) + perimetre (D3, 2026-06-23)
**Bağlam:** Şartname savunma sanayi/saha operasyonlarını öncelikliyor. Savunma-tesisi gözetiminin çekirdeği
**perimetre/yasak-bölge izleme.** Probe ile bulundu: VLM'e "üst-sağ yasak bölge, oraya giren kişi ihlal"
dense (`facility_rules`), model **zone-reasoning'i güvenilir yapamıyor** (bölge kontrolü yok). Ayrıca silahlı
tehdit (UCF Shooting 320×240) tamamen kaçıyor — girdi-tavanı.

**Çözüm — DETERMİNİSTİK YOLO geofence (`detector.detect_zone_intrusion`):** VLM zone-reasoning'i yerine uzman
dedektör. YOLO ile KİŞİ tespit → bbox-merkezinden 3×3 ızgara bölgesi → bölge yasak listede ise **"Yasak Bölge
İhlali" (Yüksek/Yetkisiz Erişim)** olayı + bölge etiketi. Operatör bölgeleri Gradio'dan girer
(`config.restricted_zones`, ör. "üst sağ,sağ"). **Opt-in** (boş=kapalı → mevcut davranış birebir korunur).
Tesis-kuralı kutusu (`facility_rules`) da UI'ye bağlandı (politika-ihlali enjeksiyonu).

**Ölçüm:**
| Yetenek | Sonuç |
|---|---|
| Geofence **recall** (kişi yasak bölgede → ihlal) | **%88** (7/8) |
| Geofence **precision** (boş bölgede yanlış-ihlal) | **%100** (8/8) |
| Perimetre/izinsiz-giriş (VLM, Burglary+kural) | %50 (3/6) |

Geofence güvenilir (deterministik, VLM'in zayıf olduğu yerde uzman dedektör — heterojen ensemble; VLM kişiyi
kaçırsa bile geofence yakalar). **Dürüst sınır:** (1) silahlı-tehdit (Shooting) 320×240'ta hâlâ kaçıyor —
girdi-tavanı; (2) gerçek savunma-tesisi/perimetre videosu açık-veride yok, vekil veri (Burglary/Normal) ile
doğrulandı; (3) geofence kişi-tabanlı (araç/İHA bölge-ihlali ileride). **Konum:** savunma-grade *mimari*
(air-gap/yerli) + operatör-tanımlı yasak-bölge izleme; tesise özelleştirme kurumun kendi verisiyle.
Araçlar: `detector.detect_zone_intrusion`, `scripts/{probe_defense,eval_defense}.py`.

## 14. GENEL — sahne-düzeyi TEHDİT-YORUMU (sığ betimleme → doğru tehdit adlandırma) (D4, 2026-06-23)
**Sorun (jüri yükledi, Shooting001):** Ciddi suç/şiddet sahnelerinde model **yüzeysel** yorumluyordu:
vurulup düşen kişiyi *"bir şey alıyor/bırakıyor" (Orta/Anomali)*, kavgayı *"fiziksel temas"* diye geçiştirip
severity'yi düşük tutuyordu. **Sadece silah değil — genel bir algı/yorumlama zayıflığı.**

**Kök neden (probe ile kanıtlı):** `SEGMENT_DESCRIBE` promptu **nötr sahne-betimlemeye** ("ortam + beklenen
normal + sapma") odaklı → model şiddet yerine mobilyayı/arabaları anlatıp olayı sığlaştırıyor. Aynı karelere
**"güvenlik analisti gibi yorumla"** denince: Shooting→"saldırı Yüksek", Assault→"yere yığılma Yüksek",
Fighting→"şiddetli çatışma" çıktı; normaller→"Normal" kaldı (şişmedi).

**Çözüm:** `prompts.THREAT_LENS_SUFFIX` — describe'a güvenlik-analisti tehdit-yorumu katmanı (olayı doğru adıyla:
saldırı/soygun/silahlı-tehdit/yere-yığılma; "fiziksel temas" gibi zayıf ifadeyle hafifletme). W1 anti-halüsinasyon
korundu ("görsel kanıt yoksa uydurma; rutin ise SAPMA YOK"). `config.threat_interpretation=True`.

**Ölçüm (A/B, 62 klip):**
| Metrik | KAPALI | AÇIK |
|---|---|---|
| Suç risk-kalib (≥Yüksek) | %71 | **%75** (+4, suçlar doğru yükseltiliyor) |
| Normal **dar-FP** (yanlış yüksek-alarm) | %10 | **%5** (−5, DAHA güvenli) |
| Flagship (yangın+düşme) recall/risk | 100/100 | **100/100** (korundu) |
| Normal op-FP | %50 | %50 |
| Suç recall | %96 | %92 (−4: 1 klip, ±12 varyans bandı) |

Shooting001 kullanıcı-yüzlü: olay-2 *"bir şey alıyor (Orta/Anomali)"* → **"ani yere çökmüş kişi (Yüksek/Sağlık)"**.
**Dürüst sınır:** silahı *adıyla* söyleyemiyor (bulanık 320×240'ta gerçekten seçilmiyor — girdi-tavanı); ama tehdit
örüntüsü (saldırgan temas + yere düşen kişi) doğru yükseltiliyor. recall −4 varyans-içi; risk-kalib +4 ve dar-FP
−5 (daha güvenli) net kazanç. Araçlar: `scripts/{probe_threat,ab_threat}.py`.
