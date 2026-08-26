#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""`data/eval_genelleme/` — ALAN DISI genelleme stres testi kumesi.

ON KAYIT: docs/on_kayit_genelleme_2026-08-25.md

Kaynak: `data/isafety_bench` (CC BY-NC-SA 4.0). LISANS.json:
  degerlendirmede_kullanilabilir = TRUE · egitimde = FALSE · yeniden yayim = FALSE
Bu kume YALNIZCA degerlendirme icindir; agirlik uretilmez.
`dilajan/veri_lisans.py` bunu fail-closed zorlar.

Tohumlu (seed=7) 50 tehlike + 50 normal. Sembolik bag (kopya yok).

Kullanim:  python scripts/eval_genelleme_kur.py
"""
from __future__ import annotations

import glob
import json
import os
import random
import shutil
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

KAYNAK = os.path.join(KOK, "data", "isafety_bench", "videos")
HEDEF = os.path.join(KOK, "data", "eval_genelleme")
N = 50
TOHUM = 7


def main():
    # LISANS KAPISI — degerlendirme icin acik olmali
    try:
        from dilajan.veri_lisans import degerlendirme_icin_dogrula
        degerlendirme_icin_dogrula("data/isafety_bench")
        print("lisans kapisi: degerlendirme SERBEST")
    except ImportError:
        lis = json.load(open(os.path.join(
            KOK, "data/isafety_bench/LISANS.json"), encoding="utf-8"))
        if not lis.get("degerlendirmede_kullanilabilir"):
            print("!! LISANS: degerlendirme KAPALI")
            return 1
        print("lisans: degerlendirmede_kullanilabilir = True")
    except Exception as ex:
        print("!! lisans kapisi: %s" % ex)
        return 1

    esleme = [("hazard", "Anomali", "Hazard"), ("normal", "Normal", "Normal")]
    toplam = 0
    print("%-10s%-28s%7s%9s" % ("kaynak", "hedef", "havuz", "secilen"))
    print("-" * 56)
    for alt, kova, ad in esleme:
        havuz = sorted(glob.glob(os.path.join(KAYNAK, alt, "*.mp4")))
        rng = random.Random(TOHUM)
        sec = rng.sample(havuz, min(N, len(havuz)))
        dst = os.path.join(HEDEF, kova, ad)
        os.makedirs(dst, exist_ok=True)
        for p in sec:
            d = os.path.join(dst, os.path.basename(p))
            if os.path.lexists(d):
                continue
            try:
                os.link(p, d)               # SABIT BAG once (Windows da okur)
            except OSError:
                try:
                    os.symlink(os.path.relpath(p, dst), d)
                except OSError:
                    shutil.copy2(p, d)
        toplam += len(sec)
        print("%-10s%-28s%7d%9d" % (alt, kova + "/" + ad, len(havuz), len(sec)))
    print("-" * 56)
    print("%-38s%9d" % ("TOPLAM", toplam))
    print()
    print("ALAN UYARISI (LISANS.json): dagitim alani sabit-kamera endustriyel")
    print("CCTV; bu set YouTube kaynakli. Sonuc GENELLEME STRES TESTIDIR.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
