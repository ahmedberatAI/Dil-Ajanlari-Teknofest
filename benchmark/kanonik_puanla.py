#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""KANONIK PUANLAMA — cok-etiketli yer gercegiyle yeniden skorlama.

`benchmark/kanonik_etiket.py` icerik (sha256) basina ETIKET KUMESI uretti.
Bu betik arsiv satirlarini hash uzerinden o kayda BAGLAR ve iki seyi duzeltir:

  1. CIFT METRIGI — ayni icerik ciftin IKI tarafinda olamaz. Hem GUVENSIZ hem
     GUVENLI sinif tasiyan icerikler o ciftten DISLANIR (temiz negatif degil).
     Yaya ciftinde 3 icerik boyle; eski olcumde 3'u de NEGATIF sayiliyordu.

  2. SAHA KESINLIGI — bir atesleme, atesledigi sinif icerigin ETIKET
     KUMESINDE varsa DOGRUDUR. Kaynak sette 27 `class0` icerigi AYNI ZAMANDA
     `class1`; yelek kuralinin o kliplerdeki ateslemeleri "capraz" degil
     DOGRUDUR. Eskiden bu duzeltme 12 klibe GOZLE bakilarak tahmin ediliyordu;
     artik dosya hash'inden KESIN olarak biliniyor.

     SINIR — durustce: bu duzeltme yalnizca kaynagin KENDI kopyaladigi
     kliplerdeki gizli etiketleri geri getirir. Yeleksiz kisi gosterip
     yalnizca `class0` etiketli (kopyasi olmayan) bir klip HALA tek etiketli
     gorunur. Yani bu ALT SINIRDIR, tam duzeltme degil.

Kullanim:  python benchmark/kanonik_puanla.py [arsiv.json]
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from benchmark.yumusak_esik import (                    # noqa: E402
    dagilimlari_oku, mcc, _argmaks, _satirlari_al,
)

KURAL = {   # ad -> (slot, esik, yon, hangi sinifi iddia eder)
    "forklift": ("catal_kasa_sayisi", 3, "ust", "class3"),
    "pano": ("pano_koyuluk_0_10", 6, "ust", "class2"),
    "yetkisiz": ("makine_basinda_yelek", None, "yelek", "class1"),
    "yaya": ("yaya_cizgi_mesafe", 7, "alt", "class0"),
}
CIFT_GUVENLI = {"class0": "class4", "class1": "class5",
                "class2": "class6", "class3": "class7"}
ON_SLOT, ON_ASGARI = "makine_basinda_kisi", 1


def ozet(yol, blok=1 << 20):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        while True:
            b = f.read(blok)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


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
        else:
            k = str(_argmaks(seg.get(ON_SLOT)) or "").rstrip("+")
            if k.isdigit() and int(k) >= ON_ASGARI and v == "YOK":
                return True
    return False


def main():
    if len(sys.argv) > 1:
        arsiv = sys.argv[1]
    else:
        d = sorted(glob.glob(os.path.join(KOK, "benchmark/results/eval_*.json")),
                   key=os.path.getmtime)
        arsiv = d[-1]
    kan_yol = os.path.join(KOK, "benchmark/results/kanonik_etiket.json")
    if not os.path.exists(kan_yol):
        print("once `python benchmark/kanonik_etiket.py` calistir")
        return 1
    kan = json.load(open(kan_yol, encoding="utf-8"))["icerik"]

    sat = _satirlari_al(json.load(open(arsiv, encoding="utf-8")))
    print("arsiv: " + os.path.basename(arsiv) + "   satir: " + str(len(sat)))

    # --- arsiv satirlarini ICERIGE bagla ---
    bagli, bagsiz = {}, []
    for p, r in sat.items():
        tam = os.path.join(KOK, p.replace("/", os.sep))
        if not os.path.exists(tam):
            bagsiz.append(p)
            continue
        h = ozet(os.path.realpath(tam))
        if h in kan:
            bagli[h] = r
        else:
            bagsiz.append(p)
    print("icerige baglanan: %d   baglanamayan: %d" % (len(bagli), len(bagsiz)))
    if bagsiz[:3]:
        print("   ornek baglanamayan: " + str(bagsiz[:3]))

    # --- 1) CIFT METRIGI (kanonik) ---
    print()
    print("CIFT METRIGI — kanonik (celiskili icerikler DISLANDI)")
    print("%-12s%6s%5s%5s%5s%5s%9s%10s" %
          ("kural", "n", "TP", "FP", "FN", "TN", "MCC", "dislanan"))
    print("-" * 62)
    for ad, (slot, esik, yon, sinif) in KURAL.items():
        gl = CIFT_GUVENLI[sinif]
        tp = fp = fn = tn = 0
        dis = 0
        for h, r in bagli.items():
            et = set(kan[h]["etiketler"])
            poz, neg = sinif in et, gl in et
            if poz and neg:
                dis += 1
                continue                      # temiz negatif OLAMAZ
            if not (poz or neg):
                continue
            a = atesledi(dagilimlari_oku(r), slot, esik, yon)
            if poz:
                tp, fn = (tp + 1, fn) if a else (tp, fn + 1)
            else:
                fp, tn = (fp + 1, tn) if a else (fp, tn + 1)
        n = tp + fp + fn + tn
        if n:
            print("%-12s%6d%5d%5d%5d%5d%+9.3f%10d"
                  % (ad, n, tp, fp, fn, tn, mcc(tp, fp, fn, tn), dis))

    # --- 2) SAHA KESINLIGI (cok-etiketli) ---
    print()
    print("SAHA KESINLIGI — ham vs COK-ETIKETLI duzeltilmis")
    print("%-12s%10s%12s%14s%12s" %
          ("kural", "atesleme", "ham dogru", "cok-etiketli", "kazanc"))
    print("-" * 62)
    for ad, (slot, esik, yon, sinif) in KURAL.items():
        ates = ham = cok = 0
        for h, r in bagli.items():
            if not atesledi(dagilimlari_oku(r), slot, esik, yon):
                continue
            ates += 1
            et = set(kan[h]["etiketler"])
            # HAM: yalnizca TEMSILCI dosyanin sinifi (eski yontem)
            tems = os.path.basename(os.path.dirname(kan[h]["temsilci"]))
            if tems == sinif:
                ham += 1
            if sinif in et:                    # COK-ETIKETLI: kumede varsa dogru
                cok += 1
        if ates:
            print("%-12s%10d%8d %.3f%9d %.3f%9s"
                  % (ad, ates, ham, ham / ates, cok, cok / ates,
                     "+%.3f" % ((cok - ham) / ates)))

    # --- 3) AYRIM (tr/te) ---
    print()
    print("AYRIM BAZLI (kanonik ayrim: bir kopyasi _te ise icerik TESTTE)")
    print("%-12s%8s%6s%5s%5s%5s%5s%9s" %
          ("kural", "ayrim", "n", "TP", "FP", "FN", "TN", "MCC"))
    print("-" * 62)
    for ad, (slot, esik, yon, sinif) in KURAL.items():
        gl = CIFT_GUVENLI[sinif]
        for ayrim in ("tr", "te"):
            tp = fp = fn = tn = 0
            for h, r in bagli.items():
                if kan[h]["ayrim"] != ayrim:
                    continue
                et = set(kan[h]["etiketler"])
                poz, neg = sinif in et, gl in et
                if (poz and neg) or not (poz or neg):
                    continue
                a = atesledi(dagilimlari_oku(r), slot, esik, yon)
                if poz:
                    tp, fn = (tp + 1, fn) if a else (tp, fn + 1)
                else:
                    fp, tn = (fp + 1, tn) if a else (fp, tn + 1)
            n = tp + fp + fn + tn
            if n:
                print("%-12s%8s%6d%5d%5d%5d%5d%+9.3f"
                      % (ad, ayrim, n, tp, fp, fn, tn, mcc(tp, fp, fn, tn)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
