"""GORUS MUHAFIZI — slot YALNIZCA dogru kamerada sorulur.

NEDEN VAR (olculdu, 96 klip): yaya yolu slotu forklift kliplerinin 49/50'sinde
atesliyordu — yaya yolu cizgisi sorusunun ANLAMSIZ oldugu bir kamerada.
Kamera 14 benzerligi min 0,842 · kamera 9 maks 0,575 -> temiz esik 0,708.

KRITIK KISIT — muhafiz bir SAHNE filtresidir, ETIKET tahmincisi DEGIL.
Gorus imzasinin cift ICINDE ihlal/normal ayirma gucu olculdu:
    yol   cifti 0,385 · pano cifti 0,275  -> muhafiz GUVENLI
    yetki cifti 0,833                     -> muhafiz YASAK
Bu yuzden muhafiz YALNIZCA yol slotuna baglidir. Yelek slotuna baglanmasi
reddedilen geofence yaklasiminin ta kendisi olurdu.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan import gozlem as G
from tests.taban import sinif_varsayilani

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print("  ok  ", ad)
    else: k += 1; print("  FAIL", ad)

class Ayar:
    yol_dislanan_gorus = ",".join(["1.0"] * 144)
    yol_gorus_esik = 0.708
    panel_roi_vlm = ""
    yol_roi_vlm = ""

print("=== HANGI SLOTLAR MUHAFIZLI ===")
c("yol slotu muhafizli", G.SLOT_YAYA_CIZGI_MESAFE.dislanan_gorus_alani == "yol_dislanan_gorus")
c("YELEK slotu muhafizSIZ (etiket sizintisi 0,833)",
  not getattr(G.SLOT_YELEK, "dislanan_gorus_alani", ""))
c("on kosul slotu muhafizSIZ",
  not getattr(G.SLOT_MAKINE_KISI, "dislanan_gorus_alani", ""))
c("pano slotu muhafizSIZ", not getattr(G.SLOT_PANO_KOYULUK, "dislanan_gorus_alani", ""))
c("forklift slotu muhafizSIZ", not getattr(G.SLOT_CATAL_KASA, "dislanan_gorus_alani", ""))

print()
print("=== K2: MUHAFIZ KAPALI IKEN HER SEY SORULUR ===")
class Bos: yol_dislanan_gorus = ""; yol_gorus_esik = 0.708
c("bos imza -> slot sorulur", G.gorus_uygun_mu(G.SLOT_YAYA_CIZGI_MESAFE, Bos(), [("00:00", b"x")]))
c("varsayilan imza BOS (K2)", sinif_varsayilani("yol_dislanan_gorus") == "")
c("varsayilan esik 0,708", abs(sinif_varsayilani("yol_gorus_esik") - 0.708) < 1e-9)

print()
print("=== KARE YOKSA MUHAFIZ ENGELLEMEZ (K3) ===")
c("frames=None -> sorulur", G.gorus_uygun_mu(G.SLOT_YAYA_CIZGI_MESAFE, Ayar(), None))
c("frames=[] -> sorulur", G.gorus_uygun_mu(G.SLOT_YAYA_CIZGI_MESAFE, Ayar(), []))

print()
print("=== MUHAFIZSIZ SLOT AYARDAN ETKILENMEZ ===")
c("forklift slotu her sahnede sorulur",
  G.gorus_uygun_mu(G.SLOT_CATAL_KASA, Ayar(), [("00:00", b"x")]))

print()
print("=== ATLANAN, HATA DEGILDIR ===")
kayit = G.GozlemKaydi()
c("GozlemKaydi.atlanan alani var", hasattr(kayit, "atlanan"))
c("atlanan baslangicta bos", kayit.atlanan == {})
c("atlanan slot DEGER uretmez", kayit.al("yaya_cizgi_mesafe") is None)

print()
print("=== BOLGELI DOLDURMADA ATLAMA ===")
# Goruntu matematigi test_pano.py'de olculur; burada KABLOLAMA test edilir:
# `gorus_uyuyor` True derse slot ATLANMALI, cagri YAPILMAMALI.
import dilajan.pano as _pano
_asil = _pano.gorus_uyuyor
_pano.gorus_uyuyor = lambda frames, imza, esik=0.6: True   # "bu DISLANAN kamera"
class SahteOturum:
    hazir = True
    def __init__(self): self.istemci = None
    def sor(self, *a, **kw): return "5"
class SahteIstemci:
    def __init__(self): self.acilan = []
    def gorev(self, g_): return self
    def video_oturumu(self, video, system=""): self.acilan.append(video); return SahteOturum()
ist = SahteIstemci()
kayit2 = G.slotlari_doldur_bolgeli(
    ist, [G.SLOT_YAYA_CIZGI_MESAFE, G.SLOT_CATAL_KASA],
    lambda roi, kapsam="segment": f"V[{roi}|{kapsam}]", Ayar(),
    frames=[("00:00", b"x")])
c("muhafizli slot ATLANDI", "yaya_cizgi_mesafe" in kayit2.atlanan)
c("muhafizsiz slot DOLDU", kayit2.al("catal_kasa_sayisi") == 5)
c("atlanan slot icin oturum ACILMADI (bosa cagri yok)", len(ist.acilan) == 1)
c("atlanan HATA olarak sayilmaz", "yaya_cizgi_mesafe" not in kayit2.hatalar)

_pano.gorus_uyuyor = lambda frames, imza, esik=0.6: False  # "bu DOGRU kamera"
ist2 = SahteIstemci()
kayit3 = G.slotlari_doldur_bolgeli(
    ist2, [G.SLOT_YAYA_CIZGI_MESAFE, G.SLOT_CATAL_KASA],
    lambda roi, kapsam="segment": f"V[{roi}|{kapsam}]", Ayar(),
    frames=[("00:00", b"x")])
c("dogru kamerada slot SORULUR", kayit3.al("yaya_cizgi_mesafe") == 5)
c("dogru kamerada atlama YOK", kayit3.atlanan == {})
_pano.gorus_uyuyor = _asil

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
