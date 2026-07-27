#!/usr/bin/env python
"""TESHIS ARACI — "model bende calismiyor" diyen takim uyesine NEDENINI ve COZUMUNU soyler.

Bu betik GPU'suz, torch'suz, vLLM'siz, hatta hicbir proje bagimliligi KURULMAMIS bir
makinede de calisir: modul seviyesinde YALNIZCA standart kutuphane import edilir ve
her kontrol tek tek try/except ile sarilidir. Hicbir kosulda cokmez.

Kullanim::

    python scripts/doctor.py                 # tam teshis (renkli tablo + tavsiye)
    python scripts/doctor.py --skip-torch    # torch alt-surec probunu atla (hizli)
    python scripts/doctor.py --json          # makine-okunur cikti
    python scripts/doctor.py --simulate no-gpu       # GPU yokmus gibi davran (test)
    python scripts/doctor.py --simulate low-vram     # 8 GB kart varmis gibi davran (test)
    python scripts/doctor.py --simulate windows no-server

Cikis kodu:
    0 = HAZIRSIN (ya sunucuya erisiliyor ya da bu makinede yerel sunucu baslatilabilir)
    1 = KRITIK ENGEL var (tavsiye bolumu ne yapilacagini komutlariyla soyler)

Not (yarisma kurali): burada onerilen "LAN" yolu takimin KENDI agindaki KENDI
makinesine baglanmaktir. Dis API / bulut / ucretli servis KULLANILMAZ, dolayisiyla
"tamamen yerel calisma" sartina uyar.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- durum kodlari -----------------------------------------------------------
OK = "OK"        # sorun yok
WARN = "UYARI"   # calisir ama dikkat
FAIL = "HATA"    # bu yol tikali
INFO = "BILGI"   # yalnizca bilgi

_RENK = {
    OK: "\033[92m",     # yesil
    WARN: "\033[93m",   # sari
    FAIL: "\033[91m",   # kirmizi
    INFO: "\033[96m",   # cyan
}
_SIFIRLA = "\033[0m"
_KALIN = "\033[1m"

# Model agirlik/VRAM esikleri (GB) — Qwen3-VL-8B-FP8 ~10 GB agirlik + KV cache
VRAM_RAHAT = 20.0    # varsayilan ayarlarla sorunsuz
VRAM_ASGARI = 16.0   # calisir ama max_model_len/gpu_memory_utilization dusurulmeli
VRAM_KUCUK = 11.0    # 8B-FP8 zor sigar -> daha kucuk model / 4-bit gerekir
DISK_ASGARI_GB = 25.0  # HF onbellegi icin onerilen bos alan

# İstemci (yalniz arayuz + LAN'daki sunucuya baglanma) icin gereken paketler.
# torch/vllm BU LISTEDE YOKTUR: LAN yolunda uyenin GPU'ya da torch'a da ihtiyaci yok.
ISTEMCI_PAKETLERI: Tuple[Tuple[str, str, str], ...] = (
    # (dagitim adi, import adi, pip spesifikasyonu)
    ("openai", "openai", '"openai>=2.0"'),
    ("gradio", "gradio", '"gradio>=6.0"'),
    ("pydantic", "pydantic", '"pydantic>=2.7"'),
    ("pydantic-settings", "pydantic_settings", '"pydantic-settings>=2.4"'),
    ("langgraph", "langgraph", '"langgraph>=1.2,<2"'),
    ("langchain", "langchain", '"langchain>=1.3,<2"'),
    ("langchain-openai", "langchain_openai", '"langchain-openai>=1.3,<2"'),
    ("av", "av", '"av>=14"'),
    ("opencv-python-headless", "cv2", '"opencv-python-headless>=4.10"'),
    ("pillow", "PIL", '"pillow>=10"'),
)

# Yalniz SUNUCU (yerelde model kosturma) icin gerekenler.
SUNUCU_PAKETLERI: Tuple[Tuple[str, str, str], ...] = (
    ("vllm", "vllm", "vllm==0.23.0"),
    ("transformers", "transformers", "transformers"),
    ("qwen-vl-utils", "qwen_vl_utils", '"qwen-vl-utils>=0.0.14"'),
)

# Opsiyonel (yoklugunda kod FAIL-OPEN calisir).
OPSIYONEL_PAKETLER: Tuple[Tuple[str, str, str], ...] = (
    ("ultralytics", "ultralytics", "ultralytics"),
)


# =============================================================================
# Altyapi: renk, yazdirma, guvenli komut calistirma
# =============================================================================
def _stdout_utf8() -> None:
    """Windows konsolunda (cp1252) Turkce karakter cokmesini onler. Hata verirse sessiz gecer."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def _renk_ac(zorla: Optional[bool]) -> bool:
    """ANSI renk kullanilsin mi? Windows'ta sanal-terminal kipini acmayi dener."""
    if zorla is False:
        return False
    try:
        if os.environ.get("NO_COLOR"):
            return False
        if zorla is not True and not sys.stdout.isatty():
            return False
        if os.name == "nt":
            try:
                import ctypes

                k = ctypes.windll.kernel32  # type: ignore[attr-defined]
                k.SetConsoleMode(k.GetStdHandle(-11), 7)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
            except Exception:
                return False
        return True
    except Exception:
        return False


class Rapor:
    """Kontrol sonuclarini toplar ve tablo halinde yazar."""

    def __init__(self, renkli: bool) -> None:
        self.renkli = renkli
        self.satirlar: List[Dict[str, Any]] = []

    def ekle(self, no: str, ad: str, durum: str, deger: str,
             anlami: str = "", cozum: str = "", **ek: Any) -> Dict[str, Any]:
        satir = {"no": no, "ad": ad, "durum": durum, "deger": deger,
                 "anlami": anlami, "cozum": cozum, **ek}
        self.satirlar.append(satir)
        return satir

    def bul(self, no: str) -> Dict[str, Any]:
        for s in self.satirlar:
            if s["no"] == no:
                return s
        return {}

    def _boya(self, metin: str, durum: str) -> str:
        if not self.renkli:
            return metin
        return f"{_RENK.get(durum, '')}{metin}{_SIFIRLA}"

    def yaz(self) -> None:
        for s in self.satirlar:
            etiket = f"[{s['durum']}]"
            print(f"{s['no']:>3} {s['ad']:<26} {self._boya(f'{etiket:<8}', s['durum'])} {s['deger']}",
                  flush=True)
            for etiket_ad, anahtar in (("anlami", "anlami"), ("cozum ", "cozum")):
                if not s.get(anahtar):
                    continue
                parcalar = _sar(s[anahtar], 72)
                print(f"      {etiket_ad} : {parcalar[0]}", flush=True)
                for devam in parcalar[1:]:
                    print(f"               {devam}", flush=True)


def _sar(metin: str, genislik: int) -> List[str]:
    """Basit satir sarma (textwrap'e bagimli olmadan, komut satirlarini bolmeden)."""
    try:
        cikti: List[str] = []
        for ham in metin.split("\n"):
            satir = ""
            for kelime in ham.split(" "):
                if satir and len(satir) + 1 + len(kelime) > genislik:
                    cikti.append(satir)
                    satir = kelime
                else:
                    satir = f"{satir} {kelime}".strip()
            cikti.append(satir)
        return cikti or [metin]
    except Exception:
        return [metin]


def calistir(args: List[str], timeout: float = 15.0) -> Tuple[int, str, str]:
    """Komutu guvenle calistirir. Her hata (yok/zaman asimi/izin) kod 127 ile doner."""
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return (p.returncode,
                p.stdout.decode("utf-8", "replace").strip(),
                p.stderr.decode("utf-8", "replace").strip())
    except Exception as e:  # FileNotFoundError, TimeoutExpired, PermissionError...
        return 127, "", f"{type(e).__name__}: {str(e)[:200]}"


def paket_surumu(dagitim: str, modul: str) -> Optional[str]:
    """Paketin surumunu IMPORT ETMEDEN dondurur (metadata). Bulunamazsa None."""
    try:
        from importlib import metadata

        return metadata.version(dagitim)
    except Exception:
        pass
    try:  # metadata yoksa en azindan modul var mi diye bak
        from importlib import util

        return "kurulu" if util.find_spec(modul) is not None else None
    except Exception:
        return None


# =============================================================================
# 0) Proje ayarlari (pydantic varsa oradan, yoksa ortam degiskeni + .env'den)
# =============================================================================
def ayarlari_oku() -> Dict[str, Any]:
    """settings'i yuklemeye calisir; yuklenemezse ortam degiskenlerinden tahmin eder."""
    sonuc: Dict[str, Any] = {"kaynak": "varsayilan", "hata": "", "alanlar": []}
    try:
        if PROJECT_ROOT not in sys.path:
            sys.path.insert(0, PROJECT_ROOT)
        from dilajan.config import settings  # type: ignore

        sonuc.update({
            "kaynak": "dilajan.config",
            "host": settings.vllm_host,
            "port": int(settings.vllm_port),
            "model": settings.model_name,
            "max_model_len": settings.max_model_len,
            "gpu_util": settings.gpu_memory_utilization,
            "base_url": settings.base_url,
        })
        try:
            sonuc["alanlar"] = sorted(getattr(type(settings), "model_fields", {}) or {})
        except Exception:
            sonuc["alanlar"] = []
        return sonuc
    except Exception as e:
        sonuc["hata"] = f"{type(e).__name__}: {str(e)[:160]}"

    # --- yedek yol: config import edilemedi (or. pydantic-settings kurulu degil)
    dosya_env: Dict[str, str] = {}
    try:
        env_yolu = os.path.join(PROJECT_ROOT, ".env")
        if os.path.isfile(env_yolu):
            with open(env_yolu, "r", encoding="utf-8", errors="replace") as fh:
                for ham in fh:
                    ham = ham.strip()
                    if not ham or ham.startswith("#") or "=" not in ham:
                        continue
                    k, _, v = ham.partition("=")
                    dosya_env[k.strip().upper()] = v.strip().strip('"').strip("'")
    except Exception:
        pass

    def al(ad: str, varsayilan: str) -> str:
        return os.environ.get(f"DILAJAN_{ad}") or dosya_env.get(f"DILAJAN_{ad}") or varsayilan

    host = al("VLLM_HOST", "127.0.0.1")
    try:
        port = int(al("VLLM_PORT", "8000"))
    except Exception:
        port = 8000
    sonuc.update({
        "kaynak": "ortam degiskeni (.env)",
        "host": host,
        "port": port,
        "model": al("MODEL_NAME", "Qwen/Qwen3-VL-8B-Instruct-FP8"),
        "max_model_len": al("MAX_MODEL_LEN", "8192"),
        "gpu_util": al("GPU_MEMORY_UTILIZATION", "0.90"),
        "base_url": f"http://{host}:{port}/v1",
    })
    return sonuc


# =============================================================================
# 1) Isletim sistemi / WSL
# =============================================================================
def kontrol_os(rapor: Rapor, sim: set) -> Dict[str, Any]:
    try:
        sistem = "Windows" if "windows" in sim else platform.system()
        surum = "11 (simulasyon)" if "windows" in sim else platform.release()
        wsl_dagitim = ""
        wsl_mi = False
        if "windows" not in sim:
            try:
                wsl_dagitim = os.environ.get("WSL_DISTRO_NAME", "")
                if wsl_dagitim:
                    wsl_mi = True
                elif sistem == "Linux" and os.path.exists("/proc/version"):
                    with open("/proc/version", "r", errors="replace") as fh:
                        wsl_mi = "microsoft" in fh.read().lower()
            except Exception:
                pass

        if sistem == "Linux" and wsl_mi:
            deger = f"Linux {surum} (WSL2{': ' + wsl_dagitim if wsl_dagitim else ''})"
            return rapor.ekle("1", "Isletim sistemi / WSL", OK, deger,
                              "WSL2 icindesin — vLLM'in DESTEKLEDIGI ortam. Yerel sunucu "
                              "baslatabilirsin (GPU sartlari asagida).",
                              wsl=True, linux=True, sistem=sistem)
        if sistem == "Linux":
            return rapor.ekle("1", "Isletim sistemi / WSL", OK, f"Linux {surum} (yerel)",
                              "Yerel Linux — vLLM'in birincil destekledigi ortam.",
                              wsl=False, linux=True, sistem=sistem)
        if sistem == "Windows":
            return rapor.ekle(
                "1", "Isletim sistemi / WSL", FAIL, f"Windows {surum} (WSL DISINDA)",
                "vLLM Windows'ta YERLI olarak CALISMAZ. Bu Python surecinden model "
                "SUNAMAZSIN. (Arayuzu/istemciyi Windows'ta calistirip modeli LAN'daki "
                "kaptandan almak SERBEST — bkz. YOL 1.)",
                "Yerelde model kosturmak istiyorsan WSL2 kur:  wsl --install -d Ubuntu-24.04  "
                "(yonetici PowerShell, sonra yeniden baslat). Kosturmayacaksan YOL 1'i kullan.",
                wsl=False, linux=False, sistem=sistem)
        return rapor.ekle("1", "Isletim sistemi / WSL", WARN, f"{sistem} {surum}",
                          "Bu isletim sistemi projede test edilmedi (Linux/WSL2 bekleniyor).",
                          "Linux veya WSL2 + Ubuntu 24.04 kullan; ya da YOL 1 (LAN) ile bagli calis.",
                          wsl=False, linux=False, sistem=sistem)
    except Exception as e:
        return rapor.ekle("1", "Isletim sistemi / WSL", WARN, "tespit edilemedi",
                          f"Kontrol hata verdi: {type(e).__name__}: {str(e)[:120]}",
                          wsl=False, linux=False, sistem="?")


# =============================================================================
# 2) Python surumu / yorumlayici
# =============================================================================
def kontrol_python(rapor: Rapor) -> Dict[str, Any]:
    try:
        # venv olusturma komutu isletim sistemine gore degisir
        if os.name == "nt":
            venv_komut = "py -3.12 -m venv .venv && .venv\\Scripts\\activate"
        else:
            venv_komut = "python3.12 -m venv .venv && source .venv/bin/activate"
        v = sys.version_info
        surum = f"{v.major}.{v.minor}.{v.micro}"
        try:
            venv = (hasattr(sys, "real_prefix") or sys.prefix != getattr(sys, "base_prefix", sys.prefix)
                    or bool(os.environ.get("VIRTUAL_ENV")))
        except Exception:
            venv = False
        deger = f"{surum}  ({'venv' if venv else 'SISTEM PYTHON'}: {sys.executable})"
        if (v.major, v.minor) == (3, 12):
            durum, anlam, cozum = OK, "Beklenen surum (3.12). Bagimlilik tekerlekleri bu surum icin cozuldu.", ""
        elif v.major == 3 and 10 <= v.minor <= 13:
            durum = WARN
            anlam = (f"Proje 3.12 ile dogrulandi; sen {surum} kullaniyorsun. Istemci tarafi "
                     "buyuk olasilikla calisir, vLLM tekerlekleri sorun cikarabilir.")
            cozum = f"Sorun yasarsan 3.12 ile venv ac: {venv_komut}"
        else:
            durum = FAIL
            anlam = (f"{surum} destek araliginin disinda; bagimliliklarin cogu (vllm, av, "
                     "torch) bu surum icin teker yayinlamamis olabilir.")
            cozum = f"Python 3.12 kur ve venv olustur: {venv_komut}"
        if not venv and durum == OK:
            durum = WARN
            anlam += " Sanal ortam (venv) kullanmiyorsun — sistem Python'ini kirletme riski var."
            cozum = f"{venv_komut} && pip install -r requirements.txt"
        return rapor.ekle("2", "Python surumu / venv", durum, deger, anlam, cozum,
                          surum=surum, venv=venv)
    except Exception as e:
        return rapor.ekle("2", "Python surumu / venv", WARN, "tespit edilemedi",
                          f"Kontrol hata verdi: {type(e).__name__}: {str(e)[:120]}", surum="?", venv=False)


# =============================================================================
# 3) NVIDIA GPU (nvidia-smi)
# =============================================================================
def kontrol_gpu(rapor: Rapor, sim: set) -> Dict[str, Any]:
    try:
        if "no-gpu" in sim:
            yol = None
        else:
            yol = shutil.which("nvidia-smi")
            if not yol and os.path.exists("/usr/lib/wsl/lib/nvidia-smi"):
                yol = "/usr/lib/wsl/lib/nvidia-smi"

        if not yol:
            return rapor.ekle(
                "3", "NVIDIA GPU", FAIL, "nvidia-smi bulunamadi",
                "Bu makinede kullanilabilir bir NVIDIA GPU tespit edilemedi (surucu yok, "
                "kart NVIDIA degil ya da WSL'e GPU aktarilmiyor). Qwen3-VL-8B-FP8'i BU "
                "makinede kosturamazsin.",
                "En kolay cozum YOL 1 (kaptanin sunucusuna LAN uzerinden baglan) — asagidaki "
                "tavsiye bolumune bak. GPU'n VARSA: Windows'a guncel NVIDIA surucusunu kur "
                "(WSL icin ayrica CUDA toolkit gerekmez, surucu Windows tarafina kurulur).",
                gpu_var=False, vram_gb=0.0)

        if "low-vram" in sim:
            rc, out, err = 0, "0, NVIDIA GeForce RTX 3070 Laptop GPU, 8192, 7800, 566.03", ""
        else:
            rc, out, err = calistir(
                [yol, "--query-gpu=index,name,memory.total,memory.free,driver_version",
                 "--format=csv,noheader,nounits"], timeout=20.0)

        if rc != 0 or not out:
            return rapor.ekle(
                "3", "NVIDIA GPU", FAIL, f"nvidia-smi calisti ama hata verdi (rc={rc})",
                f"Surucu/kart iletisimi kurulamadi. Cikti: {(err or out)[:160]}",
                "Windows tarafinda NVIDIA surucusunu guncelle ve WSL'i yeniden baslat: "
                "wsl --shutdown  (sonra terminali yeniden ac).",
                gpu_var=False, vram_gb=0.0)

        kartlar: List[Dict[str, Any]] = []
        for ham in out.splitlines():
            parcalar = [p.strip() for p in ham.split(",")]
            if len(parcalar) < 5:
                continue
            try:
                kartlar.append({
                    "index": parcalar[0], "ad": parcalar[1],
                    "toplam_gb": round(float(parcalar[2]) / 1024.0, 1),
                    "bos_gb": round(float(parcalar[3]) / 1024.0, 1),
                    "surucu": parcalar[4],
                })
            except Exception:
                continue
        if not kartlar:
            return rapor.ekle("3", "NVIDIA GPU", WARN, "cikti ayristirilamadi",
                              f"nvidia-smi ciktisi beklenen bicimde degil: {out[:120]}",
                              gpu_var=False, vram_gb=0.0)

        en_iyi = max(kartlar, key=lambda k: k["toplam_gb"])
        deger = (f"{len(kartlar)} kart | {en_iyi['ad']} | {en_iyi['toplam_gb']} GB toplam, "
                 f"{en_iyi['bos_gb']} GB bos | surucu {en_iyi['surucu']}")
        vram = en_iyi["toplam_gb"]
        if vram >= VRAM_RAHAT:
            durum = OK
            anlam = "VRAM varsayilan ayarlar (8B-FP8, max_model_len=8192) icin yeterli."
            cozum = ""
        elif vram >= VRAM_ASGARI:
            durum = WARN
            anlam = (f"{vram} GB sinirda. Model agirligi ~10 GB; KV cache icin yer daralir, "
                     "uzun videolarda OOM gorebilirsin.")
            cozum = ("DILAJAN_GPU_MEMORY_UTILIZATION=0.85 DILAJAN_MAX_MODEL_LEN=4096 "
                     "python serve_vllm.py")
        elif vram >= VRAM_KUCUK:
            durum = WARN
            anlam = (f"{vram} GB dar. 8B-FP8 agirligi (~10 GB) ancak sigar, KV cache icin "
                     "neredeyse yer kalmaz.")
            cozum = ("Daha kucuk model + dusuk baglam dene:  DILAJAN_MODEL_NAME=Qwen/Qwen2.5-VL-7B-Instruct "
                     "DILAJAN_QUANTIZATION=awq DILAJAN_MAX_MODEL_LEN=4096 "
                     "DILAJAN_GPU_MEMORY_UTILIZATION=0.85 python serve_vllm.py  — ya da YOL 1 (LAN).")
        else:
            durum = FAIL
            anlam = (f"{vram} GB YETERSIZ. Qwen3-VL-8B-FP8 bu kartta SIGMAZ "
                     f"(agirlik ~10 GB + KV cache; pratikte {VRAM_ASGARI:.0f}-24 GB ister).")
            cozum = ("YOL 1 (LAN) kullan. Israrla yerelde denemek istersen 4-bit kucuk model: "
                     "DILAJAN_MODEL_NAME=Qwen/Qwen2.5-VL-3B-Instruct-AWQ DILAJAN_QUANTIZATION=awq "
                     "DILAJAN_MAX_MODEL_LEN=2048 python serve_vllm.py")
        if en_iyi["bos_gb"] < 6.0 and durum == OK:
            durum = WARN
            anlam += f" DIKKAT: su an yalniz {en_iyi['bos_gb']} GB bos — baska bir surec GPU'yu tutuyor."
            cozum = "GPU'yu kullanan surecleri kapat (nvidia-smi ile PID'leri gor) ve tekrar dene."
        return rapor.ekle("3", "NVIDIA GPU", durum, deger, anlam, cozum,
                          gpu_var=True, vram_gb=vram, bos_gb=en_iyi["bos_gb"],
                          surucu=en_iyi["surucu"], kartlar=kartlar)
    except Exception as e:
        return rapor.ekle("3", "NVIDIA GPU", WARN, "tespit edilemedi",
                          f"Kontrol hata verdi: {type(e).__name__}: {str(e)[:120]}",
                          gpu_var=False, vram_gb=0.0)


# =============================================================================
# 4) torch + CUDA (ALT SURECTE calisir: bozuk torch bu betigi COKERTEMEZ)
# =============================================================================
_TORCH_PROBU = r"""
import json
c = {}
try:
    import torch
    c["surum"] = torch.__version__
    c["cuda_derleme"] = torch.version.cuda
    try:
        c["kullanilabilir"] = bool(torch.cuda.is_available())
    except Exception as e:
        c["kullanilabilir"] = False
        c["cuda_hata"] = "%s: %s" % (type(e).__name__, str(e)[:200])
    if c.get("kullanilabilir"):
        p = torch.cuda.get_device_properties(0)
        c["cihaz"] = p.name
        c["yetenek"] = "%d.%d" % (p.major, p.minor)
        c["sm"] = p.major * 10 + p.minor
        c["toplam_gb"] = round(p.total_memory / 1024**3, 1)
except Exception as e:
    c["hata"] = "%s: %s" % (type(e).__name__, str(e)[:300])
print("<<DOCTOR>>" + json.dumps(c))
"""


def kontrol_torch(rapor: Rapor, sim: set, atla: bool, timeout: float) -> Dict[str, Any]:
    try:
        if atla:
            return rapor.ekle("4", "torch / CUDA", INFO, "atlandi (--skip-torch)",
                              "torch probu calistirilmadi.", torch_var=None, cuda_ok=False)
        if "no-torch" in sim:
            return rapor.ekle(
                "4", "torch / CUDA", FAIL, "kurulu degil (simulasyon)",
                "torch bulunamadi — yerelde model SUNAMAZSIN.",
                "Blackwell/RTX 50xx: pip install torch==2.11.0 torchvision==0.26.0 "
                "torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu130",
                torch_var=False, cuda_ok=False)

        rc, out, err = calistir([sys.executable, "-c", _TORCH_PROBU], timeout=timeout)
        veri: Dict[str, Any] = {}
        for satir in out.splitlines():
            if satir.startswith("<<DOCTOR>>"):
                try:
                    veri = json.loads(satir[len("<<DOCTOR>>"):])
                except Exception:
                    veri = {}
        if rc != 0 and not veri:
            # Alt surec cokmus olabilir (segfault / libcudart) — bu BILGIDIR, cokme degil.
            return rapor.ekle(
                "4", "torch / CUDA", FAIL, f"prob basarisiz (rc={rc})",
                f"torch import edilirken surec dustu ya da zaman asimi oldu: {(err or out)[:180]}",
                "Genellikle CUDA/torch surum uyumsuzlugu. Blackwell (RTX 50xx) icin cu130 sart: "
                "pip install --force-reinstall torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 "
                "--index-url https://download.pytorch.org/whl/cu130",
                torch_var=None, cuda_ok=False)
        if "hata" in veri or not veri.get("surum"):
            return rapor.ekle(
                "4", "torch / CUDA", FAIL, "kurulu degil",
                f"torch import edilemedi ({veri.get('hata', 'bilinmiyor')[:140]}). "
                "Yerelde model SUNAMAZSIN (istemci/arayuz icin torch GEREKMEZ).",
                "pip install torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 "
                "--index-url https://download.pytorch.org/whl/cu130",
                torch_var=False, cuda_ok=False)

        surum = veri.get("surum", "?")
        cuda_derleme = veri.get("cuda_derleme") or "CPU-only"
        if not veri.get("kullanilabilir"):
            return rapor.ekle(
                "4", "torch / CUDA", FAIL,
                f"torch {surum} (cu{cuda_derleme}) — torch.cuda.is_available()=False",
                "torch kurulu ama GPU'yu GOREMIYOR: ya CPU-only teker kurulu, ya surucu "
                f"uyumsuz, ya da WSL'e GPU aktarilmiyor. {veri.get('cuda_hata', '')[:120]}",
                "CPU-only teker kuruluysa CUDA tekerine gec: pip install --force-reinstall "
                "torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 "
                "--index-url https://download.pytorch.org/whl/cu130",
                torch_var=True, cuda_ok=False, torch_surum=surum, cuda_derleme=cuda_derleme)

        sm = int(veri.get("sm") or 0)
        yetenek = veri.get("yetenek", "?")
        deger = (f"torch {surum} (cu{cuda_derleme}) | CUDA acik | {veri.get('cihaz', '?')} "
                 f"sm_{sm} ({yetenek}) {veri.get('toplam_gb', '?')} GB")
        durum, anlam, cozum = OK, "torch GPU'yu goruyor; yerel sunucu icin bu sart saglandi.", ""
        try:
            derleme_major = int(str(cuda_derleme).split(".")[0])
        except Exception:
            derleme_major = 0
        if sm >= 120 and derleme_major and derleme_major < 13:
            durum = FAIL
            anlam = (f"Blackwell (sm_{sm}) kart ama torch cu{cuda_derleme} ile derlenmis. "
                     "Bu kombinasyon vLLM baslatirken libcudart/kernel hatasi verir.")
            cozum = ("pip install --force-reinstall torch==2.11.0 torchvision==0.26.0 "
                     "torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu130")
        return rapor.ekle("4", "torch / CUDA", durum, deger, anlam, cozum,
                          torch_var=True, cuda_ok=(durum == OK), torch_surum=surum,
                          cuda_derleme=cuda_derleme, sm=sm)
    except Exception as e:
        return rapor.ekle("4", "torch / CUDA", WARN, "tespit edilemedi",
                          f"Kontrol hata verdi: {type(e).__name__}: {str(e)[:120]}",
                          torch_var=None, cuda_ok=False)


# =============================================================================
# 5) Python paketleri (vLLM, gradio, langgraph, av, openai, ...)
# =============================================================================
def kontrol_paketler(rapor: Rapor) -> Dict[str, Any]:
    eksik_istemci: List[str] = []
    eksik_sunucu: List[str] = []
    eksik_ops: List[str] = []
    surumler: Dict[str, str] = {}

    def tara(liste, kova: List[str]) -> None:
        for dagitim, modul, pip_spec in liste:
            try:
                s = paket_surumu(dagitim, modul)
            except Exception:
                s = None
            if s:
                surumler[dagitim] = s
            else:
                kova.append(pip_spec)

    try:
        tara(ISTEMCI_PAKETLERI, eksik_istemci)
        tara(SUNUCU_PAKETLERI, eksik_sunucu)
        tara(OPSIYONEL_PAKETLER, eksik_ops)

        ozet_parcalar = []
        for ad in ("vllm", "openai", "gradio", "langgraph", "av", "pydantic-settings"):
            ozet_parcalar.append(f"{ad}={surumler.get(ad, 'YOK')}")
        deger = " ".join(ozet_parcalar)

        if eksik_istemci:
            durum = FAIL
            anlam = (f"ISTEMCI icin {len(eksik_istemci)} paket eksik — arayuzu (app.py) "
                     "ACAMAZSIN, LAN yolu bile calismaz.")
            cozum = "pip install " + " ".join(eksik_istemci)
        elif eksik_sunucu:
            durum = WARN
            anlam = (f"Istemci paketleri tam (arayuz + LAN calisir). SUNUCU icin eksik: "
                     f"{len(eksik_sunucu)} paket — bu makinede model SUNAMAZSIN.")
            cozum = ("Yalniz LAN'a baglanacaksan GEREK YOK. Yerelde sunacaksan: "
                     "pip install " + " ".join(eksik_sunucu))
        else:
            durum = OK
            anlam = "Istemci ve sunucu paketleri kurulu."
            cozum = ""
        if eksik_ops and durum == OK:
            anlam += f" (Opsiyonel eksik: {', '.join(eksik_ops)} — kod FAIL-OPEN calisir.)"
        return rapor.ekle("5", "Python paketleri", durum, deger, anlam, cozum,
                          eksik_istemci=eksik_istemci, eksik_sunucu=eksik_sunucu,
                          eksik_opsiyonel=eksik_ops, surumler=surumler)
    except Exception as e:
        return rapor.ekle("5", "Python paketleri", WARN, "tespit edilemedi",
                          f"Kontrol hata verdi: {type(e).__name__}: {str(e)[:120]}",
                          eksik_istemci=[], eksik_sunucu=[], eksik_opsiyonel=[], surumler={})


# =============================================================================
# 6) ffmpeg / ffprobe
# =============================================================================
def kontrol_ffmpeg(rapor: Rapor) -> Dict[str, Any]:
    try:
        ff = shutil.which("ffmpeg")
        fp = shutil.which("ffprobe")
        if ff and fp:
            surum = ""
            rc, out, _ = calistir([ff, "-version"], timeout=10.0)
            if rc == 0 and out:
                surum = out.splitlines()[0][:60]
            return rapor.ekle("6", "ffmpeg / ffprobe", OK, surum or ff,
                              "Arayuz onizleme transcode'u calisir.", ffmpeg=True)
        eksik = ", ".join([a for a, v in (("ffmpeg", ff), ("ffprobe", fp)) if not v])
        return rapor.ekle(
            "6", "ffmpeg / ffprobe", WARN, f"{eksik} bulunamadi",
            "Analiz CALISIR (app.py FAIL-OPEN'dir) ama tarayicida oynatilamayan kodekli "
            "videolarin ONIZLEMESI gorunmez.",
            "Ubuntu/WSL: sudo apt install -y ffmpeg   |   Windows: winget install Gyan.FFmpeg",
            ffmpeg=False)
    except Exception as e:
        return rapor.ekle("6", "ffmpeg / ffprobe", WARN, "tespit edilemedi",
                          f"Kontrol hata verdi: {type(e).__name__}: {str(e)[:120]}", ffmpeg=False)


# =============================================================================
# 7) Sunucu erisimi (/health + /v1/models)
# =============================================================================
def _http_get(url: str, timeout: float) -> Tuple[int, str, str]:
    """(http_kodu, govde, hata). Kod 0 = baglanti hic kurulamadi."""
    try:
        istek = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(istek, timeout=timeout) as yanit:  # noqa: S310 (yerel adres)
            return yanit.getcode(), yanit.read(20000).decode("utf-8", "replace"), ""
    except urllib.error.HTTPError as e:
        return e.code, "", f"HTTP {e.code}"
    except Exception as e:
        return 0, "", f"{type(e).__name__}: {str(e)[:140]}"


def kontrol_sunucu(rapor: Rapor, ayarlar: Dict[str, Any], sim: set, timeout: float) -> Dict[str, Any]:
    try:
        host = str(ayarlar.get("host", "127.0.0.1"))
        port = int(ayarlar.get("port", 8000))
        beklenen_model = str(ayarlar.get("model", ""))
        # 0.0.0.0 bir BIND adresidir; istemci olarak ona baglanilmaz -> loopback'e cevir
        istemci_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
        uzak = istemci_host not in ("127.0.0.1", "localhost", "::1")

        if "no-server" in sim:
            kod, govde, hata = 0, "", "simulasyon: baglanti yok"
        else:
            kod, govde, hata = _http_get(f"http://{istemci_host}:{port}/health", timeout)
            if kod == 0:
                kod, govde, hata = _http_get(f"http://{istemci_host}:{port}/v1/models", timeout)

        if kod == 0:
            deger = f"http://{istemci_host}:{port} ERISILEMIYOR ({hata})"
            if uzak:
                anlam = ("Kaptanin makinesine (LAN) baglanmaya calisiyorsun ama cevap yok: "
                         "sunucu kapali, IP yanlis ya da guvenlik duvari/WSL2 NAT engelliyor.")
                cozum = (f"Kaptan sunucuyu 0.0.0.0'a acmali ve (WSL2 kullaniyorsa) Windows port "
                         f"yonlendirmesi yapmali — tavsiye bolumune bak. Once basit test: "
                         f"ping {istemci_host}")
            else:
                anlam = ("Bu makinede AYAKTA bir vLLM sunucusu YOK. app.py acilir ama analiz "
                         "baslatinca baglanti hatasi alirsin.")
                cozum = ("Yerelde baslat:  python serve_vllm.py   |   ya da kaptanin sunucusuna "
                         "bagla:  DILAJAN_VLLM_HOST=<kaptan-IP> python app.py")
            return rapor.ekle("7", "vLLM sunucu erisimi", FAIL, deger, anlam, cozum,
                              erisim=False, uzak=uzak, host=istemci_host, port=port)

        # Erisim var — hangi model servisleniyor?
        kod2, govde2, _ = _http_get(f"http://{istemci_host}:{port}/v1/models", timeout)
        modeller: List[str] = []
        try:
            veri = json.loads(govde2 or govde or "{}")
            modeller = [m.get("id", "") for m in veri.get("data", []) if isinstance(m, dict)]
        except Exception:
            pass
        nerede = f"{'LAN (' + istemci_host + ')' if uzak else 'yerel'}"
        if not modeller:
            return rapor.ekle(
                "7", "vLLM sunucu erisimi", WARN,
                f"http://{istemci_host}:{port} ayakta ({nerede}) ama model listesi okunamadi",
                "Adres cevap veriyor fakat /v1/models bos/ayristirilamadi — vLLM disinda bir "
                "servis olabilir ya da model hala yukleniyordur.",
                "Sunucu loglarina bak; model yuklemesi bitene kadar (ilk seferde birkac dakika) bekle.",
                erisim=True, uzak=uzak, host=istemci_host, port=port, modeller=[])
        eslesme = beklenen_model in modeller
        durum = OK if eslesme else WARN
        anlam = (f"Sunucu ayakta ve '{modeller[0]}' servisleniyor. HAZIRSIN." if eslesme else
                 f"Sunucu ayakta ama servislenen model ({', '.join(modeller)[:80]}) beklenen "
                 f"'{beklenen_model}' ile AYNI DEGIL. Istemci model adini birebir gonderir; "
                 "eslesmezse 404/NotFound alirsin.")
        cozum = "" if eslesme else f"DILAJAN_MODEL_NAME={modeller[0]} python app.py"
        return rapor.ekle("7", "vLLM sunucu erisimi", durum,
                          f"http://{istemci_host}:{port} AYAKTA ({nerede}) | {', '.join(modeller)[:70]}",
                          anlam, cozum, erisim=True, uzak=uzak, host=istemci_host,
                          port=port, modeller=modeller, model_eslesti=eslesme)
    except Exception as e:
        return rapor.ekle("7", "vLLM sunucu erisimi", WARN, "tespit edilemedi",
                          f"Kontrol hata verdi: {type(e).__name__}: {str(e)[:120]}",
                          erisim=False, uzak=False)


# =============================================================================
# 8) DILAJAN_* ortam degiskenleri
# =============================================================================
def kontrol_env(rapor: Rapor, ayarlar: Dict[str, Any]) -> Dict[str, Any]:
    try:
        env = {k: v for k, v in sorted(os.environ.items()) if k.startswith("DILAJAN_")}
        onemli = ("DILAJAN_VLLM_HOST", "DILAJAN_VLLM_PORT", "DILAJAN_MODEL_NAME",
                  "DILAJAN_MOCK", "DILAJAN_HOST", "DILAJAN_SHARE")
        if env:
            deger = " ".join(f"{k}={v[:34]}" for k, v in env.items())
        else:
            deger = "hicbiri set edilmemis (varsayilanlar kullaniliyor)"
        eksik_onemli = [a for a in onemli if a not in env]
        anlam = (f"Ayar kaynagi: {ayarlar.get('kaynak')} | etkin sunucu adresi: "
                 f"{ayarlar.get('base_url')} | model: {ayarlar.get('model')}")
        if ayarlar.get("hata"):
            anlam += f" | UYARI: dilajan.config yuklenemedi ({ayarlar['hata'][:80]})"
        cozum = ""
        if "DILAJAN_VLLM_HOST" not in env and not ayarlar.get("hata"):
            cozum = ("LAN'daki kaptana baglanacaksan bu degiskeni set et: "
                     "DILAJAN_VLLM_HOST=<kaptan-IP> python app.py")
        return rapor.ekle("8", "DILAJAN_* degiskenleri", INFO, deger, anlam, cozum,
                          env=env, set_edilmemis=eksik_onemli)
    except Exception as e:
        return rapor.ekle("8", "DILAJAN_* degiskenleri", WARN, "okunamadi",
                          f"Kontrol hata verdi: {type(e).__name__}: {str(e)[:120]}", env={})


# =============================================================================
# 9) Disk (model onbellegi)
# =============================================================================
def kontrol_disk(rapor: Rapor) -> Dict[str, Any]:
    try:
        hedef = (os.environ.get("HF_HOME")
                 or os.environ.get("HUGGINGFACE_HUB_CACHE")
                 or os.path.join(os.path.expanduser("~"), ".cache", "huggingface"))
        # Var olan en yakin ust dizini bul (onbellek henuz olusmamis olabilir)
        olcum_yolu = hedef
        while olcum_yolu and not os.path.isdir(olcum_yolu):
            ust = os.path.dirname(olcum_yolu)
            if ust == olcum_yolu:
                break
            olcum_yolu = ust
        kullanim = shutil.disk_usage(olcum_yolu or os.path.abspath(os.sep))
        bos_gb = round(kullanim.free / 1024 ** 3, 1)
        mevcut_gb = 0.0
        if os.path.isdir(hedef):
            try:
                toplam = 0
                for kok, _dizinler, dosyalar in os.walk(hedef):
                    for d in dosyalar:
                        try:
                            toplam += os.path.getsize(os.path.join(kok, d))
                        except OSError:
                            continue
                mevcut_gb = round(toplam / 1024 ** 3, 1)
            except Exception:
                mevcut_gb = 0.0
        deger = f"{bos_gb} GB bos ({olcum_yolu}) | onbellek: {mevcut_gb} GB"
        if bos_gb >= DISK_ASGARI_GB:
            durum, anlam, cozum = OK, "Model indirmesi (~10-20 GB) icin yeterli alan var.", ""
        else:
            durum = WARN
            anlam = (f"{bos_gb} GB bos — Qwen3-VL-8B-FP8 indirmesi (~10 GB, gecici dosyalarla "
                     f"~20 GB) sigmayabilir. Onerilen: {DISK_ASGARI_GB:.0f} GB+")
            cozum = ("Yer ac ya da onbellegi baska diske tasi: HF_HOME=/baska/disk/hf "
                     "python serve_vllm.py  (LAN yolunda model INDIRILMEZ, disk gerekmez.)")
        return rapor.ekle("9", "Disk (model onbellegi)", durum, deger, anlam, cozum,
                          bos_gb=bos_gb, onbellek_gb=mevcut_gb, yol=hedef)
    except Exception as e:
        return rapor.ekle("9", "Disk (model onbellegi)", WARN, "olculemedi",
                          f"Kontrol hata verdi: {type(e).__name__}: {str(e)[:120]}", bos_gb=0.0)


# =============================================================================
# Yardimcilar: LAN IP ve mock destegi
# =============================================================================
def lan_ip(wsl: bool) -> Tuple[str, str]:
    """(ip, kaynak) dondurur. kaynak: 'windows-lan' | 'wsl-ic' | 'lan' | 'bilinmiyor'.

    ONEMLI: WSL2 KENDI NAT agindadir. WSL icindeki soketten okunan adres (or. 172.x)
    LAN'daki arkadaslarin ERISEMEYECEGI bir adrestir; onlarin ihtiyaci olan sey
    WINDOWS ana makinesinin LAN adresidir. Bu yuzden WSL'de once Windows'a sorulur.
    (Salt-okunur bir sorgu; hicbir ayar degistirilmez.)
    """
    if wsl:
        try:
            rc, out, _ = calistir(
                ["powershell.exe", "-NoProfile", "-Command",
                 "(Get-NetIPConfiguration | Where-Object IPv4DefaultGateway).IPv4Address.IPAddress"],
                timeout=15.0)
            if rc == 0 and out:
                aday = out.replace("\r", "").split("\n")[0].strip()
                if aday.count(".") == 3:
                    return aday, "windows-lan"
        except Exception:
            pass
    ic = ""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ic = s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        pass
    if not ic:
        try:
            ic = socket.gethostbyname(socket.gethostname())
        except Exception:
            ic = ""
    if not ic:
        return "<kaptanin-LAN-IP>", "bilinmiyor"
    return ic, ("wsl-ic" if wsl else "lan")


def mock_destegi_var(ayarlar: Dict[str, Any]) -> bool:
    """Depoda MOCK/OFFLINE modu GERCEKTEN var mi? (Baska bir ajan ekliyor olabilir.)

    Yoksa tavsiye bolumunde YOL 2'den HIC bahsedilmez (yanlis yonlendirme yapmamak icin).
    """
    try:
        alanlar = set(ayarlar.get("alanlar") or [])
        if alanlar & {"mock", "mock_mode", "offline", "offline_mode"}:
            return True
    except Exception:
        pass
    for goreli in ("app.py", os.path.join("dilajan", "config.py")):
        try:
            with open(os.path.join(PROJECT_ROOT, goreli), "r", encoding="utf-8", errors="replace") as fh:
                if "DILAJAN_MOCK" in fh.read():
                    return True
        except Exception:
            continue
    return False


# =============================================================================
# SANA OZEL TAVSIYE
# =============================================================================
def tavsiye(rapor: Rapor, ayarlar: Dict[str, Any], renkli: bool) -> Tuple[int, str]:
    """Tespitlere gore YOL 1/2/3'ten birini net komutlarla onerir. (cikis_kodu, ozet) doner."""
    o = rapor.bul("1")
    p = rapor.bul("2")
    g = rapor.bul("3")
    t = rapor.bul("4")
    pk = rapor.bul("5")
    sv = rapor.bul("7")

    linux = bool(o.get("linux"))
    gpu_var = bool(g.get("gpu_var"))
    vram = float(g.get("vram_gb") or 0.0)
    torch_ok = bool(t.get("cuda_ok"))
    torch_atlandi = t.get("durum") == INFO
    sunucu_paket_tam = not pk.get("eksik_sunucu")
    istemci_paket_tam = not pk.get("eksik_istemci")
    erisim = bool(sv.get("erisim"))
    uzak = bool(sv.get("uzak"))
    mock_var = mock_destegi_var(ayarlar)
    ip, ip_kaynak = lan_ip(bool(o.get("wsl")))
    model = ayarlar.get("model", "Qwen/Qwen3-VL-8B-Instruct-FP8")

    yerel_sunabilir = (linux and gpu_var and vram >= VRAM_ASGARI and sunucu_paket_tam
                       and (torch_ok or torch_atlandi))

    baslik = "SANA OZEL TAVSIYE"
    print("", flush=True)
    print(("=" * 80), flush=True)
    print((f"{_KALIN}{baslik}{_SIFIRLA}" if renkli else baslik), flush=True)
    print(("=" * 80), flush=True)

    # --- Durum tespiti tek cumlede
    if erisim and istemci_paket_tam:
        ozet = ("HAZIRSIN — sunucuya erisiliyor" + (f" (LAN: {sv.get('host')})" if uzak else " (yerel)")
                + ". Yapman gereken tek sey arayuzu acmak.")
        kod = 0
    elif yerel_sunabilir:
        ozet = "Bu makine MODEL SUNABILIR; sunucu su an kapali. Baslatman yeterli."
        kod = 0
    elif not istemci_paket_tam:
        ozet = "KRITIK: istemci paketleri eksik — once onlari kur, sonra LAN'a bagla."
        kod = 1
    elif not gpu_var:
        ozet = "KRITIK: kullanilabilir NVIDIA GPU yok — bu makinede model KOSTURULAMAZ. LAN yolunu kullan."
        kod = 1
    elif vram < VRAM_ASGARI:
        ozet = (f"KRITIK: {vram} GB VRAM varsayilan model icin yetersiz. LAN yolu ya da "
                "kucuk-model yolu.")
        kod = 1
    elif not linux:
        ozet = "KRITIK: Windows'ta vLLM yerli calismaz. LAN yolu (ya da WSL2 kurulumu)."
        kod = 1
    else:
        ozet = "KRITIK: yerel sunucu on sartlari eksik (torch/vLLM). Detaylar asagida."
        kod = 1
    print(f"\nDURUM: {ozet}\n", flush=True)

    # --- YOL 1: LAN (her zaman gosterilir; en kolay ve yarisma kuralina uygun)
    birincil = "  <-- SENIN ICIN EN UYGUN" if kod == 1 or (erisim and uzak) else ""
    print(f"YOL 1 (EN KOLAY) — LAN: kaptanin sunucusuna bagla{birincil}", flush=True)
    print("  Kaptanin makinesinde (WSL2, GPU'lu):", flush=True)
    print("      DILAJAN_VLLM_HOST=0.0.0.0 python serve_vllm.py", flush=True)
    print("  Sende (GPU GEREKMEZ, torch/vLLM GEREKMEZ):", flush=True)
    kaptan_ip = sv.get("host") if (erisim and uzak) else "<kaptanin-LAN-IP>"
    print(f"      DILAJAN_VLLM_HOST={kaptan_ip} python app.py", flush=True)
    print("  Arayuz: http://127.0.0.1:7860", flush=True)
    print("  NOT (yarisma kurali): bu, KENDI agimizdaki KENDI makinemizdir; dis API/bulut/", flush=True)
    print("       ucretli servis YOK -> 'tamamen yerel calisma' sartina UYAR.", flush=True)
    print("  KAPTAN WSL2 KULLANIYORSA (cok atlanan adim): WSL2 NAT arkasindadir, 0.0.0.0'a", flush=True)
    print("       baglanmak LAN'dan yetmez. Kaptan bir kez sunlardan BIRINI yapmali:", flush=True)
    print("       (a) .wslconfig icine  [wsl2]  networkingMode=mirrored  ekleyip  wsl --shutdown", flush=True)
    print("       (b) yonetici PowerShell'de port yonlendirme + guvenlik duvari izni:", flush=True)
    print("           netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 \\", flush=True)
    print("               connectport=8000 connectaddress=$(wsl hostname -I)", flush=True)
    print('           New-NetFirewallRule -DisplayName "vLLM 8000" -Direction Inbound '
          "-LocalPort 8000 -Protocol TCP -Action Allow", flush=True)
    print("       (Bu komutlari KAPTAN kendi makinesinde calistirir.)", flush=True)
    if not istemci_paket_tam:
        print("  ONCE SU: istemci paketleri eksik ->", flush=True)
        print("      pip install " + " ".join(pk.get("eksik_istemci") or []), flush=True)
    print("", flush=True)

    # --- YOL 2: MOCK (yalniz depoda GERCEKTEN varsa)
    if mock_var:
        print("YOL 2 — MOCK: GPU'suz gelistirme / arayuz kesfi", flush=True)
        print("      DILAJAN_MOCK=1 python app.py", flush=True)
        print("  Model yuklenmez; pipeline ve arayuz sahte ciktilarla gezilebilir "
              "(olcum/teslim icin DEGIL).", flush=True)
        print("", flush=True)

    # --- YOL 3: kendi GPU'n
    print("YOL 3 — KENDI GPU'nda yerel sunucu", flush=True)
    if yerel_sunabilir and not erisim:
        print("  Sartlar SAGLANDI. Iki terminal ac:", flush=True)
        print("      T1:  python serve_vllm.py", flush=True)
        print("      T2:  python app.py", flush=True)
        print("  Takimin sana baglanacaksa:  DILAJAN_VLLM_HOST=0.0.0.0 python serve_vllm.py", flush=True)
        if ip_kaynak == "windows-lan":
            print(f"  (Windows ana makinenin LAN IP'si: {ip} — uyeler "
                  f"DILAJAN_VLLM_HOST={ip} kullanir.)", flush=True)
        elif ip_kaynak == "wsl-ic":
            print(f"  DIKKAT: {ip} WSL2'nin IC (NAT) adresidir; LAN'daki arkadaslarin buna", flush=True)
            print("          ERISEMEZ. Uyelere WINDOWS ana makinenin LAN IP'sini ver:", flush=True)
            print("          PowerShell'de:  (Get-NetIPConfiguration | Where-Object "
                  "IPv4DefaultGateway).IPv4Address.IPAddress", flush=True)
            print("          Ayrica yukaridaki (a)/(b) WSL2 ag adimlarindan biri SART.", flush=True)
        else:
            print(f"  (Bu makinenin adresi: {ip} — uyeler DILAJAN_VLLM_HOST={ip} kullanir.)", flush=True)
    elif not gpu_var:
        print("  KULLANILAMAZ: bu makinede NVIDIA GPU yok. YOL 1'i kullan.", flush=True)
    elif vram < VRAM_KUCUK:
        print(f"  {vram} GB VRAM ile varsayilan model ({model}) SIGMAZ. Kucuk-model denemesi:", flush=True)
        print("      DILAJAN_MODEL_NAME=Qwen/Qwen2.5-VL-3B-Instruct-AWQ DILAJAN_QUANTIZATION=awq \\", flush=True)
        print("      DILAJAN_MAX_MODEL_LEN=2048 DILAJAN_GPU_MEMORY_UTILIZATION=0.85 python serve_vllm.py", flush=True)
        print("  UYARI: kucuk model ile OLCUM SONUCLARI TEKRAR URETILEMEZ; teslim/olcum daima", flush=True)
        print("         varsayilan model ile yapilir. Bu yol yalniz gelistirme icindir.", flush=True)
    elif vram < VRAM_RAHAT:
        print(f"  {vram} GB sinirda — kucultulmus ayarlarla dene:", flush=True)
        print("      DILAJAN_MAX_MODEL_LEN=4096 DILAJAN_GPU_MEMORY_UTILIZATION=0.85 python serve_vllm.py", flush=True)
        print("  Olmazsa hassasiyet-oncelikli yedek model:", flush=True)
        print("      DILAJAN_MODEL_NAME=Qwen/Qwen2.5-VL-7B-Instruct python serve_vllm.py", flush=True)
    else:
        print("  GPU yeterli ama on sartlar eksik. Sirasiyla:", flush=True)
        adim = 0
        if not linux:
            adim += 1
            print(f"    {adim}) WSL2 kur:  wsl --install -d Ubuntu-24.04   "
                  "(yonetici PowerShell, sonra restart)", flush=True)
            print("       Sonraki adimlari WSL/Ubuntu terminalinde yap (depo yolu: "
                  "/mnt/c/... altinda gorunur).", flush=True)
        if not torch_ok and not torch_atlandi:
            adim += 1
            print(f"    {adim}) torch (Blackwell/RTX 50xx icin cu130 SART):", flush=True)
            print("       pip install torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 \\", flush=True)
            print("           --index-url https://download.pytorch.org/whl/cu130", flush=True)
        if not sunucu_paket_tam:
            adim += 1
            print(f"    {adim}) sunucu paketleri:  pip install "
                  + " ".join(pk.get("eksik_sunucu") or []), flush=True)
        print(f"    {adim + 1}) baslat:  python serve_vllm.py", flush=True)
    print("", flush=True)

    # --- kalan HATA satirlarinin ozeti
    hatalar = [s for s in rapor.satirlar if s["durum"] == FAIL]
    if hatalar:
        print("GIDERILMESI GEREKENLER (HATA olan kontroller):" if kod == 1 else
              "HATA olan kontroller (yukaridaki yol icin ENGEL DEGIL, bilgi):", flush=True)
        for s in hatalar:
            print(f"  - [{s['no']}] {s['ad']}: {s['deger']}", flush=True)
    print("", flush=True)
    print(f"CIKIS KODU: {kod}  ({'hazir' if kod == 0 else 'kritik engel var'})", flush=True)
    return kod, ozet


# =============================================================================
# main
# =============================================================================
def main() -> int:
    _stdout_utf8()
    ap = argparse.ArgumentParser(
        description="DilAjanlari teshis araci: 'model calismiyor' sorununun nedenini ve cozumunu bulur.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="Makine-okunur JSON cikti (tablo yazilmaz).")
    ap.add_argument("--no-color", action="store_true", help="ANSI renklerini kapat.")
    ap.add_argument("--color", action="store_true", help="Renkleri zorla (boruya yazarken bile).")
    ap.add_argument("--skip-torch", action="store_true",
                    help="torch alt-surec probunu atla (en yavas kontrol).")
    ap.add_argument("--timeout", type=float, default=120.0,
                    help="torch probu icin saniye (varsayilan 120).")
    ap.add_argument("--net-timeout", type=float, default=3.0,
                    help="sunucu HTTP sorgusu icin saniye (varsayilan 3).")
    ap.add_argument("--simulate", nargs="*", default=[],
                    choices=["no-gpu", "low-vram", "no-torch", "windows", "no-server"],
                    help="TEST AMACLI: belirtilen arizayi varmis gibi davran (gercek sistemi degistirmez).")
    args = ap.parse_args()

    sim = set(args.simulate or [])
    renkli = False if args.json else _renk_ac(True if args.color else (False if args.no_color else None))
    rapor = Rapor(renkli)

    if not args.json:
        baslik = "DilAjanlari — TESHIS (scripts/doctor.py)"
        print(f"{_KALIN}{baslik}{_SIFIRLA}" if renkli else baslik, flush=True)
        print(f"proje: {PROJECT_ROOT}", flush=True)
        if sim:
            print(f"SIMULASYON ACIK: {', '.join(sorted(sim))}  (gercek sistem DEGISTIRILMEDI)", flush=True)
        print("-" * 80, flush=True)

    ayarlar = ayarlari_oku()
    kontrol_os(rapor, sim)
    kontrol_python(rapor)
    kontrol_gpu(rapor, sim)
    kontrol_torch(rapor, sim, args.skip_torch, args.timeout)
    kontrol_paketler(rapor)
    kontrol_ffmpeg(rapor)
    kontrol_sunucu(rapor, ayarlar, sim, args.net_timeout)
    kontrol_env(rapor, ayarlar)
    kontrol_disk(rapor)

    if args.json:
        try:
            # tavsiye ciktisini bastirmadan cikis kodunu hesapla
            import io as _io

            eski = sys.stdout
            sys.stdout = _io.StringIO()
            try:
                kod, ozet = tavsiye(rapor, ayarlar, False)
            finally:
                sys.stdout = eski
            print(json.dumps({"cikis_kodu": kod, "ozet": ozet, "ayarlar": ayarlar,
                              "kontroller": rapor.satirlar}, ensure_ascii=False, indent=2), flush=True)
            return kod
        except Exception as e:
            print(json.dumps({"hata": f"{type(e).__name__}: {e}"}, ensure_ascii=False), flush=True)
            return 1

    rapor.yaz()
    try:
        kod, _ = tavsiye(rapor, ayarlar, renkli)
    except Exception as e:  # tavsiye uretilemese bile betik cokmez
        print(f"\n(tavsiye uretilemedi: {type(e).__name__}: {str(e)[:160]})", flush=True)
        kod = 1 if any(s["durum"] == FAIL for s in rapor.satirlar) else 0
    return kod


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\niptal edildi.", flush=True)
        raise SystemExit(130)
