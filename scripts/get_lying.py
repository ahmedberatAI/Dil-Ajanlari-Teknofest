#!/usr/bin/env python
"""Simuletic CCTV 'yatan/hareketsiz kisi' gorsellerini indirir ve kisa STATIK mp4'lere
cevirir (hareketsiz kisi dogasi geregi statik; analyze_video/eval ile uyumlu).
Cikti: data/eval_scenario/Fall/lyingNN.mp4
"""
from __future__ import annotations

import os
import subprocess
import urllib.request

H = {"User-Agent": "Mozilla/5.0"}
BASE = ("https://huggingface.co/datasets/Simuletic/CCTV_Incident_Dataset_Fall_Lying_Down_Detection"
        "/resolve/main/laying_dataset/images/")
IMG_DIR = os.path.join("data", "scenario", "lying")
VID_DIR = os.path.join("data", "eval_scenario", "Fall")
IDXS = [1, 15, 30, 45, 60, 75, 90, 99]


def main() -> None:
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(VID_DIR, exist_ok=True)
    n = 0
    for i in IDXS:
        name = f"laying{i:02d}.png"
        png = os.path.join(IMG_DIR, name)
        mp4 = os.path.join(VID_DIR, f"lying{i:02d}.mp4")
        if not os.path.exists(png):
            try:
                req = urllib.request.Request(BASE + name + "?download=true", headers=H)
                with urllib.request.urlopen(req, timeout=90) as r, open(png, "wb") as w:
                    w.write(r.read())
            except Exception as e:
                print(f"indirme hatasi {name}: {str(e)[:60]}", flush=True)
                continue
        if not os.path.exists(mp4):
            # statik gorseli 3sn'lik mp4'e cevir (5 fps yeterli)
            subprocess.run(
                ["ffmpeg", "-y", "-loop", "1", "-i", png, "-t", "3", "-r", "5",
                 "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", mp4],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        if os.path.exists(mp4):
            n += 1
            print(f"hazir: {mp4}", flush=True)
    print(f"BITTI: {n} statik dusme klibi -> {VID_DIR}", flush=True)


if __name__ == "__main__":
    main()
