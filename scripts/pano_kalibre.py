#!/usr/bin/env python
"""Pano dedektorunu BIR KAMERA GORUSU icin kalibre eder (D39-E).

    python scripts/pano_kalibre.py --klipler "data/eval_defense/Normal/Closed_Panel_Cover/*.mp4"

Uretilenler (dogrudan .env / ayara yapistirilir):
    DILAJAN_PANEL_ROI          — elle verilir (bu betik dogrulamaz, yalnizca kullanir)
    DILAJAN_PANEL_LUMA_ESIK    — KAPALI kliplerin en karanligi (guvenli alt sinir)
    DILAJAN_PANEL_GORUS_IMZA   — sahne yapisi imzasi (yanlis kamerada atesleme kilidi)

NEDEN GORUS IMZASI SART (olculdu, 197 klip): sabit ROI yalnizca kalibre edildigi
kamera gorusunde anlamlidir. Ayni tesisin baska cercevesinde ROI panoya degil
baska bir karanlik yuzeye duser; kesinlik 0,259'a coker.
"""
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import pano  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402


def kareler(yol, max_side=None):
    fr, _ = extract_timestamped_frames(yol, max_side=max_side)
    return [(f"{int(t)//60:02d}:{int(t)%60:02d}", j) for t, j in fr]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--klipler", required=True,
                    help="KAPALI pano referans klipleri (glob)")
    ap.add_argument("--roi", default="0.08,0.55,0.21,0.73")
    ap.add_argument("--pay", type=float, default=0.0,
                    help="esikten cikarilacak guvenlik payi (luma birimi)")
    a = ap.parse_args()

    yollar = sorted(glob.glob(a.klipler))
    if not yollar:
        print(f"HATA: klip bulunamadi: {a.klipler}")
        return 2
    roi = pano.roi_ayristir(a.roi)
    if roi is None:
        print(f"HATA: gecersiz ROI: {a.roi!r}")
        return 2

    import io as _io
    import numpy as np
    from PIL import Image

    en_dusukler, imzalar = [], []
    for y in yollar:
        fr = kareler(y)
        if not fr:
            continue
        lum = []
        for _, j in fr:
            im = Image.open(_io.BytesIO(j)).convert("L")
            w, h = im.size
            x1, y1, x2, y2 = (int(roi[0]*w), int(roi[1]*h), int(roi[2]*w), int(roi[3]*h))
            arr = np.asarray(im, dtype=np.float32)[y1:y2, x1:x2]
            lum.append(float(arr.mean()) if arr.size else 255.0)
        en_dusukler.append(min(lum))
        imzalar.append(pano.gorus_imzasi(fr))
        print(f"  {os.path.basename(y):18s} en karanlik luma = {min(lum):6.1f}")

    if not en_dusukler:
        print("HATA: hicbir klipten kare cikarilamadi")
        return 2

    esik = min(en_dusukler) - a.pay
    # imzalarin MEDYANI — tek bir klibin sansina bagli kalmamak icin
    mat = np.array([[float(x) for x in s.split(",")] for s in imzalar if s])
    med = np.median(mat, axis=0)
    med = (med - med.mean()) / (med.std() + 1e-6)
    imza = ",".join(f"{x:.3f}" for x in med)

    # imzanin kendi kliplerine ne kadar uydugunu GOSTER (esik secmek icin)
    kor = [float(np.dot(med, r) / len(med)) for r in mat]
    print(f"\n  referans klipler n={len(en_dusukler)}")
    print(f"  KAPALI kliplerde en karanlik luma: min={min(en_dusukler):.1f} "
          f"maks={max(en_dusukler):.1f}")
    print(f"  imza kendi kliplerine korelasyon: min={min(kor):.3f} "
          f"medyan={sorted(kor)[len(kor)//2]:.3f}")
    print(f"\n  >>> ONERILEN AYAR")
    print(f"  DILAJAN_PANEL_ROI={a.roi}")
    print(f"  DILAJAN_PANEL_LUMA_ESIK={esik:.1f}")
    print(f"  DILAJAN_PANEL_GORUS_IMZA={imza}")
    print(f"\n  NOT: esik, KAPALI kliplerde HIC GORULMEYEN karanlik seviyesidir.")
    print(f"       Gorus esigi varsayilani {pano.GORUS_ESIK_VARSAYILAN}; yukaridaki "
          f"min korelasyon ({min(kor):.3f}) bunun USTUNDE olmali.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
