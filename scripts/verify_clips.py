#!/usr/bin/env python
"""Klip dogrulayici: bir dizindeki videolarin GERCEK video mu yoksa DONMUS
(hareketsiz/tek-kare-dongusu) mu oldugunu PyAV ile olcup raporlar.

NEDEN (denetim bulgusu K8): ``data/eval_scenario/Fall`` altindaki 8 "dusme"
klibi aslinda VIDEO DEGILDI -- ``get_lying.py`` tek bir PNG'yi
``ffmpeg -loop 1 -t 3 -r 5`` ile sarmalayarak uretmisti: 1024x1024, 3.0 sn,
5 fps ve KARELER ARASI SIFIR degisim. Bir VLM boyle bir klipte "dusme"
tespiti yapamaz; yalnizca tek bir fotografi betimler. Bu betik boyle
kliplerin degerlendirme setine sizmasini KANITLA engellemek icin yazildi.

OLCULEN METRIKLER
  sure (sn), fps, cozunurluk, kare sayisi
  motion_mean : ardisik kareler arasindaki ortalama mutlak fark (0-255 olcegi)
  motion_max  : en buyuk kare-arasi fark
  uniq_frames : birbirinden farkli (hash'i ayri) kare sayisi

KARAR (--strict esikleri, ortam degiskeniyle ayarlanabilir)
  DONMUS  : motion_max < MOTION_EPS (varsayilan 0.5) veya uniq_frames <= 1
  KISA    : sure < MIN_SEC (varsayilan 3.0)
  DUSUK-FPS: fps < MIN_FPS (varsayilan 10)

Kullanim:
  python scripts/verify_clips.py data/eval_scenario/Fall
  python scripts/verify_clips.py data/eval_scenario/Fall data/falls_real/Fall --strict
  MAX_FRAMES=60 python scripts/verify_clips.py data/eval_scenario/Fall --json

NOT: PyAV gerekir (WSL venv'inde kurulu). GPU/model GEREKTIRMEZ.
  wsl.exe -d Ubuntu-24.04 -- /home/omen/teknofest/.venv/bin/python scripts/verify_clips.py <dizin>
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys

MIN_SEC = float(os.environ.get("MIN_SEC", "3.0"))
MIN_FPS = float(os.environ.get("MIN_FPS", "10"))
MOTION_EPS = float(os.environ.get("MOTION_EPS", "0.5"))
MAX_FRAMES = int(os.environ.get("MAX_FRAMES", "48"))
EXTS = (".mp4", ".avi", ".mkv", ".mov", ".webm")


def probe(path: str) -> dict:
    """Tek klibi coz ve olcum sozlugu dondur (FAIL-OPEN: hata -> {'error': ...})."""
    try:
        import av  # gec import: PyAV yoksa yalnizca bu fonksiyon patlasin
        import numpy as np
    except Exception as e:  # pragma: no cover - ortam bagimli
        return {"path": path, "error": f"PyAV/numpy yok: {e}"}

    info: dict = {"path": path, "boyut_mb": round(os.path.getsize(path) / 1e6, 2)}
    try:
        with av.open(path) as c:
            st = c.streams.video[0]
            info["fps"] = round(float(st.average_rate or 0), 2)
            info["genislik"] = st.codec_context.width
            info["yukseklik"] = st.codec_context.height
            dur = float(c.duration / 1e6) if c.duration else 0.0
            if not dur and st.duration and st.time_base:
                dur = float(st.duration * st.time_base)
            info["sure_sn"] = round(dur, 2)

            prev = None
            diffs: list[float] = []
            hashes: set[str] = set()
            n = 0
            for frame in c.decode(video=0):
                arr = frame.to_ndarray(format="gray")
                # buyuk kareleri kucult -> hiz; hareket olcusu icin yeterli
                small = arr[::4, ::4].astype("int16")
                hashes.add(hashlib.md5(small.tobytes()).hexdigest())
                if prev is not None:
                    diffs.append(float(np.abs(small - prev).mean()))
                prev = small
                n += 1
                if n >= MAX_FRAMES:
                    break
            info["kare"] = n
            info["uniq_frames"] = len(hashes)
            info["motion_mean"] = round(sum(diffs) / len(diffs), 4) if diffs else 0.0
            info["motion_max"] = round(max(diffs), 4) if diffs else 0.0
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return info


def classify(info: dict) -> tuple[bool, list[str]]:
    """Olcumlerden (gecti_mi, uyari_listesi) uret."""
    if info.get("error"):
        return False, [f"COZULEMEDI ({info['error']})"]
    warn: list[str] = []
    if info.get("uniq_frames", 0) <= 1 or info.get("motion_max", 0.0) < MOTION_EPS:
        warn.append("DONMUS (kare-arasi hareket ~0)")
    if info.get("sure_sn", 0.0) < MIN_SEC:
        warn.append(f"KISA (<{MIN_SEC}sn)")
    if info.get("fps", 0.0) < MIN_FPS:
        warn.append(f"DUSUK-FPS (<{MIN_FPS})")
    return (not warn), warn


def collect(targets: list[str]) -> list[str]:
    """Dizin/dosya/glob karisimindan video yollari topla."""
    out: list[str] = []
    for t in targets:
        if os.path.isdir(t):
            for e in EXTS:
                out.extend(glob.glob(os.path.join(t, "**", "*" + e), recursive=True))
        else:
            out.extend(glob.glob(t))
    return sorted(set(p for p in out if p.lower().endswith(EXTS)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="+", help="dizin(ler) / dosya(lar) / glob")
    ap.add_argument("--json", action="store_true", help="ham olcumleri JSON olarak bas")
    ap.add_argument("--strict", action="store_true", help="uyari varsa cikis kodu 1 olsun")
    args = ap.parse_args()

    paths = collect(args.targets)
    if not paths:
        print("video bulunamadi", flush=True)
        return 0

    rows = []
    n_bad = 0
    hdr = f"{'dosya':<34}{'sure':>7}{'fps':>7}{'cozunurluk':>13}{'kare':>6}{'uniq':>6}{'mot_mean':>10}{'mot_max':>9}  durum"
    if not args.json:
        print(hdr, flush=True)
        print("-" * len(hdr), flush=True)
    for p in paths:
        info = probe(p)
        ok, warn = classify(info)
        info["gecti"] = ok
        info["uyarilar"] = warn
        rows.append(info)
        if not ok:
            n_bad += 1
        if not args.json:
            print(f"{os.path.basename(p):<34}{info.get('sure_sn', 0):>7}{info.get('fps', 0):>7}"
                  f"{str(info.get('genislik', '?')) + 'x' + str(info.get('yukseklik', '?')):>13}"
                  f"{info.get('kare', 0):>6}{info.get('uniq_frames', 0):>6}"
                  f"{info.get('motion_mean', 0):>10}{info.get('motion_max', 0):>9}  "
                  f"{'OK' if ok else ' | '.join(warn)}", flush=True)
    if args.json:
        print(json.dumps(rows, indent=1, ensure_ascii=False))
    else:
        print(f"\nTOPLAM {len(paths)} klip | GERCEK VIDEO {len(paths)-n_bad} | SORUNLU {n_bad}", flush=True)
    return 1 if (args.strict and n_bad) else 0


if __name__ == "__main__":
    sys.exit(main())
