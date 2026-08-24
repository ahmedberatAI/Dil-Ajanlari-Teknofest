"""SERVIS DAYANIKLILIGI — gecici hatalarda yeniden deneme.

NEDEN VAR (olculdu 2026-08-24): uzak servis 10 istekte ust uste
`502 Bad Gateway` dondurdu. Yeniden deneme olmadigi icin o 10 slot
"olculemedi" olarak kaydedildi. Sunum sirasinda ayni sey olursa demo
bir klipte sessizce bos doner.

AYRIM KRITIK: 5xx/429/zaman asimi GECICIDIR (tekrar dene); 4xx ISTEK
HATASIDIR (tekrarlamak yalnizca gecikme ekler). Ornek: `vlm` aliasi
goruntu kabul etmez ve 400 doner — bu asla yeniden denenmemeli.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan.llm_client import VLMClient
from dilajan.config import Settings, settings

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print("  ok  ", ad)
    else: k += 1; print("  FAIL", ad)

class SahteHata(Exception):
    def __init__(self, kod=None, mesaj=""):
        super().__init__(mesaj or f"kod {kod}")
        self.status_code = kod

def tipli(ad, kod=None, mesaj=""):
    """Belirtilen SINIF ADIYLA bir istisna uretir (openai tiplerini taklit)."""
    T = type(ad, (Exception,), {})
    e = T(mesaj or f"kod {kod}")
    if kod is not None:
        e.status_code = kod
    return e

print("=== GECICI / KALICI AYRIMI ===")
G = VLMClient._gecici_hata_mi
c("500 GECICI", G(tipli("APIStatusError", 500)))
c("502 GECICI", G(tipli("APIStatusError", 502)))
c("503 GECICI", G(tipli("APIStatusError", 503)))
c("429 GECICI", G(tipli("RateLimitError", 429)))
c("zaman asimi GECICI", G(tipli("APITimeoutError")))
c("baglanti hatasi GECICI", G(tipli("APIConnectionError")))
c("400 KALICI (vlm goruntu reddi)", not G(tipli("APIStatusError", 400)))
c("401 KALICI (anahtar)", not G(tipli("APIStatusError", 401)))
c("404 KALICI", not G(tipli("APIStatusError", 404)))
c("metinde 'bad gateway' GECICI", G(Exception("<h1>502 Bad Gateway</h1>")))
c("duz ValueError KALICI", not G(ValueError("bozuk girdi")))

print()
print("=== YENIDEN DENEME DAVRANISI ===")
class SahteTamamlama:
    def __init__(self, hatalar): self.hatalar = list(hatalar); self.cagri = 0
    def create(self, **kw):
        self.cagri += 1
        if self.hatalar:
            raise self.hatalar.pop(0)
        return "TAMAM"
class SahteIstemci:
    def __init__(self, hatalar): self.chat = type("C", (), {"completions": SahteTamamlama(hatalar)})()

def kur(hatalar):
    v = object.__new__(VLMClient)
    v.client = SahteIstemci(hatalar)
    v.model = "test"
    return v

_e = (settings.yeniden_deneme, settings.yeniden_deneme_bekleme)
try:
    settings.yeniden_deneme = 3
    settings.yeniden_deneme_bekleme = 0.001    # test hizli kossun

    v = kur([tipli("APIStatusError", 502), tipli("APIStatusError", 502)])
    t0 = time.time()
    c("iki 502'den sonra BASARILI", v._cagir_yeniden_denemeli({}) == "TAMAM")
    c("toplam 3 cagri yapildi", v.client.chat.completions.cagri == 3)
    c("deneme sayisi kaydedildi", v.son_deneme_sayisi == 2)
    c("test hizli kostu (bekleme ayardan okunuyor)", time.time() - t0 < 2.0)

    v2 = kur([tipli("APIStatusError", 400)])
    try:
        v2._cagir_yeniden_denemeli({}); ok = False
    except Exception:
        ok = True
    c("400 ANINDA firlatilir", ok)
    c("400'de TEK cagri yapilir (tekrar YOK)", v2.client.chat.completions.cagri == 1)

    v3 = kur([tipli("APIStatusError", 502)] * 9)
    try:
        v3._cagir_yeniden_denemeli({}); ok2 = False
    except Exception:
        ok2 = True
    c("butce bitince firlatilir", ok2)
    c("butce KADAR cagri (1 + 3)", v3.client.chat.completions.cagri == 4)

    settings.yeniden_deneme = 0
    v4 = kur([tipli("APIStatusError", 502)])
    try:
        v4._cagir_yeniden_denemeli({}); ok3 = False
    except Exception:
        ok3 = True
    c("KAPALI iken tek deneme (K2: eski davranis)",
      ok3 and v4.client.chat.completions.cagri == 1)
finally:
    settings.yeniden_deneme, settings.yeniden_deneme_bekleme = _e

print()
print("=== VARSAYILANLAR ===")
c("yeniden_deneme varsayilani 3", Settings.model_fields["yeniden_deneme"].default == 3)
c("bekleme varsayilani 1,5 s", Settings.model_fields["yeniden_deneme_bekleme"].default == 1.5)

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
