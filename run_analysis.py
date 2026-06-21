#!/usr/bin/env python
"""Komut satiri: bir videoyu analiz eder ve yapilandirilmis JSON uretir.

Kullanim:
    python run_analysis.py data/test_clip.mp4
    python run_analysis.py data/test_clip.mp4 --sartname --json outputs/sonuc.json
"""
from __future__ import annotations

import argparse
import json
import os
import time

from dilajan.agent import analyze_video
from dilajan.config import OUTPUT_DIR


def main() -> None:
    ap = argparse.ArgumentParser(description="Video analiz ve karar destek ajani")
    ap.add_argument("video", help="Analiz edilecek video dosyasi")
    ap.add_argument("--json", dest="json_path", help="Sonucu bu dosyaya yaz")
    ap.add_argument("--sartname", action="store_true",
                    help="Sade sartname formatinda cikti (summary/events/risk/actions)")
    args = ap.parse_args()

    if not os.path.exists(args.video):
        raise SystemExit(f"Video bulunamadi: {args.video}")

    t0 = time.time()
    result = analyze_video(args.video)
    elapsed = time.time() - t0

    out = result.to_sartname_dict() if args.sartname else result.model_dump()
    text = json.dumps(out, ensure_ascii=False, indent=2)
    print(text)
    print(f"\n[analiz suresi: {elapsed:.1f}s]")

    if args.json_path:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_path)) or ".", exist_ok=True)
        with open(args.json_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[kaydedildi: {args.json_path}]")


if __name__ == "__main__":
    main()
