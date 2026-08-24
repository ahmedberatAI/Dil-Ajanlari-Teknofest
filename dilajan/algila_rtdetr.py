"""RT-DETRv2 tabanli nesne tespiti — **Apache-2.0** yol (ultralytics YERINE).

NEDEN AYRI MODUL (D39-A, 2026-08-18)
------------------------------------
`dilajan/detector.py` ultralytics'e baglidir ve ultralytics **AGPL-3.0**'dir.
Bu deponun lisansi Apache-2.0 ve yarisma sarti da Apache-2.0'dir; AGPL kod
Apache-2.0 olarak yeniden lisanslanamaz. Bu yuzden **yeni** yetenekler
detector.py'ye eklenmez; bu modul uzerinden gider.

Kullanilan model: ``PekingU/rtdetr_v2_r50vd`` — Apache-2.0, ``transformers``
icinde yerlesik. COCO sinif indeksleri: **person = 0** (calisma zamaninda
`_dogrula_person_indeksi` ile TEYIT EDILIR, varsayilmaz).

K3 (fail-open): her genel giris noktasi hata durumunda **bos** sonuc dondurur;
cagiran taraf sebebi `son_hata()` ile okuyup karar-izine yazabilir.
K5 (offline): agirliklar HF onbelleginden okunur; once `local_files_only=True`
denenir, yalnizca o basarisiz olursa ag denenir.
K6 (24 GB): model ~86M parametre, fp32 ~350 MB. fp16 KULLANILMAZ — bu ortamda
`nvrtc: libnvrtc-builtins.so.13.0` JIT hatasi veriyor (olculdu, 2026-08-18).
"""
from __future__ import annotations

import io
import threading
from typing import List, Optional, Sequence, Tuple

MODEL_ADI = "PekingU/rtdetr_v2_r50vd"
LISANS = "Apache-2.0"

_model = None
_islemci = None
_kilit = threading.Lock()
_person_idx: Optional[int] = None
_son_hata: Optional[str] = None


def son_hata() -> Optional[str]:
    """Son basarisizligin sebebi (karar-izine yazmak icin) veya None."""
    return _son_hata


def _yukle():
    """Modeli tek sefer yukler. Basarisizsa (None, None) ve `_son_hata` dolu."""
    global _model, _islemci, _person_idx, _son_hata
    if _model is not None:
        return _model, _islemci
    with _kilit:
        if _model is not None:
            return _model, _islemci
        try:
            import torch
            from transformers import AutoImageProcessor, RTDetrV2ForObjectDetection
        except Exception as ex:
            _son_hata = f"transformers/torch ithal edilemedi: {ex}"
            return None, None
        for yerel in (True, False):          # K5: once offline dene
            try:
                isl = AutoImageProcessor.from_pretrained(MODEL_ADI, local_files_only=yerel)
                mdl = RTDetrV2ForObjectDetection.from_pretrained(
                    MODEL_ADI, local_files_only=yerel).eval()
                break
            except Exception as ex:
                if not yerel:
                    _son_hata = f"{MODEL_ADI} yuklenemedi: {ex}"
                    return None, None
        try:
            # CIHAZ TEK KAPIDAN: uzak kosumda yerel GPU YASAK -> "cpu".
            from dilajan.config import yerel_cihaz
            _c = yerel_cihaz()
            if _c != "cpu":
                mdl = mdl.to(_c)             # fp32 — K6 notuna bak
        except Exception as ex:
            _son_hata = f"CUDA'ya tasinamadi, CPU ile devam: {ex}"
        _person_idx = _dogrula_person_indeksi(mdl)
        if _person_idx is None:
            _son_hata = "COCO 'person' sinif indeksi bulunamadi"
            return None, None
        _model, _islemci = mdl, isl
        return _model, _islemci


def _dogrula_person_indeksi(mdl) -> Optional[int]:
    """'person' indeksini config'den OKUR — 0 oldugunu VARSAYMAZ."""
    try:
        for k, v in (mdl.config.id2label or {}).items():
            if str(v).strip().lower() in ("person", "insan", "kisi"):
                return int(k)
    except Exception:
        pass
    return None


def hazir() -> bool:
    """Model yuklenebiliyor mu? (agir; ilk cagride modeli yukler)"""
    return _yukle()[0] is not None


def kisileri_bul(frames: Sequence[Tuple[str, bytes]],
                 conf: float = 0.35) -> List[List[dict]]:
    """Her kare icin kisi kutulari.

    Donus: kare basina ``[{"kutu": [x1,y1,x2,y2], "guven": float}, ...]``.
    Hata olursa **kare sayisi kadar bos liste** (K3 fail-open — yanlis olay uretmez).
    """
    global _son_hata
    bos: List[List[dict]] = [[] for _ in frames]
    if not frames:
        return bos
    mdl, isl = _yukle()
    if mdl is None:
        return bos
    try:
        import torch
        from PIL import Image
        imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
        with torch.no_grad():
            g = isl(images=imgs, return_tensors="pt")
            from dilajan.config import yerel_cihaz
            _c = yerel_cihaz()
            if _c != "cpu":
                g = {k: v.to(_c) for k, v in g.items()}
            cik = mdl(**g)
            boy = torch.tensor([[im.height, im.width] for im in imgs])
            son = isl.post_process_object_detection(cik, target_sizes=boy, threshold=conf)
        out: List[List[dict]] = []
        for r in son:
            kare = []
            for sk, et, kt in zip(r["scores"].tolist(), r["labels"].tolist(),
                                  r["boxes"].tolist()):
                if int(et) == _person_idx:
                    kare.append({"kutu": [float(v) for v in kt],
                                 "guven": round(float(sk), 3)})
            out.append(kare)
        return out
    except Exception as ex:
        _son_hata = f"kisileri_bul hatasi: {type(ex).__name__}: {ex}"
        return bos
