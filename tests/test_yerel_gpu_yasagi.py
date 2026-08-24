"""YEREL GPU YASAGI — uzak servis kullanilirken yerel GPU kullanilmaz.

Yasak GPU'YA OZGUDUR: yerel modeller CPU'da calismaya DEVAM EDER; yalnizca
cihaz secimi degisir. Bu ayrim onemli, cunku yasagi "yerel model yasak" diye
uygulamak ultralytics/RT-DETR yollarini tamamen kapatirdi.

NEDEN VAR: bu kusur zaten islemisti — deterministik pano dedektorunun kisi
kontrolu her klipte RT-DETRv2'yi yerel GPU'da calistiriyordu (~3,5 GB VRAM)
ve hicbir yerde gorunmedigi icin fark edilmedi. Cihaz secimi artik TEK
KAPIDAN gecer; kodda serpistirilmis device="cuda" sabiti KALMADI.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan.config import Settings, settings, yerel_cihaz

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print("  ok  ", ad)
    else: k += 1; print("  FAIL", ad)

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print("=== KAPI DAVRANISI ===")
_eski = (settings.yerel_gpu_izni, settings.api_base_url)
try:
    settings.api_base_url = "https://evren-llmapi.ssyz.org.tr/v1"
    settings.yerel_gpu_izni = False
    c("uzak kosumda yasak ACIK", settings.yerel_gpu_yasak is True)
    c("uzak kosumda cihaz CPU", yerel_cihaz() == "cpu")
    settings.yerel_gpu_izni = True
    c("ACIK izin yasagi kaldirir", settings.yerel_gpu_yasak is False)
    settings.yerel_gpu_izni = False
    settings.api_base_url = ""
    c("YEREL kosumda yasak KAPALI (K2: eski davranis)",
      settings.yerel_gpu_yasak is False)
finally:
    settings.yerel_gpu_izni, settings.api_base_url = _eski

print()
print("=== VARSAYILAN (K2) ===")
c("yerel_gpu_izni varsayilani False",
  Settings.model_fields["yerel_gpu_izni"].default is False)

print()
print("=== KODDA SABIT device=\"cuda\" KALMAMALI ===")
kacak = []
def _kod_satirlari(yol):
    """Yalnizca KOD token'lari — yorumlar ve docstring'ler haric.

    (Ilk surum ham metinde ariyordu ve kendi aciklama yorumlarini "kacak"
    sayiyordu; testin kendisi yanlis alarm uretiyordu.)
    """
    import tokenize
    out = {}
    try:
        with open(yol, "rb") as f:
            for tok in tokenize.tokenize(f.readline):
                if tok.type == tokenize.COMMENT:
                    continue
                if tok.type == tokenize.STRING and tok.line.strip().startswith(
                        (chr(34) * 3, chr(39) * 3)):
                    continue                    # docstring / blok metin
                out.setdefault(tok.start[0], []).append(tok.string)
    except Exception:
        return {}
    return {n: "".join(v) for n, v in out.items()}

DESEN = re.compile("device" + repr(chr(92) + "s*=" + chr(92) + "s*")[1:-1]
                   + "[" + chr(34) + chr(39) + "]cuda")
for kok, _d, dosyalar in os.walk(os.path.join(KOK, "dilajan")):
    for f in dosyalar:
        if not f.endswith(".py"):
            continue
        yol = os.path.join(kok, f)
        for n, kod in _kod_satirlari(yol).items():
            if DESEN.search(kod) or (".to(" + chr(34) + "cuda" + chr(34) + ")") in kod:
                kacak.append(os.path.relpath(yol, KOK) + ":" + str(n))
c(f"dilajan/ icinde sabit cuda yok (bulunan: {kacak})", not kacak)

print()
print("=== TEK KAPI GERCEKTEN CAGRILIYOR MU ===")
import dilajan.detector as D
c("detector._cihaz kapiyi kullanir", D._cihaz() == yerel_cihaz())
src = open(os.path.join(KOK, "dilajan", "detector.py"), encoding="utf-8").read()
c("detector predict cagrilari _cihaz() kullanir",
  src.count("device=_cihaz()") >= 7)
src2 = open(os.path.join(KOK, "dilajan", "algila_rtdetr.py"), encoding="utf-8").read()
c("algila_rtdetr yerel_cihaz() kullanir", "yerel_cihaz" in src2)

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
