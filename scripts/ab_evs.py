#!/usr/bin/env python
"""EVS feasibility A/B: ayni kareler image-path (mevcut) vs video-path (+EVS sunucu-tarafi).
Olcer: (1) video-path CALISIYOR mu (ortam), (2) latency farki, (3) cikti-sagligi (Turkce betim).
Sunucu --video-pruning-rate>0 ile calismali (DILAJAN_VIDEO_PRUNING_RATE=0.5)."""
from __future__ import annotations
import sys, time, base64, io, glob
sys.path.insert(0, ".")
import av, numpy as np
from PIL import Image
from openai import OpenAI
from dilajan.config import settings
from dilajan.video import extract_timestamped_frames
from dilajan.prompts import SYSTEM_PERSONA

client = OpenAI(base_url=settings.base_url, api_key=settings.api_key, timeout=settings.request_timeout)
INSTR = ("Bu güvenlik kamerası görüntüsünü Türkçe betimle: ne oluyor, kimler/neler var, "
         "riskli/anormal bir durum var mı? Kısa ve net.")
CLIPS = (sorted(glob.glob("data/eval/Shooting/*.mp4"))[:1]
         + sorted(glob.glob("data/eval_big/Fighting/*.mp4"))[:1]
         + ["data/sample_data/01_yangin.mp4"])


def frames_to_mp4(frames, fps=2):
    buf = io.BytesIO()
    first = Image.open(io.BytesIO(frames[0][1])).convert("RGB")
    w, h = first.size
    w -= w % 2; h -= h % 2  # x264 even dims
    cont = av.open(buf, mode="w", format="mp4")
    try:
        stream = cont.add_stream("libx264", rate=fps)
    except Exception:
        stream = cont.add_stream("mpeg4", rate=fps)
    stream.width, stream.height = w, h
    stream.pix_fmt = "yuv420p"
    for _, jpeg in frames:
        img = Image.open(io.BytesIO(jpeg)).convert("RGB").resize((w, h))
        vf = av.VideoFrame.from_ndarray(np.array(img), format="rgb24")
        for pkt in stream.encode(vf):
            cont.mux(pkt)
    for pkt in stream.encode():
        cont.mux(pkt)
    cont.close()
    return buf.getvalue()


def call(content):
    msgs = [{"role": "system", "content": SYSTEM_PERSONA}, {"role": "user", "content": content}]
    t = time.time()
    r = client.chat.completions.create(model=settings.model_name, messages=msgs, temperature=0.2, max_tokens=300)
    return time.time() - t, (r.choices[0].message.content or "").strip()


def img_content(frames):
    c = []
    for ts, jpeg in frames:
        c.append({"type": "text", "text": f"[Kare zamanı: {ts}]"})
        c.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}})
    c.append({"type": "text", "text": INSTR})
    return c


def vid_content(mp4):
    return [{"type": "video_url", "video_url": {"url": "data:video/mp4;base64," + base64.b64encode(mp4).decode()}},
            {"type": "text", "text": INSTR}]


def main():
    ti = tv = 0.0
    for clip in CLIPS:
        frames, info = extract_timestamped_frames(clip, 1.0)
        frames = frames[:12]
        nm = clip.split("/")[-1][:26]
        di, oi = call(img_content(frames))
        ti += di
        print(f"\n=== {nm} ({info.width}x{info.height}, {len(frames)} kare) ===")
        print(f"  IMAGE-path : {di:5.1f}s | {oi[:150]}")
        try:
            mp4 = frames_to_mp4(frames)
            dv, ov = call(vid_content(mp4))
            tv += dv
            print(f"  VIDEO+EVS  : {dv:5.1f}s | {ov[:150]}")
        except Exception as e:
            print(f"  VIDEO+EVS  : HATA -> {type(e).__name__}: {str(e)[:200]}")
    print(f"\nTOPLAM image {ti:.1f}s | video+EVS {tv:.1f}s" + (f" ({100*(ti-tv)/max(ti,1):+.0f}%)" if tv else ""))


if __name__ == "__main__":
    main()
