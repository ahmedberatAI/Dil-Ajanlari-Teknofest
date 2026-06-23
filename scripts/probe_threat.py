#!/usr/bin/env python
"""GENEL hipotez testi: sahne-duzeyi TEHDIT-YORUMU adimi sig betimlemeyi dogru tehdit-yorumuna
yukseltir mi (suclarda recall/derinlik artar) NORMALLERI yanlis-sismeden?

Her klip icin: (a) mevcut serbest-betim (literal), (b) tehdit-sentezi promptu. Karsilastir."""
from __future__ import annotations
import glob, sys
sys.path.insert(0, ".")
from dilajan.video import extract_timestamped_frames, build_segments
from dilajan.llm_client import VLMClient
from dilajan import prompts

LITERAL = prompts.SEGMENT_DESCRIBE_INSTRUCTION
THREAT = (
    "Bu güvenlik kamerası karelerini bir GÜVENLİK ANALİSTİ gibi yorumla. Yüzeysel betimleme yapma; "
    "ne OLDUĞUNU anlamaya çalış. Görüntüde ciddi bir güvenlik olayı (kavga/saldırı, soygun/gasp, "
    "silahlı tehdit/çatışma, bir kişinin vurulması/yere düşmesi, panik/kaçışma) belirtisi VAR MI? "
    "Varsa olayı DOĞRU adıyla ve önem derecesiyle anlat. Belirsizse en olası ciddi yorumu söyle ama "
    "abartma. Gerçekten olağan/rutin ise 'normal' de. Kısa Türkçe."
)

CLIPS = (sorted(glob.glob("data/eval/Shooting/Shooting001*.mp4")) +
         sorted(glob.glob("data/eval/Fighting/*.mp4"))[:1] +
         sorted(glob.glob("data/eval/Assault/*.mp4"))[:1] +
         sorted(glob.glob("data/eval/Normal/*.mp4"))[:2])


def first_seg(path):
    fr, _ = extract_timestamped_frames(path)
    segs = build_segments(fr)
    return segs[0] if segs else None


def main():
    cli = VLMClient()
    for p in CLIPS:
        seg = first_seg(p)
        if not seg:
            continue
        name = p.split("/")[-1]
        lit = cli.analyze_frames(seg.frames, LITERAL.format(start=seg.start_str, end=seg.end_str),
                                 temperature=0.2, max_tokens=200, repetition_penalty=1.15)
        thr = cli.analyze_frames(seg.frames, THREAT, temperature=0.2, max_tokens=200, repetition_penalty=1.15)
        print("\n" + "=" * 80)
        print("KLIP:", name)
        print("  [LITERAL] ", lit.strip()[:320])
        print("  [TEHDİT ] ", thr.strip()[:320])


if __name__ == "__main__":
    main()
