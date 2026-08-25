#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""KAYNAK VERI SETI DENETIMI — mukerrer dosya ve ETIKET CELISKISI.

BULGU (2026-08-25): degerlendirme kosumunda 33 klip "mukerrer" diye elendi ve
elenenlerin coğu SINIFLAR ARASI cikti — ornegin
    Unauthorized_Intervention/1_te1.mp4  ==  Safe_Walkway_Violation/0_te8.mp4
Daha agiri: AYNI DOSYA hem GUVENLI hem GUVENSIZ etiketiyle sette duruyor:
    Normal/Safe_Walkway/4_te4.mp4  ==  Anomali/Safe_Walkway_Violation/0_tr123.mp4

Bu bir olcum kusuru degil KAYNAK VERI kusurudur ve her metrigi zehirler:
  · ayni klip hem TP hem TN sayilabilir
  · cift bazli MCC anlamsizlasir (ayni goruntu iki tarafta)
  · egitim/test ayrimi delinir (bir klibin kopyasi karsi tarafta olabilir)

Bu betik MODEL CALISTIRMAZ. Yalnizca dosya icerigini hashler ve haritalar.

Kullanim:  python benchmark/veri_kusuru_denetimi.py [--set data/industrial]
"""
from __future__ import annotations

import collections
import glob
import hashlib
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SINIF_ADI = {
    "class0": ("GUVENSIZ", "Safe_Walkway_Violation"),
    "class1": ("GUVENSIZ", "Unauthorized_Intervention"),
    "class2": ("GUVENSIZ", "Opened_Panel_Cover"),
    "class3": ("GUVENSIZ", "Carrying_Overload_with_Forklift"),
    "class4": ("GUVENLI", "Safe_Walkway"),
    "class5": ("GUVENLI", "Authorized_Intervention"),
    "class6": ("GUVENLI", "Closed_Panel_Cover"),
    "class7": ("GUVENLI", "Safe_Carrying"),
}
# hangi guvensiz sinif hangi guvenli sinifin KARSITI (cift bazli metrik)
KARSIT = {"class0": "class4", "class1": "class5", "class2": "class6",
          "class3": "class7"}


def ozet(yol, blok=1 << 20):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        while True:
            b = f.read(blok)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    kok = "data/industrial"
    if "--set" in sys.argv:
        kok = sys.argv[sys.argv.index("--set") + 1]
    kok = os.path.join(KOK, kok)

    dosyalar = sorted(glob.glob(os.path.join(kok, "class*", "*.mp4")))
    print("taranan dosya: %d   (%s)" % (len(dosyalar), os.path.relpath(kok, KOK)))
    if not dosyalar:
        return 1

    gruplar = collections.defaultdict(list)
    for i, p in enumerate(dosyalar):
        sinif = os.path.basename(os.path.dirname(p))
        gruplar[ozet(p)].append((sinif, os.path.basename(p)))
        if (i + 1) % 100 == 0:
            print("   ... %d/%d" % (i + 1, len(dosyalar)), file=sys.stderr)

    coklu = {h: g for h, g in gruplar.items() if len(g) > 1}
    fazla = sum(len(g) - 1 for g in coklu.values())
    print()
    print("BENZERSIZ ICERIK : %d" % len(gruplar))
    print("MUKERRER GRUP    : %d   (fazladan kopya: %d)" % (len(coklu), fazla))

    # --- grup turleri ---
    ayni_sinif = capraz_ayni_kova = CELISKI = 0
    celiskiler, caprazlar = [], []
    cift_say = collections.Counter()
    for h, g in coklu.items():
        siniflar = sorted({s for s, _ in g})
        kovalar = {SINIF_ADI[s][0] for s in siniflar}
        if len(siniflar) == 1:
            ayni_sinif += 1
        elif len(kovalar) == 1:
            capraz_ayni_kova += 1
            caprazlar.append(g)
            for a in siniflar:
                for b in siniflar:
                    if a < b:
                        cift_say[(a, b)] += 1
        else:
            CELISKI += 1
            celiskiler.append(g)
            for a in siniflar:
                for b in siniflar:
                    if a < b:
                        cift_say[(a, b)] += 1

    print()
    print("GRUP TURLERI")
    print("  ayni sinif icinde tekrar          : %-4d  (zararsiz, yalniz fazlalik)" % ayni_sinif)
    print("  FARKLI SINIF / ayni kova          : %-4d  (etiket cakismasi)" % capraz_ayni_kova)
    print("  GUVENLI <-> GUVENSIZ CELISKISI    : %-4d  (AYNI VIDEO hem guvenli hem degil)" % CELISKI)

    print()
    print("CAKISAN SINIF CIFTLERI (kac mukerrer grup)")
    for (a, b), n in cift_say.most_common():
        ka, na = SINIF_ADI[a]
        kb, nb = SINIF_ADI[b]
        bayrak = "  <<< CELISKI" if ka != kb else ""
        print("  %-8s(%-9s) <-> %-8s(%-9s)  %3d%s" % (a, ka, b, kb, n, bayrak))

    if celiskiler:
        print()
        print("GUVENLI/GUVENSIZ CELISKILERI (tam liste)")
        for g in celiskiler:
            print("   " + "  ==  ".join("%s/%s [%s]" % (s, f, SINIF_ADI[s][0])
                                        for s, f in sorted(g)))

    # --- CIFT BAZLI METRIGE ETKI ---
    print()
    print("CIFT BAZLI METRIGE ETKI  (ayni icerik ciftin IKI tarafinda mi?)")
    print("%-34s%10s%10s%12s" % ("cift", "ihlal n", "normal n", "ZEHIRLI"))
    for gs, gv in KARSIT.items():
        ihl = {ozet_ for ozet_, g in gruplar.items()
               if any(s == gs for s, _ in g)}
        nrm = {ozet_ for ozet_, g in gruplar.items()
               if any(s == gv for s, _ in g)}
        ortak = ihl & nrm
        ad = SINIF_ADI[gs][1] + " / " + SINIF_ADI[gv][1]
        print("%-34s%10d%10d%12d" % (ad[:34], len(ihl), len(nrm), len(ortak)))

    # --- EGITIM/TEST AYRIMI DELINDI MI ---
    print()
    print("EGITIM/TEST AYRIMI  (ayni icerik hem _tr hem _te'de mi?)")
    delik = 0
    for h, g in coklu.items():
        tr = any("_tr" in f for _, f in g)
        te = any("_te" in f for _, f in g)
        if tr and te:
            delik += 1
    print("  hem _tr hem _te'de gorunen icerik: %d grup" % delik)

    cikti = {
        "benzersiz": len(gruplar), "mukerrer_grup": len(coklu),
        "fazladan_kopya": fazla, "ayni_sinif": ayni_sinif,
        "capraz_ayni_kova": capraz_ayni_kova, "celiski": CELISKI,
        "gruplar": [[list(x) for x in sorted(g)] for g in coklu.values()],
    }
    yol = os.path.join(KOK, "benchmark", "results", "veri_kusuru_denetimi.json")
    json.dump(cikti, open(yol, "w", encoding="utf-8"), ensure_ascii=False)
    print()
    print("kaydedildi: " + os.path.relpath(yol, KOK))
    return 0


if __name__ == "__main__":
    sys.exit(main())
