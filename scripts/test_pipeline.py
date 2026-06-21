#!/usr/bin/env python
"""Video -> kare cikarma -> segment -> VLM analiz zincirini dogrular (entegrasyon testi)."""
from __future__ import annotations

import json
import os
import time

from dilajan.config import settings
from dilajan.llm_client import VLMClient
from dilajan.prompts import SEGMENT_ANALYSIS_INSTRUCTION
from dilajan.utils import extract_json
from dilajan.video import build_segments, extract_timestamped_frames

import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
VIDEO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PROJECT_ROOT, "data", "test_clip.mp4")


def main() -> None:
    print(">> Kareler cikariliyor...")
    frames, info = extract_timestamped_frames(VIDEO)
    print(f"   süre={info.duration_str}  fps={info.fps:.1f}  örnek_kare={info.sampled_frames}  çözünürlük={info.width}x{info.height}")

    segments = build_segments(frames)
    print(f">> {len(segments)} segment olusturuldu")
    for s in segments:
        print(f"   segment {s.index}: {s.start_str}-{s.end_str}  ({len(s.frames)} kare)")

    client = VLMClient()
    assert client.health_check(), "vLLM sunucusu erisilemez!"

    print("\n>> Her segment analiz ediliyor...")
    t0 = time.time()
    all_events = []
    for s in segments:
        instr = SEGMENT_ANALYSIS_INSTRUCTION.format(start=s.start_str, end=s.end_str)
        raw = client.analyze_frames(s.frames, instr, max_tokens=512)
        print(f"   --- segment {s.index} HAM ÇIKTI ---\n{raw[:600]}\n   --- son ---")
        try:
            data = extract_json(raw)
            evs = data.get("events", [])
        except Exception as e:
            print(f"   [segment {s.index}] JSON ayristirilamadi: {e}\n   ham: {raw[:200]}")
            evs = []
        for e in evs:
            print(f"   [{e.get('time')}] {e.get('event')}  ({e.get('severity')}/{e.get('category')})")
        all_events.extend(evs)
    print(f"\n>> Toplam {len(all_events)} olay, {time.time()-t0:.1f}s")
    print("PIPELINE_OK")


if __name__ == "__main__":
    main()
