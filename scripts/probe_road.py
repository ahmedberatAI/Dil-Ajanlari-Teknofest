#!/usr/bin/env python
"""RoadAccidents kliplerinde KOK-NEDEN probe: cozunurluk, ornek kareler, ince hareket-profili,
ve mevcut pipeline ciktisi. Motion-adaptive anahtar-kare enjeksiyonu ise yarar mi gormek icin."""
from __future__ import annotations

import io
import sys
import os

import av
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dilajan.video import extract_timestamped_frames, build_segments  # noqa: E402


def motion_profile(path: str, fps_probe: float = 10.0):
    """Yogun ornekleme (10 fps) ile ardisik-kare mutlak-fark (gri) profili -> carpisma zirvesi nerede?"""
    container = av.open(path)
    stream = container.streams.video[0]
    tb = stream.time_base
    interval = 1.0 / fps_probe
    next_t = 0.0
    prev = None
    rows = []
    for frame in container.decode(stream):
        t = float(frame.pts * tb) if frame.pts is not None else 0.0
        if t + 1e-6 >= next_t:
            g = np.asarray(frame.to_image().convert("L").resize((64, 64)), dtype=np.float32)
            if prev is not None:
                rows.append((round(t, 2), float(np.abs(g - prev).mean())))
            prev = g
            next_t = t + interval
    container.close()
    return rows


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/e2_vehicle/RoadAccidents/RoadAccidents021_x264.mp4"
    path = os.path.join(ROOT, path) if not os.path.isabs(path) else path
    print("VIDEO:", os.path.basename(path))

    frames, info = extract_timestamped_frames(path)
    print(f"  cozunurluk(orijinal->resize sonrasi degil): {info.width}x{info.height}  sure={info.duration:.1f}s  fps={info.fps:.1f}")
    print(f"  ornek kare sayisi (fps=2): {len(frames)}  zamanlar={[round(t,1) for t,_ in frames]}")

    mp = motion_profile(path)
    if mp:
        peak = max(mp, key=lambda r: r[1])
        mean = np.mean([m for _, m in mp])
        print(f"  HAREKET profili (10fps): zirve t={peak[0]}s (deger={peak[1]:.1f}, ortalama={mean:.1f}, zirve/ort={peak[1]/max(mean,1e-6):.1f}x)")
        # zirve etrafindaki 2 fps ornekleme bu ani yakaliyor mu?
        sampled_ts = [t for t, _ in frames]
        nearest = min(sampled_ts, key=lambda t: abs(t - peak[0])) if sampled_ts else None
        print(f"  fps=2 en yakin ornek kare: t={nearest}s  (zirveye uzaklik={abs(nearest-peak[0]):.2f}s)")
        # en hareketli 5 an
        top = sorted(mp, key=lambda r: -r[1])[:5]
        print(f"  en hareketli 5 an: {[(t, round(v,1)) for t,v in top]}")

    # mevcut pipeline ciktisi
    print("\n  --- mevcut pipeline (analyze) ---")
    try:
        from dilajan.agent.graph import analyze_video
        res = analyze_video(path)
        evs = res.events
        print(f"  olay sayisi: {len(evs)}")
        for e in evs:
            sev = getattr(getattr(e, "severity", None), "value", getattr(e, "severity", "?"))
            cat = getattr(getattr(e, "category", None), "value", getattr(e, "category", "?"))
            print(f"    [{getattr(e,'time','?')}] {str(getattr(e,'event',''))[:80]}  (sev={sev}, kat={cat})")
        print(f"  risk: {getattr(res.risk.level, 'value', res.risk.level)}")
        print(f"  ozet: {str(res.summary)[:220]}")
    except Exception:
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
