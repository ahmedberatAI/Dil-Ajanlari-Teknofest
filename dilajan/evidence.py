"""Zamansal storyboard ve kriptografik zincir içeren İSG kanıt paketi.

Her yüksek önem olay için tek, keyfî "en yakın" kare yerine başlangıç/orta/bitiş
çevresinden en çok üç farklı kare çıkarılır. Kaynak video, ham kare ve çizimli PNG
özetleri SHA-256 ile mühürlenir; her kare kaydı bir önceki kayıt hash'ini içerir.
LLM çağrısı ve model indirmesi yoktur.
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


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for parca in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(parca)
    return h.hexdigest()


def _kanonik_sha(kayit: dict) -> str:
    ham = json.dumps(kayit, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return _sha_bytes(ham)


def _hedef_zamanlar(event, son_kare: float) -> list[float]:
    bas = float(_secs(event.time))
    bit = float(_secs(event.end_time)) if event.end_time else bas
    if bit > bas:
        aday = [bas, (bas + bit) / 2.0, bit]
    else:
        aday = [max(0.0, bas - 1.0), bas, min(son_kare, bas + 1.0)]
    out: list[float] = []
    for t in aday:
        t = min(max(0.0, t), son_kare)
        if t not in out:
            out.append(t)
    return out


def build_evidence_bundle(video_path: str, result: AnalysisResult, out_dir: str,
                          min_severity: Severity = Severity.YUKSEK,
                          query: Optional[str] = None) -> dict:
    """Yüksek önem olaylar için storyboard + zincirli manifest üretir.

    Geriye uyumluluk için her olay kaydındaki ``dosya``, ``zaman`` ve ``sha256``
    ilk storyboard karesini göstermeye devam eder. Ayrıntılı kayıt ``kareler``
    alanındadır. Kare çıkarılamazsa fail-open hata sözlüğü döner.
    """
    os.makedirs(out_dir, exist_ok=True)
    try:
        frames, _info = extract_timestamped_frames(video_path)
    except Exception as ex:
        return {"error": f"kareler çıkarılamadı: {ex}", "dir": out_dir,
                "frames": [], "count": 0}
    if not frames:
        return {"error": "video karesi bulunamadı", "dir": out_dir,
                "frames": [], "count": 0}

    try:
        kaynak_sha = _sha_file(video_path)
        kaynak_boyut = os.path.getsize(video_path)
    except Exception as ex:
        return {"error": f"kaynak video mühürlenemedi: {ex}", "dir": out_dir,
                "frames": [], "count": 0}

    manifest = {
        "sema_surumu": "isg-evidence-v2",
        "video": os.path.basename(video_path),
        "video_boyut_bayt": kaynak_boyut,
        "video_sha256": kaynak_sha,
        "olusturma": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "genel_risk": result.risk.level.value,
    }
    try:
        qa = str(getattr(result, "query_answer", None) or "").strip()
    except Exception:
        qa = ""
    if qa:
        manifest["operator_sorgusu"] = operator_query_of(result, query) or "(kayıtta yok)"
        manifest["ajan_sorgu_yaniti"] = qa
        manifest["sorgu_notu"] = (
            QUERY_DATA_NOTE + " Sorgu analizi odaklar, filtrelemez: sorguyla ilgisiz "
            "kritik olaylar da bu manifeste girer.")

    manifest["olaylar"] = []
    targets = [e for e in result.events
               if _SEV_ORD.get(e.severity, 0) >= _SEV_ORD[min_severity]] or result.events
    saved: list[str] = []
    onceki_zincir = kaynak_sha
    son_kare = max(float(fr[0]) for fr in frames)

    for i, event in enumerate(targets):
        olay_kaydi = {
            "zaman": event.time,
            "bitis_zamani": event.end_time,
            "olay": event.event,
            "onem": event.severity.value,
            "kategori": event.category.value,
            "bolge": event.region,
            "bbox_2d": event.bbox,
            "isg_kod": getattr(event, "isg_kod", None),
            "isg_slot": getattr(event, "isg_slot", None),
            "isg_deger": getattr(event, "isg_deger", None),
            "ppe_src": bool(getattr(event, "ppe_src", False)),
            "kareler": [],
        }
        kullanilan_kareler: set[float] = set()
        for j, hedef in enumerate(_hedef_zamanlar(event, son_kare)):
            best = min(frames, key=lambda fr: abs(float(fr[0]) - hedef))
            kare_zamani = float(best[0])
            if kare_zamani in kullanilan_kareler:
                continue
            kullanilan_kareler.add(kare_zamani)
            try:
                img = Image.open(io.BytesIO(best[1])).convert("RGB")
            except Exception:
                continue
            w, h = img.size
            draw = ImageDraw.Draw(img)
            if event.bbox and len(event.bbox) >= 4:
                try:
                    x1, y1, x2, y2 = [c / 1000.0 for c in event.bbox[:4]]
                    draw.rectangle([x1 * w, y1 * h, x2 * w, y2 * h],
                                   outline=(220, 30, 30), width=3)
                except Exception:
                    pass
            etiket = (f"{event.time}–{event.end_time or event.time} "
                      f"{event.severity.value}: {(event.event or '')[:48]}")
            draw.rectangle([0, 0, w, 18], fill=(0, 0, 0))
            draw.text((3, 4), etiket, fill=(255, 255, 255))
            zaman_adi = f"{kare_zamani:07.2f}".replace(".", "_")
            fn = f"kanit_{i + 1:02d}_{j + 1:02d}_{zaman_adi}.png"
            fp = os.path.join(out_dir, fn)
            try:
                img.save(fp)
                png_sha = _sha_file(fp)
            except Exception:
                continue
            zincir_girdisi = {
                "olay_no": i + 1,
                "kare_no": j + 1,
                "dosya": fn,
                "kare_zamani_s": kare_zamani,
                "ham_kare_sha256": _sha_bytes(best[1]),
                "png_sha256": png_sha,
                "onceki_kayit_sha256": onceki_zincir,
            }
            zincir_sha = _kanonik_sha(zincir_girdisi)
            kare_kaydi = dict(zincir_girdisi, kayit_sha256=zincir_sha)
            onceki_zincir = zincir_sha
            olay_kaydi["kareler"].append(kare_kaydi)
            saved.append(fp)

        if not olay_kaydi["kareler"]:
            continue
        ilk = olay_kaydi["kareler"][0]
        olay_kaydi.update({"dosya": ilk["dosya"], "sha256": ilk["png_sha256"]})
        manifest["olaylar"].append(olay_kaydi)

    manifest["zincir_koku_sha256"] = kaynak_sha
    manifest["zincir_sonu_sha256"] = onceki_zincir
    mpath = os.path.join(out_dir, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return {"dir": out_dir, "frames": saved, "manifest": mpath,
            "count": len(saved), "event_count": len(manifest["olaylar"])}
