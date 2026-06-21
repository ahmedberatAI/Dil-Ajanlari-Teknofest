#!/usr/bin/env python
"""Qwen3-VL mekansal grounding (bbox) yetenegini ve koordinat formatini test eder."""
import sys
sys.path.insert(0, ".")
from dilajan.llm_client import VLMClient
from dilajan.video import build_segments, extract_timestamped_frames

C = VLMClient()
TESTS = [
    ("data/eval_scenario/Fire/posVideo4.873.avi", "yangın/alev/duman"),
    ("data/eval_scenario/Fall/lying15.mp4", "yerde yatan/hareketsiz kişi"),
]
for path, what in TESTS:
    frames, info = extract_timestamped_frames(path, fps_sample=2)
    seg = build_segments(frames)[0]
    mid = seg.frames[len(seg.frames) // 2: len(seg.frames) // 2 + 1]  # tek temsili kare
    q = (f"Bu güvenlik kamerası karesinde {what} NEREDE konumlanmış? "
         "Konumu sınırlayıcı kutu (bounding box) olarak JSON ver: "
         '[{"bbox_2d":[x1,y1,x2,y2],"label":"..."}]. Sadece JSON döndür.')
    out = C.analyze_frames(mid, q, max_tokens=200)
    print(f"=== {path.split('/')[-1]} ({info.width}x{info.height}, kare ~{len(seg.frames)} -> 1) ===")
    print(out.strip()[:300])
    print()
