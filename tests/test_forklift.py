#!/usr/bin/env python
"""D40 — forklift asiri yuk dedektoru (IKI YOL) regresyon kilidi.

    python tests/test_forklift.py       # cikis kodu 0 = hepsi gecti

NEDEN BU DEDEKTOR VAR (olculdu 2026-08-19, 50 klip):
    ANLAMSAL soru  "asiri yuk var mi?"  -> MCC +0,000  DEJENERE (50/50 "gorunmuyor")
    ISLEMSEL soru  "kac kasa var?"      -> MCC +0,762  dogruluk 0,880
    GEOMETRI (perspektif duzeltmeli)    -> MCC +0,641  dogruluk 0,820
    GEOMETRI (perspektifsiz ham oran)   -> MCC +0,280  <- duzeltme SART

Kaynak makale (Onal & Dandil 2024, Data in Brief 56:110756): "2 blocks or less"
guvenli, "3 blocks or more" ihlal.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from dilajan import forklift as F  # noqa: E402
from dilajan.config import Settings  # noqa: E402

_gecti = 0
_kaldi = 0


def check(ad, kosul, ayrinti=""):
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print(f"  ok   {ad}")
    else:
        _kaldi += 1
        print(f"  FAIL {ad}  {ayrinti}")


BOYUT = (480, 270)


def kare(ts, kasa_h=60, kasa_w=70, y_alt=200, x_sol=200):
    """Turuncu bir istif dikdortgeni olan sentetik kare."""
    a = np.full((BOYUT[1], BOYUT[0], 3), 120, dtype=np.uint8)   # gri zemin
    y1, y2 = max(0, y_alt - kasa_h), y_alt
    x1, x2 = x_sol, min(BOYUT[0], x_sol + kasa_w)
    a[y1:y2, x1:x2] = (210, 110, 40)      # turuncu kasa
    b = io.BytesIO()
    Image.fromarray(a).save(b, format="JPEG", quality=95)
    return (ts, b.getvalue())


print("=== VLM cevabi -> kasa sayisi ===")
for c, bek in (("3", 3), ("2", 2), ("0", 0), ("6+", 6),
               (" 4 ", 4), ("GORUNMUYOR", None), ("", None),
               ("__HATA__ X", None), ("Karede 2 kasa var, toplam 3", 3)):
    check(f"{c!r} -> {bek}", F._sayiya_cevir(c) == bek, f"-> {F._sayiya_cevir(c)}")

print("\n=== turuncu maske + sinir kutusu ===")
k = kare("00:00", kasa_h=60, kasa_w=70, y_alt=200, x_sol=200)
o = F.istif_olcum([k])
check("istif bulundu", o is not None)
if o:
    check("boy ~60", abs(o["h"] - 60) <= 3, f"-> {o['h']}")
    check("en ~70", abs(o["w"] - 70) <= 3, f"-> {o['w']}")
    check("alt kenar ~200", abs(o["y_alt"] - 200) <= 3, f"-> {o['y_alt']}")

print("\n=== turuncu YOKSA olcum None (K3) ===")
bos = np.full((BOYUT[1], BOYUT[0], 3), 120, dtype=np.uint8)
b = io.BytesIO(); Image.fromarray(bos).save(b, format="JPEG", quality=95)
check("duz gri kare -> None", F.istif_olcum([("00:00", b.getvalue())]) is None)
check("bozuk JPEG -> None", F.istif_olcum([("00:00", b"bozuk")]) is None)
check("bos liste -> None", F.istif_olcum([]) is None)

print("\n=== PERSPEKTIF: uzaktaki buyuk istif, yakindaki kucuk istifle ayni olmali ===")
# Ayni FIZIKSEL istif: uzakta (y_alt kucuk) kucuk gorunur, yakinda (y_alt buyuk) buyuk.
yakin = F.istif_olcum([kare("00:00", kasa_h=100, kasa_w=100, y_alt=250)])
uzak = F.istif_olcum([kare("00:00", kasa_h=40, kasa_w=40, y_alt=100)])
fy = F.perspektif_boy(yakin, 0.0)
fu = F.perspektif_boy(uzak, 0.0)
check("perspektif duzeltmesi ikisini YAKINLASTIRIYOR",
      fy is not None and fu is not None and abs(fy - fu) < 0.05,
      f"-> yakin={fy:.3f} uzak={fu:.3f}")
# ham oran ikisinde de ayni (kare) — asil kazanc BOY/UZAKLIK normalizasyonunda
check("ufuk kestirimi calisiyor",
      isinstance(F.ufuk_kestir([yakin, uzak] * 5), float))

print("\n=== esik karari ===")
alcak = [kare(f"00:0{i}", kasa_h=40, kasa_w=100, y_alt=250) for i in range(3)]
yuksek = [kare(f"00:0{i}", kasa_h=180, kasa_w=100, y_alt=250) for i in range(3)]
check("alcak istif -> asiri DEGIL",
      F.asiri_yuk_geometri(alcak, y_ufuk=0.0, esik=0.5) is False)
check("yuksek istif -> ASIRI",
      F.asiri_yuk_geometri(yuksek, y_ufuk=0.0, esik=0.5) is True)
check("istif yoksa -> None (K3)",
      F.asiri_yuk_geometri([("00:00", b.getvalue())], y_ufuk=0.0) is None)

print("\n=== K2: bayrak KAPALI iken varsayilanlar ===")
s = Settings()
check("varsayilan forklift_yuk BOS", s.forklift_yuk == "", f"-> {s.forklift_yuk!r}")
check("varsayilan esik 3 (kaynak makale)", s.forklift_esik == 3)
check("kalibrasyon sabitleri ayarda", hasattr(s, "forklift_y_ufuk")
      and hasattr(s, "forklift_f_pers_esik"))

print("\n=== asiri_yuk dispatcher ===")


class SahteIstemci:
    def __init__(self, cevap):
        self.cevap = cevap

    def analyze_frames(self, *a, **k):
        return self.cevap


check("vlm 3 kasa -> ihlal",
      F.asiri_yuk(yuksek, yontem="vlm", istemci=SahteIstemci("3")) is not None)
check("vlm 2 kasa -> ihlal DEGIL",
      F.asiri_yuk(yuksek, yontem="vlm", istemci=SahteIstemci("2")) is None)
check("vlm GORUNMUYOR -> None (K3)",
      F.asiri_yuk(yuksek, yontem="vlm", istemci=SahteIstemci("GORUNMUYOR")) is None)
check("geometri yolu istemcisiz calisir",
      F.asiri_yuk(yuksek, yontem="geometri", y_ufuk=0.0,
                  f_pers_esik=0.5) is not None)
r = F.asiri_yuk(yuksek, yontem="ikisi", istemci=SahteIstemci("4"),
                y_ufuk=0.0, f_pers_esik=0.5)
check("'ikisi': ikisi de ihlal derse ihlal", r is not None)
check("'ikisi': VLM ihlal demezse ihlal YOK",
      F.asiri_yuk(yuksek, yontem="ikisi", istemci=SahteIstemci("2"),
                  y_ufuk=0.0, f_pers_esik=0.5) is None)
check("'ikisi': geometri ihlal demezse ihlal YOK",
      F.asiri_yuk(alcak, yontem="ikisi", istemci=SahteIstemci("4"),
                  y_ufuk=0.0, f_pers_esik=0.5) is None)
if r:
    check("olay kasa sayisini tasiyor", r.get("vlm_kasa") == 4, f"-> {r}")

print("\n=== istemci YOKKEN vlm yolu cokmez (K3) ===")
check("vlm yolu istemcisiz -> None",
      F.asiri_yuk(yuksek, yontem="vlm", istemci=None) is None)

print(f"\ngecen={_gecti}  kalan={_kaldi}")
sys.exit(1 if _kaldi else 0)
