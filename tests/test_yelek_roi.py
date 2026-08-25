#!/usr/bin/env python
"""Yelek slotunun ROI'ye tasinabilirligi — mekanik + K2.

ON KAYIT: docs/on_kayit_yelek_roi_2026-08-25.md

NEDEN: `Unauthorized_Intervention`'daki alti kacirmanin B grubunda model
"yelek VAR" derken %92-99,7 EMIN — ve bakti gi kiside gercekten yelek var.
Sorun HANGI KISIYE baktigi: bir kalibrasyon degil REFERANS sorunu.
Kural zaten "makinenin/panonun BASINDA duran kisi" diyor ve `panel_roi_vlm`
makine basini ZATEN tanimliyor. Soru o kirpmada sorulursa referans YAPISAL
olarak tekleser.

Kisi-basina kirpma alternatifi OLCULDU ve ACILMADI: genis plan kliplerinde
CPU dedektor de kimseyi bulamiyor (2 klipte 0 kisi), kalabalik kliplerde ise
11-13 kisi arasindan secmek belirsizligi modelden alip bulusa tasir.
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

print("=== K2: VARSAYILAN BOS -> SEVK DAVRANISI BIREBIR ===")
c("yelek_roi_vlm SINIF varsayilani BOS",
  taban.sinif_varsayilani("yelek_roi_vlm") == "")
c("yelek_on_roi_vlm SINIF varsayilani BOS",
  taban.sinif_varsayilani("yelek_on_roi_vlm") == "")

class Bos: pass
c("BOS ayarda yelek slotu TAM KARE", G.roi_coz(G.SLOT_YELEK, Bos()) == "")
c("BOS ayarda on kosul slotu TAM KARE", G.roi_coz(G.SLOT_MAKINE_KISI, Bos()) == "")

print("=== IKI KOL AYRI ALANDAN OKUR (B1 / B2 ayrilabilsin) ===")
c("yelek ve on kosul FARKLI alan okur",
  G.SLOT_YELEK.roi_alani != G.SLOT_MAKINE_KISI.roi_alani)
c("yelek slotu panel alanini DOGRUDAN okumaz (kol ayri acilabilsin)",
  G.SLOT_YELEK.roi_alani != "panel_roi_vlm")

class B1:                       # yalniz yelek tasindi
    yelek_roi_vlm = "0.00,0.47,0.29,0.81"
    yelek_on_roi_vlm = ""
c("B1: yelek ROI'de", G.roi_coz(G.SLOT_YELEK, B1()) == "0.00,0.47,0.29,0.81")
c("B1: on kosul TAM KAREDE", G.roi_coz(G.SLOT_MAKINE_KISI, B1()) == "")

class B2(B1):                   # ikisi birden
    yelek_on_roi_vlm = "0.00,0.47,0.29,0.81"
c("B2: on kosul da ROI'de",
  G.roi_coz(G.SLOT_MAKINE_KISI, B2()) == "0.00,0.47,0.29,0.81")

print("=== GRUPLAMA: ayni ROI+kapsam TEK video (K4) ===")
uretilen = []
def video_uret(roi, kapsam="segment", fps=None):
    uretilen.append((roi, kapsam)); return b"v"
class Oturum:
    hazir = True
    istemci = None
    def sor(self, soru, guided_choice=None, **kw): return "1"
class Ist:
    def gorev(self, _x): return self
    def video_oturumu(self, video, system=""): return Oturum()

G.slotlari_doldur_bolgeli(Ist(), [G.SLOT_YELEK, G.SLOT_MAKINE_KISI],
                          video_uret, B2())
c("B2: iki slot AYNI ROI -> TEK video", len(uretilen) == 1)
uretilen.clear()
G.slotlari_doldur_bolgeli(Ist(), [G.SLOT_YELEK, G.SLOT_MAKINE_KISI],
                          video_uret, B1())
c("B1: farkli ROI -> IKI video", len(uretilen) == 2)
uretilen.clear()
G.slotlari_doldur_bolgeli(Ist(), [G.SLOT_YELEK, G.SLOT_MAKINE_KISI],
                          video_uret, Bos())
c("KAPALI: yine TEK video (sevk davranisi degismedi)", len(uretilen) == 1)

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
