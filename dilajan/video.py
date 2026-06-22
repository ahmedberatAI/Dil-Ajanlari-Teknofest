"""Video isleme: zaman damgali kare cikarma ve segmentleme (PyAV ile).

VLM'e video gondermek yerine, videoyu belirli bir hizda ornekleyip her kareyi
zaman damgasiyla etiketliyoruz. Bu yaklasim:
  - token kullanimini kontrol altinda tutar (max_frames_per_segment),
  - olaylari net zaman damgalariyla eslestirmeyi saglar,
  - uzun videolari segmentlere bolerek olceklenebilir kilar.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import List, Tuple

import av
from PIL import Image

from dilajan.config import settings
from dilajan.utils import format_timestamp

# (zaman_saniye, jpeg_bytes)
TimedFrame = Tuple[float, bytes]


@dataclass
class VideoInfo:
    path: str
    duration: float          # saniye
    fps: float
    width: int
    height: int
    sampled_frames: int = 0

    @property
    def duration_str(self) -> str:
        return format_timestamp(self.duration)


@dataclass
class Segment:
    index: int
    start: float
    end: float
    frames: List[Tuple[str, bytes]] = field(default_factory=list)  # (MM:SS, jpeg)

    @property
    def start_str(self) -> str:
        return format_timestamp(self.start)

    @property
    def end_str(self) -> str:
        return format_timestamp(self.end)


def _enhance_clahe(img: Image.Image) -> Image.Image:
    """Dusuk cozunurluklu/grainy CCTV icin CLAHE kontrast iyilestirmesi (LAB-L kanali)."""
    try:
        import cv2
        import numpy as np
        arr = np.asarray(img.convert("RGB"))
        lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        out = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2RGB)
        return Image.fromarray(out)
    except Exception:
        return img  # cv2 yoksa/hata olursa orijinali dondur (toleransli)


def _resize_jpeg(img: Image.Image, max_side: int, min_side: int = 0, quality: int = 88) -> bytes:
    w, h = img.size
    longest = max(w, h)
    # buyukse kucult; dusuk cozunurluklu (CCTV) kareleri buyut
    if longest > max_side:
        scale = max_side / longest
    elif min_side and longest < min_side:
        scale = min_side / longest
    else:
        scale = 1.0
    if scale != 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    if img.mode != "RGB":
        img = img.convert("RGB")
    if settings.frame_enhance:
        img = _enhance_clahe(img)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def extract_timestamped_frames(
    path: str,
    fps_sample: float | None = None,
    max_side: int | None = None,
) -> Tuple[List[TimedFrame], VideoInfo]:
    """Videoyu `fps_sample` hizinda ornekler; (zaman, jpeg) listesi + VideoInfo döner."""
    fps_sample = fps_sample or settings.fps_sample
    max_side = max_side or settings.frame_max_side

    container = av.open(path)
    stream = container.streams.video[0]
    stream.thread_type = "AUTO"

    tb = stream.time_base
    fps = float(stream.average_rate) if stream.average_rate else 0.0
    if stream.duration is not None and tb is not None:
        duration = float(stream.duration * tb)
    elif container.duration is not None:
        duration = container.duration / av.time_base
    else:
        duration = 0.0

    interval = 1.0 / fps_sample
    next_t = 0.0
    frames: List[TimedFrame] = []
    width = height = 0

    for frame in container.decode(stream):
        t = float(frame.pts * tb) if frame.pts is not None else (frames[-1][0] + interval if frames else 0.0)
        if t + 1e-6 >= next_t:
            img = frame.to_image()
            width, height = img.size
            frames.append((t, _resize_jpeg(img, max_side, settings.frame_min_side)))
            next_t = t + interval

    container.close()
    if duration <= 0.0 and frames:
        duration = frames[-1][0]

    info = VideoInfo(
        path=path, duration=duration, fps=fps,
        width=width, height=height, sampled_frames=len(frames),
    )
    return frames, info


def build_segments(
    frames: List[TimedFrame],
    segment_seconds: float | None = None,
    max_frames_per_segment: int | None = None,
    overlap: float | None = None,
) -> List[Segment]:
    """Kareleri zaman pencerelerine böler; her segmentte azami kare sayisini asarsa
    eşit araliklarla alt-örnekler. `overlap`>0 ise ardisik pencereler ortusur (segment-siniri
    olaylari iki pencerede de gorunur; dedup birlestirir) — uzun videolarda sinir-kaybini onler."""
    segment_seconds = segment_seconds or settings.segment_seconds
    max_frames = max_frames_per_segment or settings.max_frames_per_segment
    overlap = settings.segment_overlap if overlap is None else overlap
    # guvenlik: ortusme segment uzunlugundan kucuk olmali (ilerleme garantisi)
    overlap = max(0.0, min(overlap, segment_seconds - 1.0))

    if not frames:
        return []

    total = frames[-1][0]
    segments: List[Segment] = []
    idx = 0
    start = 0.0
    while start <= total + 1e-6:
        end = start + segment_seconds
        bucket = [(t, j) for (t, j) in frames if start <= t < end]
        if bucket:
            if len(bucket) > max_frames:
                step = len(bucket) / max_frames
                bucket = [bucket[int(i * step)] for i in range(max_frames)]
            seg = Segment(
                index=idx,
                start=start,
                end=min(end, total),
                frames=[(format_timestamp(t), j) for (t, j) in bucket],
            )
            segments.append(seg)
            idx += 1
        start = end - overlap if overlap > 0 else end
    return segments
