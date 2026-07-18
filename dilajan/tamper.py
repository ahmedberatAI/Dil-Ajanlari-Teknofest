"""Kamera sabotaj / donma tespiti (hizli-kazanim; deterministik, VLM'siz).

Saha guvenliginde kamera BESLEMESININ kendisi bir saldiri yuzeyidir: besleme donabilir
(kayit dondurma), lens ortulebilir/boyanabilir veya karartilabilir. VLM bu durumu
"olay yok" sanabilir; bu modul kare-istatistigiyle (varyans + ardisik-kare farki)
DETERMINISTIK olarak yakalar ve bir GUVENLIK olayi uretir.

Cikti: {"kind","detail","time"} veya None. Tamamen yerel; FAIL-OPEN (hata -> None).
"""
from __future__ import annotations

import io
from typing import List, Optional, Sequence, Tuple

from PIL import Image

# (zaman_damgasi, jpeg_bytes)
Frame = Tuple[str, bytes]


def _grays(frames: Sequence[Frame], size: int = 64):
    import numpy as np
    out = []
    for _, jpeg in frames:
        a = np.asarray(Image.open(io.BytesIO(jpeg)).convert("L").resize((size, size)), dtype=np.float32)
        out.append(a)
    return out


def detect_tamper(frames: Sequence[Frame], freeze_eps: float = 1.0,
                  low_var: float = 8.0) -> Optional[dict]:
    """Donmus (freeze) veya ortulmus/karartilmis (blackout/cover) kamera beslemesini tespit eder.

    - Karartma/ortme: TUM karelerde global varyans cok dusuk (~duz/tek-renk) -> lens ortulu/karartilmis.
    - Donma: ardisik kareler neredeyse OZDES (fark ~0) -> besleme donmus.
    FAIL-OPEN: yetersiz kare/hata -> None (normal akisi bozmaz)."""
    try:
        import numpy as np
        if len(frames) < 3:
            return None
        grays = _grays(frames)
        variances = [float(g.var()) for g in grays]
        # 1) Karartma / ortme: hicbir karede anlamli detay yok (dusuk varyans)
        if max(variances) < low_var:
            mean_b = float(np.mean([g.mean() for g in grays]))
            kind = "kamera karartma" if mean_b < 40 else "kamera örtme/tek-renk"
            return {"kind": kind,
                    "detail": f"görüntü varyansı çok düşük (~{max(variances):.1f}); lens örtülü/karartılmış olabilir",
                    "time": frames[0][0]}
        # 2) Donma: ardisik kareler neredeyse ozdes
        diffs = [float(np.abs(grays[i] - grays[i - 1]).mean()) for i in range(1, len(grays))]
        if diffs and max(diffs) < freeze_eps:
            return {"kind": "kamera donması",
                    "detail": f"ardışık kareler neredeyse özdeş (maks fark ~{max(diffs):.2f}); besleme donmuş olabilir",
                    "time": frames[0][0]}
        return None
    except Exception:
        return None
