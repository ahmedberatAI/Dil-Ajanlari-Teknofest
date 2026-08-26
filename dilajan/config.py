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
    # `.env` DEPO KOKUNDEN okunur, calisma dizininden DEGIL.
    # KUSUR (2026-08-25 sunum denetimi): `env_file=".env"` CWD'ye goreliydi.
    # `cd /tmp && python ~/proje/app.py` ile baslatilinca .env SESSIZCE yok
    # sayiliyor, base_url yerel vLLM'e duyuyor, isg_slotlari bosaliyordu —
    # yani sistem sahnede "calisiyor gorunup" hicbir ISG kurali kosmuyordu.
    model_config = SettingsConfigDict(
        env_prefix="DILAJAN_",
        env_file=(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), ".env"), ".env"),
        extra="ignore"
    )

    # --- Model / servisleme ---
    # SOTA secim (2026-06-21 A/B): Qwen3-VL-8B (Qwen3 omurgasi -> akici Turkce, kategori %0->%100).
    # Onceki: Qwen/Qwen2.5-VL-7B-Instruct (hassasiyet-oncelikli yedek; DILAJAN_MODEL_NAME ile gecilir).
    model_name: str = "Qwen/Qwen3-VL-8B-Instruct-FP8"

    # --- D41: GOREVE GORE MODEL (uzak serviste 10 alias acik) ----------------
    # HEPSI BOS = tek model (model_name) -> yerel davranis BIREBIR AYNI (K2).
    # Uzak serviste doldurulur; her alan farkli bir alias'a gidebilir.
    #
    # NEDEN AYRI MODEL (dokumantasyonun KENDI olcumleri):
    #   JSON uretimi     : llm-fast 1,000 = llm-large 1,000  -> BUYUK MODEL BOSUNA
    #   Arac cagirma     : llm-fast 1,000 = llm-large 1,000  -> BUYUK MODEL BOSUNA
    #   Siniflandirma    : llm-fast 0,900 · llm-large 0,950  (fark 1 gorevden)
    #   TR-MMLU          : llm-fast %73,3 · llm-large %79,6  -> BILGI isinde buyuk
    #   Tarih            : llm-fast %84,0 · llm-large %96,0
    #   Gecikme          : llm-fast medyan 0,91 s
    # Sistem TUM takimlarca paylasildigi icin buyuk modeli gereksiz mesgul etmek
    # yalnizca bize degil herkese maliyet yaziyor.
    #
    # Sartname acisindan da onemli: "model tabanli karar mekanizmalari" ve
    # "dinamik analiz" isteniyor; goreve gore model + yonlendirici bunun karsiligi.
    # OLCULDU (149 klip x 3 alias, hata 0): modeller ZIT YONDE uzmanlasmis.
    #   llm-large : SAYMA/geometri en iyi (forklift MCC +0,725) AMA kisi/oznitelik
    #               sorularinda neredeyse hep "GORUNMUYOR" der (yelek 47/50, pano 49/49)
    #   vlm       : KISI/OZNITELIK'te tek basarili (yelek MCC +0,500 dagitim-durustu;
    #               yerel model orada TAMAMEN cokmustu) AMA saymada en zayifi (FP=13)
    # Bu yuzden tek alias DEGIL, SORU TIPINE gore yonlendirme.
    model_algi: str = ""        # kisi/oznitelik algisi          -> vlm (video-yerli)
    model_sayim: str = ""       # sayma/geometri sorulari        -> llm-large
    model_yapi: str = ""        # olay cikarimi, JSON, siniflama -> llm-fast
    model_ozet: str = ""        # Turkce ozet + aksiyon onerisi  -> llm-large
    model_diyalog: str = ""     # operator diyalogu (Otonomi %20)-> llm-large
    model_yonlendirme: str = "" # ajan ici yonlendirme kararlari -> router (8B)
    model_guvenlik: str = ""    # icerik guvenligi siniflamasi   -> guard (4B)
    model_gomme: str = ""       # getirme/RAG                    -> bge-m3-embed
    vllm_host: str = "127.0.0.1"
    vllm_port: int = 8000
    api_key: str = "EMPTY"  # yerel vLLM sunucusu anahtari yok sayar
    # D41: uzak cikarim servisi (yarisma tahsisi). BOS = yerel vLLM (varsayilan).
    #   .env ->  DILAJAN_API_BASE_URL=https://evren-llmapi.ssyz.org.tr/v1
    #            DILAJAN_API_KEY=sk-evren-teamNN-...
    # Dokumantasyonun kendi ornekleri EVREN_API_KEY / EVREN_BASE_URL kullaniyor;
    # ikisi de desteklenir (bkz. `etkin_api_key`, `base_url`).
    api_base_url: str = ""
    api_timeout: float = 1800.0   # dokuman: istemci varsayilani 600 s YETERSIZ
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
    disable_thinking: bool = False   # D36: HIBRIT AKIL YURUTEN modeller (Qwen3.8/Qwen3.6) sohbet
                                     # sablonunda varsayilan olarak <think> blogu acar ve akil yurutmeyi
                                     # `content` icine yazar -> (1) JSON AYRISTIRILAMAZ, (2) token butcesi
                                     # dusunmede tukenir, cevap hic gelmez, (3) gecikme patlar.
                                     # OLCULDU (Qwen3.8-27B, tek cagri): ACIK 8,3 sn / 300 token / JSON YOK
                                     # -> KAPALI 1,9 sn / 43 token / JSON TAMAM.
                                     # Sablon `enable_thinking=false` ile bos <think></think> on-doldurur.
                                     # VARSAYILAN FALSE (K2): mevcut Qwen3-VL-8B yolu BIREBIR degismez.
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
    temperature: float = 0.0
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
    chat_kritik_hatirlatma: bool = True   # D36: DIYALOGDA bekleyen Kritik/Yuksek bulguyu
                                     # yanit sonunda TEK SATIRLA hatirlat (chat_agent._bekleyen_kritik_notu).
                                     # OLCULEN KUSUR: "Video kac saniye?" -> ajan "12 saniye" deyip DURUYORDU;
                                     # baglamda cozulmemis KRITIK bulgu beklerken. Sartname Otonomi maddesi
                                     # "inisiyatif alma" istiyor. Prompt ile UC iterasyon YAKINSAMADI
                                     # (5,00 -> 4,80 -> 4,60), bu yuzden garanti KODA tasindi.
                                     # VARSAYILAN ACIK: yalnizca chat_agent yolunu etkiler; eval_defense
                                     # olcum kulliyati DIYALOG KULLANMAZ, dolayisiyla arsivler etkilenmez.
                                     # Yanit bulguyu zaten aniyorsa hatirlatma EKLENMEZ (tekrar olmaz).
    isg_lens: bool = False           # D36: describe'a IS GUVENLIGI mercegi ekle (prompts.ISG_LENS_SUFFIX).
                                     # KOK NEDEN: temel describe talimati bir SUC/GUVENLIK sozlugudur ve
                                     # ISG tehlikelerini ACIKCA yasaklar ("ekipman/yuk tasima OLAY DEGILDIR").
                                     # eval_defense'te anomali kliplerinin %72'si SIFIR olay uretiyordu;
                                     # ozetler bos degil, KENDINDEN EMIN OLUMSUZ idi -> model yanlis seyi ariyor.
                                     # VARSAYILAN KAPALI (K2): acilmadan once eval_defense'te A/B ile OLCULECEK.
                                     # Opened_Panel_Cover'i DUZELTMEZ (o algi siniri; deterministik dedektor isi).
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
    # --- PANO KAPAGI (D39-E, 2026-08-18) -----------------------------------
    # Elektrik/kontrol panosu kapagi ACIK ve BASIBOS mu? Deterministik: dar ROI'de
    # kareler boyunca MINIMUM ortalama parlaklik ("acik kapak = karanlik oyuk")
    # + panonun basinda kisi VAR MI (RT-DETRv2, Apache-2.0).
    #
    # NEDEN VLM DEGIL (olculdu): VLM tam karede 0/12, panoya KIRPILMIS halde bile
    # 1/12 dogru; Qwen3.8-27B 99 klipte 0. Deterministik olcum: %93,2.
    # NEDEN KISI TERIMI SART: `Authorized_Intervention`da pano da FIZIKSEL OLARAK
    # aciktir. Yalniz parlaklik -> MCC +0,513 / FP=21. Bilesik -> +0,845 / FP=1.
    #
    # ROI ve esik TESISE OZGUDUR; baska kamerada yeniden kalibre edilmelidir.
    # Bu yuzden varsayilan BOS = KAPALI (K2: bayrak kapaliyken cikti birebir ayni).
    panel_roi: str = ""              # "x1,y1,x2,y2" (0-1 orani). Bizim tesis: "0.08,0.55,0.21,0.73"
    # VLM pano SLOTUNUN kirpma bolgesi — deterministik dedektorun
    # `panel_roi`sinden AYRI tutulur: luma dedektoru DAR bir seride en iyi
    # calisirken VLM slotu %8 paya ihtiyac duyuyor (olculdu).
    # BOS = kirpma yok = tam kare (olculdu: DEJENERE, MCC -0,192).
    panel_roi_vlm: str = ""
    panel_luma_esik: float = 87.6    # bu esigin ALTINA inen ROI parlakligi -> kapak ACIK
                                     # (tesisimizde hicbir KAPALI klipte gorulmeyen seviye)
    panel_kisi_kontrolu: bool = True  # panonun basinda kisi varsa -> YETKILI BAKIM, olay uretme.
                                     # KAPATMAK yanlis pozitifi 1'den 21'e cikarir (olculdu).
    panel_severity: str = "Yüksek"   # uretilen olayin onem derecesi
    # GORUS KILIDI — sabit ROI yalnizca KALIBRE EDILDIGI kamera gorusunde anlamlidir.
    # OLCULDU (197 klip): kilit YOKKEN kural, ayni tesisin BASKA cercevesindeki
    # yaya-yolu kliplerinde bosa atesliyor (Safe_Walkway_Violation 17/25,
    # Normal/Safe_Walkway 12/23) ve kesinlik 0,259'a cokuyor.
    # `scripts/pano_kalibre.py` ile uretilir. BOS = kilit yok (tek kameralı dagitim).
    panel_gorus_imza: str = ""
    panel_gorus_esik: float = 0.60   # Pearson kor. esigi; olculmus ayrim: gorus-ici
                                     # +0,938 · gorus-arasi +0,175 -> 0,60 genis marj

    # --- FORKLIFT ASIRI YUK (D40, 2026-08-19) -------------------------------
    # Kaynak makale (Onal & Dandil 2024) etiketi ISLEMSEL tanimliyor:
    # "2 blocks or less" guvenli, "3 blocks or more" ihlal. Yani karar KASA SAYMAK.
    #
    # IKI BAGIMSIZ YOL OLCULDU (50 klip):
    #   "vlm"      : modele "catalda kac kasa var?" diye sorulur -> MCC +0,762
    #                (ANLAMSAL soru "asiri yuk var mi?" -> +0,000, DEJENERE)
    #   "geometri" : turuncu istifin PERSPEKTIF duzeltmeli yuksekligi -> MCC +0,641
    #                (perspektifsiz ham oran yalnizca +0,280)
    #   "ikisi"    : ikisi de ihlal derse ihlal (FP dusurur, duyarlilik dusurur;
    #                OLCULMEDI — acmadan once olculmeli)
    #
    # "3 kasa" BU TESISIN konvansiyonudur, genel ISG kurali DEGILDIR.
    # Varsayilan BOS = KAPALI (K2: bayrak kapaliyken cikti birebir ayni).
    forklift_yuk: str = ""            # "" | "vlm" | "geometri" | "ikisi"
    forklift_esik: int = 3            # kaynak makale: >= 3 kasa ihlal
    forklift_y_ufuk: float = 0.3      # tesise ozgu; etiketsiz kestirildi
    forklift_f_pers_esik: float = 0.5751   # tesise ozgu
    forklift_severity: str = "Yüksek"

    # --- D43: GOZLEM DUZLEMI (yapilandirilmis algi + deterministik kural) ------
    # OLCULDU: mevcut serbest-metin boru hatti 20 guvensiz klibin 0'inda ISG
    # ihlali uretiyordu; AYNI model AYNI kliplerde ISLEMSEL soru soruldugunda
    # 12-20/20 dogru karar veriyor. Kayip zinciri:
    #   K1 betimleme ihlali iddia etti      0/20  <- kayip burada BASLIYOR
    #   K2 bilgi zorla verilse olaya gecen 11/20  (%45 kayip)
    #   K3 olaydan eslestiricinin yakaladigi 4/11 (%64 kayip)
    # Gozlem duzlemi K2 ve K3'u YAPISAL OLARAK ortadan kaldirir: cikarim adimi
    # yok (cevap tipli), olay metni SABLON (model nesri degil).
    #
    # BOS = KAPALI -> mevcut davranis BIREBIR ayni (K2).
    #   "*"                          -> tum kurallar
    #   "catal_kasa_sayisi,..."      -> yalniz secilen slotlar
    isg_slotlari: str = ""
    # TESIS TANIMA KAPISI — gozlem duzleminin ALAN KILIDI.
    # OLCULDU (2026-08-25, 100 alan disi klip / iSafetyBench):
    # Tesise KALIBRE ISG kurallari alan disinda GURULTU uretiyor. Normal
    # kliplerin 22/50'sinde YALNIZCA ISG kurali atesliyor; tehlike tespitine
    # katkisi SIFIR (recall her iki kipte de 0,900). Dahasi normal kliplerde
    # (26/50) tehlike kliplerinden (13/50) DAHA SIK atesliyor — ters yonde.
    #    ISG acik  : recall 0,900 · normal FP 0,540 · MCC +0,401
    #    ISG kapali: recall 0,900 · normal FP 0,100 · MCC +0,800
    # Cozum: slotlari SAHNE KILIDINE bagla. Imza DOLU iken slot yalnizca
    # sahne kalibre tesise BENZIYORSA sorulur. BOS = kilit yok = eski
    # davranis (K2) -> mevcut olcumler birebir yeniden uretilir.
    # DIKKAT: bu bir ETIKET kapisi DEGIL, ALAN kapisidir. Etiket sizintisi
    # riski yok cunku kilit "bu bizim tesisimiz mi" diye sorar, "bu hangi
    # sinif" diye degil — ve kalibre tesiste TUM siniflar kilidi gecer.
    # --- TURKCE URETIM KOLLARI — OLCULDU ve SEVK EDILDI (2026-08-25) ---
    # docs/on_kayit_turkce_kol234_kosum2_2026-08-25.md (kosumdan ONCE yazildi)
    # docs/sonuc_turkce_kol234_2026-08-25.md
    #
    # BIRLIKTE olculdu (n=60, temperature=0.2 = SEVK sicakligi, eslesmis):
    #   acilis_Goruntu     0,917 -> 0,000      meta_son_cumle 0,417 -> 0,133
    #   ort_karakter       291   -> 230        olay dusurme   10/64 -> 0/64
    #   ozet_kanonik_pano  0,478 -> 1,000      yelek 0,583 -> 1,000
    # KORUMA: isg_match BIREBIR AYNI · category_match 37->37 (McNemar p=1,000)
    #
    # DIKKAT — bu ikisi ETKILESIYOR ve AYRI AYRI acilmamalidir:
    # Kol 4 TEK BASINA `ozet_kanonik_pano`yu 0,571 -> 0,158'e DUSURUYOR
    # (uslup kisiti modeli kanonik terimden uzaklastiriyor). Kol 2 bunu
    # 1,000'e cikariyor. SEVK EDILEN yapilandirma IKISI BIRDEN aciktir;
    # yalniz birini acmak OLCULMEMIS bir yapilandirmadir.
    ozet_terim_sozlugu: bool = True
    ozet_uslup_kisiti: bool = True
    isg_gorus_imza: str = ""
    isg_gorus_esik: float = 0.708
    # NOT: `forklift_esik` YUKARIDA (D40 blogu) tanimli — burada TEKRAR
    # ETMIYORUZ. Ayni Settings govdesinde iki kez bildirildiginde ikinci tanim
    # birincisini SESSIZCE eziyordu: yukaridaki blokta yapilan bir esik
    # degisikligi hicbir uyari vermeden etkisiz kaliyordu.
    # `isg_kural.EsikKurali(esik_alani="forklift_esik")` tek tanimi okur.
    panel_koyuluk_esik: int = 3       # 0-10 olcekte; kalibrasyon tesise ozgu
    # YAYA YOLU — ROI kirpmasi ZORUNLU (tam karede MCC +0,192, ROI ile +0,638).
    # BOS = slot tam kareye sorulur = olculmus DUSUK performans.
    yol_roi_vlm: str = ""
    # YELEK SLOTU ROI'SI — referans (grounding) sorununa saldiri.
    # Kural "makinenin/panonun BASINDA duran kisi" diyor; `panel_roi_vlm`
    # makine basini ZATEN tanimliyor (pano slotunda +0,960). Yelek sorusu o
    # kirpmada sorulursa "basindaki kisi" referansi YAPISAL olarak tekleser —
    # kadraj disindaki 10-12 kisi soruya karisamaz. Dedektor YOK, secici YOK,
    # ek soru YOK (yalnizca bir ek video kodlamasi + bir ek oturum).
    # OLCULDU (2026-08-25): kacirmalarin B grubunda model "yelek VAR" derken
    # %92-99,7 EMIN ve HAKLI — sorun hangi kisiye baktigi.
    # BOS = tam kare = SEVK EDILEN davranis (K2).
    # On kayit: docs/on_kayit_yelek_roi_2026-08-25.md
    yelek_roi_vlm: str = ""
    # ON KOSUL slotunun ROI'si — AYRI alan, cunku kirpma makinenin ONUNDEKI
    # kisiyi kadraj disinda birakip kapiyi yanlislikla kapatabilir. B1 kolu
    # yalniz yelek slotunu tasir, B2 ikisini birden. Iki kol AYRI olculur.
    yelek_on_roi_vlm: str = ""
    # YELEK KURALININ ON KOSUL KAPISI — ACIK/KAPALI.
    # OLCULDU (2026-08-25, 658 icerik): kapi ciftin NEGATIF tarafinda HIC IS
    # YAPMIYOR. Dogru reddedilen 34 klibin 34'u de YELEK SLOTUNUN KENDISI
    # tarafindan tutuluyor (`yelek=VAR`); kapinin tuttugu negatif SIFIR.
    # Buna karsilik 12 DOGRU POZITIFI kesiyor: o kliplerde model
    # "yelek=YOK" diyor (guven 1,000) ama ayri sorulan kisi sayimi 0 diyor
    # ve CELISKIDE kapi kazaniyor. Yelek slotunun secenek kumesinde ZATEN
    # `KISI_YOK` var — yani "kisi var mi" sorusu slot icinde soruluyor;
    # ayri kapi bunu TEKRAR soruyor ve zayif olana guveniyor.
    #   kapi ACIK : TP 91 FP 4 FN 17 TN 34  -> MCC +0,679
    #   kapi KAPALI: TP103 FP 4 FN  5 TN 34 -> MCC +0,841   (+0,163)
    # Kazanc her iki ayrimda da tutuyor (_tr +0,174 · _te +0,141).
    # BEDEL: saha kesinligi 0,268 -> 0,175 (gorus muhafiziyla 0,206).
    # VARSAYILAN True = SEVK EDILEN davranis (K2).
    yelek_on_kosul: bool = True
    # NOT — YELEK SLOTUNA GORUS MUHAFIZI KONULAMAZ.
    # Kapinin isini bir gorus muhafizinin yapmasi denendi ve mevcut bir
    # olcum tarafindan REDDEDILDI: bu ciftte GORUS ETIKETLE 0,833 KORELE
    # (`tests/test_gorus_muhafizi.py`). Muhafiz, sahne gecerliligi yerine
    # ETIKETI sizdirirdi. Yol slotunda muhafiz mesru cunku orada dislanan
    # kamera (forklift) ciftin DISINDA kaliyor; yelek ciftinde ise gorus
    # farkinin KENDISI etikete bagli.
    yol_mesafe_esik: int = 7          # cizgiye uzaklik < esik -> ihlal
    # GORUS MUHAFIZI — yol slotu YALNIZCA dogru kamerada sorulur.
    # `yol_dislanan_gorus`: DISLANAN kameranin (forklift, kamera 14) referans
    # imzasi. Sahne buna benziyorsa yol slotu HIC sorulmaz.
    # Olculdu (96 klip): kamera 14 benzerligi min 0,842 · kamera 9 maks 0,575.
    # BOS = muhafiz kapali = eski davranis (K2).
    yol_dislanan_gorus: str = ""
    yol_gorus_esik: float = 0.708
    # Yol slotunun KENDI kare hizi. 0 = "kare hizina DOKUNMA" (ozgun fps).
    # Olculdu: ozgun fps +0,535 · fps 8 +0,217 — yaya yolu ihlali ANLIK.
    yol_kodlama_fps: float = 0.0
    # YENIDEN KODLAMA KONTROLU (varsayilan KAPALI = eski davranis, K2).
    # Acikken gozlem duzlemi videolari ORTAK SPEKTE kodlar: sabit fps + sabit
    # bit hizi. Boylece "skor icerikten mi, kodlama izinden mi geliyor?"
    # sorusu deneyle ayrilir. Olculdu: bu sette fps tek basina yetkisiz
    # ciftinde MCC +1,000 (bizim gonderdigimiz baytlarda), bit hizi forklift
    # ciftinde +0,882.
    # SERVIS DAYANIKLILIGI — uzak servis TUM takimlarca paylasiliyor.
    # OLCULDU (2026-08-24, kapi probu): servis 10 istekte ust uste
    # `502 Bad Gateway` dondurdu. Yeniden deneme OLMADIGI icin o 10 slot
    # "olculemedi" olarak kaydedildi. Sunum sirasinda ayni sey olursa
    # demo bir klipte sessizce bos doner.
    # SADECE gecici hatalar yeniden denenir (5xx / zaman asimi / baglanti).
    # 4xx (or. `vlm` goruntu kabul etmiyor -> 400) ASLA denenmez: istek
    # yanlistir, tekrarlamak yalnizca gecikme ekler.
    yeniden_deneme: int = 3           # ek deneme sayisi (0 = kapali, eski davranis)
    yeniden_deneme_bekleme: float = 1.5   # ilk bekleme (s); her denemede 2x + jitter
    # TEKRAR URETILEBILIR KODLAMA — OLCULDU (2026-08-25):
    # Ayni klip iki kez kodlaninca BAYT BAYT farkli cikiyor (0/8 ayni).
    # Kaynak: x264'un cozunurluge gore sectigi is parcacigi sayisi — dusuk
    # cozunurluklu ROI kirpmalari zaten tekrar uretilebilir cikiyordu.
    # Model AYNI baytlarda tamamen deterministik (50/50 klipte 3/3 ayni cevap),
    # yani kosumlar arasi ~0,05'lik MCC dalgalanmasinin kaynagi KODLAYICI.
    # `-threads 1` bunu cozer ama kodlamayi ~5x yavaslatir; VARSAYILAN KAPALI.
    # Bir olcumun BIREBIR yeniden uretilmesi gerektiginde acilir.
    kodlama_kararli: bool = False
    kodlama_normalize: bool = False
    kodlama_fps: float = 8.0
    kodlama_bit: str = "800k"
    isg_slot_azami_kare: int = 8      # servis siniri 16; deponun diger problari 8

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
    # Hangi KKD kitleri kosulacak (virgulle). Gecerli: "baret", "yelek".
    # AYRI MODELLER cunku iki veri setinin ETIKET UZAYLARI AYRIK — birlestirme
    # yelek sinifi icin sistematik yanlis-negatif uretirdi (bkz. detector.KKD_KITLERI).
    # D35 GORSEL DENETIM: hedef tesiste isciler BARET TAKMIYOR, hi-vis YELEK giyiyor
    # -> bu dagitim icin anlamli kit YELEKTIR. Ikisi de varsayilan olarak listede;
    # agirligi olmayan kit SESSIZCE atlanir (K3 fail-open).
    # NOT: `ppe_detection=False` iken bu ayarin HICBIR etkisi yoktur (K2).
    # Ikisi de DAGITIMA HAZIR (olculdu, scripts/yelek_esik_tara.py):
    #   baret: test mAP50 0,934 · baret_yok P 0,893 / R 0,891
    #   yelek: test mAP50 0,905 · yelek_yok P 0,898 / R 0,783
    # ⚠️ YELEK BIR ARA DAGITILMIYORDU: ilk egitimde (741 kutu) P 0,535 cikmisti ve
    # iki tarafli kabul olcutunu (P>=0,85 VE R>=0,50) saglamiyordu. Ikinci veri
    # kaynagi (Mendeley 8vf7z6v5sb) egitim kutusunu 3.185'e cikarinca gecti.
    # DERS: "model zayif" demeden once VERI MIKTARINI kontrol et.
    #
    # D35 GORSEL DENETIMI: hedef tesiste isciler BARET TAKMIYOR, hi-vis YELEK
    # giyiyor -> bu dagitim icin ASIL kit YELEKTIR; baret santiye senaryosu icin.
    # NOT: `ppe_detection=False` iken bu ayarin HICBIR etkisi yoktur (K2).
    ppe_kits: str = "baret,yelek"
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
        `verify_pose_falls` YOLO-poz modelini cagirir (dilajan/detector.py). NOT: cihaz
        artik `yerel_cihaz()` kapisindan gecer; uzak kosumda CPU'ya duser.
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

    def gorev_modeli(self, gorev: str) -> str:
        """Gorev icin kullanilacak model adi. Tanimli degilse `model_name`.

        gorev: "algi" | "yapi" | "ozet" | "diyalog" | "yonlendirme" |
               "guvenlik" | "gomme"
        Bilinmeyen gorev -> `model_name` (sessiz basarisizlik YOK: cagiran taraf
        yanlis ad verirse varsayilana duser, ASLA baska bir modele kaymaz).
        """
        ad = (getattr(self, f"model_{gorev}", "") or "").strip()
        return ad or self.model_name

    @property
    def base_url(self) -> str:
        """Model API adresi. Bos ise YEREL vLLM (varsayilan davranis, K5).

        D41 (2026-08-21): yarisma duzenleyicisi ortak bir cikarim servisi tahsis
        etti (8xH200, BF16, kuantizasyon yok). Servis OpenAI uyumlu oldugundan
        yalnizca base_url + anahtar degisiyor; cagri yerleri AYNI kaliyor.
        Sartnamedeki "offline/yerel" ifadesinin iptal edildigi takim tarafindan
        bildirildi (2026-08-21).

        Oncelik: DILAJAN_API_BASE_URL > EVREN_BASE_URL > yerel vLLM.
        """
        import os as _os
        u = (self.api_base_url or _os.environ.get("EVREN_BASE_URL") or "").strip()
        return u.rstrip("/") if u else f"http://{self.vllm_host}:{self.vllm_port}/v1"

    @property
    def etkin_api_key(self) -> str:
        """Kullanilacak anahtar. ASLA loglanmaz/yazdirilmaz.

        Oncelik: DILAJAN_API_KEY > EVREN_API_KEY > "EMPTY" (yerel vLLM anahtar
        istemez). Dokumantasyonun kurali: anahtar KODA GOMULMEZ, ortamdan okunur.
        """
        import os as _os
        for v in (self.api_key, _os.environ.get("EVREN_API_KEY", "")):
            v = (v or "").strip()
            if v and v != "EMPTY":
                return v
        return "EMPTY"

    @property
    def etkin_timeout(self) -> float:
        """Istemcinin GERCEKTEN kullanacagi zaman asimi.

        `api_timeout` alani vardi ama HICBIR calisma-zamani yolunda
        okunmuyordu: `VLMClient` her zaman `request_timeout`u (120 s)
        kullaniyordu. Dokumantasyon uzak servis icin 600 s'yi bile YETERSIZ
        sayarken, .env'deki `DILAJAN_API_TIMEOUT=1800` tamamen etkisizdi.
        Uzun video istekleri 120 s'yi asinca APITimeoutError firliyor, o da
        gozlem duzleminde "slot cozulemedi"ye ve oradan "ihlal yok"a
        donusuyordu — yani sessiz olcum kaybi.

        Yerel yolda davranis DEGISMEZ (K2): `request_timeout` dondurulur.
        """
        return self.api_timeout if self.uzak_api_mi else self.request_timeout

    # YEREL GPU YASAGI — varsayilan olarak UZAK KOSUMDA ACIK.
    # Yarisma tahsisi 8xH200 UZAK servistir; yerel GPU kullanmak yasaktir.
    # Yasak GPU'YA OZGUDUR: yerel modeller CPU'da calismaya DEVAM EDER.
    # Yerelde GPU kullanmak icin ACIKCA izin verilir:
    #     DILAJAN_YEREL_GPU_IZNI=1
    yerel_gpu_izni: bool = False

    # --- SLOT GUVENI (kisitli cozme dagilimi) ---
    # ACIKKEN her slot cagrisi `logprobs` ile gider ve izinli secenekler uzerindeki
    # olasilik dagilimi `GozlemKaydi.guven` icine yazilir. EK CAGRI YOK — zaten
    # yapilan tek ileri gecisin dagilimi okunur; gecikme ve token maliyeti AYNI.
    # KAPALIYKEN (varsayilan) istek govdesine `logprobs` alani HIC EKLENMEZ ve
    # hicbir kod yolu `guven` sozlugunu okumaz -> sevk davranisi BAYT OZDES (K2).
    slot_guven: bool = False

    @property
    def yerel_gpu_yasak(self) -> bool:
        """Yerel GPU kullanimi yasak mi? (uzak kosumda EVET, izin verilmedikce)"""
        return self.uzak_api_mi and not self.yerel_gpu_izni

    @property
    def uzak_api_mi(self) -> bool:
        """Uzak servise mi baglaniyoruz? (kunye/raporlama icin)"""
        return not self.base_url.startswith("http://127.0.0.1") and                not self.base_url.startswith(f"http://{self.vllm_host}:")


settings = Settings()


def yerel_cihaz() -> str:
    """Yerel modellerin KOSACAGI cihaz: "cuda" ya da "cpu".

    Yasak GPU'YA OZGUDUR — yerel model calistirmak serbesttir, yerel GPU
    kullanmak degil. Bu yuzden burada istisna FIRLATILMAZ; cihaz CPU'ya
    cevrilir ve is CALISMAYA DEVAM EDER.

    NEDEN TEK KAPI: bu kusur sinifi zaten islemisti — deterministik pano
    dedektorunun kisi kontrolu her klipte RT-DETRv2'yi yerel GPU'da
    calistiriyordu (~3,5 GB VRAM) ve hicbir yerde gorunmedigi icin kimse
    fark etmedi. Cihaz secimi tek bir yerden gecerse boyle bir sey sessizce
    geri gelemez.
    """
    if settings.yerel_gpu_yasak:
        return "cpu"
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


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
