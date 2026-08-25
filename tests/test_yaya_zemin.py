#!/usr/bin/env python
"""Yaya yolu: YEREL nitelik slotu + capraz ON KOSUL ust siniri.

ON KAYIT: docs/on_kayit_yaya_zemin_2026-08-25.md

NEDEN: Bu sinif icin DOKUZ kol denendi ve dokuzu da reddedildi — ama dokuzunun
hepsi ayni soru tipinin varyasyonuydu ("kisi cizgiye ne kadar yakin" / "icinde
mi disinda mi"). Degisen sey hep ROI, fps veya esikti; SORU TIPI hic degismedi.
Emsal ayni depoda: pano ikili/anlamsal sorulunca 34/34 ayni cevabi verip
dejenere oldu, ayni fizik yerel ve olculebilir sorulunca MCC +0,960 verdi.

Bu test kolun MEKANIGINI korur (skorunu degil — skor on kayitli kosumdan gelir).
"""
import os, sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import tests.taban as taban  # noqa: E402
taban.taban_uygula()

from dilajan import gozlem as G, isg_kural as K  # noqa: E402
from dilajan.schema import Severity  # noqa: E402

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print(f"  ok   {ad}")
    else: k += 1; print(f"  KALAN {ad}")

print("=== SLOT: yalnizca SORU TIPI farkli olmali ===")
z, m = G.SLOT_YAYA_ZEMIN, G.SLOT_YAYA_CIZGI_MESAFE
for alan in ("roi_alani", "kapsam", "dislanan_gorus_alani",
             "gorus_esik_alani", "fps_alani", "gorev"):
    c(f"{alan} mesafe slotuyla AYNI",
      getattr(z, alan) == getattr(m, alan))
c("secenekler KAPALI ve kacisi VAR",
  z.secenekler == ["YESIL_BOYALI_YOL", "SARI_CIZGI_UZERI", "GRI_BETON",
                   "GORUNMUYOR"])
c("soru ILISKISEL degil (mesafe/uzaklik gecmiyor)",
  "mesafe" not in z.soru.lower() and "uzaklik" not in z.soru.lower())
c("soru YEREL (ayak/zemin geciyor)",
  "ayak" in z.soru.lower() and "zemin" in z.soru.lower())
c("katalogda kayitli", G.SLOT_KATALOG.get("yaya_zemin") is z)

print("=== ON KOSUL UST SINIRI (on_azami) ===")
c("varsayilan SINIRSIZ -> mevcut kurallar DEGISMEZ (K2)",
  all(kr.on_azami >= 10 ** 9 for kr in K.KURALLAR if kr.slot != "yaya_zemin"))

class Kayit:
    def __init__(self, d): self.degerler = d
    def al(self, a, v=None): return self.degerler.get(a, v)

zemin_kural = [kr for kr in K.KURALLAR if kr.slot == "yaya_zemin"][0]
c("kod ISG sinif etiketi (metrik bunu okur)",
  zemin_kural.kod == "Safe_Walkway_Violation")
c("kapi: makinede KIMSE YOKKEN gecerli",
  zemin_kural.on_kosul_saglandi(Kayit({"makine_basinda_kisi": 0})) is True)
c("kapi: makinede 1 kisi VARSA kural SUSAR",
  zemin_kural.on_kosul_saglandi(Kayit({"makine_basinda_kisi": 1})) is False)
c("kapi: on slot OLCULEMEDIYSE kural SUSAR (fail-closed)",
  zemin_kural.on_kosul_saglandi(Kayit({})) is False)

print("=== KURAL DAVRANISI ===")
class Ayar: pass
ay = Ayar()
c("GRI_BETON + kapi acik -> IHLAL",
  zemin_kural.degerlendir(Kayit({"yaya_zemin": "GRI_BETON",
                                 "makine_basinda_kisi": 0}), ay) is not None)
c("YESIL_BOYALI_YOL -> ihlal YOK",
  zemin_kural.degerlendir(Kayit({"yaya_zemin": "YESIL_BOYALI_YOL",
                                 "makine_basinda_kisi": 0}), ay) is None)
c("GORUNMUYOR -> ihlal YOK (olculemedi != ihlal)",
  zemin_kural.degerlendir(Kayit({"yaya_zemin": "GORUNMUYOR",
                                 "makine_basinda_kisi": 0}), ay) is None)
c("GRI_BETON ama makinede kisi VAR -> ihlal YOK (capraz kapi)",
  zemin_kural.degerlendir(Kayit({"yaya_zemin": "GRI_BETON",
                                 "makine_basinda_kisi": 2}), ay) is None)
olay = zemin_kural.degerlendir(Kayit({"yaya_zemin": "GRI_BETON",
                                      "makine_basinda_kisi": 0}), ay)
c("metin OLCULENI anlatir (beton geciyor)", "beton" in olay["metin"].lower())
c("metin gercek Turkce (kaliplar bununla eslesir)",
  "ı" in olay["metin"] or "ş" in olay["metin"] or "İ" in olay["metin"])

print("=== ILISKISEL KOL SILINMEDI (eslesmis karsilastirma sarti) ===")
c("mesafe kurali hala katalogda",
  any(kr.slot == "yaya_cizgi_mesafe" for kr in K.KURALLAR))
c("iki kural AYNI kodu paylasir",
  len([kr for kr in K.KURALLAR if kr.kod == "Safe_Walkway_Violation"]) == 2)

print("=== K2: SEVK YAPILANDIRMASI DEGISMEDI ===")
class Sevk: isg_slotlari = "catal_kasa_sayisi,makine_basinda_yelek,pano_koyuluk_0_10"
c("sevk ayarinda yol slotu SORULMAZ",
  not any("yaya" in a for a in K.gerekli_slotlar(Sevk())))
c("yaya_zemin SINIF varsayilaninda kapali",
  "yaya" not in (taban.sinif_varsayilani("isg_slotlari") or ""))

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
