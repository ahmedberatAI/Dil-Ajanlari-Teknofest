#!/usr/bin/env python
"""Temporal lokalizasyon testi icin KONTROLLU kompozit klipler kurar:
normal(15s) + OLAY(15s) + normal(15s) = 45s; gercek olay penceresi [15s, 30s].
Boylece ajanin olayi DOGRU zaman penceresine yerlestirip yerlestirmedigi olculur.

Cikti: data/temporal/<isim>.mp4  + data/temporal/windows.json (gercek pencereler)
"""
from __future__ import annotations

import json
import os
import subprocess

OUT = os.path.join("data", "temporal")
SEG = 15  # her parca saniye
# (isim, normal1, olay_klibi, normal2)
COMPS = [
    ("comp_fire", "data/industrial/class0/0_tr128.mp4", "data/eval_scenario/Fire/posVideo4.873.avi", "data/industrial/class6/6_te12.mp4"),
    ("comp_explosion", "data/industrial/class6/6_te12.mp4", "data/ucf_explosion.mp4", "data/industrial/class0/0_tr128.mp4"),
]


def _dur(path):
    import av
    c = av.open(path)
    s = c.streams.video[0]
    d = float(s.duration * s.time_base) if s.duration else SEG
    c.close()
    return d


def build(name, n1, ev, n2):
    """Her parcayi tam SEG saniyeye SABITLER (kisa kaynak tpad ile son kareyi dondurarak uzatilir),
    boylece gercek olay penceresi tam [SEG, 2*SEG] olur."""
    out = os.path.join(OUT, name + ".mp4")
    pad = f"tpad=stop_mode=clone:stop_duration={SEG}"  # kisa parcayi SEG'e tamamla
    fc = (
        f"[0:v]trim=0:{SEG},{pad},scale=640:360,setsar=1,setpts=PTS-STARTPTS[a];"
        f"[1:v]trim=0:{SEG},{pad},scale=640:360,setsar=1,setpts=PTS-STARTPTS[b];"
        f"[2:v]trim=0:{SEG},{pad},scale=640:360,setsar=1,setpts=PTS-STARTPTS[c];"
        f"[a][b][c]concat=n=3:v=1[out]"
    )
    cmd = ["ffmpeg", "-y", "-i", n1, "-i", ev, "-i", n2,
           "-filter_complex", fc, "-map", "[out]", "-r", "25", "-an", out]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    windows = {}
    for name, n1, ev, n2 in COMPS:
        try:
            out = build(name, n1, ev, n2)
            windows[name + ".mp4"] = {"event_start": SEG, "event_end": 2 * SEG, "total": 3 * SEG,
                                      "event_source": ev.split("/")[-1]}
            print(f"kuruldu: {out}  | gercek olay penceresi [{SEG}s,{2*SEG}s]")
        except Exception as e:
            print(f"hata {name}: {e}")
    with open(os.path.join(OUT, "windows.json"), "w", encoding="utf-8") as f:
        json.dump(windows, f, ensure_ascii=False, indent=2)
    print("pencereler:", os.path.join(OUT, "windows.json"))


if __name__ == "__main__":
    main()
