"""Kanit paketi (hizli-kazanim).

Yuksek-onemli olaylarin oldugu zaman-damgalarindaki anahtar kareleri, olayin bbox'i CIZILMIS
olarak cikarir + her kare icin SHA-256 iceren bir JSON manifest uretir. Tamamen deterministik
(LLM yok). Eskalasyon/adli-denetim icin butunluk (hash-zinciri) saglar; operator videoyu elle taramaz.
"""
from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
from typing import Optional

from PIL import Image, ImageDraw

from dilajan.schema import AnalysisResult, Severity
from dilajan.utils import QUERY_DATA_NOTE, operator_query_of
from dilajan.video import extract_timestamped_frames

_SEV_ORD = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}


def _secs(mmss: str) -> int:
    try:
        m, s = str(mmss).split(":")
        return int(m) * 60 + int(s)
    except Exception:
        return 0


def build_evidence_bundle(video_path: str, result: AnalysisResult, out_dir: str,
                          min_severity: Severity = Severity.YUKSEK,
                          query: Optional[str] = None) -> dict:
    """Yuksek-onemli olaylar icin kanit kareleri (bbox overlay) + hash'li manifest uretir.

    Donus: {"dir","frames":[png yollari],"manifest":json yolu,"count":n} veya {"error":...,"dir":...}.
    FAIL-OPEN: kare cikarilamazsa hata alani doner (cökmez).

    `query`: operatorun serbest-metin analiz sorgusu (opsiyonel; verilmezse karar-izinden
    okunur). Sorgu/yanit alanlari manifeste YALNIZCA `result.query_answer` doluyken girer."""
    os.makedirs(out_dir, exist_ok=True)
    try:
        frames, _info = extract_timestamped_frames(video_path)
    except Exception as ex:
        return {"error": f"kareler çıkarılamadı: {ex}", "dir": out_dir, "frames": [], "count": 0}
    if not frames:
        return {"error": "video karesi bulunamadı", "dir": out_dir, "frames": [], "count": 0}

    manifest = {
        "video": os.path.basename(video_path),
        "olusturma": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "genel_risk": result.risk.level.value,
    }
    # --- SORGU-GUDUMLU ANALIZ KAYDI (denetlenebilirlik) ---------------------------------
    # SHA-256 ZINCIRI ETKILENMEZ: her `olaylar[i].sha256` degeri YALNIZ ilgili PNG'nin DISKE
    # YAZILMIS baytlarindan hesaplanir (asagidaki dongu, img.save sonrasi). Manifest icerigi
    # hicbir hash'e girmez -> buraya alan eklemek butunluk dogrulamasini bozmaz.
    # B2: sorgu yoksa manifest anahtarlari BIREBIR eski hali (video, olusturma, genel_risk, olaylar).
    # B5: operator metni VERI olarak, "talimat degildir" notuyla birlikte kaydedilir.
    try:
        qa = str(getattr(result, "query_answer", None) or "").strip()
    except Exception:
        qa = ""
    if qa:
        manifest["operator_sorgusu"] = operator_query_of(result, query) or "(kayıtta yok)"
        manifest["ajan_sorgu_yaniti"] = qa
        manifest["sorgu_notu"] = (QUERY_DATA_NOTE + " Sorgu analizi odaklar, filtrelemez: "
                                  "sorguyla ilgisiz kritik olaylar da bu manifeste girer.")
    manifest["olaylar"] = []
    targets = [e for e in result.events if _SEV_ORD.get(e.severity, 0) >= _SEV_ORD[min_severity]] or result.events
    saved = []
    for i, e in enumerate(targets):
        et = _secs(e.time)
        best = min(frames, key=lambda fr: abs(fr[0] - et))  # olay zamanina en yakin kare
        try:
            img = Image.open(io.BytesIO(best[1])).convert("RGB")
        except Exception:
            continue
        W, H = img.size
        draw = ImageDraw.Draw(img)
        if e.bbox and len(e.bbox) >= 4:  # 0-1000 normalize bbox -> piksel
            try:
                x1, y1, x2, y2 = [c / 1000.0 for c in e.bbox[:4]]
                draw.rectangle([x1 * W, y1 * H, x2 * W, y2 * H], outline=(220, 30, 30), width=3)
            except Exception:
                pass
        label = f"{e.time} {e.severity.value}: {(e.event or '')[:48]}"
        draw.rectangle([0, 0, W, 18], fill=(0, 0, 0))
        draw.text((3, 4), label, fill=(255, 255, 255))
        fn = f"kanit_{i + 1:02d}_{e.time.replace(':', '')}.png"
        fp = os.path.join(out_dir, fn)
        try:
            img.save(fp)
        except Exception:
            continue
        with open(fp, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        manifest["olaylar"].append({
            "dosya": fn, "zaman": e.time, "olay": e.event, "onem": e.severity.value,
            "kategori": e.category.value, "bolge": e.region, "bbox_2d": e.bbox, "sha256": digest,
        })
        saved.append(fp)

    mpath = os.path.join(out_dir, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return {"dir": out_dir, "frames": saved, "manifest": mpath, "count": len(saved)}
