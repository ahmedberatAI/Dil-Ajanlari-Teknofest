#!/usr/bin/env python
"""Senaryo-uyumlu degerlendirme seti kurar -> data/eval_scenario/<Kategori>/

Kategoriler:
  Fire   : FIRESENSE pozitif (yangin/duman) klipleri
  Normal : yuksek-cozunurluklu endustriyel (mundane fabrika) + UCF normal klipleri
"""
from __future__ import annotations

import glob
import os
import shutil

OUT = os.path.join("data", "eval_scenario")
N_FIRE = int(os.environ.get("N_FIRE", "10"))
N_IND = int(os.environ.get("N_IND", "8"))
N_UCF_NORM = int(os.environ.get("N_UCF_NORM", "4"))


def copy_into(cat: str, srcs: list[str]) -> int:
    d = os.path.join(OUT, cat)
    os.makedirs(d, exist_ok=True)
    n = 0
    for s in srcs:
        dst = os.path.join(d, os.path.basename(s))
        if not os.path.exists(dst):
            shutil.copy(s, dst)
        n += 1
    return n


def main() -> None:
    fire = sorted(glob.glob("data/scenario/_dl/pos/*.avi"))[:N_FIRE]
    ind = sorted(glob.glob("data/industrial/class*/*.mp4"))[:N_IND]
    ucf = sorted(glob.glob("data/eval/Normal/*.mp4"))[:N_UCF_NORM]
    nf = copy_into("Fire", fire)
    nn = copy_into("Normal", ind + ucf)
    print(f"Fire={nf}  Normal={nn} ({len(ind)} endustriyel + {len(ucf)} UCF) -> {OUT}")


if __name__ == "__main__":
    main()
