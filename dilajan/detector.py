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


_pose_model = None


def _get_pose_model():
    global _pose_model
    if _pose_model is None:
        from ultralytics import YOLO
        _pose_model = YOLO("yolo11n-pose.pt")  # ilk kullanimda ~6MB
    return _pose_model


def verify_fallen(frames: Sequence[Tuple[str, bytes]], kp_conf: float = 0.5,
                  conf: float = 0.35) -> Tuple[str, str]:
    """VLM'in 'kisi yere dusmus/hareketsiz' iddiasini POZ ile dogrular (dusme vs comelme/egilme).

    Literatur esikleri (PMC7729773 / ACM 3478027): torso dikeyden <30° = DIK (comelme/egilme/oturma,
    DUSME DEGIL); >50° veya (aspect w/h>1 ve spine-ratio<1.2) = YATAY/dusmus. COCO-17: omuz 5,6 / kalca 11,12.
    Donus: ('CONFIRM'|'REJECT'|'ABSTAIN', not). FAIL-SAFE: poz guvenilmezse ABSTAIN (VLM iddiasi korunur).
    REJECT = kisi DIK -> sahte 'dusmus kisi'; severity DUSURULUR (silinmez)."""
    try:
        import numpy as np
        model = _get_pose_model()
        imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
        results = model.predict(imgs, conf=conf, verbose=False, device="cuda")
        votes = []  # True=dusmus(yatay), False=dik(ADL)
        for r in results:
            kpts = getattr(r, "keypoints", None)
            if kpts is None or kpts.xy is None or len(kpts.xy) == 0:
                continue
            xy = kpts.xy.cpu().numpy()
            cfn = kpts.conf.cpu().numpy() if kpts.conf is not None else None
            # en yuksek keypoint-guvenli kisiyi sec
            bi, bs = -1, -1.0
            for i in range(xy.shape[0]):
                s = float(cfn[i].mean()) if cfn is not None else 1.0
                if s > bs:
                    bs, bi = s, i
            if bi < 0:
                continue
            kp = xy[bi]
            c = cfn[bi] if cfn is not None else np.ones(17)
            if not all(c[j] >= kp_conf for j in (5, 6, 11, 12)):
                continue  # omuz/kalca net degil -> bu kareyi atla (abstain'e katki)
            sh = (kp[5] + kp[6]) / 2.0
            hp = (kp[11] + kp[12]) / 2.0
            v = hp - sh
            ang = float(np.degrees(np.arctan2(abs(v[0]), abs(v[1]))))  # 0=dik, 90=yatay
            pts = kp[c >= kp_conf]
            if len(pts) >= 3:
                w = float(pts[:, 0].max() - pts[:, 0].min())
                h = float(pts[:, 1].max() - pts[:, 1].min())
                ar = w / max(h, 1e-6)
            else:
                ar = 0.0
            sr = float(np.linalg.norm(v)) / max(float(np.linalg.norm(kp[5] - kp[6])), 1e-6)
            if ang < 30.0:
                votes.append(False)                      # DIK = comelme/egilme/oturma
            elif ang > 50.0 or (ar > 1.0 and sr < 1.2):
                votes.append(True)                       # YATAY = dusmus
            # 30-50° belirsiz -> sayma
        n_fall = sum(1 for v in votes if v)   # yatay/dusmus kare sayisi
        n_up = len(votes) - n_fall            # dik kare sayisi
        if len(votes) < max(2, int(0.4 * len(frames))):
            return "ABSTAIN", "poz güvenilmez (omuz/kalça net değil veya kişi yok)"
        # Temporal: dusme = bir noktada YATAY poz olur (dustukten sonra); comelme/egilme HIC yatay olmaz.
        if n_fall >= 2:
            return "CONFIRM", f"{n_fall} karede yatay/düşmüş poz -> düşme doğrulandı"
        # REJECT yalniz SUREKLI-dik (comelme/egilme uzun sure): cok kare DIK + HIC yatay yok.
        # Konservatif esik (n_up>=6) gercek dusmeleri korur (kisa/gecisli -> ABSTAIN -> VLM korunur).
        if n_fall == 0 and n_up >= 6:
            return "REJECT", f"{n_up} güvenilir karede SÜREKLİ DİK torso (çömelme/eğilme), hiç yatay yok -> düşme değil"
        return "ABSTAIN", f"belirsiz/yetersiz (yatay {n_fall}, dik {n_up}) -> VLM korunur"
    except Exception as e:
        return "ABSTAIN", f"poz hata: {e}"


def _region_of(cx: float, cy: float, w: float, h: float) -> str:
    """Piksel merkezini 3x3 Türkçe ızgara bölgesine eşler (graph._bbox_to_region ile tutarlı)."""
    xr = "sol" if cx < w / 3 else ("sağ" if cx > 2 * w / 3 else None)
    yr = "üst" if cy < h / 3 else ("alt" if cy > 2 * h / 3 else None)
    if xr and yr:
        return f"{yr} {xr}"
    return yr or xr or "merkez"


def detect_zone_intrusion(frames: Sequence[Tuple[str, bytes]], zones: Sequence[str],
                          conf: float = 0.35) -> dict:
    """SAVUNMA geofence: YASAK/kisitli bolgelerde KISI tespit eder (perimetre ihlali).

    VLM'in zone-reasoning'i guvenilmez oldugu icin DETERMINISTIK: YOLO ile kisi(ler)i bulur,
    bbox-merkezinden 3x3 bolge hesaplar; bolge yasak listede ise ihlal. Donus: {bolge: (MM:SS, guven)}
    (her yasak-bolge icin ILK tespit). Hata olursa bos (toleransli — yanlis ihlal uretmez)."""
    try:
        zones_n = {z.strip().lower() for z in zones if z and z.strip()}
        if not zones_n:
            return {}
        model = _get_model()
        imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
        results = model.predict(imgs, conf=conf, verbose=False, device="cuda")
        hits: dict = {}
        for fi, r in enumerate(results):
            w, h = imgs[fi].size
            for box, cls, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(),
                                    r.boxes.conf.tolist()):
                if int(cls) != 0:  # COCO 0 = person
                    continue
                cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                reg = _region_of(cx, cy, w, h)
                if reg.lower() in zones_n and reg not in hits:
                    hits[reg] = (frames[fi][0], round(float(cf), 2))  # ILK tespit (zaman, guven)
        return hits
    except Exception:
        return {}


def available() -> bool:
    try:
        import ultralytics  # noqa: F401
        return True
    except Exception:
        return False
