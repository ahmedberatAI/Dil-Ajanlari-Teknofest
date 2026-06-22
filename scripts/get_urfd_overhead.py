#!/usr/bin/env python
"""G8: URFD (UR Fall Detection) cam1 = TAVAN/overhead kamera dusme klipleri indirir + mp4'e cevirir.

GMDCSA (frontal ev-webcam) acigini kapatir: URFD cam1 gercek bir GOZETIM/tavan acisindandir.
Falls simule (acted) ama kamera-montaji gercek surveillance gorusudur. Lisans: CC-BY-NC-SA (arastirma).
PNG dizisi -> mp4 (ffmpeg). Cikti: data/falls_surveillance/Fall/urfd_fallNN.mp4

Kullanim:  N=6 python scripts/get_urfd_overhead.py
"""
from __future__ import annotations

import glob
import os
import subprocess
import tempfile
import urllib.request
import zipfile

BASE = "https://fenix.ur.edu.pl/mkepski/ds/data/"
OUT = os.path.join("data", "falls_surveillance", "Fall")
N = int(os.environ.get("N", "6"))


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    made = 0
    for i in range(1, N + 1):
        n = f"{i:02d}"
        z = f"fall-{n}-cam1-rgb.zip"
        out_mp4 = os.path.join(OUT, f"urfd_fall{n}.mp4")
        if os.path.exists(out_mp4):
            made += 1
            continue
        tmp = tempfile.mkdtemp()
        zp = os.path.join(tmp, z)
        try:
            urllib.request.urlretrieve(BASE + z, zp)
            with zipfile.ZipFile(zp) as zf:
                zf.extractall(tmp)
        except Exception as e:
            print(f"  dl/extract hata {n}: {e}", flush=True)
            continue
        pngs = sorted(glob.glob(os.path.join(tmp, "**", "*.png"), recursive=True))
        if not pngs:
            print(f"  png yok {n}", flush=True)
            continue
        seq = os.path.join(tmp, "seq")
        os.makedirs(seq, exist_ok=True)
        for k, p in enumerate(pngs):
            os.symlink(os.path.abspath(p), os.path.join(seq, f"f{k:05d}.png"))
        r = subprocess.run(
            ["ffmpeg", "-y", "-framerate", "15", "-i", os.path.join(seq, "f%05d.png"),
             "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", out_mp4],
            capture_output=True,
        )
        if os.path.exists(out_mp4):
            print(f"  yapildi: {out_mp4} ({len(pngs)} kare)", flush=True)
            made += 1
        else:
            print(f"  ffmpeg hata {n}: {r.stderr.decode()[-200:]}", flush=True)
    print(f"DONE: {made} overhead dusme klibi -> {OUT}")


if __name__ == "__main__":
    main()
