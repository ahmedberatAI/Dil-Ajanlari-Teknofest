#!/usr/bin/env python
"""Hedef-domain eval_defense kosum profilleri.

Bu betik model/pipeline davranisini kendiliginden degistirmez; yalnizca
`benchmark/eval_clips.py` icin tekrarlanabilir ortam degiskenleri hazirlar.

Kullanim:
    python scripts/eval_defense_profile.py --profile baseline
    python scripts/eval_defense_profile.py --profile isg
    python scripts/eval_defense_profile.py --profile detectors
    python scripts/eval_defense_profile.py --profile all --cats Anomali,Normal
    python scripts/eval_defense_profile.py --profile all --dry-run
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


PROFILES = {
    "baseline": {
        # Saf mevcut davranis: hedef-domain setinde once bunu kos.
        "DILAJAN_ISG_LENS": "false",
        "DILAJAN_ISG_SLOTLARI": "",
        "DILAJAN_PPE_DETECTION": "false",
        "DILAJAN_PANEL_ROI": "",
        "DILAJAN_FORKLIFT_YUK": "",
    },
    "isg": {
        # Prompt mercegi + yapilandirilmis gozlem duzlemi; varsayilanlara dokunmaz.
        "DILAJAN_ISG_LENS": "true",
        "DILAJAN_ISG_SLOTLARI": "*",
    },
    "detectors": {
        # Deterministik uzmanlar: KKD + pano/forklift ayarlari ancak veri/kalibrasyon
        # hazirsa etkili olur. ROI bos birakilirsa pano dedektoru K2 geregi kapali kalir.
        "DILAJAN_PPE_DETECTION": "true",
        "DILAJAN_PPE_KITS": "baret,yelek",
    },
    "all": {
        "DILAJAN_ISG_LENS": "true",
        "DILAJAN_ISG_SLOTLARI": "*",
        "DILAJAN_PPE_DETECTION": "true",
        "DILAJAN_PPE_KITS": "baret,yelek",
    },
}


def _merged_profile(name: str) -> dict[str, str]:
    if name == "baseline":
        return dict(PROFILES["baseline"])
    out = dict(PROFILES["baseline"])
    out.update(PROFILES[name])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", choices=sorted(PROFILES), default="baseline",
                    help="Kosulacak iyilestirme kolu.")
    ap.add_argument("--cats", default="Anomali,Normal",
                    help="EVAL_CATS degeri. Ornek: Anomali veya Anomali,Normal")
    ap.add_argument("--eval-dir", default=os.path.join("data", "eval_defense"),
                    help="Degerlendirme dizini (varsayilan: data/eval_defense).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Komutu calistirmadan ortam degiskenlerini yazdir.")
    args = ap.parse_args()

    env = dict(os.environ)
    env["DILAJAN_EVAL_DIR"] = args.eval_dir
    env["EVAL_CATS"] = args.cats
    env.update(_merged_profile(args.profile))

    keys = ["DILAJAN_EVAL_DIR", "EVAL_CATS"] + sorted(_merged_profile(args.profile))
    print(f"eval_defense profili: {args.profile}")
    for k in keys:
        print(f"  {k}={env.get(k, '')}")

    cmd = [sys.executable, os.path.join(ROOT, "benchmark", "eval_clips.py")]
    if args.dry_run:
        print("calistirilacak komut: " + " ".join(cmd))
        return 0
    return subprocess.call(cmd, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
