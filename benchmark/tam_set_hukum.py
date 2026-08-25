#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TAM SET HUKMU — on kayitli S1/S2/S3 olcutleri MEKANIK uygulanir.

ON KAYIT: docs/on_kayit_tam_set_2026-08-25.md
  S1 REPLIKASYON : MCC >= (sevk degeri - 0,15)
  S2 MARJ        : dogruluk - cerceve tabani >= 0,05
  S3 YAYA YOLU   : MCC >= +0,45 VE saha kesinligi >= 0,237

Sayilar EL ILE yazilmaz; kanonik yer gercegiyle hesaplanir
(`benchmark/kanonik_etiket.py` + arsiv).

Kullanim:  python benchmark/tam_set_hukum.py [arsiv.json]
"""
from __future__ import annotations

import glob
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from benchmark.kanonik_puanla import (                    # noqa: E402
    KURAL, CIFT_GUVENLI, atesledi, ozet,
)
from benchmark.yumusak_esik import (                      # noqa: E402
    dagilimlari_oku, mcc, _satirlari_al,
)

SEVK_197 = {"pano": 0.960, "forklift": 0.881, "yetkisiz": 0.689}
S1_ESIK = {k: round(v - 0.15, 3) for k, v in SEVK_197.items()}
# ETIKETSIZ olculmus cerceve tabani (dengeli alt-orneklem, 5 tohum)
CERCEVE = {"yaya": 0.728, "yetkisiz": 0.797, "pano": 0.661, "forklift": 0.750}
S2_MARJ = 0.05
S3_MCC, S3_SAHA = 0.45, 0.237


def main():
    arsiv = sys.argv[1] if len(sys.argv) > 1 else sorted(
        glob.glob(os.path.join(KOK, "benchmark/results/eval_*.json")),
        key=os.path.getmtime)[-1]
    kan = json.load(open(os.path.join(
        KOK, "benchmark/results/kanonik_etiket.json"), encoding="utf-8"))["icerik"]
    sat = _satirlari_al(json.load(open(arsiv, encoding="utf-8")))

    bagli = {}
    for p, r in sat.items():
        t = os.path.join(KOK, p.replace("/", os.sep))
        if os.path.exists(t):
            h = ozet(os.path.realpath(t))
            if h in kan:
                bagli[h] = r
    print("arsiv: %s   icerik: %d" % (os.path.basename(arsiv), len(bagli)))

    olcum = {}
    for ad, (slot, esik, yon, sinif) in KURAL.items():
        gl = CIFT_GUVENLI[sinif]
        tp = fp = fn = tn = 0
        ates = dogru = 0
        for h, r in bagli.items():
            et = set(kan[h]["etiketler"])
            a = atesledi(dagilimlari_oku(r), slot, esik, yon)
            if a:
                ates += 1
                if sinif in et:
                    dogru += 1
            poz, neg = sinif in et, gl in et
            if (poz and neg) or not (poz or neg):
                continue
            if poz:
                tp, fn = (tp + 1, fn) if a else (tp, fn + 1)
            else:
                fp, tn = (fp + 1, tn) if a else (fp, tn + 1)
        n = tp + fp + fn + tn
        olcum[ad] = {
            "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "mcc": mcc(tp, fp, fn, tn),
            "dogruluk": (tp + tn) / float(n) if n else 0.0,
            "saha": dogru / float(ates) if ates else 0.0,
            "atesleme": ates,
        }

    print()
    print("### S1 — REPLIKASYON  (esik = sevk degeri - 0,15)")
    print("%-12s%10s%12s%10s%10s" % ("kural", "197'de", "TAM SET", "esik", "hukum"))
    print("-" * 56)
    s1 = True
    for ad in ("pano", "forklift", "yetkisiz"):
        m = olcum[ad]["mcc"]
        ok = m >= S1_ESIK[ad]
        s1 = s1 and ok
        print("%-12s%+10.3f%+12.3f%+10.3f%10s"
              % (ad, SEVK_197[ad], m, S1_ESIK[ad], "GECTI" if ok else "KALDI"))
    print("  -> S1 %s" % ("GECTI" if s1 else "KALDI"))

    print()
    print("### S2 — MARJ  (dogruluk - cerceve tabani >= %.2f)" % S2_MARJ)
    print("%-12s%11s%12s%9s%10s" %
          ("kural", "dogruluk", "cerceve", "marj", "hukum"))
    print("-" * 56)
    s2 = True
    for ad in ("pano", "forklift", "yetkisiz"):
        d = olcum[ad]["dogruluk"]
        c = CERCEVE[ad]
        ok = (d - c) >= S2_MARJ
        s2 = s2 and ok
        print("%-12s%11.3f%12.3f%+9.3f%10s"
              % (ad, d, c, d - c, "GECTI" if ok else "KALDI"))
    print("  -> S2 %s" % ("GECTI" if s2 else "KALDI"))

    print()
    print("### S3 — YAYA YOLU  (MCC >= %.2f VE saha kesinligi >= %.3f)"
          % (S3_MCC, S3_SAHA))
    y = olcum["yaya"]
    k1 = y["mcc"] >= S3_MCC
    k2 = y["saha"] >= S3_SAHA
    print("  MCC            %+0.3f   esik %+0.2f   %s"
          % (y["mcc"], S3_MCC, "gecti" if k1 else "KALDI"))
    print("  saha kesinligi  %0.3f   esik  %0.3f   %s"
          % (y["saha"], S3_SAHA, "gecti" if k2 else "KALDI"))
    print("  -> S3 %s" % ("GECTI" if (k1 and k2) else "KALDI"))

    print()
    print("### TAM TABLO (kanonik)")
    print("%-12s%6s%5s%5s%5s%5s%9s%11s%12s" %
          ("kural", "n", "TP", "FP", "FN", "TN", "MCC", "dogruluk", "saha kes."))
    print("-" * 72)
    for ad, m in olcum.items():
        print("%-12s%6d%5d%5d%5d%5d%+9.3f%11.3f%9.3f (%d)"
              % (ad, m["n"], m["tp"], m["fp"], m["fn"], m["tn"], m["mcc"],
                 m["dogruluk"], m["saha"], m["atesleme"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
