"""Hafif uzman nesne dedektoru (YOLO) - heterojen ensemble / kanit enjeksiyonu.

VLM'in tek basina cikaramadigi GROUNDED nesne bilgisini (kisi/arac sayisi vb.) saglar.
Bu kanit, perceive describe adimina enjekte edilir ("Nesne dedektoru raporu: kisi x3, araba x1").
Kucuk model (yolo11n ~6MB) 7B vLLM ile ayni GPU'ya rahat sigar.
"""
from __future__ import annotations

import io
from collections import Counter
from typing import List, Optional, Sequence, Tuple

from PIL import Image

# COCO sinifi -> Turkce (gozetim icin ilgili alt kume; digerleri Ingilizce birakilir)
_TR = {
    "person": "kişi", "bicycle": "bisiklet", "car": "araba", "motorcycle": "motosiklet",
    "bus": "otobüs", "truck": "kamyon", "train": "tren", "boat": "tekne",
    "backpack": "sırt çantası", "handbag": "el çantası", "suitcase": "valiz",
    "knife": "bıçak", "baseball bat": "sopa", "cell phone": "telefon", "fire hydrant": "yangın musluğu",
}

_model = None


def _get_model():
    global _model
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO("yolo11n.pt")  # ilk kullanimda ~6MB indirilir
    return _model


def detect_segment(frames: Sequence[Tuple[str, bytes]], conf: float = 0.35) -> str:
    """Segment karelerindeki nesneleri tespit eder; azami eszamanli sayilarla Turkce ozet doner.
    Hata olursa bos string (toleransli)."""
    try:
        model = _get_model()
        imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
        results = model.predict(imgs, conf=conf, verbose=False, device="cuda")
        peak: Counter = Counter()
        for r in results:
            names = r.names
            per_frame: Counter = Counter()
            for c in r.boxes.cls.tolist():
                per_frame[names[int(c)]] += 1
            for cls, n in per_frame.items():
                peak[cls] = max(peak[cls], n)  # karelerdeki azami eszamanli varlik
        if not peak:
            return ""
        # en cok 6 sinif, sayiya gore
        parts = [f"{_TR.get(c, c)} x{n}" for c, n in peak.most_common(6)]
        return "Nesne dedektörü (azami eşzamanlı): " + ", ".join(parts)
    except Exception:
        return ""


def available() -> bool:
    try:
        import ultralytics  # noqa: F401
        return True
    except Exception:
        return False
