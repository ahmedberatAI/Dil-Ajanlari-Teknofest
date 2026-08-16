"""Merkezi yapilandirma.

Tum ayarlar `DILAJAN_` onekiyle ortam degiskeni veya `.env` dosyasiyla
gecersiz kilinabilir. Ornek:  DILAJAN_VLLM_PORT=8001
"""
from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator

from pydantic import Field, model_validator
from pydantic.aliases import AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DILAJAN_", env_file=".env", extra="ignore"
    )

    # --- Model / servisleme ---
    # SOTA secim (2026-06-21 A/B): Qwen3-VL-8B (Qwen3 omurgasi -> akici Turkce, kategori %0->%100).
    # Onceki: Qwen/Qwen2.5-VL-7B-Instruct (hassasiyet-oncelikli yedek; DILAJAN_MODEL_NAME ile gecilir).
    model_name: str = "Qwen/Qwen3-VL-8B-Instruct-FP8"
    vllm_host: str = "127.0.0.1"
    vllm_port: int = 8000
    api_key: str = "EMPTY"  # yerel vLLM sunucusu anahtari yok sayar
    max_model_len: int = 8192
    gpu_memory_utilization: float = 0.90  # PERF: 0.85->0.90 (VRAM headroom ~21/24GB olculdu) -> daha fazla KV blogu
    max_num_seqs: int = 32     # PERF: es-zamanli dizi tavani (continuous-batching); 0=vLLM varsayilani. Yuksek-hacim icin.
    kv_cache_dtype: str = ""   # PERF: "fp8" DENENDI -> bu Blackwell/WSL kismi-CUDA ortaminda FlashInfer JIT linklenemiyor
                               # (collect2/ld error; flashinfer-sampler de ayni sebeple kapali). REDDEDILDI. ""=varsayilan (calisir)
    video_pruning_rate: float = 0.0  # PERF/EVS (vLLM 0.23, OPT-IN): temporal-token budama; >0 ise perceive-describe
                                     # VIDEO-path'ten gider (server'a --video-pruning-rate gerekir). OLCULDU: izole
                                     # describe -40% AMA tam-pipeline ~0 (describe kucuk parca; verify/ground image-path;
                                     # mp4-encode maliyeti) + accuracy SAPMA (normal klipte FP) -> DEFAULT KAPALI.
    enable_prefix_caching: bool = True  # PERF: paylasilan uzun Turkce sistem-promptu HER segment cagrisinda
                                        # tekrar ediyor -> prefix-cache prefill'i yeniden-hesaplamaz (buyuk TTFT/
                                        # throughput kazanci). V1'de blok-hash'e mm-hash dahil -> farkli kareler
                                        # karismaz (accuracy-risksiz, KV-seviyesi). Aninda geri-al: =false.
    dtype: str = "bfloat16"
    trust_remote_code: bool = False  # InternVL gibi modeller icin true
    quantization: str = ""           # "awq" vb.; bos = otomatik algila/yok
    enable_tools: bool = False        # Qwen3-VL hermes parser'i farkli; act zaten JSON-dispatch kullanir
    mm_processor_kwargs: str = ""     # vLLM mm-processor-kwargs JSON (InternVL tiling: max_dynamic_patch)

    # --- Video ornekleme ---
    segment_seconds: float = 10.0  # her analiz segmentinin uzunlugu (sn)
    segment_overlap: float = 0.0   # ardisik segmentler arasi ortusme (sn); >0 ise segment-siniri olaylari
                                   # iki pencerede de gorunur (dedup birlestirir). Uzun videolarda sinir-kaybini onler.
    fps_sample: float = 2.0        # saniyede ornieklenecek kare sayisi (ablasyon: risk-kalib 25->46%)
    max_frames_per_segment: int = 12  # bir segmentte VLM'e gonderilecek azami kare
    frame_max_side: int = 768      # kare uzun kenari ust siniri (token tasarrufu)
    frame_min_side: int = 640      # dusuk cozunurluklu CCTV kareleri bu boyuta buyutulur
    frame_enhance: bool = False    # CLAHE kontrast iyilestirme (dusuk cozunurluklu CCTV legibility)
    scene_cut_threshold: float = 0.30  # M3: ardisik kare RENK-HISTOGRAM mesafe esigi; ustu = sert sahne-kesimi.
                                       # KONSERVATIF: yangin/parlama sahne-ICI titremesi gercek-kesime rakip
                                       # (olculdu: yangin 0.208 > splice 0.197), bu yuzden YANLIZCA cok-dramatik
                                       # kesimleri yakalar (yangin klibini yanlis-bolmemek icin). Asil cozum:
                                       # reason'daki HER-ZAMAN-acik neden-sonuc-bagimsizlik talimati. (0 = devre disi)

    # --- Uretim ---
    temperature: float = 0.2
    max_tokens: int = 1024
    request_timeout: float = 120.0
    max_parallel_segments: int = 6  # segment analizinde eszamanli istek sayisi (vLLM batch'ler)
    n_samples: int = 1  # self-consistency: >1 ise grafik N kez calisip risk oylanir (kararlilik modu)
    event_consistency_n: int = 1  # H (algı self-consistency / SelfCheckGPT+AnomalyRuler): >1 ise her segment
                                  # N kez algılanır; olay yalnız koşuların ÇOĞUNDA tekrar ederse tutulur
                                  # (stokastik halüsinasyon elenir, gerçek olay kalır). Reason/act tek sefer çalışır.
    perceive_repetition_penalty: float = 1.15  # algi (describe) repetition_penalty: degenerate dongu/tekrari kirar
                                               # -> belirsiz okumada UYDURMA olay sismesini azaltir (or. yuruyen isciyi
                                               # "dusmus kisi" sanma). OLCULDU: 1.15 -> 6_te12 uydurma-kisi gitti,
                                               # falls_real recall %89 KORUNDU (risk-kalib 78->89). 1.3 fazla agresif
                                               # (recall 89->78), bu yuzden 1.15. (1.0 = kapali)
    use_detector: bool = False  # YOLO nesne dedektoru kanitini perceive'e enjekte et (heterojen ensemble)
    risk_recall_bias: bool = False    # OPT-IN "yuksek-duyarlilik risk modu" (Agent-C #1, maliyet-asimetrik).
                                      # TEHLIKE-kategori (Guvenlik/Kaza/Saglik/Yetkisiz) olayi Orta+ ise genel RISK
                                      # >= Yuksek. OLCULDU (A/B): risk-kalib +12 (76->88) AMA dar-FP +4 (4->8) +
                                      # dispatch de tetiklenir (act risk'e bagli). Bu yuzden DEFAULT KAPALI (muhafazakar
                                      # dar-FP~0 profili korunur); yuksek-guvenlik dagitimlarinda acilabilir. Default-guvenli
                                      # surum = dispatch'i biased-risk'ten ayirmak (gelecek is).
    persist_escalation: bool = False  # Agent-C: zamansal-SUREKLILIK yukseltmesi. Bir TEHLIKE-kategori olayi
                                      # >=2 bitisik segmentte SURUYORSA (end_time set) severity Orta->Yuksek (+1, capped).
                                      # Tek-yonlu/yukari -> recall'i bozmaz, izole olayi cezalandirmaz. Sistematik
                                      # dusuk-puanlamayi (olculen sapma -0.20) duzeltir; gercek tehlike surer, halusinasyon izoledir.
    semantic_plausibility: bool = False  # NEUROSIMBOLIK (2026, OPT-IN): kişi-merkezli yuksek-sev olay + YOLO nesne
                                         # buldu ama KİŞİ yok -> Orta'ya dusur. OLCULDU: YOLO11n grenli 320x240'ta
                                         # kişiyi kaciriyor (gercek Fighting klibinde persons_present=False) -> gercek
                                         # olayi yanlis dusurur = RECALL RISKI -> DEFAULT KAPALI. Yuksek-res'te acilabilir.
    perception_confidence: bool = True  # VL-Calibration (2026): reason'da AYRIK 'algi_guveni' (yuksek/orta/dusuk)
                                        # iste; DUSUK ise operatore "manuel teyit oneririz" aksiyonu ekle. Girdi-tavanini
                                        # (grenli'de sessiz dusuk-puanlama) DURUST + puanlanan-otonomi davranisina cevirir.
                                        # Additive (tespiti/recall'i degistirmez) -> dusuk-risk. (olculecek)
    threat_interpretation: bool = True   # GENEL: describe'a "guvenlik analisti tehdit-yorumu" katmani ekle
                                         # (prompts.THREAT_LENS_SUFFIX). Notr betim sucu yuzeysellestiriyordu
                                         # ("fiziksel temas"); bu katman olayi DOGRU adlandirir (saldiri/soygun/
                                         # silahli-tehdit). Anti-halusinasyon korunur. (olculecek)
    motion_saliency_cue: bool = True   # algida en belirgin ANI hareket anini bulup perceive'e YUMUSAK dikkat
                                       # ipucu enjekte et (motion-saliency; iddia DEGIL). Yalniz izole zirvede
                                       # tetikler (mutlak>6 VE >2x ort) -> uniform/dusuk-hareket normalde FP yok.
                                       # Geçici-olay (carpisma/devrilme onset) algisina yardim hedefi. (olculecek)
    verify_pose_falls: bool = True  # F1: VLM "kisi yere dusmus" iddiasini YOLO-poz ile dogrula (fall vs comelme).
                                    # FAIL-OPEN + yalniz-DUSUR: poz kisinin DIK (comelmis) oldugunu EMIN gosterirse
                                    # severity bir kademe duser; poz guvenilmezse VLM korunur (recall guvenli).
    batch_verify: bool = False   # PERF (OPT-IN): >=2 yuksek-sev olay -> hepsini TEK VLM cagrisinda teyit (N->1).
                                 # OLCULDU: cok-olayli kliplerde latency -24% (136->103s) AMA batch-prompt per-event'ten
                                 # daha sert olabilir (2/4 klipte risk dustu; A/B stokastik-confounded). Accuracy
                                 # kanitlanmadigi icin DEFAULT KAPALI; latency-oncelikli dagitimda acilabilir.
    verify_events: bool = True   # öz-doğrulama (deduce-then-verify): yüksek-severity olaylari teyit et,
                                 # dogrulanmazsa severity DUSUR (silme). FP kontrol + agentic oz-kontrol.
                                 # "Yuksek-Duyarlilik modu" icin DILAJAN_VERIFY_EVENTS=false.
    spatial_grounding: bool = True  # yuksek-severity olayin karedeki konumunu (bbox + bölge) cikar (Qwen3-VL native grounding)
    facility_rules: str = ""        # tesise-ozgu kurallar (dagitimda set edilir); politika-ihlali tespitini saglar (W4)
    restricted_zones: str = ""      # SAVUNMA: yasak/kisitli bolgeler (3x3 izgara etiketleri, virgulle:
                                    # "üst sağ,sağ,alt sağ"). Set edilirse YOLO-geofence: bu bolgelerde
                                    # KISI tespit edilirse "Yasak Bölge İhlali" (Yüksek/Yetkisiz Erişim).
                                    # Deterministik (VLM zone-reasoning guvenilmez); opt-in (bos=kapali).
    adaptive_reexamine: bool = True  # belirsiz (Orta) olaylari kosullu yeniden-incele (agentic dongu; ajan "tekrar bak" der)

    # --- D33: KKD (BARET) DETERMINISTIK TESPITI ---
    # K2 VARSAYILAN KAPALI: False iken graph'ta TEK SATIR bile calismaz (erken-donus),
    # olay uretilmez, karar-izine yazilmaz -> mevcut olcumler BIREBIR yeniden uretilir.
    #
    # NEDEN DETERMINISTIK (HANDOFF §6.2): KKD tespiti VLM isi DEGIL. Dedektorun ham
    # ciktisi VLM'e "kanit" METNI olarak ENJEKTE EDILMEZ — olculdu: yanlis alarm
    # %0 -> %12. Desen `restricted_zones` geofence'i ile aynidir: dedektor kendi
    # karar verir, sonuc TIPLI bir olaya donusur.
    #
    # D33 KANITI: `guided_choice` ile zorunlu secimde VLM, acik/kapali pano kapagi
    # sorusunda 20 klibin 20'sinde "KAPALI" dedi (10'u gercekte ACIK) -> ince ikili
    # gorsel durum VLM'in okuyamadigi bir sey. Baret var/yok AYNI problem sinifi.
    #
    # GEREKSINIM: `yolo11n-ppe.pt` (scripts/train_ppe.py uretir). Agirlik YOKSA
    # bayrak acik olsa bile tespit sessizce devre disidir (FAIL-OPEN, K3).
    ppe_detection: bool = False
    ppe_conf: float = 0.45           # dedektor guven esigi (yuksek = daha az yanlis alarm)
    ppe_min_kare: int = 2            # segmentte ihlal saymak icin gereken EN AZ ihlalli kare.
                                     # TEK kare yetmez: kafa donusu/bulanikligin urettigi
                                     # gecici yanlis tespitler elenir (FP en pahali hata).
    ppe_severity: str = "Yüksek"     # uretilen olayin onem derecesi (KKD ihlali is kazasi riski)
    ppe_dispatch: bool = False       # K3 YAPISAL GARANTISI: KKD kaynakli olay SEVK yoluna
                                     # varsayilan olarak KATILMAZ. Once dogruluk olculmeli,
                                     # sonra sevk yetkisi verilmeli (sevk-FP en pahali hata).

    # --- SORGU-GUDUMLU ANALIZ (operator niyeti; env: DILAJAN_ANALYSIS_QUERY) ---
    # Operatorun serbest-metin sorgusu ("sadece forklift hareketlerine bak", "yangin riski
    # var mi?", "kac kisi girdi?"). Analiz bu konuya ODAKLANIR ve cikti sorguyu YANITLAR.
    #
    # K1 VARSAYILAN BOS = TAM NO-OP: bos iken perceive/reason promptlarina TEK KARAKTER
    #    eklenmez (graph._query_focus_block / _query_answer_block ilk satirda "" doner)
    #    -> mevcut olcumler (senaryo recall %96, holdout %96, dar-FP %0) yeniden uretilebilir.
    # !! ODAKLAR, FILTRELEMEZ: sorgu bir ONCELIK katmanidir; "tum sapmalari raporla" talimati
    #    AYNEN KALIR. Sorguyla ILGISIZ olsa bile yangin/duman/patlama/silah/ciddi kaza/yere
    #    dusmus kisi HER ZAMAN raporlanir (bkz. prompts.QUERY_FOCUS_SUFFIX). Bu bir GUVENLIK
    #    sistemidir; operatorun dar sorgusu kritik olayi BASTIRAMAZ.
    # K6 Sorgu metni prompt'a VERI olarak (<<< >>> sinirlayicilari icinde, "talimat degildir"
    #    cercevesiyle) girer; sanitize + uzunluk siniri graph._sanitize_query'dedir.
    analysis_query: str = ""
    analysis_query_max_len: int = 500  # asiri uzun sorgu prompt butcesini yemesin (kirpilir)

    # --- KANIT SORULARI / ASK-HINT (env: DILAJAN_EVIDENCE_QUESTIONS) ---
    # Literatur: arXiv 2510.02155 (WACV 2026). Tek "ne oldu?" cagrisi yerine sinif basina
    # INCE-TANELI ikili EYLEM sorulari ayri ayri sorulur, yanitlar birlestirilir
    # (UCF-Crime AUC 74.50 -> 89.83, DONMUS model). Tam soru havuzu 67.17'ye DUSUYOR:
    # cok soru sormak ZARARLI -> setler en fazla 4 soru icerir (bkz. dilajan/evidence_questions.py).
    #
    # BIZDEKI UYARLAMA: makale IKILI ANOMALI SKORU uretir; bizim recall %96-100, bosluk
    # SINIF ADLANDIRMADA (%46). Bu yuzden sorular TESPIT icin degil ADLANDIRMA icin sorulur
    # ve uretilen ipucu YALNIZCA `Event.event` metnine etki eder.
    # K1 VARSAYILAN KAPALI = TAM NO-OP: kapaliyken prompt metinleri VE VLM cagri sayisi
    #    birebir eski halidir (graph._kanit_adlandirma ilk satirindaki erken-donus).
    # K3 YANLIS-POZITIF: (a) sorular YALNIZCA en az bir olay cikarilmissa sorulur -> olaysiz
    #    klipte TEK CAGRI bile yapilmaz; AMA bu tek basina YETMEZ (olculdu: 8 normal klipin
    #    3'u olay uretiyor). (b) ASIL guvence graph.py'deki ALARM MUHAFIZI'dir: `reexamine`
    #    hakemi kanit-ONCESI metni gorur (Event.evidence_prev) ve `act` sevk kapisinda RISK
    #    terimi adlandirma yapildiysa maskelenir -> severity/SEVK ozellikten ETKILENMEZ.
    evidence_questions: bool = False
    evidence_question_set: str = "sokak"  # "sokak" (UCF-Crime sokak sucu) | "tesis" (endustri/savunma)

    # --- Politika hakemligi (policy_gate) — BEYAN-BAGLI ONEM DERECESI (kusur #2) ---
    # SORUN (olculdu): model politika-ihlalini GORUYOR ve DOGRU ADLANDIRIYOR ama ONEM DERECESINI
    # dusuk veriyor (47 tespitin 34'u severity=Dusuk) -> risk tabani Dusuk -> sevk kapisi acilmiyor.
    # Prompt-seviyesi severity talimati DENENDI, BASARISIZ (10/100, McNemar p=0.267).
    # COZUM: severity operatorun BEYANINDAN gelir; olay<->kural eslesmesi MODEL ile (anlamsal) yapilir.
    facility_policy: str = ""       # ANA ANAHTAR. BOS = TAM NO-OP (LLM cagrisi yok, olay kopyalanmaz,
                                    # karar-izine satir bile eklenmez -> K2 bir bayrak sozune degil,
                                    # policy_gate'in ILK SATIRINDAKI erken-donuse dayanir).
                                    # NEDEN facility_rules'tan AYRI: facility_rules perceive promptuna
                                    # HARFIYEN enjekte ediliyor (graph.py _analyze_one_segment /
                                    # _perceive_single_pass); o metne dokunmak ALGI yolunu ve A/B
                                    # karsilastirmasini kirletir. Satir basina bir kural:
                                    #   <ihlal tanimi> [| <uygun gorunum>] [| Düşük|Orta|Yüksek|Kritik] [| sevk]
    policy_default_severity: str = "Yüksek"  # kuralda onem etiketi yoksa BEYAN varsayilani
    policy_accept_hedged: bool = False   # True: cekinceli ("olasi/supheli/veya") metinler de yukseltilir.
                                         # Varsayilan KAPALI -> yanlis-pozitif butcesi kazanctan onceliklidir.
    policy_max_rules: int = 8            # ayristirilacak azami kural maddesi
    policy_max_escalations: int = 4      # video basina azami severity yukseltmesi (butce)
    policy_dispatch: bool = False        # K3 YAPISAL GARANTISI: politika kaynakli yukseltme SEVK yoluna
                                         # ULASMAZ (normal_dispatch_fp cebirsel olarak DEGISMEZ).
                                         # True + kural satirinda 'sevk' etiketi -> sevk de acilir (B2 kolu).
    policy_verify_frames: bool = False   # OPT-IN kacis: yukseltmeyi karsitsal 2/2 GORSEL teyide baglar
                                         # (fail-closed). FP/gecikme profili OLCULMEMISTIR -> varsayilan KAPALI.

    # --- Hizli-kazanim dedektor senaryolari (opt-in; deterministik YOLO/geometri -> grenli-guvenli) ---
    detect_vehicles: bool = False   # YOLO ile arac (araba/kamyon/otobüs/motosiklet) tespiti. Araclar iri/kaba-sinif
                                    # oldugundan grenli CCTV'de kisiden GUVENILIR. vehicle_zones set ise ihlal uretir.
    vehicle_zones: str = ""         # araç YASAK/yanlis-konum bolgeleri (3x3 izgara etiketleri, virgulle). Bu
                                    # bolgelerde arac = "Yetkisiz/Yanlis Konumlu Arac" (Yüksek/Yetkisiz Erişim).
                                    # Bos ise: bir segmentte SUREKLI (dwell) gorulen durak arac bilgi amacli raporlanir.
    detect_crowd: bool = False      # YOLO kisi-sayimi + hareket ile toplanma (gathering) ve ani-dagilma (panik) tespiti.
                                    # Sartname ornegini ("00:35 personel toplanmasi") dogrudan karsilar.
    crowd_min_persons: int = 5      # bir segmentte bu sayi+ kisi ESZAMANLI gorulurse "toplanma" olayi uretilir

    # --- Hizli mod (E4: gercege-yakin dusuk gecikme) ---
    # DILAJAN_FAST_MODE=1 -> tek-gecisli algi + verify/grounding/reexamine kapali + daha az/kucuk kare.
    # Gecikmeyi ~3-4x dusurur; dogruluk-hiz odunlesimi olculmustur (docs/iyilestirmeler.md).
    fast_mode: bool = False
    single_pass_perceive: bool = False  # algida TEK VLM cagrisi (describe+extract birlesik)

    # --- MOCK (modelsiz) mod — GPU/vLLM OLMADAN pipeline + arayuz ---
    # VARSAYILAN KAPALI. Acikken `VLMClient` HICBIR AG CAGRISI YAPMAZ; yerine prompt turunu
    # taniyip DETERMINISTIK sahte yanit uretir (bkz. dilajan/llm_client.py "MOCK MOTORU").
    # AMAC: GPU'su/WSL'i olmayan takim uyeleri arayuzu ve LangGraph akisini uctan uca gorebilsin.
    # DURUSTLUK: uretilen ozet "[MOCK]" ile damgalanir ve ilk kullanimda stderr'e buyuk uyari basilir;
    #            bu ciktilar OLCUM/BENCHMARK icin KULLANILAMAZ (bkz. llm_client.MOCK_TAG).
    # Env: DILAJAN_MOCK=1  (geriye-uyum icin DILAJAN_MOCK_MODE=1 de kabul edilir)
    mock_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices("DILAJAN_MOCK", "DILAJAN_MOCK_MODE"),
        description="Modelsiz (sahte, deterministik) yanit modu — yalniz demo/gelistirme icin",
    )

    @model_validator(mode="after")
    def _apply_fast_profile(self):
        """fast_mode acikken dusuk-gecikme profilini uygular (acik daha-dusuk override'lar korunur).

        Ayrica mock_mode acikken CUDA gerektiren TEK varsayilan-ACIK dedektor yolu kapatilir:
        `verify_pose_falls` YOLO-poz modelini `device="cuda"` ile cagirir (dilajan/detector.py).
        Mock modun hedef kitlesi GPU'su OLMAYAN makinelerdir; orada bu cagri fail-open ile
        ABSTAIN dondurur ama her segmentte gereksiz ultralytics yuklemesi/gecikmesi olusur.
        Diger dedektor bayraklari (use_detector / semantic_plausibility / detect_* ) ZATEN
        varsayilan KAPALI oldugu icin dokunulmaz — operator acikca acarsa fail-open calisir.
        """
        if self.mock_mode:
            self.verify_pose_falls = False
        if self.fast_mode:
            self.single_pass_perceive = True
            self.verify_events = False
            self.spatial_grounding = False
            self.adaptive_reexamine = False
            if self.fps_sample > 1.0:
                self.fps_sample = 1.0
            if self.max_frames_per_segment > 6:
                self.max_frames_per_segment = 6
            if self.frame_max_side > 512:
                self.frame_max_side = 512
            if self.frame_min_side > 448:
                self.frame_min_side = 448
        return self

    @property
    def base_url(self) -> str:
        return f"http://{self.vllm_host}:{self.vllm_port}/v1"


settings = Settings()


# ---------------------------------------------------------------------------
# K2 — ISTEK-KAPSAMLI KONFIG (istek izolasyonu)
# ---------------------------------------------------------------------------
# SORUN: app.analyze() her istekte MODUL-GLOBAL `settings`i yaziyordu
# (facility_rules/restricted_zones/detect_vehicles/vehicle_zones/detect_crowd).
# Eszamanli iki analiz veya coklu-kullanici (DILAJAN_SHARE / DILAJAN_HOST=0.0.0.0)
# durumunda A isteginin tesis-kurali B'nin analizine SIZIYORDU; ayrica degerler
# analiz bitince temizlenmedigi icin bir sonraki isteme de tasiniyordu.
#
# NEDEN CONTEXTVAR DEGIL (secenek (a) REDDEDILDI):
#   perceive dugumu segmentleri `ThreadPoolExecutor` ile PARALEL isliyor ve
#   `settings.facility_rules` / `restricted_zones` / `detect_*` okumalari
#   _analyze_one_segment icinde, yani ISCI THREAD'lerde gerceklesiyor.
#   contextvars isci thread'lere OTOMATIK TASINMAZ (ThreadPoolExecutor
#   submit ederken context kopyalamaz) -> override worker'da GORUNMEZ,
#   operatorun girdigi tesis kurallari SESSIZCE DUSER. Bu, yarisdan daha kotu
#   (fonksiyonel gerileme) olurdu ve duzeltmesi graph.py'yi degistirmeyi
#   gerektirirdi (bizim sahiplendigimiz dosya degil).
#
# SECILEN COZUM (b, daha az invaziv): global mutasyon bir "kapi" ile korunur ve
# eski degerler try/finally ile GERI YUKLENIR. Ayni anda yalniz TEK istek
# istek-kapsamli alanlari degistirebilir; digerleri sirasini bekler. Tam
# proses-ici izolasyon degildir ama sizinti/yaris riskini kaldirir ve
# graph.py/detector.py'nin `settings.<alan>` okumasini HIC BOZMAZ.
#
# NEDEN Lock DEGIL de Semaphore: analyze() bir GENERATOR'dur ve kapi `yield`
# uzerinden tutulur. Gradio/anyio bir jeneratorun ardisik `__next__` cagrilarini
# FARKLI worker thread'lerde kosturabilir; threading.Lock/RLock sahiplik-baglidir
# ve baska bir thread'den release edilirse RuntimeError verir. Semaphore'un
# sahiplik kavrami yoktur -> thread'ler arasi guvenli acquire/release.
_CONFIG_GATE = threading.BoundedSemaphore(1)

#: Istek basina (UI formundan) degistirilebilen alanlar — belgeleme/dogrulama amacli.
REQUEST_SCOPED_FIELDS = (
    "facility_rules",
    "restricted_zones",
    "detect_vehicles",
    "vehicle_zones",
    "detect_crowd",
    "crowd_min_persons",
    # Politika hakemligi: tesis politikasi (onem derecesi beyani) ve sevk yetkisi de
    # ISTEK-KAPSAMLIDIR (bir operatorun beyani digerinin analizine sizmamali).
    "facility_policy",
    "policy_dispatch",
    # Sorgu-gudumlu analiz: operatorun SERBEST METIN sorgusu da istek-kapsamlidir — bir
    # operatorun "sadece forklift" sorgusu, eszamanli calisan baska bir analizin algisini
    # daraltamaz (K5). Kapi (semaphore) + try/finally geri-yukleme ayni desende calisir.
    "analysis_query",
    # KKD (baret) deterministik tespiti: bir operatorun actigi dedektor, eszamanli
    # calisan baska bir analize SIZMAMALI (facility_rules ile ayni gerekce).
    "ppe_detection",
    # Kanit sorulari (ASK-HINT): ozelligin acik/kapali olmasi ve hangi soru setinin
    # kullanildigi da ISTEK-KAPSAMLIDIR — bir operatorun "tesis" seti, eszamanli kosan
    # baska bir analizin sorularini degistiremez (analysis_query ile AYNI desen).
    "evidence_questions",
    "evidence_question_set",
)


@contextmanager
def request_config(**overrides: Any) -> Iterator[Settings]:
    """Istek suresince `settings` uzerinde gecici override uygular (istek izolasyonu).

    Kullanim::

        with request_config(facility_rules="...", detect_crowd=True):
            ...  # graph/detector `settings.facility_rules` okumaya DEVAM eder

    Davranis:
      * Blok boyunca kapi (semaphore) tutulur -> ikinci bir istek, birincisi
        bitene kadar istek-kapsamli alanlari EZEMEZ.
      * Cikista (normal, hata veya GeneratorExit) ESKI degerler geri yuklenir,
        yani ayarlar bir sonraki isteme sizmaz.
      * Bilinmeyen alan adlari SESSIZCE yok sayilir (fail-open; UI sozlesmesi
        degisirse analiz cokmesin).
      * `overrides` bos olsa bile kapi tutulur (davranis tekdüze kalir).
    """
    fields = getattr(Settings, "model_fields", None) or {}
    clean: Dict[str, Any] = {k: v for k, v in overrides.items() if k in fields}
    _CONFIG_GATE.acquire()
    previous: Dict[str, Any] = {}
    try:
        for key, value in clean.items():
            try:
                previous[key] = getattr(settings, key)
                setattr(settings, key, value)
            except Exception:  # fail-open: tek alan uygulanamazsa analiz surer
                previous.pop(key, None)
        yield settings
    finally:
        for key, value in previous.items():
            try:
                setattr(settings, key, value)
            except Exception:
                pass
        try:
            _CONFIG_GATE.release()
        except ValueError:  # cift-release (teorik) -> sessiz gec
            pass


def apply_cuda_env() -> None:
    """Bu Blackwell/WSL ortamindaki karisik-CTK CUDA sorunlarini gideren ortam
    degiskenlerini ayarlar. Standart CUDA kurulumlarinda zararsiz no-op'tur.

    vLLM/torch import edilmeden ONCE cagrilmalidir.
    """
    cuda_home = os.environ.get("CUDA_HOME", "/usr/local/cuda")
    if os.path.isdir(cuda_home):
        os.environ.setdefault("CUDA_HOME", cuda_home)
        os.environ["PATH"] = f"{cuda_home}/bin:" + os.environ.get("PATH", "")
        os.environ["LD_LIBRARY_PATH"] = (
            f"{cuda_home}/lib:" + os.environ.get("LD_LIBRARY_PATH", "")
        )
        # cccl'nin kati nvcc<->CTK surum esitlik kontrolunu atla (CUDA 13.x guvenli)
        os.environ.setdefault(
            "NVCC_APPEND_FLAGS", "-DCCCL_DISABLE_CTK_COMPATIBILITY_CHECK"
        )
        # flashinfer sampler JIT kismi toolkit layout'una linklenemiyor -> yerlesik sampler
        os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
    os.environ.setdefault("VLLM_LOGGING_LEVEL", "WARNING")
