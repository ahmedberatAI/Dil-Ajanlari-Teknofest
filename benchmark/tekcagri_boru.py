#!/usr/bin/env python
"""D42 — MEVCUT COK ASAMALI BORU HATTI ayni 12 klipte: gecikme, CAGRI SAYISI, token, K1 denetimi.

ADALET NOTU: dilajan/agent/graph.py `_get_vlm()` ile TEK istemci kurar ve
settings.model_name kullanir; .env'de DILAJAN_MODEL_NAME=llm-large. Yani boru hatti
ZATEN UZAK SERVISTE ve TEK CAGRI kolunun ANA MODELIYLE kosuyor -> "yerel model,
haksiz karsilastirma" itirazi bu olcum icin GECERSIZ.
"""
import json, os, sys, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- cagri sayaci: OpenAI SDK seviyesinde ---
KAYIT = []
from openai.resources.chat.completions import Completions
_orig = Completions.create


def _patched(self, *a, **kw):
    t0 = time.time()
    r = _orig(self, *a, **kw)
    try:
        KAYIT.append({"model": kw.get("model"), "sure": round(time.time() - t0, 2),
                      "ptok": r.usage.prompt_tokens, "ctok": r.usage.completion_tokens})
    except Exception:
        KAYIT.append({"model": kw.get("model"), "sure": round(time.time() - t0, 2)})
    return r


Completions.create = _patched

from dilajan.config import settings
from dilajan.agent import analyze_video

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KLIPLER = [
    ("holdout/Explosion001",   True,  "data/eval_holdout/Explosion/Explosion001_x264.mp4"),
    ("holdout/Fighting023",    True,  "data/eval_holdout/Fighting/Fighting023_x264.mp4"),
    ("holdout/RoadAcc021",     True,  "data/eval_holdout/RoadAccidents/RoadAccidents021_x264.mp4"),
    ("holdout/Shooting001",    True,  "data/eval_holdout/Shooting/Shooting001_x264.mp4"),
    ("holdout/Normal_6te10",   False, "data/eval_holdout/Normal/6_te10.mp4"),
    ("holdout/Normal_939",     False, "data/eval_holdout/Normal/Normal_Videos_939_x264.mp4"),
    ("isg/Forklift_asiri_yuk", True,  "data/eval_defense/Anomali/Carrying_Overload_with_Forklift/3_tr5.mp4"),
    ("isg/Yaya_yolu_ihlali",   True,  "data/eval_defense/Anomali/Safe_Walkway_Violation/0_tr11.mp4"),
    ("isg/Pano_kapagi_acik",   True,  "data/eval_defense/Anomali/Opened_Panel_Cover/2_tr126.mp4"),
    ("isg/Guvenli_tasima",     False, "data/eval_defense/Normal/Safe_Carrying/7_tr18.mp4"),
    ("isg/Guvenli_yaya_yolu",  False, "data/eval_defense/Normal/Safe_Walkway/4_tr47.mp4"),
    ("isg/Pano_kapagi_kapali", False, "data/eval_defense/Normal/Closed_Panel_Cover/6_tr1.mp4"),
]
SEVERITY = ["Düşük", "Orta", "Yüksek", "Kritik"]
import re
MMSS = re.compile(r"^\d{2}:\d{2}$")


def denetle(v):
    hedef = {"summary", "events", "risk", "actions"}
    ks = set(v.keys())
    ev = v.get("events") or []
    return {"tam4": ks == hedef, "fazla": sorted(ks - hedef), "eksik": sorted(hedef - ks),
            "n_event": len(ev), "n_action": len(v.get("actions") or []),
            "event_alan_tam": all(isinstance(e, dict) and set(e.keys()) == {"time", "event"} for e in ev),
            "time_mmss": all(MMSS.match(str(e.get("time", ""))) for e in ev),
            "risk": v.get("risk"), "risk_kumede": v.get("risk") in SEVERITY,
            "actions_bos": len(v.get("actions") or []) == 0,
            "summary_uzunluk": len(v.get("summary") or "")}


def main():
    sadece = sys.argv[1:] if len(sys.argv) > 1 else None
    sonuc = {"kunye": {"tarih": datetime.now().isoformat(timespec="seconds"),
                       "model_name": settings.model_name, "base_url": settings.base_url,
                       "n_samples": settings.n_samples,
                       "frame_max_side": settings.frame_max_side,
                       "not": "boru hatti kendi ic T/max_tokens degerlerini kullanir"},
             "satirlar": []}
    for etiket, anomali, rel in KLIPLER:
        if sadece and etiket not in sadece:
            continue
        yol = os.path.join(KOK, rel)
        KAYIT.clear()
        t0 = time.time()
        try:
            r = analyze_video(yol)
            sure = time.time() - t0
            v = r.to_sartname_dict()
            d = denetle(v)
            cagri = list(KAYIT)
            ptok = sum(c.get("ptok", 0) for c in cagri)
            ctok = sum(c.get("ctok", 0) for c in cagri)
            print("%-24s %7.1fs cagri=%2d girdi_tok=%6d cikti_tok=%5d risk=%-8s n_ev=%d n_ac=%d tam4=%s"
                  % (etiket, sure, len(cagri), ptok, ctok, str(d["risk"]), d["n_event"],
                     d["n_action"], d["tam4"]))
            sonuc["satirlar"].append({"klip": etiket, "anomali": anomali, "sure_s": round(sure, 2),
                                      "cagri_sayisi": len(cagri), "girdi_token": ptok,
                                      "cikti_token": ctok, "cagrilar": cagri,
                                      "denetim": d, "cikti": v})
        except Exception as e:
            print("%-24s HATA %s: %s" % (etiket, type(e).__name__, str(e)[:200]))
            sonuc["satirlar"].append({"klip": etiket, "anomali": anomali,
                                      "hata": "%s: %s" % (type(e).__name__, str(e)[:300]),
                                      "cagri_sayisi": len(KAYIT)})
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = os.path.join(KOK, "benchmark", "results", "tekcagri_boru_%s.json" % ts)
    json.dump(sonuc, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("yazildi: " + p)


if __name__ == "__main__":
    main()
