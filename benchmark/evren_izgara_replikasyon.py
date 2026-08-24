#!/usr/bin/env python
"""D42 — ESKI COZUNURLUK TARAMASI ile YENI IZGARA'nin KLIP KLIP KARSILASTIRMASI.

NEDEN: devir notundaki en kritik iddia
    "yelek 768->1280: MCC 0,000 -> 0,560 · McNemar p=0,0013 · 16 duzeldi/2 bozuldu"
Bu iddia, tum gorevin gerekcesiydi ("cozunurluk yelek sinifinda BELIRLEYICI").
Yeni izgarada AYNI model (llm-large) AYNI cozunurlukte (1280) hala 44/50 klipte
"GORUNMUYOR" diyor. Iki olcum AYNI kliplerde AYNI soruyu sordugunu iddia ediyor;
o halde ham cevaplar KLIP KLIP karsilastirilmali.

    python benchmark/evren_izgara_replikasyon.py
"""
from __future__ import annotations

import collections
import json
import os

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESKI = os.path.join(KOK, "benchmark/results/evren_cozunurluk_ham_20260824_120530.jsonl")
YENI = os.path.join(KOK, "benchmark/results/evren_izgara_20260824_122459.jsonl")
MODEL = "llm-large"        # eski tarama YALNIZ bu modelle yapilmisti


def main():
    eski = collections.defaultdict(dict)      # (sinif,coz) -> klip -> cevap
    for l in open(ESKI, encoding="utf-8"):
        r = json.loads(l)
        eski[(r["sinif"], r["max_side"])][r["klip"]] = (r.get("cevap") or "").strip().upper()

    yeni = collections.defaultdict(dict)
    for l in open(YENI, encoding="utf-8"):
        r = json.loads(l)
        if r.get("model") != MODEL or r.get("ham_cevap") is None:
            continue
        yeni[(r["sinif"], r["cozunurluk"])][r["klip"]] = r["ham_cevap"].strip().upper()

    print(f"ESKI tarama : {os.path.basename(ESKI)}  (yalniz {MODEL})")
    print(f"YENI izgara : {os.path.basename(YENI)}  ({MODEL} kolu)\n")

    for anahtar in sorted(set(eski) & set(yeni), key=str):
        sinif, coz = anahtar
        ortak = sorted(set(eski[anahtar]) & set(yeni[anahtar]))
        if not ortak:
            continue
        ayni = sum(1 for k in ortak if eski[anahtar][k] == yeni[anahtar][k])
        print(f"=== {sinif}@{coz} · ortak klip {len(ortak)} · "
              f"BIREBIR AYNI {ayni}/{len(ortak)} ({ayni/len(ortak):.0%}) ===")
        de = collections.Counter(eski[anahtar][k] for k in ortak)
        dy = collections.Counter(yeni[anahtar][k] for k in ortak)
        print(f"  ESKI dagilim: {dict(de.most_common())}")
        print(f"  YENI dagilim: {dict(dy.most_common())}")
        farkli = [(k, eski[anahtar][k], yeni[anahtar][k])
                  for k in ortak if eski[anahtar][k] != yeni[anahtar][k]]
        if farkli:
            print(f"  FARKLI {len(farkli)} klip (ilk 12):")
            for k, a, b in farkli[:12]:
                print(f"    {k:16s} eski={a:12s} yeni={b}")
        print()


if __name__ == "__main__":
    main()
