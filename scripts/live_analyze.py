#!/usr/bin/env python
"""Canli/akan kamera analizi (kayan-pencere, DECODE-ONCE). Yerel; webcam / RTSP / dosya-akisi.

Iyilestirmeler (hizli-kazanim):
  - DECODE-ONCE: kareler cv2 ile bir kez okunur ve DOGRUDAN ajan pipeline'ina verilir
    (eski surumdeki 'gecici mp4'e yaz -> PyAV ile yeniden decode et' gidis-donusu kaldirildi).
  - KAMERA SABOTAJ/DONMA: her pencere once deterministik tamper kontrolunden gecer
    (donma / ortme / karartma) -> VLM'siz GUVENLIK uyarisi (besleme gecersizse VLM'e gitmez).
  - RTSP OTO-YENIDEN-BAGLANMA: akis koparsa ussel-backoff ile yeniden baglanir (7/24 dayaniklilik).

Kullanim:
    python scripts/live_analyze.py 0                 # webcam (0. cihaz)
    python scripts/live_analyze.py rtsp://...        # IP kamera (RTSP)
    python scripts/live_analyze.py data/x.mp4        # dosyayi akis gibi isle (test)
Ortam: WINDOW (sn, vars 12), MAX_WINDOWS (test icin sinir, vars 0=sinirsiz)
"""
from __future__ import annotations

import os
import sys
import time

import cv2  # noqa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan import tamper  # noqa: E402
from dilajan.agent import analyze_prepared  # noqa: E402
from dilajan.config import settings  # noqa: E402
from dilajan.video import build_video_info, timedframes_from_bgr  # noqa: E402


def _open(source):
    return cv2.VideoCapture(source)


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else "0"
    source = int(src) if str(src).isdigit() else src
    is_stream = isinstance(source, str)
    window = float(os.environ.get("WINDOW", "12"))
    max_win = int(os.environ.get("MAX_WINDOWS", "0"))
    fps_sample = settings.fps_sample

    cap = _open(source)
    if not cap.isOpened():
        print(f"[hata] kaynak açılamadı: {source}")
        return
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
    stride = max(1, int(round(fps / max(0.1, fps_sample))))  # decode-once: her stride'da bir kare ornekle
    win_frames = max(1, int(window * fps))
    print(f"CANLI ANALİZ (decode-once) | kaynak={source} | pencere={window:.0f}s | "
          f"{w}x{h}@{fps:.0f}fps | örnek={fps_sample:.1f}fps")

    idx, ended, backoff = 0, False, 1.0
    while not ended:
        sampled, fpos, i = [], 0, 0
        lost = False
        while fpos < win_frames:
            ok, frame = cap.read()
            if not ok:
                if is_stream:
                    lost = True
                else:
                    ended = True
                break
            if fpos % stride == 0:
                sampled.append((frame, i / fps_sample))  # pencere-ici goreli zaman (sn)
                i += 1
            fpos += 1

        if len(sampled) >= 2:
            bgr_list = [f for f, _ in sampled]
            ts_list = [t for _, t in sampled]
            try:
                frames = timedframes_from_bgr(bgr_list, ts_list)
                info = build_video_info(str(source), frames, fps, w, h)
                t0 = time.time()
                # 1) Kamera sabotaj/donma (deterministik) -> besleme gecersizse VLM'e gitme
                tk = tamper.detect_tamper(frames)
                if tk:
                    print(f"\n⏱  pencere #{idx}  →  ⚠️  {tk['kind'].upper()}: {tk['detail']}  (@{tk['time']})")
                else:
                    r = analyze_prepared(frames, info)
                    risk = r.risk.level.value
                    print(f"\n⏱  pencere #{idx}  ({len(sampled)} kare, {time.time()-t0:.0f}s)  →  RİSK: {risk}")
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

        if lost:  # RTSP/akis koptu -> ussel-backoff ile yeniden baglan
            print(f"  [uyarı] akış koptu; {backoff:.0f}s sonra yeniden bağlanılıyor…")
            cap.release()
            time.sleep(min(backoff, 30.0))
            backoff = min(backoff * 2, 30.0)
            cap = _open(source)
            if cap.isOpened():
                backoff = 1.0
        if max_win and idx >= max_win:
            break

    cap.release()
    print(f"\nBİTTİ: {idx} pencere işlendi.")


if __name__ == "__main__":
    main()
