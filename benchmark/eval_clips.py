#!/usr/bin/env python
"""Klip-seviyesi degerlendirme: data/eval/<Kategori>/*.mp4 uzerinde ajani calistirir.

Metrikler:
  - Anomali recall        : anomali klibinde >=1 olay tespit edildi mi
  - Risk kalibrasyonu     : anomali -> risk >= Yuksek ; normal -> risk = Dusuk
  - Normal yanlis-pozitif : normal klipte yuksek/kritik olay veya yuksek risk uretildi mi
  - Kategori eslesmesi    : tespit edilen olay metni beklenen anahtar kelimeleri iceriyor mu
  - Gecikme               : klip basina sure ve video-saniyesi basina

K10 — MUKERRER ELEME: ayni MD5'e sahip klipler payda'yi sisirir
(or. Normal_Videos_936/937 BIREBIR AYNI dosya -> Normal paydasi 8 degil 7'dir).
Bu betik artik klipleri icerik-hash'ine gore tekillestirir; atlanan dosyalar cikti
JSON'unda "dedup" alanina yazilir. Kapatmak icin: DILAJAN_EVAL_DEDUP=0

K15 — RAPORLAMA HIJYENI: her oran metrigi ham sayimlar (k/n) ve Wilson %95 guven
araligi ile birlikte raporlanir. Kucuk n'de nokta-deger tek basina yaniltici.

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
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.agent import analyze_video  # noqa: E402
from dilajan.schema import Severity  # noqa: E402

try:
    from benchmark.dedup import dedup_paths  # noqa: E402
    from benchmark.labels import CATEGORY_EXPECT  # noqa: E402
    from benchmark.stats_utils import fmt_rate_dict, rate_from_bools  # noqa: E402
except ImportError:  # benchmark/ icinden dogrudan calistirma
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from dedup import dedup_paths  # type: ignore  # noqa: E402
    from labels import CATEGORY_EXPECT  # type: ignore  # noqa: E402
    from stats_utils import fmt_rate_dict, rate_from_bools  # type: ignore  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DILAJAN_EVAL_DIR ile farkli bir degerlendirme seti (or. senaryo-uyumlu) calistirilabilir
EVAL_DIR = os.environ.get("DILAJAN_EVAL_DIR") or os.path.join(ROOT, "data", "eval")

# K9 — SIZINTI UYARISI: eski data/eval, data/eval_big'in %100 ALT KUMESIDIR (31/31 ayni MD5).
# Ayar (tuning) ve dogrulama ayni klipler uzerinde yapilirsa sonuc IYIMSER cikar.
# Temiz, AYRIK cift: data/eval_tune (ayar) + data/eval_holdout (dogrulama).
LEAKY_EVAL_DIRS = {os.path.join(ROOT, "data", "eval"), os.path.join(ROOT, "data", "eval_big")}


def _warn_if_leaky(eval_dir: str) -> Optional[str]:
    """Sizintili eski set kullaniliyorsa operatoru/raporu uyarir (cikti JSON'una da yazilir)."""
    if os.path.normpath(eval_dir) not in {os.path.normpath(p) for p in LEAKY_EVAL_DIRS}:
        return None
    msg = ("UYARI (K9): data/eval, data/eval_big'in %100 alt kumesidir — bu iki set BAGIMSIZ "
           "DEGILDIR. Ayar+dogrulama ayni klipleri paylastigi icin sonuclar IYIMSER olabilir. "
           "Temiz ayrik cift icin: DILAJAN_EVAL_DIR=data/eval_holdout (dogrulama) / data/eval_tune (ayar).")
    print("\n" + "!" * 78 + f"\n{msg}\n" + "!" * 78 + "\n")
    return msg
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")
# K10 mukerrer eleme varsayilan ACIK; DILAJAN_EVAL_DEDUP=0 ile eski davranisa donulur
DEDUP = os.environ.get("DILAJAN_EVAL_DEDUP", "1").strip().lower() not in ("0", "false", "no")

SEV_ORD = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}

# kategori -> beklenen anahtar kelimeler + anomali mi  (tek kaynak: benchmark/labels.py)


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
        "risk_rationale": res.risk.rationale,
        "actions": [
            {"action": a.action, "priority": a.priority.value, "rationale": a.rationale}
            for a in res.actions
        ],
    }


def main() -> None:
    # istege bagli kategori filtresi: EVAL_CATS="Normal" veya "RoadAccidents,Explosion"
    only = {c.strip() for c in os.environ.get("EVAL_CATS", "").split(",") if c.strip()}
    clips = []
    for cat in sorted(os.listdir(EVAL_DIR)) if os.path.isdir(EVAL_DIR) else []:
        # '_' ile baslayan klasorler KARANTINA/METADATA'dir, kategori DEGILDIR ve olcume ALINMAZ.
        # (or. data/eval_scenario/_deprecated_frozen_fall — K8'de sete alinmamak uzere ayrilan
        #  donmus-PNG klipler. Filtre olmazsa bilinmeyen kategori is_anomaly=True varsayilir ve
        #  bu klipler anomali paydasina geri sizar; evaluate.py'nin '_' atlama kuraliyla ayni.)
        if cat.startswith("_"):
            continue
        if only and cat not in only:
            continue
        paths = []
        for ext in ("*.mp4", "*.avi", "*.mkv", "*.mov", "*.mpg", "*.mpeg"):
            paths.extend(glob.glob(os.path.join(EVAL_DIR, cat, ext)))
            # IC ICE kategori klasorlerini de tara (or. data/eval_defense/Anomali/<SinifAdi>/*.mp4).
            # Alt klasor adi yalnizca KOKEN bilgisidir; etiket her zaman UST kategori klasorudur.
            paths.extend(glob.glob(os.path.join(EVAL_DIR, cat, "*", ext)))
        for path in sorted(paths):
            clips.append((path, cat))
    if not clips:
        print(f"data/eval/ altinda klip yok. Once: python scripts/build_eval_set.py")
        return

    # --- K10: MD5 mukerrer eleme (payda sismesini onler) ---
    n_before = len(clips)
    dedup_skipped: list = []
    if DEDUP:
        kept_paths, dedup_skipped = dedup_paths([p for p, _ in clips], rel_to=ROOT)
        kept_set = set(kept_paths)
        clips = [(p, c) for p, c in clips if p in kept_set]
        if dedup_skipped:
            print(f"[DEDUP] {len(dedup_skipped)} mukerrer klip elendi "
                  f"({n_before} -> {len(clips)} benzersiz):")
            for s in dedup_skipped:
                dup_of = s.get("duplicate_of") or "(hash alinamadi)"
                print(f"   - {s['path']}  ==  {dup_of}")
            print()

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

    # Her metrik icin ham sayimlar + Wilson %95 CI (K15). Nokta-deger TEK BASINA raporlanmaz.
    R = {
        "recall": rate_from_bools([r["n_events"] > 0 for r in anom]),
        "risk_cal_anom": rate_from_bools([r["risk_ord"] >= 3 for r in anom]),
        "cat_match": rate_from_bools([bool(r["category_match"]) for r in anom]),
        # normal yanlis-pozitif (DAR): yuksek/kritik olay VEYA risk >= yuksek
        "normal_fp": rate_from_bools([(r["max_severity"] >= 3 or r["risk_ord"] >= 3) for r in norm]),
        # normal yanlis-pozitif (OPERASYONEL, durust): normalde HERHANGI olay VEYA fonksiyon tetigi
        "normal_fp_operational": rate_from_bools(
            [(r["n_events"] > 0 or len(r.get("triggered", [])) > 0) for r in norm]),
        "normal_dispatch_fp": rate_from_bools([len(r.get("triggered", [])) > 0 for r in norm]),
        "risk_cal_norm": rate_from_bools([r["risk_ord"] <= 1 for r in norm]),
    }
    # geriye-uyumluluk: eski duz oran alanlari (aggregate.py/compare.py bunlari okuyor)
    recall = R["recall"]["p"]
    risk_cal_anom = R["risk_cal_anom"]["p"]
    cat_match_rate = R["cat_match"]["p"]
    fp = R["normal_fp"]["p"]
    op_fp = R["normal_fp_operational"]["p"]
    dispatch_fp = R["normal_dispatch_fp"]["p"]
    risk_cal_norm = R["risk_cal_norm"]["p"]
    lat = [r["latency_s"] for r in rows]
    persec = [r["latency_s"] / max(r["duration_s"], 1) for r in rows]

    print("\n" + "=" * 72)
    print(f"Anomali klipleri: {len(anom)}   Normal klipleri: {len(norm)}"
          + (f"   (MD5 mukerrer elenen: {len(dedup_skipped)})" if dedup_skipped else ""))
    print("Tum oranlar: nokta-deger [Wilson %95 GA]  (k/n)")
    print("-" * 72)
    print(f"  Anomali RECALL (>=1 olay)      : {fmt_rate_dict(R['recall'])}")
    print(f"  Anomali risk kalibrasyonu(>=Y) : {fmt_rate_dict(R['risk_cal_anom'])}")
    print(f"  Kategori eslesme orani         : {fmt_rate_dict(R['cat_match'])}")
    print(f"  NORMAL FP (dar: sev/risk>=Y)   : {fmt_rate_dict(R['normal_fp'])}   (dusuk = iyi)")
    print(f"  NORMAL FP (operasyonel)        : {fmt_rate_dict(R['normal_fp_operational'])}   (durust metrik)")
    print(f"  NORMAL yanlis operasyonel-tetik: {fmt_rate_dict(R['normal_dispatch_fp'])}   (dusuk = iyi)")
    print(f"  Normal risk=Dusuk orani        : {fmt_rate_dict(R['risk_cal_norm'])}")
    if lat:
        print(f"  Gecikme medyan                 : {statistics.median(lat):.1f}s  "
              f"(~{statistics.median(persec):.2f}s/video-sn)")
    print("=" * 72)
    print("UYARI: kucuk n'de ust/alt sinir arasi genistir; '%0 FP' ifadesi tek basina")
    print("       kullanilmamalidir (or. 0/6 -> gercek oran %39'a kadar cikabilir).")
    print("=" * 72)

    # --- per-kategori ---
    print("Kategori bazli (recall / kat_eslesme) — n kucuk, CI ile okuyun:")
    per_category = {}
    for cat in CATEGORY_EXPECT:
        cr = [r for r in rows if r["category"] == cat]
        if not cr:
            continue
        rc = rate_from_bools([r["n_events"] > 0 for r in cr])
        cm = rate_from_bools([bool(r["category_match"]) for r in cr if r["is_anomaly"]])
        per_category[cat] = {"recall": rc, "cat_match": cm}
        print(f"  {cat:14s} recall={fmt_rate_dict(rc):26s} kat={fmt_rate_dict(cm)}")

    # --- kaydet ---
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS_DIR, f"eval_{stamp}.json")
    summary = {
        "n_anomaly": len(anom), "n_normal": len(norm),
        # --- eski duz alanlar (geriye uyumluluk; TEK BASINA raporlanmamali) ---
        "recall": recall, "risk_cal_anom": risk_cal_anom, "cat_match": cat_match_rate,
        "normal_fp": fp, "normal_fp_operational": op_fp, "normal_dispatch_fp": dispatch_fp,
        "risk_cal_norm": risk_cal_norm,
        "latency_median": statistics.median(lat) if lat else 0,
        # --- K15: ham sayimlar + Wilson %95 guven araliklari ---
        "ci": R,
        "ci_method": "wilson", "ci_level": 0.95,
        "per_category_ci": per_category,
    }
    leak_warning = _warn_if_leaky(EVAL_DIR)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            # K9: sizintili eski set kullanildiysa sonuc dosyasina da yazilir (rapor durustlugu)
            "leak_warning": leak_warning,
            "eval_dir": os.path.relpath(EVAL_DIR, ROOT).replace("\\", "/"),
            "dedup": {  # K10: hangi dosyalar neden sayilmadi
                "enabled": DEDUP,
                "n_input": n_before,
                "n_unique": len(clips),
                "n_skipped": len(dedup_skipped),
                "skipped": dedup_skipped,
            },
            "rows": rows,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nKaydedildi: {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
