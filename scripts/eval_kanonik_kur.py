#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""`data/eval_kanonik/` — MUKERRERSIZ degerlendirme kumesi (kok duzeltme).

`data/eval_full` kaynak dosyalari BIREBIR yansitir: 691 dosya, ama yalnizca
658 benzersiz icerik. Fazladan 33 kopya sinifLAR ARASI ve sessiz kusur
uretiyor (bkz. tests/test_veri_butunlugu.py).

Bu betik icerik basina TEK dosya birakir. Hangi dizine konacagi
`benchmark/kanonik_etiket.py`'nin sectigi TEMSILCI ile belirlenir
(guvensiz sinif oncelikli, esitlikte en kucuk sinif no) — keyfi degil,
deterministik.

Cok-etiketli iceriklerin DIGER etiketleri KAYBOLMAZ: puanlama
`benchmark/results/kanonik_etiket.json` uzerinden yapilir ve orada icerik
basina TAM etiket kumesi durur.

Kullanim:  python scripts/eval_kanonik_kur.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEDEF = os.path.join(KOK, "data", "eval_kanonik")
KAN = os.path.join(KOK, "benchmark", "results", "kanonik_etiket.json")

KOVA_ADI = {
    "class0": ("Anomali", "Safe_Walkway_Violation"),
    "class1": ("Anomali", "Unauthorized_Intervention"),
    "class2": ("Anomali", "Opened_Panel_Cover"),
    "class3": ("Anomali", "Carrying_Overload_with_Forklift"),
    "class4": ("Normal", "Safe_Walkway"),
    "class5": ("Normal", "Authorized_Intervention"),
    "class6": ("Normal", "Closed_Panel_Cover"),
    "class7": ("Normal", "Safe_Carrying"),
}


def main():
    if not os.path.exists(KAN):
        print("once: python benchmark/kanonik_etiket.py")
        return 1
    kan = json.load(open(KAN, encoding="utf-8"))["icerik"]
    say = {}
    n = 0
    for h, v in kan.items():
        tems = v["temsilci"]                       # data/industrial/classX/ad.mp4
        sinif = os.path.basename(os.path.dirname(tems))
        kova, ad = KOVA_ADI[sinif]
        dst_dir = os.path.join(HEDEF, kova, ad)
        os.makedirs(dst_dir, exist_ok=True)
        src = os.path.join(KOK, tems.replace("/", os.sep))
        dst = os.path.join(dst_dir, os.path.basename(tems))
        if not os.path.lexists(dst):
            try:
                os.symlink(os.path.relpath(src, dst_dir), dst)
            except OSError:
                shutil.copy2(src, dst)
        say[ad] = say.get(ad, 0) + 1
        n += 1
    print("%-34s%6s" % ("dizin", "klip"))
    print("-" * 40)
    for ad in sorted(say):
        print("%-34s%6d" % (ad, say[ad]))
    print("-" * 40)
    print("%-34s%6d" % ("TOPLAM (benzersiz icerik)", n))
    print()
    print("KIYAS: data/eval_full = 691 dosya / 658 benzersiz icerik")
    print("       data/eval_defense = 197 dosya")
    print()
    print("Cok-etiketli iceriklerin tam etiket kumesi:")
    print("  benchmark/results/kanonik_etiket.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
