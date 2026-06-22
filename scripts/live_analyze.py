#!/usr/bin/env python
"""Canli/akan kamera analizi (kayan-pencere). Yerel; webcam / RTSP / dosya-akisi destekler.

Kaynak her WINDOW saniyede bir tampona alinir, gecici klibe yazilir ve tam ajan
pipeline'i (analyze_video) ile islenir -> o pencere icin risk + zaman-damgali olaylar.

Kullanim:
    python scripts/live_analyze.py 0                 # webcam (0. cihaz)
    python scripts/live_analyze.py rtsp://...         # IP kamera (RTSP)
    python scripts/live_analyze.py data/x.mp4         # dosyayi akis gibi isle (test)
Ortam: WINDOW (sn, vars 12), MAX_WINDOWS (test icin sinir, vars 0=sinirsiz)
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

import cv2  # noqa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan.agent import analyze_video  # noqa: E402


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else "0"
    source = int(src) if src.isdigit() else src
    window = float(os.environ.get("WINDOW", "12"))
    max_win = int(os.environ.get("MAX_WINDOWS", "0"))

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[hata] kaynak açılamadı: {source}"); return
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
    win_frames = max(1, int(window * fps))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    tmp = os.path.join(tempfile.gettempdir(), "dilajan_live_win.mp4")
    print(f"CANLI ANALİZ | kaynak={source} | pencere={window:.0f}s | {w}x{h}@{fps:.0f}fps")

    idx, ended = 0, False
    while not ended:
        vw = cv2.VideoWriter(tmp, fourcc, fps, (w, h))
        n = 0
        while n < win_frames:
            ok, frame = cap.read()
            if not ok:
                ended = True; break
            vw.write(frame); n += 1
        vw.release()
        if n < 3:
            break
        t0 = time.time()
        try:
            r = analyze_video(tmp)
            risk = r.risk.level.value
            print(f"\n⏱  pencere #{idx}  ({n} kare, {time.time()-t0:.0f}s)  →  RİSK: {risk}")
            if r.events:
                for e in r.events:
                    span = f"{e.time}–{e.end_time}" if e.end_time else e.time
                    loc = f" @{e.region}" if e.region else ""
                    print(f"     [{span}] {e.severity.value}: {e.event[:65]}{loc}")
            else:
                print("     (kayda değer olay yok)")
            if r.triggered_functions:
                print(f"     ↳ tetiklenen: {', '.join(r.triggered_functions)}")
        except Exception as ex:
            print(f"  [pencere #{idx} hata] {ex}")
        idx += 1
        if max_win and idx >= max_win:
            break
    cap.release()
    print(f"\nBİTTİ: {idx} pencere işlendi.")


if __name__ == "__main__":
    main()
