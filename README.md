# 🎥 DilAjanları — Yerel Video Analiz ve Karar Destek Ajanı

**TEKNOFEST 2026 · Türkçe Yapay Zekâ Dil Ajanları Yarışması · 3. Senaryo**

Savunma sanayi tesisleri ve saha operasyonları için, bir videoyu girdi alıp **tamamen
yerel / offline** çalışan, multimodal (video + metin) bir yapay zekâ ajanı. Sistem
videodaki olayları **zaman damgasıyla** tespit eder, **Türkçe özet** ve **risk
değerlendirmesi** üretir, operatöre **aksiyon önerileri** sunar ve uygun **operasyonel
fonksiyonları dinamik olarak çağırır** — çıktının tamamı yapılandırılmış JSON'dur.

> Yığın: **Qwen3-VL-8B** (görsel-dil modeli, FP8) · **vLLM** (yerel servisleme) ·
> **LangGraph** (ajan) · **Gradio** (arayüz). Dış API / bulut / ücretli yazılım **yok**.
> Öz-doğrulama + mekânsal grounding + ayarlanabilir duyarlılık modları. (7B precision-yedek korunur.)

---

## İçindekiler
- [Özellikler](#özellikler) · [Mimari](#mimari) · [Gereksinimler](#gereksinimler)
- [Kurulum](#kurulum) · [Çalıştırma](#çalıştırma) · [Çıktı Formatı](#çıktı-formatı)
- [Veri Seti](#veri-seti) · [Değerlendirme (KPI)](#değerlendirme-kpi) · [**Ölçüm Sınırlarımız**](#ölçüm-sınırlarımız)
- [Proje Yapısı](#proje-yapısı) · [Karşılaşılan Zorluklar](#karşılaşılan-zorluklar-ve-çözümler)

## Özellikler
- ⏱️ Zaman damgalı olay tespiti (önem + kategori ile)
- 📝 Operatör odaklı Türkçe özet
- ⚠️ Gerekçeli risk değerlendirmesi (Düşük/Orta/Yüksek/Kritik)
- ✅ Önceliklendirilmiş aksiyon önerileri
- 🛠️ Mock operasyonel fonksiyonların **dinamik** çağrılması (ajanın araçları)
- 💬 Analiz hakkında doğal Türkçe sohbet (operatör asistanı)
- 📊 Yapılandırılmış JSON çıktı + KPI ölçüm çerçevesi

## Mimari
Ayrıntı için → [`docs/architecture.md`](docs/architecture.md)

```
                             ┌──────────────┐
                             │  reexamine   │  (koşullu — belirsiz "Orta" olay varsa)
                             └──▲────────┬──┘
              belirsiz olay var │        │
                                │        ▼
Video → [ingest] → [perceive] ──┴──────→ [reason] → [act] → [finalize] → JSON
        kare/segment  VLM olay              özet/risk   mock       birleştir
                      tespiti                /aksiyon   fonk.
```
LangGraph **6 düğümlü** (ingest · perceive · *reexamine* · reason · act · finalize),
**koşullu kenarlı** ve hata toleranslı bir durum makinesidir: `perceive` sonrası belirsiz
olay varsa ajan kendi tespitini yeniden sorgular (döngü muhafızı ile en fazla bir kez).
Her düğümün dış gövdesi try/except ile sarılıdır; ayrıca segment içi hatalarda fail-open
davranır. Tüm model çağrıları yerel vLLM sunucusuna gider.

## Gereksinimler
**Donanım:** NVIDIA GPU (CUDA). Önerilen ≥ 24 GB VRAM (Qwen3-VL-8B-FP8 için; 7B-yedek de sığar).
Geliştirme ortamı: RTX 5090 Laptop (24 GB, Blackwell), 64 GB RAM, WSL2 + Ubuntu 24.04.

**Yazılım:** Linux veya WSL2 (Ubuntu 24.04), Python 3.12, güncel NVIDIA sürücüsü.

## Kurulum

> Windows'ta vLLM yereli desteklemediği için **WSL2 + Ubuntu** kullanılır.

```bash
# 1) (gerekiyorsa) WSL2 + Ubuntu 24.04
wsl --install -d Ubuntu-24.04

# 2) Sistem paketleri
sudo apt update && sudo apt install -y python3-venv python3-pip ffmpeg fonts-dejavu-core

# 3) Sanal ortam
python3 -m venv ~/teknofest/.venv
source ~/teknofest/.venv/bin/activate
pip install --upgrade pip

# 4) PyTorch (Blackwell / RTX 50xx -> CUDA 13.0 tekerlekleri)
pip install torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 \
    --index-url https://download.pytorch.org/whl/cu130

# 5) Proje bağımlılıkları
pip install -r requirements.txt
```

**Blackwell / karışık-CTK notu:** Bu GPU ailesinde vLLM JIT derlemesi için ek ortam
değişkenleri gerekir; tümü `dilajan/config.py:apply_cuda_env()` içinde otomatik ayarlanır
(standart CUDA kurulumlarında zararsız no-op). Manuel kabuk için `env.sh` kullanılabilir.

## Çalıştırma

```bash
# 1) Model sunucusu (ayrı terminal) — ilk açılış ~90s (model + CUDA graph)
python serve_vllm.py        # http://127.0.0.1:8000/v1

# 2a) CLI ile analiz
python run_analysis.py data/test_clip.mp4
python run_analysis.py data/test_clip.mp4 --sartname --json outputs/sonuc.json

# 2b) Web arayüzü
python app.py               # http://127.0.0.1:7860

# 3) KPI değerlendirmesi
python benchmark/evaluate.py

# (test videosu üretmek için)
python scripts/make_test_video.py
```

## Çıktı Formatı

```json
{
  "summary": "00:06'ta forklift devrildi ve 00:08'de bir kişi yerde hareketsiz...",
  "events": [
    {"time": "00:06", "event": "Forklift devrildi", "severity": "Kritik", "category": "Kaza"},
    {"time": "00:08", "event": "Bir kişi yerde yatıyor", "severity": "Kritik", "category": "Sağlık"}
  ],
  "risk": {"level": "Kritik", "rationale": "Kaza ve olası yaralanma; acil müdahale gerekiyor."},
  "actions": [{"action": "Sağlık ekibini yönlendir", "priority": "Kritik", "rationale": "..."}],
  "video_duration": "00:12",
  "triggered_functions": ["acil_durdurma_tetikle", "saglik_ekibi_yonlendir", "olay_kaydi_olustur"]
}
```
Sade şartname formatı için `--sartname` (summary/events/risk/actions).

## Veri Seti
Depoda **hiçbir video dağıtılmaz**; her klip açık kaynaklardan indirme script'leriyle çekilir.
Tam envanter, lisanslar ve bilinen kusurlar → [`docs/veri_kaynaklari.md`](docs/veri_kaynaklari.md).

| | Değer (2026-07-25 `md5sum` + `ffprobe` denetimi) |
|---|---|
| `data/` altındaki video dosyası | 412 |
| **Benzersiz video (MD5)** | **214** |
| **Doğruluk ölçümüne giren benzersiz klip** | **140 klip / 44.0 dakika** |

> Ham dosya sayısını video sayısı olarak raporlamıyoruz: kopyaların çoğu aynı klibin birden fazla
> değerlendirme setinde bulunmasından gelir; kalanı ham indirme artığı (`scenario/_dl/`) ve
> denenip kullanılmayan veridir (`nvidia/`).

**Bilinen veri kusurları (gizlemiyoruz):**
- `data/eval`, `data/eval_big`'in **%100 alt kümesiydi** (31/31 MD5 aynı) → "bağımsız büyük-n
  doğrulaması" iddiası **geri çekildi**. Düzeltme olarak `eval_big` ayrık `data/eval_tune` (31) ve
  `data/eval_holdout` (32) alt-kümelerine bölündü (kesişim = 0); **temiz holdout ölçümü henüz koşulmadı**,
  yayınlanan `eval_big` rakamları bölünmeden öncedir.
- `data/eval_scenario/Fall` klipleri **video değildi** (tek PNG'nin sarılmış hâli: 1024×1024, 3.0 sn,
  sıfır hareket) → **gerçek düşme videolarıyla değiştirildi** (9 × GMDCSA 720p60 + 6 × URFD 480p15).
  Bu 15 klip `data/falls_real` + `data/falls_surveillance` ile birebir aynıdır — kalite kazancıdır ama
  **bağımsız kanıt eklemez**. Ayrıca **senaryo-seti rakamları eski kompozisyona aittir; yeniden ölçülecek.**
- `data/test_clip.mp4` olayı **kareye gömülü metinle** taşır → model orada OCR yapar;
  bu klip bir yetenek kanıtı değil, yalnızca duman testidir.
- **UCF-Crime Creative Commons değildir** (akademik/araştırma) ve klipler üçüncü-taraf bir
  HuggingFace aynasından çekilir.
- **Hızlı doğrulama:** `python scripts/make_test_video.py` ile sentetik test klibi.

## Değerlendirme (KPI)
Veriye dayalı bir değerlendirme altyapısı kurulmuştur:
- `benchmark/eval_clips.py` — dengeli set (anomali + normal) üzerinde anomali recall, **normal yanlış-pozitif oranı**, risk kalibrasyonu, kategori eşleşmesi, gecikme; sonuçlar `benchmark/results/` altında JSON olarak saklanır.
- `benchmark/judge.py` — özet kalitesi için LLM-as-judge.
- `benchmark/dialogue_test.py` — diyalog/otonomi robustluk testi (bağlam-değişimi, prompt-injection, halüsinasyon probu).
- `benchmark/variance.py`, `benchmark/compare.py` — varyans ve iterasyonlar arası karşılaştırma.
- `benchmark/stats_utils.py` — **raporlama hijyeni**: Wilson %95 güven aralığı, örneklem
  büyüklüğüne göre ondalık disiplini, pseudo-replikasyon uyarısı (`python benchmark/test_stats_utils.py`).

**Raporlama kuralımız:** küçük örneklemde nokta-değer tek başına verilmez. Her oran
`k/n` **+ Wilson %95 güven aralığı** ile sunulur (`benchmark/stats_utils.py`); n ≤ 48 ise
ondalıklı yüzde yazılmaz. Kanonik değerlerin tamamı ve ölçüm sınırlarımız →
[**`docs/olcum_durustlugu.md`**](docs/olcum_durustlugu.md).

**Güncel sonuçlar (varsayılan: Qwen3-VL-8B-FP8 + öz-doğrulama + grounding):**

| Metrik | Sonuç (`k/n`) | Wilson %95 GA |
|---|---|---|
| Anomali recall — senaryo seti ¹ | **18/18** (en kötü kayıtlı koşu 17/18) | [%82, %100] · (17/18 → [%74, %99]) |
| Anomali recall — UCF `eval_big` (grenli 320×240) | **44/48** (diğer 2 koşu 42/48) | [%80, %97] · (42/48 → [%75, %94]) |
| Gerçek düşme (GMDCSA) / overhead düşme (URFD) | 8/9 · 6/6 | [%56, %98] · [%61, %100] |
| Normal yanlış-pozitif — adversaryel `eval_stress` | **0/9** (gözlenen FP yok) | **[%0, %30]** |
| Normal yanlış-pozitif — 1080p endüstriyel ² | **0/8** (gözlenen FP yok) | **[%0, %32]** |
| Özet kalitesi (bağımsız Gemma hakem) | **4.62 ± 0.53** | 30 klip × 3 eksen |
| Aksiyon kalitesi (bağımsız Gemma hakem) | **4.74 ± 0.44** | 18 klip × 4 eksen |
| Diyalog robustluğu (bağımsız Gemma hakem) | **5.00** (std 0 — tavan-doygun) | 7 tek-tur + 4 çok-tur |
| Eşzamanlı throughput (×4) | **+13.5%** (3.7 → 4.2 video/dk) | kayıtlı log ile |

> ¹ **Senaryo seti o ölçümden sonra değişti:** düşme klipleri (8 adet donmuş-PNG) gerçek videolarla
> değiştirildi ve set 25 anomali + 12 normal oldu. Tablodaki 18/18, **eski kompozisyonun** kayıtlı
> sonucudur; yeni sette ölçüm henüz koşulmadı.
>
> ² Bu, **sınıf başına 1 klip** olan eski endüstriyel havuzun (8 klip, hepsi "Normal") sonucudur.
> Havuz o zamandan beri 40 klibe çıkarıldı ve buradan **20 anomali + 20 normal**lik hedef-domain
> seti `data/eval_defense` üretildi — **bu sette henüz ölçüm koşulmadı.**

> **Dürüst 3-seviyeli recall (grenli UCF, 51 bağımsız klip):**
> TESPİT (olay var mı) **49/51 [%87–%99]** · AKSİYON (doğru müdahale sınıfı) **36/51 [%57–%81]** ·
> TANIMA (birebir alt-etiket) **22/51 [%31–%57]**. Grenli 320×240'ta ince tip-tanıma bilgi-teorik
> tavandır (model-boyu değil; `docs/iyilestirmeler.md` §15–§16). Bu rakamlar önce 81 ölçüm üzerinden
> %96/%73/%46 olarak raporlanmıştı; `eval ⊂ eval_big` örtüşmesi nedeniyle 27 klip iki kez sayılmıştı
> ve mükerrer-arınmış hâlleriyle yeniden verilmiştir.
>
> **"%0 yanlış-pozitif" demiyoruz.** 0/9 gözlem, gerçek FP oranının %30'a kadar olabilmesiyle uyumludur.
> Ayrıca *operasyonel*-FP (dispatch kapısıyla engellenen, "Düşük" seviyeli zararsız notlar) daha yüksektir:
> senaryo normalinde 4/12 [%14–%61], `eval_big` normalinde 6/16 [%18–%61].

## Ölçüm Sınırlarımız
Bu bölüm projenin zayıf yanlarını **bilerek** yayınlar: yetersizliği biz ölçtük ve yazdık.
Tam gerekçeler ve sayılar → [`docs/olcum_durustlugu.md`](docs/olcum_durustlugu.md) §6.

- **Küçük örneklem, varyans-baskın.** En büyük setimiz 48 anomali + 16 normal. Tek bir klip
  sonucu %2–17 oynatır → sıralama/şampiyonluk iddiası bu boyutta yapılamaz.
- **Recall tanımımız gevşek.** Manşet recall "**≥1 herhangi bir olay üretildi**" demektir; tipin
  doğru olması gerekmez. Katı ölçümde aynı sistem TANIMA **22/51 (%43)**'e düşer.
- **Yayınlanan kalite skorları dayanaklılık değil iç tutarlılık ölçüyor.** O koşuda hakeme
  yalnızca metin (sistemin kendi olay listesi + kendi özeti) verilmişti; hakem videoyu görmedi.
  Bu tasarımda **kendinden emin bir halüsinasyon tam puan alabilir.** `judge_independent.py`
  artık ground-truth'a karşı olgusal dayanaklılık ve opsiyonel kare-kanıtı da üretiyor,
  **ama ölçüm henüz yeniden koşulmadı** — düzeltme araçta, rakamlarda değil.
- **Gece / IR / termal görüntüde sıfır kapsam.** Tüm setlerimiz gündüz görünür-ışıktır;
  savunma dağıtımının birincil kaynağı hakkında hiçbir ölçümümüz yok.
- **Hedef domainde ÖLÇÜLMÜŞ pozitif yok.** Denetimde tek gerçek 1080p tesis verimizin (`data/industrial`)
  8/8'i "Normal" etiketliydi. **Veri boşluğu kapatıldı:** `data/eval_defense` = 20 anomali + 20 normal,
  tamamı 1080p gerçek tesis görüntüsü (yürüme yolu ihlali · yetkisiz müdahale · açık pano kapağı ·
  forklift ile aşırı yük). **Ama bu sette henüz ölçüm koşulmadı** — tesis-içi iddialarımız hâlâ
  komşu domainlerden transfer varsayımıdır.
- **Forklift devrilmesi için gerçek açık veri yok.** Şartname örneğinin açık lisanslı gerçek
  devrilme videosu bulunamadı. En yakın gerçek kanıtlar: `eval_defense`'teki 5 forklift aşırı-yük
  klibi (1080p, devrilme öncesi riskli durum) ve UCF `RoadAccidents` klipleri.
- **Çözünürlük–etiket confound'u.** `eval_big`'de anomalilerin %100'ü 320×240, normallerin
  %50'si 1080p; `eval_scenario`'da anomalilerin hiçbiri 1080p değil, normallerin %67'si öyle.
  Kararın ne kadarının olaydan, ne kadarının görüntü kalitesinden geldiğini ayrıştıramıyoruz.

> Her iyileştirme baseline'a karşı ölçülür; güvenlik senaryosunda **yüksek recall + düşük
> dar-yanlış-pozitif** önceliklendirilir, operasyonel-FP dürüstçe raporlanır. Ablasyonlar
> (Qwen2.5-VL-7B precision-yedek dâhil) `docs/iyilestirmeler.md`'de.

## Proje Yapısı
```
dilajan/          ana paket: config, video, schema, prompts, llm_client,
                  mock_functions, chat_agent, agent/ (LangGraph grafiği)
serve_vllm.py     vLLM sunucu başlatıcı
run_analysis.py   CLI (video -> JSON)
app.py            Gradio arayüzü (timeline + risk rozeti + canlı ilerleme + sohbet)
benchmark/        eval_clips, judge, dialogue_test, variance, compare, stats_utils + results/
scripts/          test videosu üreteci, veri seti indiriciler, yardımcı betikler
docs/             mimari, ölçüm dürüstlüğü, veri kaynakları, performans raporu,
                  şartname uyumu, demo senaryosu, sunum iskeleti/pptx, GitHub rehberi
requirements-lock.txt   tam sürüm kilidi (pip freeze)
```

## Karşılaşılan Zorluklar ve Çözümler
- **Blackwell (sm_120) uyumu:** vLLM 0.23 CUDA 13'e derli; torch'u `cu130`'a hizalayarak
  `libcudart.so.13` uyumsuzluğu çözüldü.
- **Karışık CTK sürümleri (nvcc 13.2 vs cccl 13.3):** flashinfer JIT derlemesini engelleyen
  sürüm kontrolü `NVCC_APPEND_FLAGS=-DCCCL_DISABLE_CTK_COMPATIBILITY_CHECK` ile aşıldı.
- **Performans:** `enforce_eager` kaldırılıp CUDA graphs açılarak decode hızı ~68× arttı
  (0.5 → ~37 token/s).
- **Tool-calling güvenilirliği:** Yerel 7B modelde native `tool_choice` kararsız davrandığı
  için operasyonel fonksiyon seçimi **yapılandırılmış-JSON dispatch**'e taşındı (güvenilir,
  çoklu, model-tabanlı dinamik seçim).
- **Düşük çözünürlüklü gerçek görüntüde az-tespit:** Katı JSON olay-promptu, grainy CCTV'de
  modeli aşırı temkinli yapıp olayları kaçırıyordu (serbest tarif ise aynı kareleri doğru
  yorumluyordu). Çözüm: **iki aşamalı algı** — önce serbest Türkçe tarif, sonra tariften olay
  çıkarımı. Bu, gerçek UCF-Crime kliplerinde tespit oranını belirgin artırdı.
- **Risk kalibrasyonu:** Model gerçek tehlikeyi tarif edip riski düşük puanlıyordu. Severity
  kalibrasyonu (tehdit kelimeleri) + risk tabanı guardrail'i ile anomalilerde risk yükseldi
  (QWK 0.733); normal kliplerde dar-yanlış-pozitif gözlenmedi (0/9 [%0–%30], 0/8 [%0–%32]),
  operasyonel-FP daha yüksek (4/12, 6/16) ve dürüstçe raporlanır.
- **Performans:** vLLM eşzamanlı istekleri batch'ler; **prefix-caching** ile eşzamanlı (×4)
  throughput **+13.5%** (3.7 → 4.2 video/dk), tek-akış ort **0.86 s/video-sn** (n=6 klip,
  0.44–3.75 aralığı). Kayıt: `benchmark/results/bench_perf_{baseline,prefixcache}_20260625.log`.
  *(Serving-flag turunun ek kazancı — "4.6 video/dk / +24%" — kayıtlı log olmadığı için geri çekildi.)*
- **Diyalog robustluğu:** Bağlam-değişimi/prompt-injection denemelerine karşı few-shot reddetme
  örnekleriyle ajan göreve bağlı kalacak biçimde sertleştirildi (bağımsız hakem 5.00/5;
  n = 7 tek-tur + 4 çok-tur senaryo, hakem std = 0 → **tavan-doygunluğu**, ayrım gücü sınırlı).
- **Daha büyük model denemesi (32B-AWQ):** Qwen2.5-VL-32B-Instruct-AWQ indirilip servis edilmeye
  çalışıldı. AWQ kernelleri Blackwell'de **çalıştı** (ağırlıklar yüklendi — uyumsuzluk yok), ancak
  ~20.5 GB ağırlık + KV cache 24 GB laptop GPU'ya sığmadı (*"No available memory for cache blocks"*).
  Sonuç: 32B pratikte ~32 GB+ (masaüstü GPU) ister.
- **Orta-boy model denemesi (InternVL3.5-14B-AWQ):** İndirilip servis edildi (24 GB'a sığar).
  AWQ Blackwell'de çalıştı; ancak InternVL'in **ağır çok-parçalı (tiling) görsel tokenizasyonu**
  12 kareyi ~40K token'a çıkarıp context'i taşırdı → 6 kareye düşürmek zorunda kaldık. Tam 32-klip
  kıyasında **7B daha iyi çıktı:** recall 23/24 vs 14/24, normal yanlış-pozitif 0/8 vs 1/8, gecikme
  ~1.3 vs ~3.05 s/video-sn; ayrıca InternVL'in Türkçesinde yabancı-kelime sızıntısı.
  *(n=32 — yön belirgin, ama tek klip farkı büyük; kesin bir üstünlük payı iddia edilmiyor.)*
  **Veriye dayalı karar: Qwen2.5-VL-7B** uzun süre en iyi dengeydi.
- **SOTA yükseltme (Qwen3-VL-8B-FP8):** A/B testinde 7B'yi **kategori adlandırma** (senaryo %83→%100,
  UCF suçları %0→%100) ve **Türkçe akıcılıkta** açıkça geçti; 24 GB'a FP8 ile KV başlığıyla sığar.
  Bedeli belirsiz normallerde daha yüksek yanlış-pozitif → **öz-doğrulama** (deduce-then-verify) ile
  dengelendi (hem FP kontrol hem agentic öz-kontrol). *Türkçe dil ajanı* yarışmasında bu belirleyici.
  **Güncel varsayılan: Qwen3-VL-8B-FP8 + öz-doğrulama + mekânsal grounding** (7B precision-yedek/ablation).

## Dokümanlar & Teslimatlar
- Mimari → [`docs/architecture.md`](docs/architecture.md)
- **Ölçüm dürüstlüğü: kanonik değerler + ölçüm sınırlarımız** → [`docs/olcum_durustlugu.md`](docs/olcum_durustlugu.md)
- Veri envanteri, lisanslar, bilinen veri kusurları → [`docs/veri_kaynaklari.md`](docs/veri_kaynaklari.md)
- Şartname uyum matrisi → [`docs/sartname_uyum.md`](docs/sartname_uyum.md)
- Kapsamlı performans raporu → [`docs/performans_raporu.md`](docs/performans_raporu.md)
- İyileştirme & deney günlüğü (literatür-temelli) → [`docs/iyilestirmeler.md`](docs/iyilestirmeler.md)
- Demo videosu senaryosu → [`docs/demo_script.md`](docs/demo_script.md)
- Sunum iskeleti / başlangıç deck → [`docs/sunum_iskeleti.md`](docs/sunum_iskeleti.md), `docs/sunum.pptx`
- GitHub & açık kaynak rehberi → [`docs/github_yukleme.md`](docs/github_yukleme.md)
- Veri seti → [`data/README.md`](data/README.md)

## Lisans
Apache License 2.0 — bkz. [`LICENSE`](LICENSE).
