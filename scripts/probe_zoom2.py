#!/usr/bin/env python
"""DUZELTILMIS ROI-zoom (Agent-1/Cerberus deseni): TAM-KARE + en-aktif kisi KIRPINTI BIRLIKTE.
Onceki probe yanlisti (yalniz kirpinti -> baglam kaybi; tum-kisi birlesimi -> zoom yok).
Bu sefer: full frame(ler) + TEK en-aktif kisi kirpintisi (buyutulmus) -> tip sorusu. Suc + normal."""
from __future__ import annotations
import glob, io, sys
sys.path.insert(0, ".")
from PIL import Image
from dilajan.video import extract_timestamped_frames, build_segments
from dilajan.llm_client import VLMClient
from dilajan import detector

Q = ("Görseller: önce TAM SAHNE kareleri, ardından 'ZOOM' etiketli en hareketli kişinin YAKINLAŞTIRILMIŞ hali. "
     "Bu olayda NE TÜR bir durum var? Doğru adıyla söyle: silahlı saldırı/ateş etme, kavga/dövüş, gasp/soygun, "
     "vandalizm/tahrip, fiziksel saldırı, trafik kazası, yangın/patlama, kişinin düşmesi — yoksa 'normal'. "
     "Kısa: olay türü + 1 cümle gerekçe.")


def best_person_roi(frames, pad=0.45):
    """Segment boyunca alan×guven en yuksek TEK kisi bbox'i -> ROI [0,1] + o karenin index'i."""
    model = detector._get_model()
    imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
    res = model.predict(imgs, conf=0.30, verbose=False, device="cuda")
    best = None  # (score, fi, x1,y1,x2,y2 normalize)
    for fi, (r, im) in enumerate(zip(res, imgs)):
        w, h = im.size
        for b, c, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
            if int(c) != 0:
                continue
            area = ((b[2]-b[0])/w) * ((b[3]-b[1])/h)
            sc = area * float(cf)
            if best is None or sc > best[0]:
                best = (sc, fi, b[0]/w, b[1]/h, b[2]/w, b[3]/h)
    if best is None:
        return None, imgs
    _, fi, x1, y1, x2, y2 = best
    dw, dh = (x2-x1)*pad, (y2-y1)*pad
    return (max(0, x1-dw), max(0, y1-dh), min(1, x2+dw), min(1, y2+dh)), imgs


def crop_jpeg(im, roi, up=448):
    w, h = im.size
    c = im.crop((int(roi[0]*w), int(roi[1]*h), int(roi[2]*w), int(roi[3]*h)))
    cw, ch = c.size
    if cw and ch and up/max(cw, ch) > 1:
        s = up/max(cw, ch); c = c.resize((int(cw*s), int(ch*s)), Image.LANCZOS)
    b = io.BytesIO(); c.save(b, format="JPEG", quality=92); return b.getvalue()


CLIPS = (sorted(glob.glob("data/eval/Shooting/*.mp4"))[:2] +
         sorted(glob.glob("data/eval/Assault/*.mp4"))[:1] +
         sorted(glob.glob("data/eval/Vandalism/*.mp4"))[:1] +
         sorted(glob.glob("data/eval/Burglary/*.mp4"))[:1] +
         sorted(glob.glob("data/eval/Normal/*.mp4"))[:2])


def main():
    cli = VLMClient()
    for p in CLIPS:
        fr, _ = extract_timestamped_frames(p, max_side=768)
        seg = build_segments(fr)[0]
        # Arm A: tam kare (mevcut)
        full = cli.analyze_frames(seg.frames, Q, temperature=0.2, max_tokens=110)
        # Arm B: tam-kare (6) + 3 zoom kirpinti
        roi, imgs = best_person_roi(seg.frames)
        print("\n" + "=" * 84); print("KLIP:", p.split("/")[-1])
        print("  [A FULL]", full.strip()[:230])
        if roi is None:
            print("  [B ZOOM] (kişi yok)"); continue
        ctx = seg.frames[::max(1, len(seg.frames)//6)][:6]
        idxs = [len(imgs)//4, len(imgs)//2, 3*len(imgs)//4]
        zooms = [(f"ZOOM-{seg.frames[i][0]}", crop_jpeg(imgs[i], roi)) for i in idxs if i < len(imgs)]
        msg = list(ctx) + zooms
        b = cli.analyze_frames(msg, Q, temperature=0.2, max_tokens=110)
        print(f"  [B ZOOM] (roi {tuple(round(x,2) for x in roi)})", b.strip()[:230])


if __name__ == "__main__":
    main()
