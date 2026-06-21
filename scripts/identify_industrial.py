#!/usr/bin/env python
"""Endustriyel veri setinin her sinifindan (class0..7) ilk klibi VLM'e tarif ettirip
sinif numarasi -> davranis (guvenli/guvensiz) eslesmesini cikarir."""
from __future__ import annotations

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import build_segments, extract_timestamped_frames  # noqa: E402

Q = ("Bu bir fabrika/uretim alani guvenlik kamerasi goruntusu. Karelerde ne goruyorsun? "
     "Kac kisi var, ne yapiyorlar? Forklift, makine, panel, tasima var mi? "
     "Riskli/guvensiz bir davranis (yetkisiz bolgeye giris, asiri yuk tasima, acik panel, "
     "yetkisiz mudahale) veya bir kaza/dusme goruyor musun? Kisa ve net Turkce anlat.")


def main() -> None:
    base = os.path.join("data", "industrial")
    client = VLMClient()
    for c in range(8):
        clips = sorted(glob.glob(os.path.join(base, f"class{c}", "*.mp4")))
        if not clips:
            print(f"=== CLASS {c}: (klip yok) ===\n")
            continue
        frames, info = extract_timestamped_frames(clips[0], fps_sample=2)
        segs = build_segments(frames, segment_seconds=30)
        desc = client.analyze_frames(segs[0].frames, Q, max_tokens=300)
        print(f"=== CLASS {c}  [{os.path.basename(clips[0])}, {info.width}x{info.height}, {len(segs[0].frames)} kare] ===")
        print(desc.strip())
        print()


if __name__ == "__main__":
    main()
