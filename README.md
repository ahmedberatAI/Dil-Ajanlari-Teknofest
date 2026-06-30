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
- [Veri Seti](#veri-seti) · [Değerlendirme (KPI)](#değerlendirme-kpi)
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
Video → [ingest] → [perceive] → [reason] → [act] → [finalize] → JSON
        kare/segment  VLM olay    özet/risk   mock      birleştir
                      tespiti      /aksiyon    fonk.
```
LangGraph 5 düğümlü, hata toleranslı bir durum makinesidir; tüm model çağrıları yerel
vLLM sunucusuna gider.

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
- **Hızlı doğrulama:** `python scripts/make_test_video.py` ile sentetik test klibi.
- **Gerçek veri:** Açık kaynaklı gözetim/anomali veri setleri kullanılmaktadır.
  İndirme bağlantısı ve hazırlama adımları → [`data/README.md`](data/README.md).

## Değerlendirme (KPI)
Veriye dayalı bir değerlendirme altyapısı kurulmuştur:
- `benchmark/eval_clips.py` — dengeli set (anomali + normal) üzerinde anomali recall, **normal yanlış-pozitif oranı**, risk kalibrasyonu, kategori eşleşmesi, gecikme; sonuçlar `benchmark/results/` altında JSON olarak saklanır.
- `benchmark/judge.py` — özet kalitesi için LLM-as-judge.
- `benchmark/dialogue_test.py` — diyalog/otonomi robustluk testi (bağlam-değişimi, prompt-injection, halüsinasyon probu).
- `benchmark/variance.py`, `benchmark/compare.py` — varyans ve iterasyonlar arası karşılaştırma.

**Güncel sonuçlar (varsayılan: Qwen3-VL-8B + öz-doğrulama + grounding):**

| Metrik | Senaryo seti (yangın+düşme) | UCF-Crime (dayanıklılık) |
|---|---|---|
| Anomali recall (≥1 olay) | **%99±2** (11 koşu; tek koşu %100) | ~%78±10 (grainy; tek çekiliş %96) |
| Kategori adlandırma | %94±9 | grainy'de düşük — girdi-tavanı (aşağıda) |
| Risk kalibrasyonu | senaryo ~%95; **QWK 0.733** | — |
| Normal yanlış-pozitif | dar-FP ~%0; **operasyonel-FP ~%8–10 (dürüst)** | — |
| Diyalog robustluğu | **5.00/5** (bağımsız Gemma) | |
| Eşzamanlı throughput (x4) | **+24%** (3.7→4.6 video/dk) | |

> **Dürüst 3-seviyeli recall (grainy UCF):** TESPİT (olay var mı) **%96** · AKSİYON (doğru müdahale sınıfı)
> **%73** · TANIMA (birebir alt-etiket) **%46** — grainy 320×240'ta ince tip-tanıma bilgi-teorik tavandır
> (model-boyu değil; bkz `docs/iyilestirmeler.md` §15-§16).
>
> Not: değerlendirme setleri küçük → yanlış-pozitif/recall **varyans-baskın** (ortalama±std raporlanır);
> ayrıntı ve ablasyonlar (Qwen2.5-VL-7B precision-yedek dahil) `docs/iyilestirmeler.md`'de.

> Her iyileştirme baseline'a karşı ölçülür; güvenlik senaryosunda **yüksek recall + düşük dar-yanlış-pozitif
> (~%0)** önceliklendirilir; operasyonel-FP (~%8–10) dürüstçe raporlanır.

## Proje Yapısı
```
dilajan/          ana paket: config, video, schema, prompts, llm_client,
                  mock_functions, chat_agent, agent/ (LangGraph grafiği)
serve_vllm.py     vLLM sunucu başlatıcı
run_analysis.py   CLI (video -> JSON)
app.py            Gradio arayüzü (timeline + risk rozeti + canlı ilerleme + sohbet)
benchmark/        eval_clips, judge, dialogue_test, variance, compare + results/
scripts/          test videosu üreteci, veri seti indiriciler, yardımcı betikler
docs/             mimari, demo senaryosu, sunum iskeleti/pptx, GitHub rehberi
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
  (QWK 0.733); normalde dar-yanlış-pozitif ~%0 tutuldu (operasyonel-FP ~%8–10 dürüstçe raporlanır).
- **Performans:** vLLM eşzamanlı istekleri batch'ler; prefix-caching + serving-flag'leriyle (gpu-util
  0.90, max-num-seqs 32) eşzamanlı (x4) throughput **+24%** (3.7→4.6 video/dk), tek-akış ~1.5 s/vsn (hızlı mod ~0.6).
- **Diyalog robustluğu:** Bağlam-değişimi/prompt-injection denemelerine karşı few-shot reddetme
  örnekleriyle ajan göreve bağlı kalacak biçimde sertleştirildi (diyalog robustluğu 5.00/5).
- **Daha büyük model denemesi (32B-AWQ):** Qwen2.5-VL-32B-Instruct-AWQ indirilip servis edilmeye
  çalışıldı. AWQ kernelleri Blackwell'de **çalıştı** (ağırlıklar yüklendi — uyumsuzluk yok), ancak
  ~20.5 GB ağırlık + KV cache 24 GB laptop GPU'ya sığmadı (*"No available memory for cache blocks"*).
  Sonuç: 32B pratikte ~32 GB+ (masaüstü GPU) ister.
- **Orta-boy model denemesi (InternVL3.5-14B-AWQ):** İndirilip servis edildi (24 GB'a sığar).
  AWQ Blackwell'de çalıştı; ancak InternVL'in **ağır çok-parçalı (tiling) görsel tokenizasyonu**
  12 kareyi ~40K token'a çıkarıp context'i taşırdı → 6 kareye düşürmek zorunda kaldık. Tam 32-klip
  kıyasında **7B daha iyi çıktı:** recall %96 vs %58, normal yanlış-pozitif %0 vs %12, gecikme
  ~1.3 vs ~3.05 s/video-sn; ayrıca InternVL'in Türkçesinde yabancı-kelime sızıntısı.
  **Veriye dayalı karar: Qwen2.5-VL-7B** uzun süre en iyi dengeydi.
- **SOTA yükseltme (Qwen3-VL-8B-FP8):** A/B testinde 7B'yi **kategori adlandırma** (senaryo %83→%100,
  UCF suçları %0→%100) ve **Türkçe akıcılıkta** açıkça geçti; 24 GB'a FP8 ile KV başlığıyla sığar.
  Bedeli belirsiz normallerde daha yüksek yanlış-pozitif → **öz-doğrulama** (deduce-then-verify) ile
  dengelendi (hem FP kontrol hem agentic öz-kontrol). *Türkçe dil ajanı* yarışmasında bu belirleyici.
  **Güncel varsayılan: Qwen3-VL-8B-FP8 + öz-doğrulama + mekânsal grounding** (7B precision-yedek/ablation).

## Dokümanlar & Teslimatlar
- Mimari → [`docs/architecture.md`](docs/architecture.md)
- İyileştirme & deney günlüğü (literatür-temelli) → [`docs/iyilestirmeler.md`](docs/iyilestirmeler.md)
- Demo videosu senaryosu → [`docs/demo_script.md`](docs/demo_script.md)
- Sunum iskeleti / başlangıç deck → [`docs/sunum_iskeleti.md`](docs/sunum_iskeleti.md), `docs/sunum.pptx`
- GitHub & açık kaynak rehberi → [`docs/github_yukleme.md`](docs/github_yukleme.md)
- Veri seti → [`data/README.md`](data/README.md)

## Lisans
Apache License 2.0 — bkz. [`LICENSE`](LICENSE).
