#!/usr/bin/env python
"""Klip-seviyesi degerlendirme: data/eval/<Kategori>/*.mp4 uzerinde ajani calistirir.

Metrikler:
  - Anomali recall        : anomali klibinde >=1 olay tespit edildi mi
  - Risk kalibrasyonu     : anomali -> risk >= Yuksek ; normal -> risk = Dusuk
  - Normal yanlis-pozitif : normal klipte yuksek/kritik olay veya yuksek risk uretildi mi
  - Kategori eslesmesi    : tespit edilen olay metni beklenen anahtar kelimeleri iceriyor mu
  - Gecikme               : klip basina sure ve video-saniyesi basina

Sonuclar benchmark/results/<zaman>.json olarak kaydedilir (iterasyonlar arasi karsilastirma icin).
Kullanim:  python benchmark/eval_clips.py
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.agent import analyze_video  # noqa: E402
from dilajan.schema import Severity  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DILAJAN_EVAL_DIR ile farkli bir degerlendirme seti (or. senaryo-uyumlu) calistirilabilir
EVAL_DIR = os.environ.get("DILAJAN_EVAL_DIR") or os.path.join(ROOT, "data", "eval")
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")

SEV_ORD = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}

# kategori -> beklenen anahtar kelimeler + anomali mi
CATEGORY_EXPECT = {
    "RoadAccidents": (["kaza", "çarpış", "araç", "trafik", "devril"], True),
    "Explosion": (["patlama", "duman", "yangın", "alev", "parlama"], True),
    "Fighting": (["kavga", "dövüş", "saldır", "şiddet", "itiş"], True),
    "Assault": (["saldır", "darp", "şiddet", "kavga", "vur"], True),
    "Abuse": (["istismar", "şiddet", "darp", "saldır", "taciz"], True),
    "Burglary": (["hırsız", "soygun", "yetkisiz", "kır", "giriş"], True),
    "Shooting": (["silah", "ateş", "vur", "çatış"], True),
    "Vandalism": (["vandal", "tahrip", "zarar", "kır"], True),
    # --- senaryo-uyumli kategoriler (endustri/saha guvenligi) ---
    "Fire": (["yangın", "alev", "ateş", "yan", "tutuş"], True),
    "Smoke": (["duman", "is", "yangın", "tüt"], True),
    "Fall": (["düş", "yere", "hareketsiz", "yığıl", "bayıl", "yatıyor", "yatan", "kalkamı"], True),
    "Normal": ([], False),
}


def _video_seconds(mmss: str) -> int:
    try:
        m, s = mmss.split(":")
        return int(m) * 60 + int(s)
    except Exception:
        return 0


def evaluate_clip(path: str, category: str) -> dict:
    keywords, is_anomaly = CATEGORY_EXPECT.get(category, ([], True))
    t0 = time.time()
    res = analyze_video(path)
    dt = time.time() - t0

    n_events = len(res.events)
    max_sev = max((SEV_ORD[e.severity] for e in res.events), default=0)
    risk_ord = SEV_ORD.get(res.risk.level, 0)
    cat_match = any(any(k in e.event.lower() for k in keywords) for e in res.events) if keywords else None
    dur = _video_seconds(res.video_duration or "00:00")

    return {
        "path": os.path.relpath(path, ROOT),
        "category": category,
        "is_anomaly": is_anomaly,
        "n_events": n_events,
        "max_severity": max_sev,
        "risk_ord": risk_ord,
        "risk_level": res.risk.level.value,
        "category_match": cat_match,
        "triggered": res.triggered_functions,
        "duration_s": dur,
        "latency_s": round(dt, 1),
        "summary": res.summary,
        "events": [
            {"time": e.time, "event": e.event, "severity": e.severity.value,
             "category": e.category.value, "region": e.region}
            for e in res.events
        ],
    }


def main() -> None:
    # istege bagli kategori filtresi: EVAL_CATS="Normal" veya "RoadAccidents,Explosion"
    only = {c.strip() for c in os.environ.get("EVAL_CATS", "").split(",") if c.strip()}
    clips = []
    for cat in sorted(os.listdir(EVAL_DIR)) if os.path.isdir(EVAL_DIR) else []:
        if only and cat not in only:
            continue
        paths = []
        for ext in ("*.mp4", "*.avi", "*.mkv", "*.mov", "*.mpg", "*.mpeg"):
            paths.extend(glob.glob(os.path.join(EVAL_DIR, cat, ext)))
        for path in sorted(paths):
            clips.append((path, cat))
    if not clips:
        print(f"data/eval/ altinda klip yok. Once: python scripts/build_eval_set.py")
        return

    print(f"{len(clips)} klip degerlendiriliyor...\n")
    rows = []
    for path, cat in clips:
        try:
            r = evaluate_clip(path, cat)
        except Exception as e:
            print(f"[HATA] {path}: {e}")
            continue
        rows.append(r)
        mark = "✓" if (r["category_match"] or (not r["is_anomaly"] and r["max_severity"] < 3)) else "·"
        print(f"  {mark} [{cat:13s}] olay={r['n_events']} risk={r['risk_level']:6s} "
              f"kat_eslesme={r['category_match']} {r['latency_s']}s  {os.path.basename(path)}")

    # --- toplulastir ---
    anom = [r for r in rows if r["is_anomaly"]]
    norm = [r for r in rows if not r["is_anomaly"]]

    def frac(xs):
        return (sum(xs) / len(xs)) if xs else 0.0

    recall = frac([1 if r["n_events"] > 0 else 0 for r in anom])
    risk_cal_anom = frac([1 if r["risk_ord"] >= 3 else 0 for r in anom])
    cat_match_rate = frac([1 if r["category_match"] else 0 for r in anom])
    # normal yanlis-pozitif (DAR): yuksek/kritik olay VEYA risk >= yuksek
    fp = frac([1 if (r["max_severity"] >= 3 or r["risk_ord"] >= 3) else 0 for r in norm])
    # normal yanlis-pozitif (OPERASYONEL, durust): normalde HERHANGI olay VEYA fonksiyon tetiklendi mi
    op_fp = frac([1 if (r["n_events"] > 0 or len(r.get("triggered", [])) > 0) else 0 for r in norm])
    dispatch_fp = frac([1 if len(r.get("triggered", [])) > 0 else 0 for r in norm])  # yanlis operasyonel cagri
    risk_cal_norm = frac([1 if r["risk_ord"] <= 1 else 0 for r in norm])
    lat = [r["latency_s"] for r in rows]
    persec = [r["latency_s"] / max(r["duration_s"], 1) for r in rows]

    print("\n" + "=" * 60)
    print(f"Anomali klipleri: {len(anom)}   Normal klipleri: {len(norm)}")
    print(f"  Anomali RECALL (>=1 olay)      : {recall*100:.0f}%")
    print(f"  Anomali risk kalibrasyonu(>=Y) : {risk_cal_anom*100:.0f}%")
    print(f"  Kategori eslesme orani         : {cat_match_rate*100:.0f}%")
    print(f"  NORMAL FP (dar: sev/risk>=Y)   : {fp*100:.0f}%   (dusuk = iyi)")
    print(f"  NORMAL FP (operasyonel: herhangi olay/tetik): {op_fp*100:.0f}%   (durust metrik)")
    print(f"  NORMAL yanlis operasyonel-tetik: {dispatch_fp*100:.0f}%   (dusuk = iyi)")
    print(f"  Normal risk=Dusuk orani        : {risk_cal_norm*100:.0f}%")
    if lat:
        print(f"  Gecikme medyan                 : {statistics.median(lat):.1f}s  "
              f"(~{statistics.median(persec):.2f}s/video-sn)")
    print("=" * 60)

    # --- per-kategori ---
    print("Kategori bazli (recall / kat_eslesme):")
    for cat in CATEGORY_EXPECT:
        cr = [r for r in rows if r["category"] == cat]
        if not cr:
            continue
        rc = frac([1 if r["n_events"] > 0 else 0 for r in cr])
        cm = frac([1 if r["category_match"] else 0 for r in cr if r["is_anomaly"]])
        print(f"  {cat:14s} n={len(cr)}  recall={rc*100:3.0f}%  kat={cm*100:3.0f}%")

    # --- kaydet ---
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS_DIR, f"eval_{stamp}.json")
    summary = {
        "n_anomaly": len(anom), "n_normal": len(norm),
        "recall": recall, "risk_cal_anom": risk_cal_anom, "cat_match": cat_match_rate,
        "normal_fp": fp, "normal_fp_operational": op_fp, "normal_dispatch_fp": dispatch_fp,
        "risk_cal_norm": risk_cal_norm,
        "latency_median": statistics.median(lat) if lat else 0,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
    print(f"\nKaydedildi: {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
