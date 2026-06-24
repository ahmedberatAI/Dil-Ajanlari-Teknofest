"""Merkezi yapilandirma.

Tum ayarlar `DILAJAN_` onekiyle ortam degiskeni veya `.env` dosyasiyla
gecersiz kilinabilir. Ornek:  DILAJAN_VLLM_PORT=8001
"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import model_validator
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
    gpu_memory_utilization: float = 0.85
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

    # --- Hizli mod (E4: gercege-yakin dusuk gecikme) ---
    # DILAJAN_FAST_MODE=1 -> tek-gecisli algi + verify/grounding/reexamine kapali + daha az/kucuk kare.
    # Gecikmeyi ~3-4x dusurur; dogruluk-hiz odunlesimi olculmustur (docs/iyilestirmeler.md).
    fast_mode: bool = False
    single_pass_perceive: bool = False  # algida TEK VLM cagrisi (describe+extract birlesik)

    @model_validator(mode="after")
    def _apply_fast_profile(self):
        """fast_mode acikken dusuk-gecikme profilini uygular (acik daha-dusuk override'lar korunur)."""
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
