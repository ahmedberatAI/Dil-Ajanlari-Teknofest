#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tam set (691 klip) puanlama — GENEL + DENGELI + KATMANLI.

ON KAYIT: docs/on_kayit_tam_set_2026-08-25.md

UC OKUMA YAN YANA verilir cunku her biri farkli bir seyi gizler:
  GENEL    — tam set, ama DENGESIZ (or. yaya 210/75) -> MCC sisebilir
  DENGELI  — tohumlu alt-orneklem x5 -> dengesizlik etkisi kalkar
  KATMANLI — kamera kumesi ICINDE -> CERCEVE KARISTIRICISI kalkar

Katmanli okuma bu setin en onemli okumasidir: etiket, kisiler silinmis arka
plandan %72,8 (yaya) / %79,7 (yetkisiz) dogrulukla tahmin edilebiliyor.
Kural KATMAN ICINDE de ayirt ediyorsa skor kadrajdan GELMIYOR demektir.
Katmanlar `benchmark/kamera_katmanlari.py` ile ETIKETSIZ uretilir.

Kullanim:  python benchmark/tam_set_puanla.py [arsiv.json]
"""
from __future__ import annotations

import glob
import json
import os
import random
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from benchmark.yumusak_esik import (                       # noqa: E402
    dagilimlari_oku, mcc, _argmaks, _p_esik_ustu, _satirlari_al,
)

# (ad, ihlal dizin, normal dizin, slot, esik, yon)
CIFT = {
    "forklift": ("Anomali/Carrying_Overload_with_Forklift", "Normal/Safe_Carrying",
                 "catal_kasa_sayisi", 3, "ust"),
    "pano": ("Anomali/Opened_Panel_Cover", "Normal/Closed_Panel_Cover",
             "pano_koyuluk_0_10", 6, "ust"),
    "yetkisiz": ("Anomali/Unauthorized_Intervention", "Normal/Authorized_Intervention",
                 "makine_basinda_yelek", None, "yelek"),
    "yaya": ("Anomali/Safe_Walkway_Violation", "Normal/Safe_Walkway",
             "yaya_cizgi_mesafe", 7, "alt"),
    "yaya_zemin": ("Anomali/Safe_Walkway_Violation", "Normal/Safe_Walkway",
                   "yaya_zemin", None, "zemin"),
}
SEVK_197 = {"forklift": 0.881, "pano": 0.960, "yetkisiz": 0.689}
KABUL = {"forklift": 0.73, "pano": 0.81, "yetkisiz": 0.54}      # sevk - 0,15
# ETIKETSIZ olculen cerceve tabani (dengeli alt-orneklem, 5x)
CERCEVE = {"yaya": 0.728, "yetkisiz": 0.797, "pano": 0.661, "forklift": 0.750}
ON_SLOT, ON_ASGARI = "makine_basinda_kisi", 1


def atesledi(segler, slot, esik, yon):
    for seg in segler:
        d = seg.get(slot)
        if not d:
            continue
        v = _argmaks(d)
        if yon == "ust":
            s = str(v or "").rstrip("+")
            if s.isdigit() and int(s) >= esik:
                return True
        elif yon == "alt":
            s = str(v or "").rstrip("+")
            if s.isdigit() and int(s) < esik:
                return True
        elif yon == "zemin":
            if v == "GRI_BETON":
                return True
        else:                                   # yelek: ON KOSUL + etiket
            k = str(_argmaks(seg.get(ON_SLOT)) or "").rstrip("+")
            if k.isdigit() and int(k) >= ON_ASGARI and v == "YOK":
                return True
    return False


def topla(satirlar, cift, kume_klipleri=None):
    """(TP, FP, FN, TN, klip_adlari)"""
    ihl, nrm, slot, esik, yon = cift
    tp = fp = fn = tn = 0
    for p, r in sorted(satirlar.items()):
        y = "/" + p.replace("\\", "/")
        ad = os.path.basename(p)
        if kume_klipleri is not None and ad not in kume_klipleri:
            continue
        poz = ("/" + ihl + "/") in y
        neg = ("/" + nrm + "/") in y
        if not (poz or neg):
            continue
        a = atesledi(dagilimlari_oku(r), slot, esik, yon)
        if poz:
            tp, fn = (tp + 1, fn) if a else (tp, fn + 1)
        else:
            fp, tn = (fp + 1, tn) if a else (fp, tn + 1)
    return tp, fp, fn, tn


def dengeli_mcc(satirlar, cift, tekrar=5):
    """Dengesizligi kaldirmak icin tohumlu alt-orneklem."""
    ihl, nrm, slot, esik, yon = cift
    poz, neg = [], []
    for p, r in sorted(satirlar.items()):
        y = "/" + p.replace("\\", "/")
        if ("/" + ihl + "/") in y:
            poz.append(atesledi(dagilimlari_oku(r), slot, esik, yon))
        elif ("/" + nrm + "/") in y:
            neg.append(atesledi(dagilimlari_oku(r), slot, esik, yon))
    k = min(len(poz), len(neg))
    if k == 0:
        return 0.0, 0.0
    ler = []
    for t in range(tekrar):
        rng = random.Random(t)
        a = rng.sample(poz, k)
        b = rng.sample(neg, k)
        tp = sum(a)
        fn = k - tp
        fp = sum(b)
        tn = k - fp
        ler.append(mcc(tp, fp, fn, tn))
    ort = sum(ler) / len(ler)
    sd = (sum((x - ort) ** 2 for x in ler) / len(ler)) ** 0.5
    return ort, sd


def saha_kesinligi(satirlar, cift):
    ihl, nrm, slot, esik, yon = cift
    a = d = 0
    for p, r in satirlar.items():
        if not atesledi(dagilimlari_oku(r), slot, esik, yon):
            continue
        a += 1
        if ("/" + ihl + "/") in ("/" + p.replace("\\", "/")):
            d += 1
    return d, a


def main():
    if len(sys.argv) > 1:
        yol = sys.argv[1]
    else:
        d = sorted(glob.glob(os.path.join(KOK, "benchmark/results/eval_*.json")),
                   key=os.path.getmtime)
        yol = d[-1]
    ham = json.load(open(yol, encoding="utf-8"))
    sat = _satirlari_al(ham)
    kunye = ham.get("kosum") or {}
    print("arsiv: " + os.path.basename(yol) + "   satir: " + str(len(sat)))
    print("slotlar: " + str(kunye.get("isg_slotlari")))
    kaps = sum(1 for r in sat.values() if r.get("guven_trace"))
    print("guven izi tasiyan: %d/%d" % (kaps, len(sat)))
    if kaps == 0:
        print("!! dagilim yok")
        return 2

    kat_yol = os.path.join(KOK, "benchmark/results/kamera_katmanlari.json")
    kat = json.load(open(kat_yol, encoding="utf-8")) if os.path.exists(kat_yol) else None

    print()
    print("%-12s%6s%5s%5s%5s%5s%9s%16s%11s" %
          ("cift", "n", "TP", "FP", "FN", "TN", "MCC", "dengeli MCC", "saha kes."))
    print("-" * 82)
    for ad, cift in CIFT.items():
        tp, fp, fn, tn = topla(sat, cift)
        n = tp + fp + fn + tn
        if n == 0:
            continue
        m = mcc(tp, fp, fn, tn)
        dm, ds = dengeli_mcc(sat, cift)
        dd, da = saha_kesinligi(sat, cift)
        bayrak = ""
        if ad in KABUL:
            bayrak = "  <- 197'de %+.3f, esik %+.2f %s" % (
                SEVK_197[ad], KABUL[ad], "OK" if m >= KABUL[ad] else "KALDI")
        print("%-12s%6d%5d%5d%5d%5d%+9.3f%11.3f±%.3f%7.3f (%d/%d)%s"
              % (ad, n, tp, fp, fn, tn, m, dm, ds,
                 (dd / da if da else 0.0), dd, da, bayrak))

    # ---------- KATMANLI ----------
    if not kat:
        print("\n(kamera katmanlari dosyasi yok — katmanli okuma atlandi)")
        return 0
    print()
    print("=" * 82)
    print("KATMANLI OKUMA — kamera kumesi ICINDE (cerceve karistiricisi KALKAR)")
    print("%-12s%-8s%6s%5s%5s%5s%5s%9s%12s" %
          ("cift", "katman", "n", "TP", "FP", "FN", "TN", "MCC", "cerceve"))
    print("-" * 82)
    for ad, cift in CIFT.items():
        anahtar = "yaya" if ad == "yaya_zemin" else ad
        for k in (kat.get("ciftler", {}).get(anahtar) or []):
            if not k.get("kullanilabilir"):
                continue
            kl = set(k["klipler"])
            tp, fp, fn, tn = topla(sat, cift, kl)
            n = tp + fp + fn + tn
            if n == 0:
                continue
            print("%-12s%-8s%6d%5d%5d%5d%5d%+9.3f%12s"
                  % (ad, "kume%d" % k["kume"], n, tp, fp, fn, tn,
                     mcc(tp, fp, fn, tn),
                     ("%.3f" % CERCEVE[anahtar]) if anahtar in CERCEVE else "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
