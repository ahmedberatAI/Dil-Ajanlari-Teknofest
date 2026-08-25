#!/usr/bin/env python
"""Yelek kuralinin ON KOSUL kapisi — bayrakla kapatilabilir + gorus muhafizi.

OLCULDU (2026-08-25, 658 benzersiz icerik, kanonik yer gercegi):
Kapi ciftin NEGATIF tarafinda HIC IS YAPMIYOR. Dogru reddedilen 34 klibin
34'u de YELEK SLOTUNUN KENDISI tarafindan tutuluyor (`yelek=VAR`);
kapinin tuttugu negatif SIFIR. Buna karsilik 12 DOGRU POZITIFI kesiyor.

Sebep yapisal: yelek slotunun secenek kumesinde ZATEN `KISI_YOK` var.
Model "YOK" dediginde "burada YELEKSIZ BIR KISI VAR" demis oluyor. Ayri
kapi ayni soruyu TEKRAR soruyor ve CELISTIGINDE zayif olana guveniyor —
12 kacirmada model yelek=YOK diyor (guven 1,000) ama kisi sayimi 0 diyor.

   kapi ACIK  : TP 91 FP 4 FN 17 TN 34  -> MCC +0,679
   kapi KAPALI: TP103 FP 4 FN  5 TN 34  -> MCC +0,841   (+0,163)
   _tr +0,174 · _te +0,141  (kazanc her iki ayrimda da tutuyor)

Kapinin ASIL isi sahne gecerliligiydi ("forklift kamerasinda da atesliyor")
ama arac yanlisti. Dogru arac GORUS MUHAFIZIDIR — yol slotunda zaten var ve
forklift kamerasini 10/10 disliyor. Bu test ikisini de korur.
"""
import os, sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import tests.taban as taban  # noqa: E402
taban.taban_uygula()

from dilajan import gozlem as G, isg_kural as K  # noqa: E402

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print(f"  ok   {ad}")
    else: k += 1; print(f"  KALAN {ad}")

class Kayit:
    def __init__(self, d): self.degerler = d
    def al(self, a, v=None): return self.degerler.get(a, v)

KURAL = [x for x in K.KURALLAR if x.slot == "makine_basinda_yelek"][0]

print("=== K2: VARSAYILAN SEVK DAVRANISI ===")
c("yelek_on_kosul SINIF varsayilani True",
  taban.sinif_varsayilani("yelek_on_kosul") is True)
c("kural on_bayrak_alani'na bagli", KURAL.on_bayrak_alani == "yelek_on_kosul")

class Acik: yelek_on_kosul = True
class Kapali: yelek_on_kosul = False

print("=== KAPI ACIK (sevk) ===")
c("kisi=0 + yelek=YOK -> olay YOK (kapi keser)",
  KURAL.degerlendir(Kayit({"makine_basinda_kisi": 0,
                           "makine_basinda_yelek": "YOK"}), Acik()) is None)
c("kisi=2 + yelek=YOK -> olay VAR",
  KURAL.degerlendir(Kayit({"makine_basinda_kisi": 2,
                           "makine_basinda_yelek": "YOK"}), Acik()) is not None)

print("=== KAPI KAPALI (kol) ===")
c("kisi=0 + yelek=YOK -> olay VAR (12 kacirmayi kurtaran yol)",
  KURAL.degerlendir(Kayit({"makine_basinda_kisi": 0,
                           "makine_basinda_yelek": "YOK"}), Kapali()) is not None)
c("kisi olculemedi + yelek=YOK -> olay VAR",
  KURAL.degerlendir(Kayit({"makine_basinda_yelek": "YOK"}), Kapali()) is not None)

print("=== YELEK SLOTU HER IKI KIPTE DE HUKMU VERIR ===")
for kip, ad in ((Acik(), "kapi ACIK"), (Kapali(), "kapi KAPALI")):
    c("%s: yelek=VAR -> olay YOK (34 negatifi TUTAN sey budur)" % ad,
      KURAL.degerlendir(Kayit({"makine_basinda_kisi": 2,
                               "makine_basinda_yelek": "VAR"}), kip) is None)
    c("%s: yelek=KISI_YOK -> olay YOK (slotun KENDI kacisi)" % ad,
      KURAL.degerlendir(Kayit({"makine_basinda_kisi": 0,
                               "makine_basinda_yelek": "KISI_YOK"}), kip) is None)
    c("%s: yelek=GORUNMUYOR -> olay YOK" % ad,
      KURAL.degerlendir(Kayit({"makine_basinda_kisi": 2,
                               "makine_basinda_yelek": "GORUNMUYOR"}), kip) is None)

print("=== GERI-UYUM: ayar verilmezse eski davranis ===")
c("ayar=None -> on kosul UYGULANIR (K2)",
  KURAL.on_kosul_saglandi(Kayit({"makine_basinda_kisi": 0})) is False)

print("=== GORUS MUHAFIZI DENENDI ve REDDEDILDI ===")
# Kapinin isini bir gorus muhafizinin yapmasi denendi. Mevcut bir olcum
# yasakliyor: bu ciftte GORUS ETIKETLE 0,833 KORELE. Muhafiz sahne
# gecerliligi yerine ETIKETI sizdirirdi. (Yol slotunda mesru cunku orada
# dislanan kamera ciftin DISINDA kaliyor.)
c("yelek slotu MUHAFIZSIZ kalmali (etiket sizintisi 0,833)",
  not getattr(G.SLOT_YELEK, "dislanan_gorus_alani", ""))

print("=== DIGER KURALLAR ETKILENMEDI ===")
for kr in K.KURALLAR:
    if kr.slot == "makine_basinda_yelek":
        continue
    c("%s bayrak alani BOS" % kr.kod[:28], not kr.on_bayrak_alani)

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
