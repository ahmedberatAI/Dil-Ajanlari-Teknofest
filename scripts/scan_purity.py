#!/usr/bin/env python
"""G12: Mevcut tum cikti JSON'larinda Turkce-disi KARAKTER sizintisini olcer.

Yabanci-script (Cince/Japonca/Korece/Kiril/Arapca) net sizintidir. Oran + ornek raporlar.
"""
import glob
import json
import os
import re
import sys

# Latin-disi scriptler (Turkce ç/ğ/ı/ö/ş/ü Latin'dir, sorun degil)
FOREIGN = re.compile(r"[一-鿿぀-ヿ가-힯Ѐ-ӿ؀-ۿ฀-๿]")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def texts_of(row: dict):
    out = [row.get("summary", ""), row.get("risk_rationale", "")]
    for e in row.get("events", []):
        out.append(e.get("event", ""))
    for a in row.get("actions", []):
        out += [a.get("action", ""), a.get("rationale") or ""]
    return [t for t in out if t]


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "benchmark", "results", "eval_*.json")))
    n_text = n_leak = 0
    samples = []
    for f in files:
        try:
            rows = json.load(open(f, encoding="utf-8")).get("rows", [])
        except Exception:
            continue
        for r in rows:
            for t in texts_of(r):
                n_text += 1
                if FOREIGN.search(t):
                    n_leak += 1
                    if len(samples) < 10:
                        samples.append((os.path.basename(f), t[:120]))
    # diyalog
    dp = os.path.join(ROOT, "benchmark", "results", "dialogue_responses.json")
    if os.path.exists(dp):
        d = json.load(open(dp, encoding="utf-8"))
        for it in d.get("single", []) + d.get("multi", []):
            t = it.get("resp", "")
            n_text += 1
            if FOREIGN.search(t):
                n_leak += 1
                if len(samples) < 10:
                    samples.append(("dialogue", t[:120]))
    print(f"Taranan metin: {n_text}")
    print(f"Yabanci-script sizintisi: {n_leak}  (%{100*n_leak/max(n_text,1):.1f})")
    for src, s in samples:
        print(f"  [{src}] {s}")


if __name__ == "__main__":
    main()
