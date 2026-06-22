#!/usr/bin/env python
"""Temporal lokalizasyon olcumu: kontrollu kompozit kliplerde (normal->olay->normal)
ajan olayi DOGRU zaman penceresine yerlestiriyor mu? TIoU + pencere-ici/disi sayar."""
import json
import os
import sys

sys.path.insert(0, ".")
from dilajan.agent import analyze_video  # noqa: E402

SEVORD = {"Düşük": 1, "Orta": 2, "Yüksek": 3, "Kritik": 4}


def secs(mmss: str) -> int:
    try:
        m, s = str(mmss).split(":")
        return int(m) * 60 + int(s)
    except Exception:
        return 0


def main():
    W = json.load(open(os.path.join("data", "temporal", "windows.json"), encoding="utf-8"))
    tious = []
    for name, info in W.items():
        path = os.path.join("data", "temporal", name)
        r = analyze_video(path)
        es, ee = info["event_start"], info["event_end"]
        hits = sorted(secs(e.time) for e in r.events if SEVORD.get(e.severity.value, 0) >= 3)
        in_win = [t for t in hits if es <= t <= ee]
        out_win = [t for t in hits if t < es or t > ee]
        loc = "EVET" if (in_win and not out_win) else ("KISMEN" if in_win else "HAYIR")
        print(f"\n{name}  (kaynak: {info['event_source']})")
        print(f"  gerçek olay penceresi: [{es},{ee}]s  |  yüksek-sev olay zamanları: {hits}")
        print(f"  pencere-içi={len(in_win)}  pencere-dışı(yanlış)={len(out_win)}  -> doğru-lokalizasyon: {loc}")
        if hits:
            pmin, pmax = min(hits), max(hits)
            inter = max(0, min(pmax, ee) - max(pmin, es))
            union = max(pmax, ee) - min(pmin, es)
            tiou = inter / union if union > 0 else (1.0 if pmin == es and pmax == ee else 0.0)
            tious.append(tiou)
            print(f"  tahmini pencere: [{pmin},{pmax}]s  |  TIoU={tiou:.2f}")
    if tious:
        print(f"\n=== Ortalama TIoU: {sum(tious)/len(tious):.2f}  (n={len(tious)}) ===")


if __name__ == "__main__":
    main()
