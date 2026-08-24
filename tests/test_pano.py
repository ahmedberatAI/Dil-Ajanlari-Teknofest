#!/usr/bin/env python
"""D39-E — pano kapagi dedektoru + D39-D `kkd_available` onarimi.

    python tests/test_pano.py       # cikis kodu 0 = hepsi gecti

NEDEN BU DEDEKTOR VAR (olculdu 2026-08-18, docs/pano_dedektoru_2026-08-18.md):
    VLM tam karede  0/12 · panoya KIRPILMIS halde 1/12 · Qwen3.8-27B 99'da 0
    deterministik parlaklik olcumu -> %93,2 (gercek guvenlik gorevi, bilesik kural)

NEDEN KURAL BILESIK (bu dosyanin en onemli kilidi):
    `Authorized_Intervention` kliplerinde pano da FIZIKSEL OLARAK aciktir.
    Kisi terimi olmadan yanlis pozitif 1'den 21'e cikiyor.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from dilajan import algila_rtdetr, detector, pano  # noqa: E402
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


ROI = "0.08,0.55,0.21,0.73"          # bizim tesiste olculmus pano kutusu
BOYUT = (320, 240)


def kare(ts, zemin=150, roi_parlaklik=None):
    """Duz gri kare; istege bagli olarak ROI bolgesi FARKLI parlaklikta."""
    a = np.full((BOYUT[1], BOYUT[0]), zemin, dtype=np.uint8)
    if roi_parlaklik is not None:
        x1, y1 = int(0.08 * BOYUT[0]), int(0.55 * BOYUT[1])
        x2, y2 = int(0.21 * BOYUT[0]), int(0.73 * BOYUT[1])
        a[y1:y2, x1:x2] = roi_parlaklik
    b = io.BytesIO()
    Image.fromarray(a, mode="L").convert("RGB").save(b, format="JPEG", quality=95)
    return (ts, b.getvalue())


def sahte_kisi(kutular):
    """`algila_rtdetr.kisileri_bul` yerine sabit tespit koyar (GPU'suz test)."""
    def _f(frames, conf=0.35):
        return [[{"kutu": list(k), "guven": 0.9} for k in kutular] for _ in frames]
    return _f


print("=== ROI ayristirma (gecersiz girdi HICBIR ZAMAN olay uretmemeli) ===")
for s in ("", "   ", "0.1,0.2", "a,b,c,d", "0.5,0.2,0.1,0.9", "0.1,0.2,0.3",
          "-0.1,0,0.5,0.5", "0,0,1.5,1"):
    check(f"gecersiz ROI reddedildi: {s!r}", pano.roi_ayristir(s) is None)
check("gecerli ROI ayristi", pano.roi_ayristir(ROI) is not None)

print("\n=== K2: bayrak KAPALI iken hicbir sey calismaz ===")
zifiri = [kare("00:00", roi_parlaklik=5)]
check("panel_roi bos -> None", pano.pano_durumu(zifiri, "") is None)
check("panel_roi bosluk -> None", pano.pano_durumu(zifiri, "   ") is None)
_s = Settings()
check("varsayilan panel_roi BOS (K2)", _s.panel_roi == "", f"-> {_s.panel_roi!r}")
check("varsayilan panel_kisi_kontrolu ACIK", _s.panel_kisi_kontrolu is True)

print("\n=== parlaklik kurali ===")
kapali = [kare(f"00:0{i}", roi_parlaklik=200) for i in range(3)]
check("KAPALI pano olay uretmez",
      pano.pano_durumu(kapali, ROI, kisi_kontrolu=False) is None)

acik = [kare(f"00:0{i}", roi_parlaklik=30) for i in range(3)]
r = pano.pano_durumu(acik, ROI, kisi_kontrolu=False)
check("ACIK pano olay uretir", r is not None)
if r:
    check("luma esigin altinda", r["luma"] < r["esik"], f"-> {r['luma']} < {r['esik']}")
    check("kare sayisi dogru", r["n_kare"] == 3, f"-> {r['n_kare']}")

check("esik sinirinda (88 > 87,6) KAPALI sayilir",
      pano.pano_durumu([kare("00:00", roi_parlaklik=88)], ROI,
                       luma_esik=87.6, kisi_kontrolu=False) is None)

print("\n=== MINIMUM alinir, ortalama DEGIL (pano klip ICINDE acilabilir) ===")
# Olculmus gerekce: `2_te12` orta karede KAPALI gorunuyordu; ortalama alan kural kacirirdi.
karisik = [kare("00:00", roi_parlaklik=200), kare("00:01", roi_parlaklik=200),
           kare("00:02", roi_parlaklik=20), kare("00:03", roi_parlaklik=200)]
r = pano.pano_durumu(karisik, ROI, kisi_kontrolu=False)
check("tek karede acik olmasi YETER", r is not None)
if r:
    check("olay EN KARANLIK kareye damgalanir", r["time"] == "00:02", f"-> {r['time']}")

print("\n=== KISI TERIMI — bu dedektorun asil kilidi ===")
# ROI 320x240'ta ~(25,132)-(67,175)
_asil = algila_rtdetr.kisileri_bul
try:
    algila_rtdetr.kisileri_bul = sahte_kisi([(20.0, 120.0, 70.0, 200.0)])
    check("pano acik AMA basinda kisi VAR -> olay YOK (yetkili bakim)",
          pano.pano_durumu(acik, ROI, kisi_kontrolu=True) is None)

    algila_rtdetr.kisileri_bul = sahte_kisi([(250.0, 10.0, 300.0, 90.0)])
    r = pano.pano_durumu(acik, ROI, kisi_kontrolu=True)
    check("UZAKTAKI kisi olayi engellemez", r is not None)
    if r:
        check("kisi_vardi=False rapor edilir", r["kisi_vardi"] is False)

    algila_rtdetr.kisileri_bul = sahte_kisi([])
    check("K3: kisi dedektoru BOS donerse parlaklik karari ayakta",
          pano.pano_durumu(acik, ROI, kisi_kontrolu=True) is not None)

    def _patlayan(frames, conf=0.35):
        raise RuntimeError("dedektor coktu")
    algila_rtdetr.kisileri_bul = _patlayan
    check("K3: kisi dedektoru PATLARSA olay uretilmez (yanlis alarm yerine sessizlik)",
          pano.pano_durumu(acik, ROI, kisi_kontrolu=True) is None)
finally:
    algila_rtdetr.kisileri_bul = _asil

print()
print("=== GORUS KILIDI (197 klipte olculdu: FP 43 -> 5) ===")
# Sabit ROI yalnizca kalibre edildigi kamera gorusunde anlamlidir. Kilit yokken
# kural ayni tesisin BASKA cercevesinde bosa atesliyordu: Safe_Walkway_Violation
# 17/25, Normal/Safe_Walkway 12/23 -> kesinlik 0,259. Kilitle 0,750.
imza_acik = pano.gorus_imzasi(acik)
check("imza uretilebiliyor", bool(imza_acik))
check("bos imza -> kilit YOK (geriye uyumlu)", pano.gorus_uyuyor(acik, ""))
check("kendi imzasi ile eslesiyor", pano.gorus_uyuyor(acik, imza_acik))

# YANLIS KAMERA GORUSU: ROI'si yine karanlik AMA sahne YAPISI bambaska.
# (Duz zemin + ayni yerde koyu leke YETMEZ — kilit YAPIYA bakar, parlakliga degil;
#  iki duz sahne 16x9'a indirgenince ayni yapiya sahiptir. Bu, kilidin dogru
#  davranisidir: farkli olan sey yapi olmali.)
def yanlis_gorus(ts):
    a = np.full((BOYUT[1], BOYUT[0]), 30, dtype=np.uint8)
    a[:, BOYUT[0] // 2:] = 220                 # sag yari parlak — pano sahnesinde yok
    a[: BOYUT[1] // 3, :] = 200                # ust bant parlak
    x1, y1 = int(0.08 * BOYUT[0]), int(0.55 * BOYUT[1])
    x2, y2 = int(0.21 * BOYUT[0]), int(0.73 * BOYUT[1])
    a[y1:y2, x1:x2] = 20                       # ROI yine KARANLIK
    b = io.BytesIO()
    Image.fromarray(a, mode="L").convert("RGB").save(b, format="JPEG", quality=95)
    return (ts, b.getvalue())


baska = [yanlis_gorus(f"00:0{i}") for i in range(3)]
check("yanlis gorus kurgusu: ROI GERCEKTEN karanlik",
      pano.pano_durumu(baska, ROI, kisi_kontrolu=False) is not None,
      "-> kilit olmadan ATESLERDI (testin anlamli olmasi icin sart)")
check("FARKLI sahne imzayi GECEMEZ", not pano.gorus_uyuyor(baska, imza_acik))
check("gorus uymuyorsa ROI KARANLIK OLSA BILE olay uretilmez",
      pano.pano_durumu(baska, ROI, kisi_kontrolu=False,
                       gorus_imza=imza_acik) is None)
check("gorus uyuyorsa olay uretilir",
      pano.pano_durumu(acik, ROI, kisi_kontrolu=False,
                       gorus_imza=imza_acik) is not None)
check("BOZUK imza -> ATESLEMEZ (guvenli yon)",
      pano.pano_durumu(acik, ROI, kisi_kontrolu=False,
                       gorus_imza="bu,bir,imza,degil") is None)
_s2 = Settings()
check("varsayilan panel_gorus_imza BOS (K2)", _s2.panel_gorus_imza == "")
check("varsayilan gorus esigi 0,60", abs(_s2.panel_gorus_esik - 0.60) < 1e-9)


print("\n=== K3: bozuk girdi ===")
check("bozuk JPEG -> None", pano.pano_durumu([("00:00", b"bozuk")], ROI,
                                             kisi_kontrolu=False) is None)
check("bos kare listesi -> None", pano.pano_durumu([], ROI) is None)

print("\n=== D39-D: kkd_available SESSIZ BASARISIZLIK onarimi ===")
# Eskiden yalnizca DOSYAYA bakiyordu: ultralytics yokken True donuyor, model
# yuklenemiyor, detect_ppe_violation None donuyor, ize de yazilmiyordu.
_ag, _av = detector.kkd_agirlik_var, detector.available
try:
    detector.kkd_agirlik_var = lambda kit="baret": True
    detector.available = lambda: False
    neden = detector.kkd_neden_yok("baret")
    check("agirlik VAR ama arka uc YOK -> sebep verilir", neden is not None)
    check("sebep ultralytics'i isaret eder", bool(neden) and "ultralytics" in neden,
          f"-> {neden!r}")
    check("kkd_available artik False", detector.kkd_available("baret") is False)

    detector.kkd_agirlik_var = lambda kit="baret": False
    neden = detector.kkd_neden_yok("baret")
    check("agirlik YOK -> sebep verilir", bool(neden) and "agirlik" in neden,
          f"-> {neden!r}")

    detector.kkd_agirlik_var = lambda kit="baret": True
    detector.available = lambda: True
    check("ikisi de tamam -> sebep None", detector.kkd_neden_yok("baret") is None)
    check("ikisi de tamam -> available True", detector.kkd_available("baret") is True)
finally:
    detector.kkd_agirlik_var, detector.available = _ag, _av

print(f"\ngecen={_gecti}  kalan={_kaldi}")
sys.exit(1 if _kaldi else 0)
