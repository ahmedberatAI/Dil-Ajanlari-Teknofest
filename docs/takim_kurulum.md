# 👥 Takım Kurulum ve Çalışma Rehberi

**Hedef okur:** modeli kendi makinesinde çalıştıramayan takım üyeleri.
**Amaç:** kimse "bende çalışmıyor" diye boşta kalmasın.

> **30 saniyelik özet:** Modeli kurmaya çalışmayın. Kaptanın makinesindeki model
> sunucusuna **ağ üzerinden bağlanın** → [YOL 1](#yol-1--lan-paylaşımı-en-kolay-gpu-gerekmez).
> Tek komut:
> ```bash
> DILAJAN_VLLM_HOST=<kaptanin-lan-ip> python app.py
> ```
> Bu **kod değişikliği gerektirmez** (doğrulandı: `dilajan/config.py` → `base_url`).
>
> **İkinci 30 saniye — veri:** `git pull` **kodu getirir, veriyi getirmez** (`data/` 14 GB ve
> `.gitignore`'da). Çoğu iş için **veriye hiç ihtiyacın yok** → [VERIYI ALMA](#veriyi-alma--kim-hangi-veriye-ihtiyaç-duyar).

---

## İçindekiler
1. [Hızlı teşhis: hangi yol senin yolun?](#1-hızlı-teşhis-hangi-yol-senin-yolun)
2. [YOL 1 — LAN paylaşımı (en kolay, GPU gerekmez)](#yol-1--lan-paylaşımı-en-kolay-gpu-gerekmez)
3. [YOL 2 — Mock mod (model yokken arayüz geliştirme)](#yol-2--mock-mod-model-yokken-geliştirme)
4. [YOL 3 — Kendi makinende çalıştırma](#yol-3--kendi-makinende-çalıştırma)
5. [GPU olmadan katkı listesi](#5-gpu-olmadan-katkı-listesi-boşta-kalma)
6. [Sık karşılaşılan hatalar](#6-sık-karşılaşılan-hatalar-ve-çözümleri)
7. [Bu rehberde ne doğrulandı, ne doğrulanmadı](#7-bu-rehberde-ne-doğrulandı-ne-doğrulanmadı)

**Ayrıca (YOL 3'ten hemen sonra):**
[**VERIYI ALMA** — kim hangi veriye ihtiyaç duyar?](#veriyi-alma--kim-hangi-veriye-ihtiyaç-duyar)

---

## 1. Hızlı teşhis: hangi yol senin yolun?

Önce şunu çalıştır (repo kökünden):

```bash
python scripts/doctor.py
```

Bu betik **hiçbir proje bağımlılığı kurulmamış** bir makinede bile çalışır (yalnız standart
kütüphane kullanır, her kontrol try/except ile sarılıdır) ve sonunda **sana özel tavsiye**
basar: hangi YOL senin yolun, hangi komutu yazacaksın.

```bash
python scripts/doctor.py                # tam teshis + tavsiye
python scripts/doctor.py --skip-torch   # hizli (torch alt-surec probu atlanir)
python scripts/doctor.py --json         # makine-okunur cikti
```
Çıkış kodu: `0` = hazırsın · `1` = kritik engel var (tavsiye bölümü ne yapacağını söyler).

> **`No such file or directory` alıyorsan** kopyan eskidir → `git pull`. Aynı bilgiyi veren
> **elle teşhis** aşağıda.

**Elle teşhis — Windows PowerShell (4 komut, 4 cevap):**

```powershell
nvidia-smi                                   # 1) NVIDIA GPU + VRAM var mi?
wsl -l -v                                    # 2) WSL2 + Ubuntu-24.04 var mi?
python -c "import sys; print(sys.version)"   # 3) Python 3.12 var mi?
Test-NetConnection 192.168.1.102 -Port 8000  # 4) Kaptanin sunucusuna erisim var mi?
```

**Elle teşhis — Linux / WSL / macOS:**

```bash
nvidia-smi
python3 --version
curl -sf http://192.168.1.102:8000/health && echo "KAPTAN AYAKTA" || echo "ERISIM YOK"
```

### Karar tablosu

| Gördüğün çıktı | Git |
|---|---|
| `nvidia-smi` "not recognized"/komut yok → NVIDIA GPU veya sürücü yok | **YOL 1** |
| GPU var ama VRAM < 16 GB (`nvidia-smi` sağ üstteki `MiB` değeri) | **YOL 1** |
| GPU var, WSL2 yok ve kurmak istemiyorsun | **YOL 1** |
| Kaptan çevrimdışı, sen arayüz/pipeline geliştireceksin | **YOL 2** |
| NVIDIA GPU ≥ 16 GB **ve** WSL2 Ubuntu-24.04 var | **YOL 3** |
| Hiçbiri yok, ama katkı vermek istiyorsun | **[Bölüm 5](#5-gpu-olmadan-katkı-listesi-boşta-kalma)** |

---

## YOL 1 — LAN paylaşımı (EN KOLAY, GPU GEREKMEZ)

Kaptanın makinesinde model sunucusu çalışır; sen kendi makinenden **aynı ağ üzerinden**
bağlanırsın. Senin makinende **GPU, CUDA, WSL, vLLM — hiçbiri gerekmez.**

> ### 🏁 Yarışma kuralı notu (önemli)
> Bu kurulum **"tamamen yerel"** kuralına **UYAR**: dış API yok, bulut yok, ücretli servis yok.
> Model **bizim makinemizde**, **bizim ağımızda** çalışır — sadece iki bilgisayar arasında
> yerel bir TCP bağlantısı vardır.
> **YASAK olan** şunlar olurdu: bulut GPU kiralamak (Colab / RunPod / AWS), dış model API'si
> (OpenAI / Gemini / Claude), ücretli servis. Bunların hiçbirini kullanmıyoruz.

### Adım 1 (KAPTAN) — WSL2 NAT duvarını kaldır ⚠️ *atlanamaz*

**Bu adım olmadan LAN paylaşımı ÇALIŞMAZ.** WSL2 varsayılan olarak **NAT** ağı kullanır:
WSL içindeki 8000 portu Windows'tan `localhost` ile görünür, ama **ağdaki başka bir
makineden görünmez**. Bu makinede ölçüldü:

```
WSL içi IP     : 172.23.191.136     <- ayri, izole ag
Windows Wi-Fi  : 192.168.1.102      <- arkadaslarin gordugu ag
```

**Çözüm A — mirrored networking (önerilen, kalıcı).** Windows 11 22H2+ gerekir:

```powershell
# Windows PowerShell (normal kullanici yeterli)
@"
[wsl2]
networkingMode=mirrored
"@ | Out-File -Encoding utf8 "$env:USERPROFILE\.wslconfig"

wsl --shutdown          # WSL'i kapat; bir sonraki aciliste yeni ag modu gecerli olur
```
Bundan sonra WSL, Windows'un ağ arayüzünü paylaşır: WSL içinde `0.0.0.0`'a bağlanan bir
sunucu, LAN'dan `192.168.1.102:8000` olarak görünür.

**Çözüm B — portproxy (mirrored açılamıyorsa).** WSL'in iç IP'si her yeniden başlatmada
değişir, bu yüzden **WSL'i her yeniden başlattığında tekrar çalıştır**:

```powershell
# YONETICI PowerShell
$wslIp = (wsl -d Ubuntu-24.04 hostname -I).Trim().Split(" ")[0]
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 `
      connectport=8000 connectaddress=$wslIp
netsh interface portproxy show v4tov4          # dogrulama

# Geri almak icin:
# netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0
```

### Adım 2 (KAPTAN) — Güvenlik duvarında 8000 portunu aç

```powershell
# YONETICI PowerShell — YALNIZ ozel ag profili (kafe/otel agina acmayin)
New-NetFirewallRule -DisplayName "DilAjan vLLM 8000" -Direction Inbound `
  -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private

# Yarisma/calisma bitince KALDIR:
# Remove-NetFirewallRule -DisplayName "DilAjan vLLM 8000"
```

> Bu bir güvenlik ayarı değişikliğidir; **kaptanın kendisi** çalıştırmalı, `-Profile Private`
> ile sınırlı tutulmalı ve iş bitince kaldırılmalıdır.

### Adım 3 (KAPTAN) — Sunucuyu tüm arayüzlere bağla

```bash
# WSL / Ubuntu-24.04 icinde, repo kokunden
DILAJAN_VLLM_HOST=0.0.0.0 python serve_vllm.py
```
İlk açılış ~90 sn (model + CUDA graph). `serve_vllm.py` bu değeri doğrudan
`--host` bayrağına verir — **kod değişikliği yok**.

### Adım 4 (KAPTAN) — Doğru IP'yi üyelere ver

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object InterfaceAlias -match "Wi-Fi|Ethernet" |
  Select-Object InterfaceAlias, IPAddress
```
```
InterfaceAlias  IPAddress
--------------  ---------
Wi-Fi           192.168.1.102     <- BUNU ver
```

> ❌ **`vEthernet (WSL ...)` satırındaki `172.x.x.x` adresini VERME** — o WSL'in iç adresidir,
> arkadaşların makinesinden erişilemez. Üyelere `192.168.x.x` / `10.x.x.x` olanı ver.

### Adım 5 (ÜYE) — Bağlantıyı test et (uygulamayı açmadan önce)

```powershell
# Windows PowerShell
curl.exe http://192.168.1.102:8000/health      # bos govde + hatasiz cikis = AYAKTA
curl.exe http://192.168.1.102:8000/v1/models   # model adini dondurur
Test-NetConnection 192.168.1.102 -Port 8000    # TcpTestSucceeded : True olmali
```
```bash
# Linux / WSL / macOS
curl -sf http://192.168.1.102:8000/health && echo "AYAKTA" || echo "ERISIM YOK"
curl -s  http://192.168.1.102:8000/v1/models
```

Bu adım geçmeden 6. adıma geçme — geçmiyorsa
[Bölüm 6, hata #1](#6-sık-karşılaşılan-hatalar-ve-çözümleri).

### Adım 6 (ÜYE) — Uygulamayı kaptanın modeline bağla

```powershell
# Windows PowerShell
$env:DILAJAN_VLLM_HOST = "192.168.1.102"
python app.py                       # http://127.0.0.1:7860
```
```bash
# Linux / WSL / macOS
DILAJAN_VLLM_HOST=192.168.1.102 python app.py
DILAJAN_VLLM_HOST=192.168.1.102 python run_analysis.py data/test_clip.mp4   # CLI
```

**Kalıcı yapmak** (her seferinde yazmamak için) — repo kökünde `.env` dosyası:

```bash
# C:/Users/<sen>/.../DilAjanlariTeknofest/.env
DILAJAN_VLLM_HOST=192.168.1.102
```
`dilajan/config.py` bu dosyayı otomatik okur (`env_file=".env"`); komutları **repo kökünden**
çalıştırdığın sürece geçerlidir.

**✅ Nasıl anlarım çalıştığını:** arayüzün üstündeki rozet **`MODEL ÇEVRİMİÇİ`** (yeşil) olmalı.
Rozet `MODEL SUNUCUSU KAPALI` (kırmızı) diyorsa `DILAJAN_VLLM_HOST` ayarlanmamıştır veya
5. adım geçmemiştir.

### Üye tarafında kurulum: `vllm` GEREKMEZ

İstemci tarafı **vLLM'i import etmez** (doğrulandı: `app.py` → `dilajan/agent/graph.py` →
`llm_client.py` yalnız `openai` istemcisi kullanır; `vllm` sadece `serve_vllm.py` içinde,
o da alt-süreç olarak). Yani `requirements.txt`'ten **`vllm==0.23.0` satırını atlayarak**
kurabilirsin — Windows'ta doğrudan, WSL olmadan:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install "langgraph>=1.2,<2" "langchain>=1.3,<2" "langchain-openai>=1.3,<2" `
            "openai>=2.0" "pydantic>=2.7" "pydantic-settings>=2.4" `
            "av>=14" "pillow>=10" "opencv-python-headless>=4.10" "gradio>=6.0"
```

> **Dürüst uyarı — üyede sonuçlar birebir aynı olmayabilir.** Projedeki yerel YOLO adımları
> (`verify_pose_falls`, `detect_vehicles`, `detect_crowd`, `restricted_zones`)
> `dilajan/detector.py` içinde **`device="cuda"` sabitiyle** çağrılır ve GPU'suz makinede
> hata verip **fail-open** ile sessizce devre dışı kalır. Bu adımlar analizi çökertmez ama
> senin makinendeki çıktı, kaptanınkinden **farklı olabilir**.
> **Resmî ölçüm/benchmark her zaman kaptanın makinesinde koşulur.**

### Alternatif A — Kaptan doğrudan arayüzü paylaşsın (üyede sıfır kurulum)

```bash
# KAPTAN
DILAJAN_HOST=0.0.0.0 python app.py
```
Üye sadece tarayıcıdan: `http://192.168.1.102:7860` — **hiçbir kurulum gerekmez.**
Not: 1. ve 2. adımlar (NAT + güvenlik duvarı) bu kez **7860** portu için de yapılmalı.
Arayüz portu kodda sabittir (`app.py`: `server_port=7860`).

### Alternatif B — `gradio.live` tüneli (hızlı ama dikkat)

```bash
# KAPTAN — ag ayari hic yapmadan paylasilabilir link uretir
DILAJAN_SHARE=1 python app.py
```
**Dürüst uyarı:** Model ve çıkarım **%100 yerel kalır** (hiçbir veri dış bir modele gitmez),
**ama** trafik Gradio'nun **üçüncü-taraf tünel sunucusundan** geçer ve link **herkese açıktır**.
→ Yalnız **ekip içi hızlı gösterim** için kullanın. **Jüri demosunda ve resmî ölçümde
LAN (Alternatif A) veya `localhost` kullanın.**

---

## YOL 2 — Mock mod (model yokken geliştirme)

Kaptan çevrimdışıysa veya sadece arayüz/akış geliştireceksen: model **hiç yüklenmez**,
istemci **hiçbir ağ çağrısı yapmaz**, yerine deterministik sahte yanıtlar üretilir.

```bash
DILAJAN_MOCK=1 python app.py                            # arayuz
DILAJAN_MOCK=1 python run_analysis.py data/test_clip.mp4 --sartname   # CLI
```
```powershell
# Windows PowerShell
$env:DILAJAN_MOCK = "1"; python app.py
```

**Bilmen gereken 3 davranış:**
- Üretilen özet **`[MOCK]` damgası** taşır ve ilk kullanımda terminale büyük bir uyarı basılır
  → mock çıktısı yanlışlıkla gerçek sonuç sanılamaz.
- Arayüzdeki sunucu rozeti yine **`MODEL SUNUCUSU KAPALI`** (kırmızı) görünebilir: o rozet
  gerçek `/health` adresini yoklar. **Normaldir** — analiz yine çalışır.
- Mock modda `verify_pose_falls` otomatik kapanır (GPU'suz makinede gereksiz YOLO yüklemesi olmasın diye).

> `DILAJAN_MOCK=1` çalışmıyorsa kopyan eskidir → `git pull`. Anahtarın eski adı
> `DILAJAN_MOCK_MODE=1` de kabul edilir.

**Mock modu ilk kez kullanmadan önce 3 saniyelik teyit** (bu rehber yazılırken mock motoru
aynı teslim içinde hâlâ yazılıyordu — bkz. [Bölüm 7](#7-bu-rehberde-ne-doğrulandı-ne-doğrulanmadı)):

```bash
DILAJAN_MOCK=1 python run_analysis.py data/test_clip.mp4
```
Beklenen: özet **`[MOCK]`** damgalı, `events` listesi **dolu**, `decision_trace` içinde
**hata satırı yok**. Eğer `perceive: segment 0 hatasi: ...` görüyorsan mock motoru sende
eksiktir (`git pull`) — pipeline fail-open olduğu için **çökmez**, sadece boş sonuç döner.

**Modelsiz her koşulda çalışan yedek kontrol (doğrulandı):**

```bash
# Arayuz modelsiz KURULUYOR mu?  ->  "Blocks"
python -c "import app; print(type(app.build_ui()).__name__)"
```
Mock **kapalıyken** sunucu yoksa arayüz yine açılır ve gezilebilir; "Analiz Et"e basınca
beklenen hatayı verir: `Analiz tamamlanamadı — model sunucusunun çalıştığından emin olun.`

**Ne işe yarar:**
- Arayüz/CSS/yerleşim geliştirmek, yeni panel/sekme eklemek
- Pipeline ve sohbet akışını, bileşen bağlantılarını görmek
- `to_sartname_dict()` çıktı sözleşmesini bozmadığını kontrol etmek
- Demo senaryosu provası, ekran görüntüsü/sunum materyali hazırlamak

**NE İŞE YARAMAZ (kırmızı çizgi):**

> # ⛔ MOCK ÇIKTISI GERÇEK ÖLÇÜM DEĞİLDİR.
> **Mock modda üretilen hiçbir sayı; recall, yanlış-pozitif, risk kalibrasyonu, gecikme veya
> özet kalitesi olarak RAPORLANAMAZ.** Ne `benchmark/results/` altına yazılır, ne rapora,
> ne sunuma, ne README'ye girer. Yayınlanan her rakam kaptanın makinesinde, gerçek modelle
> koşulmuş ve `benchmark/results/` altında kaydı olan bir koşudan gelir
> (bkz. [`docs/olcum_durustlugu.md`](olcum_durustlugu.md)).

---

## YOL 3 — Kendi makinende çalıştırma

> Temel kurulum adımları README'de: [Kurulum](../README.md#kurulum) ve
> [Çalıştırma](../README.md#çalıştırma). **Onları tekrarlamıyoruz** — burada yalnız
> README'de olmayan / farklı olan noktalar var.

### Gerçekçi donanım eşiği

| | |
|---|---|
| GPU | **NVIDIA** (CUDA). AMD / Intel Arc / Apple Silicon → bu yığında **çalışmaz** |
| VRAM | Ağırlık (FP8) ~10 GB **+ KV cache** → pratikte **≥ 16 GB**, rahat çalışma **24 GB** |
| İşletim sistemi | Linux **veya** Windows + **WSL2** (Windows'ta vLLM yerel olarak **yok**) |
| Python | 3.12 |
| Disk | Model indirmesi için ~15–20 GB boş alan |

### README'ye ek notlar

- **WSL varsayılan distro tuzağı:** Docker Desktop kuruluysa varsayılan distro
  `docker-desktop` olabilir. Komutları **daima** distro belirterek çalıştır:
  ```powershell
  wsl -d Ubuntu-24.04 -- <komut>
  ```
- **Blackwell (RTX 50xx) → `cu130` zorunlu.** README'deki torch satırı bu yüzden `cu130`'dur;
  `cu128` kurarsan `libcudart.so.13` hatası alırsın ([hata #3](#6-sık-karşılaşılan-hatalar-ve-çözümleri)).
  RTX 30xx/40xx'te farklı bir CUDA tekerleği çalışabilir, **ama biz denemedik** —
  `vllm==0.23.0` torch sürümüne bağlıdır, **sürümleri kendi başına değiştirme**, önce takıma sor.
- **Sunucuyu her zaman `python serve_vllm.py` ile başlat**, `vllm serve ...` ile değil:
  Blackwell/WSL için gereken ortam değişkenlerini (`NVCC_APPEND_FLAGS`,
  `VLLM_USE_FLASHINFER_SAMPLER=0`, `CUDA_HOME`/`LD_LIBRARY_PATH`)
  **yalnızca** `serve_vllm.py` içindeki `apply_cuda_env()` ayarlar.

### VRAM yetmiyorsa (küçültme reçeteleri)

```bash
# 1) Once ayni modeli sikistir (en az sapma)
DILAJAN_GPU_MEMORY_UTILIZATION=0.80 \
DILAJAN_MAX_MODEL_LEN=4096 \
DILAJAN_MAX_NUM_SEQS=8 \
python serve_vllm.py

# 2) Yetmezse kucuk/hassasiyet-yedek modele gec (7B)
DILAJAN_MODEL_NAME=Qwen/Qwen2.5-VL-7B-Instruct \
DILAJAN_MAX_MODEL_LEN=4096 \
DILAJAN_GPU_MEMORY_UTILIZATION=0.85 \
python serve_vllm.py

# 3) Analiz tarafinda yuku dusur (istemci tarafi; sunucudan bagimsiz)
DILAJAN_FAST_MODE=1 python app.py          # tek-gecisli algi, daha az/kucuk kare
```

> ⚠️ **Farklı model / farklı ayar = farklı sonuç.** Bu reçeteler *çalıştırabilmek* içindir.
> Rapora giren ölçümler **yalnızca varsayılan yapılandırmayla** (Qwen3-VL-8B-FP8, öz-doğrulama +
> grounding açık) koşulur.

---

## VERIYI ALMA — kim hangi veriye ihtiyaç duyar?

> **Önce bunu oku:** `git pull` **kodu getirir, veriyi getirmez.** `data/` dizini 14 GB'dır ve
> `.gitignore`'dadır — bilerek. Depoya video koymuyoruz (lisans + boyut).
> **İyi haber:** yapacağın işlerin çoğu **hiç veri istemiyor.**

### Adım 0 — Gerçekten veriye ihtiyacın var mı?

| Ne yapacaksın | İhtiyacın olan veri | Komut |
|---|---|---|
| Arayüz / CSS / panel geliştirme, pipeline okuma, birim testi | **HİÇBİRİ** | `DILAJAN_MOCK=1 python app.py` |
| Testleri koşmak (`tests/`, `benchmark/*self*`) | **HİÇBİRİ** (sahte VLM istemcisi) | [Bölüm 5.1](#51-testler--her-prdan-önce-hepsi-saniyeler-sürer) |
| "Bir video verip çıktıyı göreyim" | **1 klip** (~5–20 MB) | `python scripts/get_ucf_clip.py RoadAccidents` |
| Yangın/düşme senaryosunu denemek | **Küçük set** (~180 MB) | `python scripts/get_firesense.py` · `python scripts/get_gmdcsa.py` |
| **Benchmark / resmî ölçüm koşmak** | **Tam set** (~3–14 GB) | aşağıdaki tablo |

**Vakit kaybetme:** ilk iki satırdaysan bu bölümün geri kalanını okumana gerek yok.
Resmî ölçüm zaten **kaptanın makinesinde** koşulur (bkz. [`docs/olcum_durustlugu.md`](olcum_durustlugu.md)).

### Adım 1 — Ne var, nereden gelir? (ağ gerekmez)

```bash
python scripts/hf_dataset_pull.py --list
```
Bu komut **hiçbir şey indirmez**; `hf_manifest.json`'u okuyup her set için
*"HF'den mi gelir, yoksa hangi betikle mi kurulur"* sorusunu yanıtlar ve
**zaten diskinde ne olduğunu** gösterir.

Setler **lisansa göre üçe ayrılır** — bu ayrım keyfî değil, zorunludur:

| Set | Klip | Kaynak | HF deposundan gelir mi? |
|---|---|---|---|
| `data/eval_stress` | 9 | FIRESENSE (CC BY 4.0) | ✅ evet |
| `data/falls_real` | 15 | GMDCSA-24 (CC BY 4.0) | ✅ evet |
| `data/robust` | 4 | kendi ürettiğimiz | ✅ evet |
| `data/eval_scenario` | 37 | **karışık** | ⚠️ **19/37**'si gelir (Fire + GMDCSA düşmeler) |
| `data/eval_defense` | 200 | Eskişehir/Mendeley | ⛔ hayır — **lisans çelişkisi**, aşağı bkz. |
| `data/falls_surveillance` | 6 | URFD (akademik) | ⛔ hayır |
| `data/eval_tune`, `eval_holdout`, `e2_vehicle` | 31 + 32 + 9 | **UCF-Crime** (CC değil) | ⛔ **asla** |

> **`eval_scenario` neden kısmi geliyor?** İçinde dört ayrı kaynak var:
> `Fall/` = 9 GMDCSA (CC BY ✅) + 6 URFD (akademik ⛔),
> `Normal/` = 8 Eskişehir (çelişkili ⚠️) + 4 UCF-Crime (⛔).
> Bu yüzden lisans kararı **set düzeyinde değil, DOSYA düzeyinde** verilir.
> Seti tamamlamak için kurucu betiklerini koşman gerekir (araç sana söyler).

### Adım 2 — HF deposundan çekme (tek komut)

> **Depo henüz yayınlanmadı.** Yayınlandığında adı takıma duyurulacak; o zamana kadar
> aşağıdaki komut sana **ne yapman gerektiğini söyleyip** düzgünce çıkar (çökmez).

```bash
pip install "huggingface_hub>=0.34"

# 1) Once ne olacagini gor (indirme YOK)
python scripts/hf_dataset_pull.py --repo KULLANICI/dilajanlari-eval --dry-run

# 2) Indir (varsayilan: dagitilabilir tum setler)
python scripts/hf_dataset_pull.py --repo KULLANICI/dilajanlari-eval

# 3) Secmeli indirme
python scripts/hf_dataset_pull.py --repo KULLANICI/dilajanlari-eval --sets eval_stress,falls_real
```
```powershell
# Windows PowerShell — depo adini kalici yap, her seferinde --repo yazma
$env:DILAJAN_HF_REPO = "KULLANICI/dilajanlari-eval"
python scripts/hf_dataset_pull.py
```

**Davranış (fiilen doğrulandı):**
- Zaten var olan ve **MD5'i tutan** dosyalar **atlanır** — komutu tekrar tekrar koşmak güvenlidir.
- Yarım kalan indirme **kaldığı yerden** sürer; `Ctrl+C` veri kaybettirmez.
- Bir dosya patlarsa **iş durmaz** (fail-open), sonunda hangi dosyanın başarısız olduğu raporlanır.
- İndirme bittiğinde **bütünlük doğrulaması otomatik koşar**; eksik/bozuk varsa çıkış kodu `6`.

### Adım 3 — HF'de OLMAYAN setler (UCF-Crime, URFD, Eskişehir)

Bu setler lisans gereği **hiçbir zaman** HF deposuna konmaz. Araç bunları
manifest'te görür, "HF'de yok" der ve **doğru kurucu betiği** önerir — betik adını
ezberlemene gerek yok, `--list` sana söyler. Referans:

```bash
# UCF-Crime turevleri (eval_tune + eval_holdout: once buyuk seti indir, sonra ayrik bol)
python scripts/get_ucf_many.py
python scripts/split_eval_big.py

# UCF RoadAccidents (arac/kalabalik E2 kaniti)
python scripts/get_vehicle_accidents.py

# URFD tavan-acili dusmeler
python scripts/get_urfd_overhead.py

# Eskisehir tesis seti: once 9.4 GB havuz, sonra 200 kliplik degerlendirme seti
python scripts/get_industrial.py
python scripts/build_defense_eval.py

# Senaryo setini tamamla (Fire + Fall + Normal bir araya getirilir)
python scripts/get_firesense.py
python scripts/get_gmdcsa.py
python scripts/build_scenario_eval.py
```

> ⛔ **UCF-Crime'ı hiçbir yere yeniden yüklemeyin.** Akademik/araştırma kullanımı için
> sunulur, Creative Commons **değildir**. Aynısı URFD için de geçerlidir.
>
> ⚠️ **Eskişehir/Mendeley seti (`eval_defense`, `industrial`) — çözülmemiş lisans çelişkisi.**
> Mendeley genel API'si **CC BY 4.0** diyor (2026-07-27'de tekrar okundu, hâlâ öyle diyor),
> ilgili *Data in Brief* makalesinde **CC BY-NC** geçtiği biliniyor. **Muhafazakâr okumayı**
> benimsedik: **CC BY-NC** (ticari kullanım yok, atıf zorunlu) — yani çelişki makale
> metninden teyit edilene kadar bu klipler **yeniden dağıtılmaz**. Araç bunları
> varsayılan olarak dışarıda tutar; teyit gelirse `--include-conditional` bayrağı açar.
> Bu, en büyük setimizin (2.4 GB, 200 klip) HF'den **gelmeyeceği** anlamına gelir —
> `get_industrial.py` zaten paralel indirdiği için pratik kayıp küçüktür.

### Adım 4 — Doğrulama (ağ gerekmez, her zaman koşulabilir)

```bash
# Yerel dosyalari manifest MD5'leri ile karsilastir
python scripts/hf_dataset_pull.py --verify

# Yerelde kurdugun (HF disi) setleri de dogrula — UCF/URFD/Eskisehir dahil
python scripts/hf_dataset_pull.py --verify --verify-all

# Aracin kendi mantigini test et (veri de ag da GEREKMEZ)
python scripts/hf_dataset_pull.py --selftest        # -> "TUM SELFTESTLER GECTI"
```
Çıkış kodu `0` = her şey yerinde · `6` = eksik/bozuk dosya var (araç hangisi olduğunu yazar).
Bozuk dosya için aynı komutu `--force` ile tekrarla.

**Bu neden önemli:** jüri benchmark'ı birebir yeniden koşabilsin diye her klibin MD5'i
`hf_manifest.json` içinde kayıtlıdır. Senin diskindeki `eval_stress` ile kaptanınki
**aynı dosyalar mı**, tek komutla kanıtlanır.

### Kaptan için: manifest üretme ve yayınlama

```bash
# Manifest'i yeniden uret (data/ degistiginde)
python scripts/hf_dataset_pull.py --make-manifest

# Yukleme komutlarini GOR — bu betik hicbir sey YUKLEMEZ, yalnizca metin basar
python scripts/hf_dataset_pull.py --upload-plan --repo KULLANICI/dilajanlari-eval
```
`--upload-plan` hangi klibin neden dışarıda kaldığını tek tek gösterir ve karışık lisanslı
klasörler için **toplu yükleme yapma** uyarısı verir. Yükleme dışa açık bir işlemdir;
komutları **kaptan kendisi**, çıktıyı gözden geçirdikten sonra çalıştırır.

**Manifest hangi dosyadan okunur?** Araç şu sırayla bakar; ilk bulduğunu kullanır ve
hangisini kullandığını çıktının ilk satırında yazar:

| Sıra | Yol | Ne zaman olur |
|---|---|---|
| 1 | `--manifest <yol>` | elle verirsen |
| 2 | `data/hf_manifest.json` | **paketleyici araç** yazdıysa veya HF'den indiyse |
| 3 | `data/_hf/hf_manifest.json` | ayrı bir dizine indirdiysen |
| 4 | `hf_manifest.json` (proje kökü) | `git pull` ile gelen kopya — **çoğu üyede bu** |

Paketleyici tarafın manifest biçimi farklıysa **otomatik uyarlanır**; o manifestteki
"bu klip pakete girdi/girmedi" kararı **bizim kural motorumuzun önüne geçer** (paketleyen
taraf, depoda ne olduğunu bilen taraftır).

### 🏁 Yarışma kuralı notu — HF neden serbest?

> **KRİTİK AYRIM:**
> - HF'i **model ÇALIŞTIRMAK** için kullanmak **YASAK** — Inference API, Inference Endpoints,
>   Spaces: hepsi "harici API / bulut" sayılır. **Kullanmıyoruz.**
> - HF'i **VERİ DAĞITMAK** ve **MODEL AĞIRLIĞI İNDİRMEK** için kullanmak **SERBEST** — indirilen
>   şey diske iner, çıkarım **%100 yerelde**, bizim vLLM sunucumuzda koşar.
>
> `scripts/hf_dataset_pull.py` yalnızca dosya indirir; **hiçbir model çağrısı yapmaz.**
> Model ağırlığı da (`Qwen3-VL-8B-Instruct-FP8`) aynı mantıkla HF'den indirilir ve
> yerelde çalışır — bu, README'deki kurulum adımlarının zaten yaptığı şeydir.
> Ayrıca bu yayın, şartnamenin *"veri setinin indirilebileceği herkese açık bağlantı"*
> şartını da güçlendirir.

---

## 5. GPU olmadan katkı listesi (boşta kalma!)

Aşağıdaki her komut **GPU'suz ve model sunucusu kapalıyken** çalışır ve **bu rehber yazılırken
fiilen koşulmuştur** (çıktılar gerçek). Repo kökünden çalıştır.

### 5.1 Testler — her PR'dan önce (hepsi saniyeler sürer)

```bash
python scripts/doctor.py --skip-torch    # ortam teshisi (bagimlilik gerektirmez)
python tests/test_agent_k1_k3_k6.py      # -> "TUM TESTLER GECTI"
python tests/test_agent_k2_k4_k5.py      # -> "TUM TESTLER GECTI"
python tests/test_capraz_dogrulama.py    # -> "TUM CAPRAZ DOGRULAMA TESTLERI GECTI"
python tests/test_kusur2_severity.py     # -> "TUM TESTLER GECTI"
```
Ajanın tek VLM temas noktası sahte istemciyle değiştirilir → **GPU/model gerekmez.**

### 5.2 İstatistik & A/B altyapısı (rapor hijyeni)

```bash
python benchmark/test_stats_utils.py     # -> "7/7 test gecti" (Wilson GA, ondalik disiplini)
python benchmark/test_paired_test.py     # -> McNemar guc analizi self-testleri
python benchmark/paired_test.py          # son iki sonuc dosyasini eslestirilmis karsilastirir
```
`paired_test.py` **kayıtlı** `benchmark/results/*.json` dosyalarını okur (model çağırmaz);
son koşumda 200 eşleşen klip üzerinden çalıştı.

### 5.3 Veri denetimi ve temizliği

```bash
python scripts/audit_eval_sets.py --selftest     # -> "TUM SELFTESTLER GECTI"
python scripts/audit_eval_sets.py --only eval_defense -v
python scripts/dedupe_data.py --root data        # RAPOR MODU: --apply olmadan hicbir sey degismez
python scripts/verify_clips.py data/eval_scenario
```
`verify_clips.py` donmuş/kısa/düşük-fps klipleri yakalar (örn. `data/eval_scenario`'da
45 klipten 9'u sorunlu çıktı). Bu iş **tamamen GPU'suzdur** ve ölçüm dürüstlüğümüzün temelidir.

### 5.4 Arayüz geliştirme (modelsiz)

```bash
python -c "import app; print(type(app.build_ui()).__name__)"    # -> Blocks
python app.py                                                   # arayuz acilir, analiz icin model gerekir
```

### 5.5 Ağ gerektiren ama GPU gerektirmeyen işler

```bash
python scripts/hf_dataset_pull.py --list   # ONCE BUNU: hangi set nereden gelir, sende ne var
python scripts/get_ucf_many.py             # veri seti indiriciler
python scripts/get_firesense.py
python scripts/get_industrial.py
python scripts/build_scenario_eval.py      # degerlendirme setleri kurar
python scripts/build_defense_eval.py
```
> Bunlar GPU istemez ama **internet + disk** ister ve dakikalar sürebilir; indirme boyutunu
> takıma haber ver. *(Bu rehber yazılırken indirme yapılmadı — komut biçimi doğrulandı,
> çalıştırılmadı.)*
>
> Hangisini koşacağını `hf_dataset_pull.py --list` sana söyler; ezberlemene gerek yok
> → [VERIYI ALMA](#veriyi-alma--kim-hangi-veriye-ihtiyaç-duyar).

### 5.6 Kod okumaya/yazmaya açık, tamamen deterministik modüller

| Dosya | İş |
|---|---|
| `dilajan/report.py` | operatör raporu / tutanak üretimi |
| `dilajan/evidence.py` | kanıt paketi (kare + meta) |
| `dilajan/tamper.py` | kamera sabotaj sezgileri (deterministik) |
| `dilajan/briefing.py` | vardiya brifingi — **fallback (modelsiz) yolu** test edilebilir |
| `benchmark/{stats_utils,paired_test,aggregate,dedup,labels}.py` | istatistik ve etiketleme |

Bu modüller için **birim testi yazmak** en yüksek değerli GPU'suz katkıdır.

### 5.7 Kod dışı (ama teslimin yarısı)

- `docs/*.md` gözden geçirme, `docs/demo_script.md` provası
- Sunum: `docs/sunum_iskeleti.md`, `scripts/make_pptx.py`, `scripts/make_takim_tanitim.py`
- README/rapor tutarlılığı: yayınlanan her rakamın
  [`docs/olcum_durustlugu.md`](olcum_durustlugu.md) ile birebir uyuştuğunu denetlemek

---

## 6. Sık karşılaşılan hatalar ve çözümleri

*(Hepsi bu projenin gerçek geçmişinden — bkz. [README "Karşılaşılan Zorluklar"](../README.md#karşılaşılan-zorluklar-ve-çözümler) ve [`docs/iyilestirmeler.md`](iyilestirmeler.md).)*

**1. `curl: (7) Failed to connect` / `TcpTestSucceeded : False`** (üye kaptana bağlanamıyor)
Sırayla kontrol et:
```bash
# a) Kaptanin makinesinde sunucu 0.0.0.0'a bagli mi? (127.0.0.1 ise disaridan GORUNMEZ)
#    Kaptanda:  DILAJAN_VLLM_HOST=0.0.0.0 python serve_vllm.py
# b) Kaptan KENDI makinesinde calisiyor mu?
curl -sf http://127.0.0.1:8000/health && echo LOKAL-OK
# c) WSL2 NAT duvari kaldirildi mi? (Adim 1 — mirrored VEYA portproxy)
# d) Guvenlik duvari kurali eklendi mi? (Adim 2)
# e) Dogru IP mi verildi? 172.x.x.x = WSL ic adresi, YANLIS.
# f) Ikiniz ayni agda misiniz? (biri Wi-Fi, digeri telefon hotspot'u olmasin)
```

**2. Arayüzde `MODEL SUNUCUSU KAPALI` rozeti**
`DILAJAN_VLLM_HOST` ayarlanmamış veya yanlış. Rozet doğrudan
`http://$DILAJAN_VLLM_HOST:8000/health` adresini yoklar. Değişkeni **`python app.py`'yi
çalıştıran kabukta** ayarla ya da `.env` dosyasına yaz.

**3. `libcudart.so.13: cannot open shared object file`**
torch **cu128** ile kurulmuş, vLLM 0.23 ise CUDA 13'e derli. Çözüm: torch'u `cu130`
tekerleğiyle yeniden kur ([README Kurulum adım 4](../README.md#kurulum)).

**4. flashinfer JIT link hatası (`collect2: ld ... error`)**
Kısmi CUDA toolkit yerleşiminde flashinfer sampler linklenemiyor. `apply_cuda_env()`
bunu `VLLM_USE_FLASHINFER_SAMPLER=0` ile kapatır → **sunucuyu `python serve_vllm.py` ile
başlat**, `vllm serve` ile değil. Aynı sebeple `DILAJAN_KV_CACHE_DTYPE=fp8` **açma** (denendi, reddedildi).

**5. CCCL/nvcc sürüm uyuşmazlığı (nvcc 13.2 vs cccl 13.3)**
JIT derlemesini durduran sürüm kontrolü `NVCC_APPEND_FLAGS=-DCCCL_DISABLE_CTK_COMPATIBILITY_CHECK`
ile aşılır — bunu da `apply_cuda_env()` otomatik ayarlar (yine: `serve_vllm.py` ile başlat).

**6. `No available memory for cache blocks` (sunucu açılışta ölüyor)**
Ağırlıklar sığdı ama KV cache'e yer kalmadı. Bizde 32B-AWQ (~20.5 GB) 24 GB'lık laptop GPU'ya
bu yüzden sığmadı. Çözüm: [YOL 3 küçültme reçeteleri](#vram-yetmiyorsa-küçültme-reçeteleri) —
`DILAJAN_GPU_MEMORY_UTILIZATION` ve `DILAJAN_MAX_MODEL_LEN` düşür, ya da 7B'ye geç.

**7. Windows'ta `pip install vllm` başarısız**
**Normal.** vLLM Windows'ta yerel çalışmaz. İki seçenek: WSL2 (YOL 3) veya
**`vllm` olmadan istemci kurulumu** ([YOL 1 üye kurulumu](#üye-tarafında-kurulum-vllm-gerekmez)).

**8. Sunucu aniden ölüyor / terminali kapatınca gidiyor (WSL süreç ağacı)**
`wsl --shutdown`, terminalin kapanması veya Windows uyku modu WSL süreç ağacını koparır.
Sunucuyu **kendi terminalinde** çalıştır ve o pencereyi kapatma. Takılı kalan süreçleri temizle:
```bash
pkill -f "api_server|EngineCore"    # WSL icinde
```

**9. `Port 8000 already in use`**
Eski sunucu hâlâ ayakta (hata #8'deki `pkill`) **veya** başka bir uygulama portu tutuyor.
Port değiştirilecekse **kaptan ve tüm üyeler aynı değeri** kullanmalı:
```bash
DILAJAN_VLLM_PORT=8001 DILAJAN_VLLM_HOST=0.0.0.0 python serve_vllm.py   # kaptan
DILAJAN_VLLM_PORT=8001 DILAJAN_VLLM_HOST=192.168.1.102 python app.py    # uye
```

**10. `Port 7860 already in use` (arayüz)**
Arayüz portu kodda sabittir (`app.py`: `server_port=7860`). Açık kalan diğer `app.py`
örneğini kapat.

**11. Windows'ta `wsl <komut>` yanlış distroya gidiyor**
Docker Desktop varsayılan distroyu değiştirmiş olabilir → daima `wsl -d Ubuntu-24.04` kullan.

---

## 7. Bu rehberde ne doğrulandı, ne doğrulanmadı

Projenin ölçüm-dürüstlüğü kuralı bu rehber için de geçerlidir.

**✅ Fiilen koşuldu / doğrulandı (2026-07-27, GPU kapalı):**
- `python scripts/doctor.py` → 9 kontrol + tavsiye bölümü, çıkış kodu 0 (sunucu kapalıyken bile çökmedi)
- `DILAJAN_VLLM_HOST=192.168.1.42` → istemci `base_url = http://192.168.1.42:8000/v1`
- `serve_vllm.py` `--host` bayrağını `settings.vllm_host`'tan alır (kod incelemesi)
- Arayüz rozeti `http://{vllm_host}:{vllm_port}/health` adresini yoklar (kod incelemesi)
- 4 test dosyası + 2 benchmark self-testi + `audit_eval_sets --selftest` → **hepsi geçti**
- `paired_test.py`, `dedupe_data.py`, `verify_clips.py` → modelsiz koştu
- `app.build_ui()` model sunucusu **kapalıyken** kuruldu
- WSL2'nin **NAT** modunda olduğu ölçüldü (WSL `172.23.191.136` ↔ Windows `192.168.1.102`)
- İstemci yolunun `vllm` import etmediği (kod incelemesi)

**✅ [VERIYI ALMA](#veriyi-alma--kim-hangi-veriye-ihtiyaç-duyar) bölümü için fiilen koşuldu (2026-07-27):**
- `hf_dataset_pull.py --make-manifest` → **1130 klip / 13.63 GB** tarandı, MD5'leri hesaplandı,
  `hf_manifest.json` üretildi (16.0 sn)
- `--list`, `--verify`, `--verify --verify-all`, `--upload-plan`, `--selftest`, `--help` → hepsi koştu
- `--verify` gerçek veri üzerinde: **47 dağıtılabilir klip** MD5 uyumlu, 0 eksik, 0 bozuk;
  `--verify-all` ile `eval_scenario` (37) + `falls_surveillance` (6) + `e2_vehicle` (9) da temiz
- **Bozuk/eksik dosya tespiti kanıtlandı:** kasten bozulmuş bir manifest ile koşuldu →
  `bozuk=1 eksik=1`, çıkış kodu `6` (yani doğrulama sessizce "geçti" demiyor)
- **Var olmayan depo:** `--repo ahmedberatAI/dilajanlari-eval-YOK-2026 --dry-run` →
  ağa gerçekten çıktı, `RepositoryNotFoundError` yakalandı, 5 maddelik yönlendirme bastı,
  çıkış kodu `4` (çökme yok)
- **Yer tutucu depo adı:** `--repo` verilmeden çalıştırıldığında yardım metni + çıkış kodu `2`
- **CWD bağımsızlığı:** tüm komutlar `/tmp` içinden koşuldu, proje kökünü doğru buldu
- `--selftest` → **33/33 GEÇTİ**; içinde: karışık lisanslı setlerin dosya-düzeyi sınıflandırması,
  "bilinmeyen kaynak = dağıtılamaz" (fail-closed), MD5 tutan dosyanın atlanması,
  tutmayanın yeniden indirilmesi, tek dosya hatasının işi çökertmemesi ve
  **paketleyici manifest biçiminin uyarlanması**
- Mendeley genel API'si **salt-okunur** sorgulandı: hâlâ **CC BY** bildiriyor → çelişki
  *devam ediyor*, bu yüzden Eskişehir klipleri varsayılan olarak dağıtım dışı

**⚠️ [VERIYI ALMA](#veriyi-alma--kim-hangi-veriye-ihtiyaç-duyar) bölümünde doğrulanmadı:**
- **HF deposundan gerçek indirme.** Depo **henüz yayınlanmadı** ve bu teslimde
  **hiçbir şey yüklenmedi** (yükleme dışa açık bir işlemdir → kaptanın onayı gerekir).
  İndirme mantığı yalnızca **sahte `hf_hub_download`** ile test edildi; gerçek ağ üzerinden
  uçtan uca indirme **yapılmamıştır**.
- `--upload-plan` çıktısındaki `hf upload` komutları **çalıştırılmadı**, yalnızca üretildi.
- `hf_manifest.json` **bu makinedeki** `data/` dizininin fotoğrafıdır. Setler değişirse
  `--make-manifest` yeniden koşulmalıdır; yoksa `--verify` yanlış "eksik" raporlar.
- Bölümdeki indirici betikler (`get_ucf_many.py`, `get_industrial.py`, …) bu turda
  **yeniden koşulmadı** — komut biçimleri repodaki dosyalardan doğrulandı, çıktıları değil.

**⚠️ Doğrulanmadı (iki makine + açık GPU gerektirir):**
- Gerçek bir üye makinesinden kaptanın sunucusuna **uçtan uca LAN bağlantısı**
- `mirrored networking` / `portproxy` / güvenlik duvarı kuralının etkisi
  *(bu komutlar sistem ve güvenlik ayarını değiştirir → **kaptan kendisi** çalıştırmalıdır)*
- Temiz bir Windows makinesinde `vllm`'siz istemci kurulumu
- **`DILAJAN_MOCK=1` uçtan uca:** anahtar ve `config.mock_mode` alanı **var** ve tanınıyor
  (sunucu kapalıyken analiz çökmedi, 0.3 sn'de tamamlandı), **ama** bu rehber yazılırken
  `llm_client.py` içindeki mock yanıt motoru henüz tamamlanmamıştı → çıktı boş geldi
  (`decision_trace`: `name 'mock_reply' is not defined`, fail-open ile yutuldu).
  **Kullanmadan önce yukarıdaki 3 saniyelik teyidi çalıştır.**
- Veri indirici / `build_*_eval` betikleri (ağ + disk gerektirir)
