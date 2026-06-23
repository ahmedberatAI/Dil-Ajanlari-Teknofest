#!/usr/bin/env python
"""HIPOTEZ: aksiyon bolgesini (kisi kumesi) KIRPIP BUYUTUNCE model suc TIPINI daha iyi taniyor mu?
Kok-neden: ayrinti (silah/eylem) tam karede kucuk/bulanik kayboluyor. ROI-zoom efektif cozunurlugu artirir.
Her klip: (a) tam-kare tip-sorusu, (b) kisi-ROI kirpilmis+buyutulmus tip-sorusu. Karsilastir + normalde sismiyor mu."""
from __future__ import annotations
import glob, io, sys
sys.path.insert(0, ".")
import numpy as np
from PIL import Image
from dilajan.video import extract_timestamped_frames, build_segments
from dilajan.llm_client import VLMClient
from dilajan import detector

Q = ("Bu güvenlik kamerası karelerinde NE TÜR bir olay var? Mümkünse olayı DOĞRU adıyla söyle: "
     "silahlı saldırı/ateş etme, kavga/dövüş, gasp/soygun, vandalizm/tahrip, fiziksel saldırı, "
     "trafik kazası, yangın/patlama, bir kişinin düşmesi — yoksa 'normal'. Kısa: olay türü + 1 cümle gerekçe.")


def person_roi(frames, pad=0.12):
    """Segment boyunca kisi bbox'larinin BIRLESIMI (aksiyon bolgesi) -> (x1,y1,x2,y2) normalize [0,1]."""
    model = detector._get_model()
    imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
    res = model.predict(imgs, conf=0.30, verbose=False, device="cuda")
    xs1, ys1, xs2, ys2 = [], [], [], []
    for r, im in zip(res, imgs):
        w, h = im.size
        for b, c in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist()):
            if int(c) != 0:
                continue
            xs1.append(b[0]/w); ys1.append(b[1]/h); xs2.append(b[2]/w); ys2.append(b[3]/h)
    if not xs1:
        return None
    x1, y1, x2, y2 = min(xs1), min(ys1), max(xs2), max(ys2)
    dw, dh = (x2-x1)*pad, (y2-y1)*pad
    return (max(0, x1-dw), max(0, y1-dh), min(1, x2+dw), min(1, y2+dh)), imgs


def crop_frames(frames, roi, imgs, up=720):
    out = []
    for (ts, _), im in zip(frames, imgs):
        w, h = im.size
        c = im.crop((int(roi[0]*w), int(roi[1]*h), int(roi[2]*w), int(roi[3]*h)))
        cw, ch = c.size
        if cw and ch:
            s = up / max(cw, ch)
            if s > 1:
                c = c.resize((max(1, int(cw*s)), max(1, int(ch*s))), Image.LANCZOS)
        b = io.BytesIO(); c.save(b, format="JPEG", quality=90)
        out.append((ts, b.getvalue()))
    return out


CLIPS = (sorted(glob.glob("data/eval/Shooting/*.mp4"))[:2] +
         sorted(glob.glob("data/eval/Assault/*.mp4"))[:1] +
         sorted(glob.glob("data/eval/Vandalism/*.mp4"))[:1] +
         sorted(glob.glob("data/eval/Normal/*.mp4"))[:2])


def main():
    cli = VLMClient()
    for p in CLIPS:
        fr, _ = extract_timestamped_frames(p, max_side=768)
        seg = build_segments(fr)[0]
        full = cli.analyze_frames(seg.frames, Q, temperature=0.2, max_tokens=120)
        r = person_roi(seg.frames)
        print("\n" + "=" * 84)
        print("KLIP:", p.split("/")[-1])
        print("  [TAM-KARE] ", full.strip()[:240])
        if not r:
            print("  [ROI-ZOOM] (kişi bulunamadı)"); continue
        roi, imgs = r
        zf = crop_frames(seg.frames, roi, imgs)
        zoom = cli.analyze_frames(zf, Q, temperature=0.2, max_tokens=120)
        print(f"  [ROI-ZOOM] (bölge {tuple(round(x,2) for x in roi)}) ", zoom.strip()[:240])


if __name__ == "__main__":
    main()
