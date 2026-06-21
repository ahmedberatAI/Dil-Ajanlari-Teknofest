#!/usr/bin/env python
"""Pipeline dogrulamasi icin sentetik test videosu uretir.

Zaman damgali, ayirt edilebilir 'olaylar' iceren ~12 saniyelik bir MP4 olusturur.
Gercek veri (UCF-Crime vb.) temin edilene kadar uctan uca testler icindir.
"""
from __future__ import annotations

import os

import av
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 640, 480, 8, 12
OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "test_clip.mp4")


def load_font(size: int) -> ImageFont.ImageFont:
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


FONT_BIG = load_font(40)
FONT_MID = load_font(24)
FONT_SMALL = load_font(16)


def _centered(d: ImageDraw.ImageDraw, y: int, text: str, font, fill) -> None:
    w = d.textlength(text, font=font)
    d.text(((W - w) / 2, y), text, fill=fill, font=font)


def scene_for_time(t: float) -> tuple[tuple[int, int, int], str, str]:
    """(arka_plan_rengi, baslik, alt_metin) - zamana gore sahne."""
    if t < 4:
        return (235, 235, 235), "Depo - Normal Operasyon", "Calisanlar gorev basinda"
    if t < 6:
        return (250, 200, 120), "Forklift Hareket Halinde", "Forklift hizla ilerliyor"
    if t < 7:
        return (220, 70, 60), "!!! FORKLIFT DEVRILDI !!!", "Devrilme - kaza ani"
    if t < 9:
        return (200, 90, 80), "Yerde Hareketsiz Kisi", "Bir kisi yerde yatiyor"
    return (140, 160, 220), "Personel Toplandi", "Birden fazla kisi olay yerinde"


def draw_frame(t: float) -> Image.Image:
    bg, title, sub = scene_for_time(t)
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)

    # basit gorsel ipuclari
    if "DEVRILDI" in title:
        d.polygon([(260, 300), (420, 320), (400, 380), (240, 360)], fill=(90, 90, 90))  # devrik forklift
    elif "Hareketsiz" in title:
        d.line([(220, 360), (420, 360)], fill=(30, 30, 30), width=14)  # yatan kisi govdesi
        d.ellipse([(200, 345), (230, 375)], fill=(30, 30, 30))         # bas
    elif "Toplandi" in title:
        for cx in (200, 280, 360, 440):
            d.ellipse([(cx - 12, 250), (cx + 12, 274)], fill=(30, 30, 30))
            d.rectangle([(cx - 10, 276), (cx + 10, 340)], fill=(30, 30, 30))
    elif "Forklift" in title:
        d.rectangle([(300, 300), (400, 360)], fill=(120, 80, 30))

    d.rectangle([(0, 0), (W, 30)], fill=(0, 0, 0))
    d.text((10, 6), f"KAMERA-01   t={t:05.1f}s", fill=(255, 255, 255), font=FONT_SMALL)
    _centered(d, 60, title, FONT_BIG, (0, 0, 0))
    _centered(d, 410, sub, FONT_MID, (40, 40, 40))
    return img


def main() -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    container = av.open(OUT, mode="w")
    stream = container.add_stream("mpeg4", rate=FPS)
    stream.width, stream.height, stream.pix_fmt = W, H, "yuv420p"

    n = int(FPS * DUR)
    for i in range(n):
        t = i / FPS
        frame = av.VideoFrame.from_image(draw_frame(t))
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    print(f"Olusturuldu: {OUT}  ({n} kare, {DUR}s, {FPS}fps)")


if __name__ == "__main__":
    main()
