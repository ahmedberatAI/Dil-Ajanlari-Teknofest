#!/usr/bin/env python
"""W1 teshis: normal kliplerde halusinasyonun kaynagini gosterir.
Her segment icin: ham TARIF (describe) + cikarilan OLAYLAR (extract).
Boylece halusinasyon describe asamasinda mi yoksa extraction'da mi doguyor anlasilir."""
import sys
sys.path.insert(0, ".")
from dilajan import prompts
from dilajan.llm_client import VLMClient
from dilajan.utils import extract_json
from dilajan.video import build_segments, extract_timestamped_frames

C = VLMClient()
CLIPS = [
    "data/eval/Normal/Normal_Videos_929_x264.mp4",
    "data/eval/Normal/Normal_Videos_943_x264.mp4",
    "data/eval_scenario/Normal/4_tr13.mp4",
]
for path in CLIPS:
    try:
        frames, _ = extract_timestamped_frames(path)
        segs = build_segments(frames)
    except Exception as e:
        print("###", path, "HATA:", e); continue
    print(f"### {path.split('/')[-1]}  ({len(segs)} segment)")
    for seg in segs:
        desc = C.analyze_frames(
            seg.frames,
            prompts.SEGMENT_DESCRIBE_INSTRUCTION.format(start=seg.start_str, end=seg.end_str),
            temperature=0.2, max_tokens=400,
        )
        ext = C.chat(
            [{"role": "system", "content": prompts.SYSTEM_PERSONA},
             {"role": "user", "content": prompts.EVENT_EXTRACTION_INSTRUCTION.format(
                 description=desc, start=seg.start_str, end=seg.end_str)}],
            temperature=0.1, max_tokens=400,
        )
        try:
            evs = extract_json(ext).get("events", [])
        except Exception:
            evs = []
        print(f"  [{seg.start_str}] TARIF: {desc.strip()[:180]}")
        print(f"        OLAYLAR: {[(str(e.get('event',''))[:48], e.get('severity')) for e in evs]}")
    print()
