#!/usr/bin/env python
"""TUM etiketli veri setlerinde GUNCEL modelle (D1 motion-cue + D2) hem METRIK hem TAM CEVAP dokumu.

Cikti:
  - per-dataset karne (recall / risk-kalib / op-FP / dar-FP / gecikme)
  - benchmark/results/answers_<ts>.jsonl  (her klip: olaylar+severity+kategori+risk+ozet)
  - her dataset icin temsili cevaplar (tespit edilen anomali / normal / KACAN / FP) -> kalite elestirisi icin
"""
from __future__ import annotations
import glob, json, os, statistics, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "benchmark"))

from eval_clips import CATEGORY_EXPECT  # is_anomaly haritasi
from dilajan.agent.graph import analyze_video
from dilajan.schema import Severity

SEV = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}
SEVSTR = {Severity.DUSUK.value: 1, Severity.ORTA.value: 2, Severity.YUKSEK.value: 3, Severity.KRITIK.value: 4}
EXTS = ("*.mp4", "*.avi", "*.mkv", "*.mov", "*.mpg", "*.mpeg")
DATASETS = [
    ("Senaryo (Yangın+Düşme+Normal)", "data/eval_scenario"),
    ("UCF dengeli (8 kategori)", "data/eval"),
    ("UCF büyük (8 kategori)", "data/eval_big"),
    ("Gerçek düşme — GMDCSA", "data/falls_real"),
    ("Overhead düşme — URFD", "data/falls_surveillance"),
    ("Araç kazası — UCF Road", "data/e2_vehicle"),
]


def sv(x):
    return getattr(x, "value", x)


def is_anom(cat):
    e = CATEGORY_EXPECT.get(cat)
    if e is not None:
        return e[1]
    return cat.lower() not in ("normal", "normalvideos", "normal_videos")


def main():
    ts = time.strftime("%Y%m%d_%H%M%S")
    jsonl = open(os.path.join(ROOT, "benchmark", "results", f"answers_{ts}.jsonl"), "w", encoding="utf-8")
    summary = {}
    samples = {}
    for name, rel in DATASETS:
        d = os.path.join(ROOT, rel)
        if not os.path.isdir(d):
            continue
        rows = []
        for cat in sorted(os.listdir(d)):
            cdir = os.path.join(d, cat)
            if not os.path.isdir(cdir):
                continue
            anom = is_anom(cat)
            paths = []
            for e in EXTS:
                paths.extend(glob.glob(os.path.join(cdir, e)))
            for p in sorted(paths):
                t0 = time.time()
                try:
                    r = analyze_video(p)
                    evs = [{"t": e.time, "olay": e.event, "sev": sv(e.severity), "kat": sv(e.category)} for e in r.events]
                    rec = dict(set=name, cat=cat, anom=anom, file=os.path.basename(p),
                               risk=sv(r.risk.level), maxsev=max([SEV[e.severity] for e in r.events], default=0),
                               n=len(r.events), events=evs, summary=r.summary, lat=round(time.time() - t0, 1),
                               dur=r.video_duration)
                except Exception as ex:
                    rec = dict(set=name, cat=cat, anom=anom, file=os.path.basename(p), error=str(ex), n=0, maxsev=0, events=[])
                rows.append(rec)
                jsonl.write(json.dumps(rec, ensure_ascii=False) + "\n")
                jsonl.flush()
        if not rows:
            continue
        A = [r for r in rows if r["anom"]]
        N = [r for r in rows if not r["anom"]]
        rec = 100 * sum(1 for r in A if r["n"] > 0) / max(len(A), 1)
        riskc = 100 * sum(1 for r in A if SEVSTR.get(r.get("risk", ""), 0) >= 3) / max(len(A), 1)
        opfp = 100 * sum(1 for r in N if r["n"] > 0) / max(len(N), 1)
        nfp = 100 * sum(1 for r in N if r["maxsev"] >= 3) / max(len(N), 1)
        lats = [r["lat"] for r in rows if "lat" in r]
        summary[name] = dict(nA=len(A), nN=len(N), recall=rec, risk=riskc, opfp=opfp, darfp=nfp,
                             lat=statistics.median(lats) if lats else 0)
        # temsili: 1 tespit-anomali, 1 KACAN-anomali, 1 FP-normal, 1 temiz-normal
        det = next((r for r in A if r["n"] > 0), None)
        miss = next((r for r in A if r["n"] == 0), None)
        fp = next((r for r in N if r["n"] > 0), None)
        clean = next((r for r in N if r["n"] == 0), None)
        samples[name] = [x for x in [("TESPIT", det), ("KACAN", miss), ("FP-normal", fp), ("temiz-normal", clean)] if x[1]]
    jsonl.close()

    print("\n" + "=" * 80)
    print(f"{'VERİ SETİ':34s} {'Anom':>4} {'Norm':>4} {'Recall':>7} {'RiskK':>6} {'OpFP':>5} {'DarFP':>6} {'Gec':>5}")
    print("-" * 80)
    for name, s in summary.items():
        print(f"{name:34s} {s['nA']:>4} {s['nN']:>4} {s['recall']:>6.0f}% {s['risk']:>5.0f}% "
              f"{s['opfp']:>4.0f}% {s['darfp']:>5.0f}% {s['lat']:>4.1f}s")
    print("=" * 80)

    for name, lst in samples.items():
        print(f"\n### {name}")
        for tag, r in lst:
            evtxt = " | ".join(f"[{e['t']}] {e['olay'][:55]} ({e['sev']}/{e['kat']})" for e in r["events"]) or "(olay yok)"
            print(f"  [{tag}] {r['file']}  risk={r.get('risk','?')}")
            print(f"     OLAY: {evtxt}")
            print(f"     OZET: {r.get('summary','')[:170]}")
    print("\nJSONL:", f"benchmark/results/answers_{ts}.jsonl")


if __name__ == "__main__":
    main()
