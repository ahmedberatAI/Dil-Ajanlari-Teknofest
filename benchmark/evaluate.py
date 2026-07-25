#!/usr/bin/env python
"""KPI degerlendirme: ajani ground-truth'a karsi calistirir ve metrik raporu uretir.

Ground truth iki KATMANLIDIR (benchmark/build_ground_truth.py urunu, K7):
  1) KLIP-DUZEYI (108 klip): kategori + anomali etiketi dataset klasor adindan gelir.
     -> tespit orani, risk kabulu, kategori eslesmesi burada olculur.
  2) TEMPORAL (yalnizca kompozit-insa klipler): olay penceresi tasarim geregi KESIN bilinir.
     -> olay P/R/F1 YALNIZ bu kliplerde MESRUDUR. Digerlerinde events=[] ve
        "insan-anotasyonu-gerekir" isaretli; F1 paydasina KATILMAZLAR.

Tum oran metrikleri Wilson %95 guven araligi ile raporlanir (K15).

Kullanim:
    python benchmark/evaluate.py
    python benchmark/evaluate.py --gt benchmark/ground_truth.json
    python benchmark/evaluate.py --categories Fire,Fall --limit 10
    python benchmark/evaluate.py --only-temporal          # yalniz kesin-pencereli klipler
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.agent import analyze_video  # noqa: E402
from dilajan.utils import format_timestamp  # noqa: E402

try:
    from benchmark.stats_utils import fmt_rate_dict, rate  # noqa: E402
except ImportError:  # benchmark/ icinden dogrudan calistirma
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from stats_utils import fmt_rate_dict, rate  # type: ignore  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ground_truth.json")
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")
TOLERANCE_S = 3.0  # zaman penceresi toleransi


def _to_sec(mmss: str) -> int:
    m, s = mmss.split(":")
    return int(m) * 60 + int(s)


def match_events(detected, gt_events, tol=TOLERANCE_S):
    """Greedy eslestirme: her GT olayini bir tespit edilen olaya bagla."""
    used = set()
    tp = matched_critical = 0
    total_critical = sum(1 for g in gt_events if g.get("critical"))
    for g in gt_events:
        lo = _to_sec(g["window"][0]) - tol
        hi = _to_sec(g["window"][1]) + tol
        kws = [k.lower() for k in g["keywords"]]
        for i, e in enumerate(detected):
            if i in used:
                continue
            try:
                et = _to_sec(e.time)
            except Exception:
                continue
            if lo <= et <= hi and any(k in e.event.lower() for k in kws):
                used.add(i)
                tp += 1
                if g.get("critical"):
                    matched_critical += 1
                break
    fp = len(detected) - len(used)
    fn = len(gt_events) - tp
    return tp, fp, fn, matched_critical, total_critical


def _f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def _risk_accept(spec: dict) -> list:
    """Kabul edilebilir risk seviyeleri. Yeni sema: 'risk_kabul' listesi.

    Eski sema ('risk': "Kritik") geriye-uyumlu desteklenir. Ikisi de yoksa risk PUANLANMAZ
    (bos liste) — uydurma bir 'dogru cevap' iddia etmeyiz.
    """
    acc = spec.get("risk_kabul")
    if isinstance(acc, list) and acc:
        return acc
    legacy = spec.get("risk")
    return [legacy] if legacy else []


def _select(gt: dict, categories, limit: int, only_temporal: bool, seed: int):
    """GT sozlugunden degerlendirilecek (rel_yol, spec) listesini secer.

    '_' ile baslayan anahtarlar METADATA'dir, atlanir.
    --limit ile alt-orneklem alinirken DETERMINISTIK KARISTIRMA yapilir (siralamaya bagli
    sistematik yanlilik olmasin diye — 'en kucuk N' yanliligi K12'nin ta kendisidir).
    """
    items = [(k, v) for k, v in gt.items()
             if not k.startswith("_") and isinstance(v, dict)]
    if only_temporal:
        items = [(k, v) for k, v in items if v.get("events")]
    if categories:
        cats = {c.strip() for c in categories.split(",") if c.strip()}
        items = [(k, v) for k, v in items if v.get("kategori") in cats]
    items.sort(key=lambda kv: kv[0])
    if limit and limit < len(items):
        rnd = random.Random(seed)
        items = sorted(rnd.sample(items, limit), key=lambda kv: kv[0])
    return items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default=DEFAULT_GT)
    ap.add_argument("--categories", default="", help="virgullu kategori filtresi (or. Fire,Fall)")
    ap.add_argument("--limit", type=int, default=0, help="deterministik alt-orneklem boyutu (0=hepsi)")
    ap.add_argument("--seed", type=int, default=20260101, help="alt-orneklem tohumu")
    ap.add_argument("--only-temporal", action="store_true",
                    help="yalnizca KESIN olay penceresi bilinen (kompozit) klipler")
    ap.add_argument("--save", action="store_true", help="sonucu benchmark/results/ altina yaz")
    args = ap.parse_args()

    with open(args.gt, encoding="utf-8") as f:
        gt = json.load(f)
    meta = gt.get("_meta", {})

    items = _select(gt, args.categories, args.limit, args.only_temporal, args.seed)
    if not items:
        print("Degerlendirilecek klip yok. Once: python benchmark/build_ground_truth.py")
        return

    n_temporal_gt = sum(1 for _k, v in items if v.get("events"))
    print("=" * 68)
    print(f"GT: {os.path.relpath(args.gt, ROOT)}   sema={meta.get('sema_surumu', 'eski')}")
    print(f"Degerlendirilecek: {len(items)} klip  "
          f"(KESIN temporal pencereli: {n_temporal_gt}, digerleri klip-duzeyi)")
    print("=" * 68)

    tot_tp = tot_fp = tot_fn = tot_mc = tot_tc = 0
    risk_k = risk_n = 0
    det_anom_k = det_anom_n = 0
    det_norm_k = det_norm_n = 0
    cat_k = cat_n = 0
    rows = []
    skipped = []

    for rel_video, spec in items:
        video = os.path.join(ROOT, rel_video)
        if not os.path.exists(video):
            skipped.append(rel_video)
            print(f"[ATLANDI] bulunamadi: {rel_video}")
            continue

        t0 = time.time()
        result = analyze_video(video)
        dt = time.time() - t0

        is_anom = bool(spec.get("anomali", True))
        gt_events = spec.get("events") or []
        detected_any = len(result.events) > 0

        # --- klip-duzeyi metrikler (her klipte MESRU) ---
        if is_anom:
            det_anom_n += 1
            det_anom_k += int(detected_any)
        else:
            det_norm_n += 1
            det_norm_k += int(detected_any)  # normalde tespit = YANLIS POZITIF

        accept = _risk_accept(spec)
        risk_ok = None
        if accept:
            risk_n += 1
            risk_ok = result.risk.level.value in accept
            risk_k += int(risk_ok)

        kws = [k.lower() for k in (spec.get("keywords") or [])]
        cat_ok = None
        if kws and is_anom:
            cat_n += 1
            cat_ok = any(any(k in e.event.lower() for k in kws) for e in result.events)
            cat_k += int(cat_ok)

        # --- temporal metrikler (YALNIZ kesin pencereli kliplerde) ---
        tp = fp = fn = mc = tc = 0
        prec = rec = None
        if gt_events:
            tp, fp, fn, mc, tc = match_events(result.events, gt_events)
            prec = tp / (tp + fp) if (tp + fp) else 0.0
            rec = tp / (tp + fn) if (tp + fn) else 0.0
            tot_tp += tp; tot_fp += fp; tot_fn += fn; tot_mc += mc; tot_tc += tc

        dur = _to_sec(result.video_duration) if result.video_duration else 0
        rows.append({
            "path": rel_video, "kategori": spec.get("kategori"), "anomali": is_anom,
            "n_events": len(result.events), "risk_level": result.risk.level.value,
            "risk_kabul": accept, "risk_ok": risk_ok, "kategori_eslesme": cat_ok,
            "temporal_gt": bool(gt_events),
            "tp": tp, "fp": fp, "fn": fn, "kritik_yakalanan": mc, "kritik_toplam": tc,
            "latency_s": round(dt, 1), "duration_s": dur,
            "triggered": list(result.triggered_functions),
        })

        tag = "TMP" if gt_events else "KLP"
        line = (f"[{tag}] {spec.get('kategori', '?'):14s} olay={len(result.events)} "
                f"risk={result.risk.level.value:6s} "
                f"riskOK={'-' if risk_ok is None else ('E' if risk_ok else 'H')} "
                f"kat={'-' if cat_ok is None else ('E' if cat_ok else 'H')} "
                f"{dt:.1f}s  {os.path.basename(rel_video)}")
        if gt_events:
            line += f"   [TP={tp} FP={fp} FN={fn}]"
        print(line)

    # ---------------- ozet ----------------
    print("\n" + "=" * 68)
    print("GENEL — tum oranlar Wilson %95 guven araligi ile (K15)")
    print("=" * 68)
    print("KLIP-DUZEYI (etiket: dataset klasor adi — DAYANAKLI):")
    r_det_a = rate(det_anom_k, det_anom_n)
    r_det_n = rate(det_norm_k, det_norm_n)
    r_risk = rate(risk_k, risk_n)
    r_cat = rate(cat_k, cat_n)
    print(f"  Anomalide >=1 olay tespiti : {fmt_rate_dict(r_det_a)}")
    print(f"  Normalde olay uretimi (FP) : {fmt_rate_dict(r_det_n)}   (dusuk = iyi)")
    print(f"  Risk seviyesi KABUL edildi : {fmt_rate_dict(r_risk)}")
    print(f"  Kategori anahtar eslesmesi : {fmt_rate_dict(r_cat)}")

    print("\nTEMPORAL (YALNIZ kesin pencereli kompozit klipler):")
    if tot_tp + tot_fp + tot_fn > 0:
        P = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) else 0.0
        R = tot_tp / (tot_tp + tot_fn) if (tot_tp + tot_fn) else 0.0
        r_crit = rate(tot_mc, tot_tc)
        print(f"  Olay tespiti F1            : {_f1(P, R):.2f}  (P={P:.2f}, R={R:.2f}, "
              f"TP={tot_tp} FP={tot_fp} FN={tot_fn})")
        print(f"  Kritik olay yakalama       : {fmt_rate_dict(r_crit)}")
        print(f"  Bu metriklerin klip sayisi : {n_temporal_gt}  "
              f"(<- F1 iddiasi YALNIZ bu kadar klibe dayanir)")
    else:
        print("  (kesin pencereli klip degerlendirilmedi — F1 raporlanmaz)")
        print("  NOT: diger kliplerde olay zaman-penceresi BILINMIYOR; F1 uydurulmaz.")

    print("\n" + "-" * 68)
    print("Kapsam notu: klip-duzeyi metrikler dataset etiketine DAYANAKLI; temporal F1 "
          "yalnizca\nkompozit-insa kliplerde mesrudur. Kalan kliplerin zaman anotasyonu "
          "icin insan gerekir.")
    if skipped:
        print(f"Bulunamayan dosya: {len(skipped)}")
    print("=" * 68)

    if args.save:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        out = os.path.join(RESULTS_DIR, f"gt_eval_{time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump({
                "gt": os.path.relpath(args.gt, ROOT),
                "gt_sema": meta.get("sema_surumu"),
                "n_klip": len(rows),
                "n_temporal_gt": n_temporal_gt,
                "klip_duzeyi_DAYANAKLI": {
                    "anomali_tespit": r_det_a, "normal_fp": r_det_n,
                    "risk_kabul": r_risk, "kategori_eslesme": r_cat,
                },
                "temporal_KESIN_PENCERE": {
                    "tp": tot_tp, "fp": tot_fp, "fn": tot_fn,
                    "kritik_yakalama": rate(tot_mc, tot_tc),
                    "n_klip": n_temporal_gt,
                },
                "atlanan": skipped,
                "rows": rows,
            }, f, ensure_ascii=False, indent=2)
        print(f"Kaydedildi: {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
