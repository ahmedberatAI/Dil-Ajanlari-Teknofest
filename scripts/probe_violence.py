#!/usr/bin/env python
"""Son kaldirac (Agent-2 #1): HAREKET tabanli siddet sinyali dusuk-cozde hayatta kalir mi?
Egitimsiz: YOLO-poz uzuv-hizi (bilek/ayak bilegi kare-arasi yer degistirme, govde-boyuna normalize) +
kisi-yakinligi. Siddet (Fighting/Assault) klipleri Normal'den AYRISIYOR mu? Ayrisirsa -> kanit enjekte + olc."""
from __future__ import annotations
import glob, io, sys
sys.path.insert(0, ".")
import numpy as np
from PIL import Image
from dilajan.video import extract_timestamped_frames, build_segments
from dilajan import detector

# COCO-17: bilekler 9,10 ; ayak bilekleri 15,16 ; omuz 5,6 ; kalca 11,12
LIMBS = [9, 10, 15, 16]


def limb_energy(path):
    """Segment boyunca ortalama uzuv-hizi (govde-boyuna normalize) + kisi sayisi."""
    fr, _ = extract_timestamped_frames(path, max_side=640)
    seg = build_segments(fr)[0]
    model = detector._get_pose_model()
    imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in seg.frames]
    res = model.predict(imgs, conf=0.30, verbose=False, device="cuda")
    prev = None
    speeds = []
    npers = []
    for r in res:
        kp = getattr(r, "keypoints", None)
        if kp is None or kp.xy is None or len(kp.xy) == 0:
            npers.append(0); continue
        xy = kp.xy.cpu().numpy()  # (kişi, 17, 2)
        cf = kp.conf.cpu().numpy() if kp.conf is not None else np.ones(xy.shape[:2])
        npers.append(xy.shape[0])
        # en güvenli kişi
        bi = int(cf.mean(1).argmax())
        k = xy[bi]; c = cf[bi]
        torso = np.linalg.norm((k[5]+k[6])/2 - (k[11]+k[12])/2) + 1e-6
        if prev is not None:
            d = [np.linalg.norm(k[j]-prev[j]) for j in LIMBS if c[j] > 0.3]
            if d:
                speeds.append(np.mean(d)/torso)
        prev = k
    return (float(np.mean(speeds)) if speeds else 0.0, float(np.mean(npers)) if npers else 0.0)


def main():
    sets = {
        "Fighting": sorted(glob.glob("data/eval/Fighting/*.mp4"))[:3],
        "Assault":  sorted(glob.glob("data/eval/Assault/*.mp4"))[:3],
        "Vandalism": sorted(glob.glob("data/eval/Vandalism/*.mp4"))[:3],
        "Normal":   sorted(glob.glob("data/eval/Normal/*.mp4"))[:5],
    }
    print(f"{'SINIF':12s} {'klip':26s} {'uzuv-hizi':>10} {'kişi':>6}")
    print("-" * 60)
    agg = {}
    for cls, paths in sets.items():
        vals = []
        for p in paths:
            try:
                sp, npr = limb_energy(p)
            except Exception as e:
                sp, npr = -1, -1
            vals.append(sp)
            print(f"{cls:12s} {p.split('/')[-1][:25]:26s} {sp:>10.3f} {npr:>6.1f}")
        agg[cls] = np.mean([v for v in vals if v >= 0]) if vals else 0
    print("-" * 60)
    for c, v in agg.items():
        print(f"  ORT {c:12s} uzuv-hizi = {v:.3f}")
    vio = np.mean([agg[c] for c in ["Fighting", "Assault", "Vandalism"]])
    print(f"\n  ŞİDDET ort={vio:.3f}  vs  NORMAL ort={agg['Normal']:.3f}  -> ayrım {vio/(agg['Normal']+1e-6):.2f}x")


if __name__ == "__main__":
    main()
