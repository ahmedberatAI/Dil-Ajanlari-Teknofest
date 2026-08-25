#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TESIS IMZASI — gozlem duzleminin ALAN KILIDI icin referans(lar) uretir.

NEDEN (olculdu 2026-08-25, 100 alan disi klip / iSafetyBench):
Tesise KALIBRE ISG kurallari alan disinda GURULTU uretiyor — normal
kliplerin 22/50'sinde YALNIZCA ISG kurali atesliyor ve tehlike tespitine
katkisi SIFIR (recall her iki kipte de 0,900). Kilit, gozlem duzlemini
kendi tesisine baglar.

COK IMZA VE KAPSAMA GARANTISI SART:
  · Tek imza kendi kliplerimizin %45'ini disarida birakti.
  · Kor kumeleme (k=4) FORKLIFT KAMERASININ TAMAMINI disarida birakti
    (50/50 klip) ve forklift kuralini +0,881'den +0,000'a dusurdu —
    cunku o kamera azinlikta kalip kendi imzasini alamadi.
Bu yuzden imzalar SINIF DIZINLERINDEN KAPSAMA GARANTILI uretilir: her
kaynak sinifi icin ayri imza cikarilir ve her sinifin GECIS ORANI
dogrulanir. Sahne imzalardan HERHANGI BIRINE benziyorsa kilit acilir.

Imza ETIKET GORMEZ: kilit "bu bizim tesisimiz mi" diye sorar, "bu hangi
sinif" diye DEGIL — kalibre tesiste TUM siniflar kilidi gecer, dolayisiyla
etiket sizintisi yok. (Sinif dizinleri yalnizca KAMERA CESITLILIGINI
garanti etmek icin kullanilir.)

Kullanim:  python scripts/tesis_imzasi_uret.py [--esik 0.60]
"""
from __future__ import annotations

import glob
import os
import random
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from dilajan.pano import gorus_imzasi, gorus_uyuyor           # noqa: E402
from dilajan.video import extract_timestamped_frames          # noqa: E402

TOHUM = 7
SINIF_BASI = 6         # her kaynak sinifindan kac klip imzaya girer
KARE = 6
KAPSAMA_ESIGI = 0.95   # her sinifin bu orandan fazlasi kilidi GECMELI


def kareler(yol, n=KARE):
    fr, _ = extract_timestamped_frames(yol)
    return list(fr)[:n]


def gecer(fr, imzalar, esik):
    return any(gorus_uyuyor(fr, im, esik) for im in imzalar)


def main():
    esik = 0.60
    if "--esik" in sys.argv:
        esik = float(sys.argv[sys.argv.index("--esik") + 1])

    siniflar = sorted(glob.glob(os.path.join(KOK, "data", "industrial", "class*")))
    if not siniflar:
        print("kaynak yok: data/industrial")
        return 1
    rng = random.Random(TOHUM)

    # --- KAPSAMA GARANTILI: her sinif icin bir imza ---
    print("imza uretimi — SINIF BASINA (kamera cesitliligi garantisi)")
    imzalar, kullanilan = [], set()
    for d in siniflar:
        havuz = sorted(glob.glob(os.path.join(d, "*.mp4")))
        if not havuz:
            continue
        sec = rng.sample(havuz, min(SINIF_BASI, len(havuz)))
        kullanilan.update(sec)
        kare = []
        for p in sec:
            kare.extend(kareler(p))
        imzalar.append(gorus_imzasi(kare))
        print("   %-8s %3d klip havuzu -> imza %d klipten" %
              (os.path.basename(d), len(havuz), len(sec)))
    print("toplam imza: %d   esik: %.2f" % (len(imzalar), esik))

    # --- KAPSAMA DOGRULAMASI: HER SINIF gecmeli ---
    print()
    print("KAPSAMA DOGRULAMASI (imzada KULLANILMAYAN klipler)")
    print("%-10s%10s%10s%8s" % ("sinif", "denenen", "gecen", "oran"))
    print("-" * 40)
    kapsama_ok = True
    for d in siniflar:
        havuz = [p for p in sorted(glob.glob(os.path.join(d, "*.mp4")))
                 if p not in kullanilan]
        if not havuz:
            continue
        dd = rng.sample(havuz, min(20, len(havuz)))
        g = sum(1 for p in dd if gecer(kareler(p, 4), imzalar, esik))
        oran = g / float(len(dd))
        if oran < KAPSAMA_ESIGI:
            kapsama_ok = False
        print("%-10s%10d%10d%8.3f%s" % (os.path.basename(d), len(dd), g, oran,
                                        "" if oran >= KAPSAMA_ESIGI else "  << EKSIK"))
    print("   -> kapsama %s (esik %.2f)"
          % ("TAM" if kapsama_ok else "EKSIK", KAPSAMA_ESIGI))

    # --- ALAN DISI SIZINTI ---
    dis_h = sorted(glob.glob(os.path.join(
        KOK, "data", "eval_genelleme", "*", "*", "*.mp4")))
    if dis_h:
        dd = rng.sample(dis_h, min(50, len(dis_h)))
        gd = sum(1 for p in dd if gecer(kareler(p, 4), imzalar, esik))
        print()
        print("ALAN DISI SIZINTI (iSafetyBench, %d klip): %d gecti = %.3f  %s"
              % (len(dd), gd, gd / float(len(dd)),
                 "(SIFIR olmali)" if gd else "<< SIFIR"))

    yol = os.path.join(KOK, "benchmark", "results", "tesis_imzasi.txt")
    open(yol, "w").write(";".join(imzalar))
    print()
    print("kaydedildi: %s  (%d imza)" % (os.path.relpath(yol, KOK), len(imzalar)))
    return 0 if kapsama_ok else 3


if __name__ == "__main__":
    sys.exit(main())
