#!/usr/bin/env python
"""ALAN KILIDI — gozlem duzlemi yalnizca KALIBRE TESISTE calisir.

OLCULDU (2026-08-25, 100 alan disi klip / iSafetyBench, CC BY-NC-SA,
YALNIZCA DEGERLENDIRME):
Tesise KALIBRE ISG kurallari alan disinda GURULTU uretiyor:
  normal kliplerin 22/50'sinde YALNIZCA ISG kurali atesliyor
  tehlike tespitine katkisi SIFIR (recall her iki kipte de 0,900)
  normal kliplerde (26/50) tehlike kliplerinden (13/50) DAHA SIK atesliyor
Kilit ACIKKEN:
  kendi setimiz : 197/197 gecti, uc matris BIREBIR korundu (K2)
  alan disi     : ISG atesleme 0,390 -> 0,020 · normal FP 0,540 -> 0,120
                  MCC +0,401 -> +0,780

KAPSAMA GARANTISI SART: kor kumeleme ile uretilen imzalar FORKLIFT
KAMERASININ TAMAMINI disarida birakmisti (50/50) ve forklift kuralini
+0,881'den +0,000'a dusurmustu. Imzalar artik SINIF BASINA uretilir ve
her sinifin gecis orani dogrulanir.

Kilit bir ETIKET kapisi DEGIL ALAN kapisidir: "bu bizim tesisimiz mi" diye
sorar, "bu hangi sinif" diye degil. Kalibre tesiste TUM siniflar gecer.
"""
import os, sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import tests.taban as taban  # noqa: E402
taban.taban_uygula()

from dilajan import gozlem as G  # noqa: E402

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print(f"  ok   {ad}")
    else: k += 1; print(f"  KALAN {ad}")

KARE = [("00:00", b"x"), ("00:01", b"y")]

print("=== K2: IMZA BOS -> KILIT YOK, ESKI DAVRANIS ===")
c("isg_gorus_imza SINIF varsayilani BOS",
  taban.sinif_varsayilani("isg_gorus_imza") == "")
c("isg_gorus_esik SINIF varsayilani 0,708",
  abs(taban.sinif_varsayilani("isg_gorus_esik") - 0.708) < 1e-9)

class Bos: pass
for slot in (G.SLOT_YELEK, G.SLOT_PANO_KOYULUK, G.SLOT_CATAL_KASA):
    c("imza BOS iken %s SORULUR" % slot.ad,
      G.gorus_uygun_mu(slot, Bos(), KARE) is True)

print("=== KILIT: UYMAYAN SAHNEDE SLOT SORULMAZ ===")
class Kilitli:
    isg_gorus_imza = ",".join(["1.0"] * 144)   # asla uymayacak referans
    isg_gorus_esik = 0.99
for slot in (G.SLOT_YELEK, G.SLOT_PANO_KOYULUK, G.SLOT_CATAL_KASA):
    c("alan disi sahnede %s SORULMAZ" % slot.ad,
      G.gorus_uygun_mu(slot, Kilitli(), KARE) is False)

print("=== KARE YOKSA ENGELLEME (K3 fail-open) ===")
c("frames bos -> kilit uygulanmaz",
  G.gorus_uygun_mu(G.SLOT_YELEK, Kilitli(), None) is True)

print("=== COK IMZA: ';' ile ayrik, HERHANGI BIRI yeterli ===")
import inspect
src = inspect.getsource(G.gorus_uygun_mu)
c("kod ';' ile boluyor", 'ger.split(";")' in src)
c("kod 'any(...)' ile herhangi birine bakiyor",
  "any(gorus_uyuyor" in src)

print("=== KILIT, DISLAMA KAPISINDAN BAGIMSIZ ===")
# DOCSTRING de bu adlari iceriyor -> GOVDEYE bak, tum kaynaga degil.
_govde = src.split('"""', 2)[-1]
c("alan kilidi dislama kapisindan ONCE calisir (govdede)",
  _govde.index("isg_gorus_imza") < _govde.index('getattr(slot, "dislanan_gorus_alani"'))

print("=== URETILMIS IMZA DOSYASI ve KAPSAMA ===")
imza_yol = os.path.join(KOK, "benchmark", "results", "tesis_imzasi.txt")
if os.path.exists(imza_yol):
    im = [x for x in open(imza_yol).read().split(";") if x.strip()]
    c("imza dosyasi COK IMZA iceriyor (>=2)", len(im) >= 2)
    c("her imza 144 boyutlu", all(len(x.split(",")) == 144 for x in im))
else:
    print("  --   imza dosyasi yok (scripts/tesis_imzasi_uret.py ile uretilir)")

print("=== KUNYE: kilit davranisi degistirir -> kayitli olmali ===")
kn = open(os.path.join(KOK, "benchmark", "eval_clips.py"), encoding="utf-8").read()
c("kunyede isg_gorus_imza_uzunluk var", '"isg_gorus_imza_uzunluk"' in kn)
c("kunyede isg_gorus_esik var", '"isg_gorus_esik"' in kn)

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
