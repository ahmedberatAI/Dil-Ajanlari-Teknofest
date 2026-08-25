#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""`data/eval_full/` — kaynak setin TAMAMINDAN degerlendirme kumesi kurar.

NEDEN: `data/eval_defense` kaynak setin yalnizca **%29'unu** kullaniyor
(197/691). Yaya yolu sinifinda oran daha da dusuk: **25/210 (%12)**.
Bugunku uc kalan sorunun ucu de ornekleme baglidir:
  1. sinif basina 24-25 ihlal klibi -> Wilson araliklari genis
  2. yaya yolu ciftinde cerceve karistiricisi (%72,9) — daha cesitli klip
     onu zayiflatabilir
  3. yelek kuralinin kamera tabanina marji ince (+0,040), n=50

LISANS: `data/industrial` **CC BY 4.0** (Mendeley xjmtb22pff). Egitim ve
degerlendirme SERBEST (`dilajan/veri_lisans.py` yalnizca isafety_bench'i
kisitlar). Baytlar KVKK geregi YENIDEN YAYIMLANMAZ — bu betik yalnizca
SEMBOLIK BAG kurar, kopya uretmez (kaynak 9,4 GB).

Kullanim:  python scripts/eval_full_kur.py [--kopya]
"""
from __future__ import annotations

import os
import shutil
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAYNAK = os.path.join(KOK, "data", "industrial")
HEDEF = os.path.join(KOK, "data", "eval_full")

# CLASSES.md'den — iki bagimsiz kaynakla DOGRULANMIS esleme
ESLEME = [
    ("class0", "Anomali", "Safe_Walkway_Violation"),
    ("class1", "Anomali", "Unauthorized_Intervention"),
    ("class2", "Anomali", "Opened_Panel_Cover"),
    ("class3", "Anomali", "Carrying_Overload_with_Forklift"),
    ("class4", "Normal", "Safe_Walkway"),
    ("class5", "Normal", "Authorized_Intervention"),
    ("class6", "Normal", "Closed_Panel_Cover"),
    ("class7", "Normal", "Safe_Carrying"),
]


def main():
    kopyala = "--kopya" in sys.argv
    if not os.path.isdir(KAYNAK):
        print("kaynak yok: " + KAYNAK)
        return 1
    toplam = 0
    print("%-10s %-34s %6s" % ("sinif", "hedef", "klip"))
    print("-" * 54)
    for sinif, kova, ad in ESLEME:
        src = os.path.join(KAYNAK, sinif)
        dst = os.path.join(HEDEF, kova, ad)
        os.makedirs(dst, exist_ok=True)
        n = 0
        for f in sorted(os.listdir(src)):
            if not f.lower().endswith(".mp4"):
                continue
            s = os.path.join(src, f)
            d = os.path.join(dst, f)
            if os.path.lexists(d):
                n += 1
                continue
            try:
                if kopyala:
                    shutil.copy2(s, d)
                else:
                    os.symlink(os.path.relpath(s, dst), d)
            except OSError:
                shutil.copy2(s, d)          # symlink desteklenmiyorsa kopyala
            n += 1
        toplam += n
        print("%-10s %-34s %6d" % (sinif, kova + "/" + ad, n))
    print("-" * 54)
    print("%-45s %6d" % ("TOPLAM", toplam))
    print()
    print("KIYAS: data/eval_defense = 197 klip (kaynak setin %29'u)")
    print("       data/eval_full    = " + str(toplam) + " klip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
