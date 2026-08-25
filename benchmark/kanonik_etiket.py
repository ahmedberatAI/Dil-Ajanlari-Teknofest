#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""KANONIK YER GERCEGI — icerik basina ETIKET KUMESI (kok duzeltme).

KUSUR (2026-08-25 denetimi, `benchmark/veri_kusuru_denetimi.py`):
Kaynak sette 691 dosya var ama yalnizca **658 benzersiz icerik**. 32 mukerrer
grubun HICBIRI ayni sinif icinde degil — hepsi SINIFLAR ARASI:
    class0 <-> class1 : 27 grup   (yaya ihlali + yetkisiz mudahale)
    class0 <-> class4 :  3 grup   <-- GUVENSIZ ile GUVENLI ayni video
    class1 <-> class4 :  1
    class0 <-> class5 :  1
    class1 <-> class2 :  1
    class4 <-> class6 :  1
Ayrica 9 grup hem `_tr` hem `_te` tarafinda -> kaynagin kendi egitim/test
ayrimi DELIK.

KOK SEBEP (goruntulere bakilarak dogrulandi): kaynak etiketler **klip basina
degil DAVRANIS basina**. Ayni videoda makinenin basinda bir operator ve
koridorda yuruyen baska bir kisi olabilir; kaynak seti bunu iki ayri sinifa
iki kopya olarak koymus. `class0`+`class5` CELISKI DEGIL — farkli kisileri
anlatiyorlar.

COZUM — tahmin YOK:
  1. Icerik (sha256) basina ETIKET KUMESI kurulur.
  2. Kova: kumede GUVENSIZ etiket varsa icerik GUVENSIZDIR.
  3. Cift uyeligi: bir icerik, ciftin GUVENSIZ sinifini tasiyorsa POZITIF;
     yalnizca GUVENLI sinifini tasiyorsa NEGATIF; IKISINI DE tasiyorsa
     o ciftten DISLANIR (temiz negatif olamaz).
  4. Ayrim: herhangi bir kopyasi `_te` ise icerik TESTE gider (test kirlenmesin).

Cikti: benchmark/results/kanonik_etiket.json

Kullanim:  python benchmark/kanonik_etiket.py
"""
from __future__ import annotations

import collections
import glob
import hashlib
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAYNAK = os.path.join(KOK, "data", "industrial")

SINIF = {
    "class0": ("GUVENSIZ", "Safe_Walkway_Violation"),
    "class1": ("GUVENSIZ", "Unauthorized_Intervention"),
    "class2": ("GUVENSIZ", "Opened_Panel_Cover"),
    "class3": ("GUVENSIZ", "Carrying_Overload_with_Forklift"),
    "class4": ("GUVENLI", "Safe_Walkway"),
    "class5": ("GUVENLI", "Authorized_Intervention"),
    "class6": ("GUVENLI", "Closed_Panel_Cover"),
    "class7": ("GUVENLI", "Safe_Carrying"),
}
CIFT = [("class0", "class4"), ("class1", "class5"),
        ("class2", "class6"), ("class3", "class7")]


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
    dosyalar = sorted(glob.glob(os.path.join(KAYNAK, "class*", "*.mp4")))
    if not dosyalar:
        print("kaynak yok: " + KAYNAK)
        return 1
    print("taranan dosya: %d" % len(dosyalar))

    icerik = collections.defaultdict(lambda: {"etiketler": set(), "dosyalar": []})
    for p in dosyalar:
        s = os.path.basename(os.path.dirname(p))
        h = ozet(p)
        icerik[h]["etiketler"].add(s)
        icerik[h]["dosyalar"].append(os.path.relpath(p, KOK).replace("\\", "/"))

    print("benzersiz icerik: %d" % len(icerik))

    kayit = {}
    for h, d in icerik.items():
        et = sorted(d["etiketler"])
        kova = "GUVENSIZ" if any(SINIF[e][0] == "GUVENSIZ" for e in et) else "GUVENLI"
        # AYRIM: herhangi bir kopya _te ise TEST (test kirlenmesin)
        ayrim = "te" if any("_te" in os.path.basename(f) for f in d["dosyalar"]) else "tr"
        # TEMSILCI dosya: guvensiz sinif oncelikli, sonra en kucuk sinif no
        oncelik = sorted(et, key=lambda e: (SINIF[e][0] != "GUVENSIZ", e))
        temsilci = sorted(f for f in d["dosyalar"]
                          if os.path.basename(os.path.dirname(f)) == oncelik[0])[0]
        # CIFT UYELIGI
        cift_uye = {}
        for gs, gl in CIFT:
            var_gs, var_gl = gs in et, gl in et
            if var_gs and var_gl:
                cift_uye[gs] = "DISLANDI"       # temiz negatif OLAMAZ
            elif var_gs:
                cift_uye[gs] = "POZITIF"
            elif var_gl:
                cift_uye[gs] = "NEGATIF"
        kayit[h] = {"etiketler": et, "kova": kova, "ayrim": ayrim,
                    "temsilci": temsilci, "dosyalar": sorted(d["dosyalar"]),
                    "cift": cift_uye}

    # --- OZET ---
    print()
    print("KOVA DAGILIMI")
    kv = collections.Counter(v["kova"] for v in kayit.values())
    for k, n in kv.most_common():
        print("  %-10s %d" % (k, n))
    print()
    print("ETIKET SAYISI (icerik basina)")
    es = collections.Counter(len(v["etiketler"]) for v in kayit.values())
    for n, c in sorted(es.items()):
        print("  %d etiket : %4d icerik" % (n, c))
    print()
    print("AYRIM")
    ay = collections.Counter(v["ayrim"] for v in kayit.values())
    for k, n in sorted(ay.items()):
        print("  %-4s %d" % (k, n))

    print()
    print("CIFT UYELIKLERI  (eski sayilarla yan yana)")
    ESKI = {"class0": (210, 75), "class1": (108, 38),
            "class2": (142, 32), "class3": (56, 30)}
    print("%-34s%12s%12s%10s%14s" %
          ("cift", "POZITIF", "NEGATIF", "DISLANAN", "eski (poz/neg)"))
    for gs, gl in CIFT:
        p = sum(1 for v in kayit.values() if v["cift"].get(gs) == "POZITIF")
        n = sum(1 for v in kayit.values() if v["cift"].get(gs) == "NEGATIF")
        d = sum(1 for v in kayit.values() if v["cift"].get(gs) == "DISLANDI")
        ad = SINIF[gs][1] + " / " + SINIF[gl][1]
        print("%-34s%12d%12d%10d%9d/%-4d"
              % (ad[:34], p, n, d, ESKI[gs][0], ESKI[gs][1]))

    yol = os.path.join(KOK, "benchmark", "results", "kanonik_etiket.json")
    json.dump({"icerik": kayit, "sinif": {k: list(v) for k, v in SINIF.items()},
               "cift": CIFT}, open(yol, "w", encoding="utf-8"), ensure_ascii=False)
    print()
    print("kaydedildi: " + os.path.relpath(yol, KOK))
    return 0


if __name__ == "__main__":
    sys.exit(main())
