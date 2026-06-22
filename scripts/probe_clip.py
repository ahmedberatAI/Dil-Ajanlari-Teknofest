#!/usr/bin/env python
"""Bir klip icin perceive 'describe' asamasinin ham ciktisini segment-segment yazar.
Kacirilan olaylari teshis icin (model ne goruyor / nasil yorumluyor)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import prompts  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import build_segments, extract_timestamped_frames  # noqa: E402

for path in sys.argv[1:]:
    frames, info = extract_timestamped_frames(path)
    segs = build_segments(frames)
    vlm = VLMClient()
    print(f"\n######## {os.path.basename(path)}  sure={info.duration_str} "
          f"segment={len(segs)} kare={info.sampled_frames} ({info.width}x{info.height}) ########")
    for s in segs:
        instr = prompts.SEGMENT_DESCRIBE_INSTRUCTION.format(start=s.start_str, end=s.end_str)
        desc = vlm.analyze_frames(s.frames, instr, temperature=0.2, max_tokens=400)
        print(f"\n--- segment {s.index} [{s.start_str}-{s.end_str}] {len(s.frames)} kare ---")
        print(desc)
