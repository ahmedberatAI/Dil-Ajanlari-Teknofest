#!/usr/bin/env python
"""Bir videonun ilk segmentini modele serbest-metin tarif ettirir (algi tani)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import build_segments, extract_timestamped_frames  # noqa: E402


def main() -> None:
    video = sys.argv[1]
    frames, info = extract_timestamped_frames(video, fps_sample=2)
    segs = build_segments(frames, segment_seconds=30)
    seg = segs[0]
    print(f"{len(seg.frames)} kare gönderiliyor, kare boyutu (jpeg): {len(seg.frames[0][1])} bayt, video {info.width}x{info.height}")
    client = VLMClient()
    q = ("Bu CCTV kamerası karelerinde ne görüyorsun? Araçlar, kişiler ve hareketleri neler? "
         "Bir trafik kazası, çarpışma, düşme veya olağandışı bir durum var mı? Ayrıntılı Türkçe anlat.")
    print(client.analyze_frames(seg.frames, q, max_tokens=400))


if __name__ == "__main__":
    main()
