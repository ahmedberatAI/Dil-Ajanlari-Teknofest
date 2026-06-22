#!/usr/bin/env python
"""Tum kayitli eval ciktilarini (klip basina EN YENI) konsolide eder + sikintili cevaplari isaretler.

Bayraklar:
  MISS        anomali klibinde olay yok (recall acigi)
  FP          normal klipte olay uretildi (sev/tetik ile)
  KAT?        anomali ama kategori-eslesme yok
  DOMAIN?     fabrika-disi sahnede 'fabrika/uretim/forklift/isci' gecmesi (domain-varsayim halusinasyonu)
  KISI?       'yere dusmus/hareketsiz kisi/isci' (gercek insan yoksa halusinasyon olabilir -> elle bak)

Kullanim:  python scripts/audit_outputs.py            # bugunku tum eval_*.json
           python scripts/audit_outputs.py 20260622   # belirli tarih oneki
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "benchmark", "results")
date = sys.argv[1] if len(sys.argv) > 1 else "20260622"

# fabrika-baglamiNIN GECERLI oldugu setler (yol icinde)
FACTORY_OK = ("industrial",)
FACTORY_TERMS = re.compile(r"fabrika|üretim hatt|uretim hatt|forklift|işçi|isci|tezgah|konveyör|konveyor|montaj")
PERSON_FALL = re.compile(r"(yere düş|yere dus|yerde hareketsiz|hareketsiz yat|yere yığıl|yere yigil|yere seril|hareketsiz kal)")


def texts(row):
    out = [row.get("summary", ""), row.get("risk_rationale", "")]
    for e in row.get("events", []):
        out.append(e.get("event", ""))
    return " ".join(t for t in out if t)


def main():
    files = sorted(glob.glob(os.path.join(RES, f"eval_{date}_*.json")))  # eski->yeni
    if not files:
        print("eval dosyasi yok")
        return
    # klip basina EN YENI calismayi tut (yeni dosya onceligi)
    latest = {}
    for f in files:
        try:
            rows = json.load(open(f, encoding="utf-8")).get("rows", [])
        except Exception:
            continue
        for r in rows:
            latest[r["path"]] = r  # sonraki (daha yeni) dosya ezer
    rows = list(latest.values())

    flags = {"MISS": [], "FP": [], "KAT?": [], "DOMAIN?": [], "KISI?": []}
    clean = 0
    for r in rows:
        path = r["path"]
        is_anom = r.get("is_anomaly")
        nev = r.get("n_events", 0)
        txt = texts(r).lower()
        is_factory_set = any(k in path for k in FACTORY_OK)
        is_fall_set = ("fall" in path.lower()) or ("falls" in path.lower())
        row_flags = []
        if is_anom and nev == 0:
            row_flags.append("MISS")
        if (not is_anom) and nev > 0:
            row_flags.append("FP")
        if is_anom and r.get("category_match") is False:
            row_flags.append("KAT?")
        if (not is_factory_set) and FACTORY_TERMS.search(txt):
            row_flags.append("DOMAIN?")
        if (not is_fall_set) and PERSON_FALL.search(txt):
            row_flags.append("KISI?")
        if not row_flags:
            clean += 1
            continue
        for fl in row_flags:
            flags[fl].append(r)

    print("=" * 70)
    print(f"DENETİM — {len(rows)} benzersiz klip · temiz={clean} · bayrakli={len(rows)-clean}")
    print("=" * 70)
    for fl, items in flags.items():
        print(f"\n### {fl}  ({len(items)})")
        for r in items[:40]:
            ev = "; ".join(f"[{e.get('time')}]{e.get('severity','')[:1]} {e.get('event','')}" for e in r.get("events", [])) or "(olay yok)"
            print(f"  · {os.path.basename(r['path'])}  [{r.get('category')}] risk={r.get('risk_level')}")
            print(f"      olaylar: {ev[:200]}")
            if fl in ("DOMAIN?", "KISI?", "FP"):
                print(f"      özet: {(r.get('summary') or '')[:160]}")


if __name__ == "__main__":
    main()
