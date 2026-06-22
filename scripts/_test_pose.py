#!/usr/bin/env python
"""F1 poz-dogrulayici birim testi: comelen isci -> REJECT; gercek dusme -> CONFIRM/ABSTAIN."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import detector  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402

clips = [
    ("comelme/yuruyen (6_te12)", "data/industrial/class6/6_te12.mp4"),
    ("gercek dusme (Subject1_fall01)", "data/falls_real/Fall/Subject1_fall01.mp4"),
    ("gercek dusme (Subject3_fall02)", "data/falls_real/Fall/Subject3_fall02.mp4"),
    ("overhead dusme (urfd_fall01)", "data/falls_surveillance/Fall/urfd_fall01.mp4"),
]
for label, path in clips:
    if not os.path.exists(path):
        print(f"  [yok] {path}")
        continue
    frames, _ = extract_timestamped_frames(path)
    verdict, note = detector.verify_fallen(frames)
    print(f"  {label:34s} -> {verdict:8s} | {note}")
