#!/usr/bin/env python
"""On kayitli NVIDIA SDG-Warehouse pilotunu run-duzeyinde puanla.

Bu dosyadaki eslesmeler ve kabul esikleri ilk model ciktisi gorulmeden
2026-08-27 tarihinde sabitlendi. Kaynak sozlesme:
docs/on_kayit_nvidia_sdg_warehouse_2026-08-27.md
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benchmark.stats_utils import fmt_rate_dict, rate_from_bools  # noqa: E402

DEFAULT_MANIFEST = os.path.join(ROOT, "data", "eval_nvidia_warehouse", "manifest.json")
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")
EXPECTED_EVAL_DIR = "data/eval_nvidia_warehouse"


def _norm(text: str) -> str:
    return (text or "").casefold().replace("i\u0307", "i")


# Bir anahtar sozcuk yalniz bu inkar kaliplarinin bulundugu parca icindeyse
# POZITIF kanit sayilmaz. Nokta/noktalivirgul/satir siniri parca siniridir.
NEGATION = re.compile(
    r"(?:tespit|g[öo]zlem|rastlan|bulun|mevcut|s[öo]z konusu)\s+"
    r"(?:edil|ol)?m(?:e|a)(?:di|dı|du|dü|mistir|mıştır|muştur|müştür|mektedir|maktadır)"
    r"|\b(?:yok|yoktur|de[ğg]il|degil)\b|\bno\b.{0,36}\b(?:detected|observed|present)\b",
    re.IGNORECASE,
)


def _positive(rx: re.Pattern[str], text: str) -> bool:
    """Cumle/parca icinde inkar edilmeyen en az bir eslesme var mi?"""
    for part in re.split(r"[.;!?\n]+", _norm(text)):
        if rx.search(part) and not NEGATION.search(part):
            return True
    return False


FIRE = re.compile(r"yang[ıi]n|alev|ate[şs]|tutu[şs]|duman|fire|flame|smoke|ignit")
VEHICLE = re.compile(r"fork\s*-?\s*lift|forklift|ara[cç]|istifleme arac|vehicle")
PERSON = re.compile(r"ki[şs]i|[cç]al[ıi][şs]an|i[şs][cç]i|insan|person|worker|pedestrian")
COLLISION = re.compile(
    r"[cç]arp|kaza|devril|raf.{0,24}(?:y[ıi]k|[cç][öo]k|devril)|"
    r"collision|crash|impact|hit.{0,20}shelf|shelf.{0,24}(?:fall|collaps|overturn)"
)
NEARMISS = re.compile(
    r"ramak|tehlikeli yak[ıi]n|yak[ıi]nla[şs]|mesafe|[cç]arp|temas|ka[cç][ıi]n|ezil|"
    r"near\s*-?\s*miss|dangerous prox|proximity|contact|avoid"
)

# Normal kliplerde raporlanacak somut, gorsel kanit gerektiren iddia aileleri.
# Bunlar basari esigini degistirmez; halusinasyonun turunu gorunur kilar.
CLAIM_FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("yangin/duman", FIRE),
    ("dusme/yarali kisi", re.compile(
        r"d[üu][şs]|y[ıi][ğg][ıi]l|yaral[ıi]|hareketsiz|bayg[ıi]n|bilin[cç]siz|"
        r"kanama|yerde yat|yere uzan|fallen|injured|unconscious|collapsed")),
    ("siddet/silah", re.compile(
        r"kavga|d[öo]v[üu][şs]|darp|sald[ıi]r|[şs]iddet|silah|b[ıi][cç]ak|"
        r"ate[şs] et|fight|assault|weapon|gun|knife")),
    ("carpisma/devrilme", COLLISION),
    ("yetkisiz giris/mudahale", re.compile(
        r"yetkisiz|izinsiz|zorla gir|k[ıi]s[ıi]tl[ıi] b[öo]lge|yasak b[öo]lge|"
        r"unauthorized|intruder|trespass")),
    ("kkd eksikligi", re.compile(
        r"\bkkd\b|baret|reflektif yelek|koruyucu g[öo]zl|koruyucu eldiven|"
        r"ki[şs]isel koruyucu|hardhat|helmet|safety vest|\bppe\b")),
)


def _text(row: dict) -> str:
    parts = [str(e.get("event") or "") for e in row.get("events") or []]
    parts.append(str(row.get("summary") or ""))
    return "\n".join(parts)


def _scenario_match(scenario: str, row: dict) -> bool:
    text = _text(row)
    if scenario == "fire":
        return _positive(FIRE, text)
    if scenario == "forklift_collision":
        return _positive(VEHICLE, text) and _positive(COLLISION, text)
    if scenario == "nearmiss":
        return (_positive(VEHICLE, text) and _positive(PERSON, text)
                and _positive(NEARMISS, text))
    if scenario == "box_pickup":
        high = int(row.get("max_severity") or 0) >= 3 or int(row.get("risk_ord") or 0) >= 3
        return not high and not bool(row.get("triggered") or [])
    raise ValueError(f"Bilinmeyen senaryo: {scenario}")


def _claim_families(row: dict) -> list[str]:
    text = _text(row)
    return [name for name, rx in CLAIM_FAMILIES if _positive(rx, text)]


def _path(value: str) -> str:
    return os.path.normpath(value).replace("\\", "/").lstrip("./")


def _latest_eval() -> str:
    candidates = sorted(glob.glob(os.path.join(RESULTS_DIR, "eval_*.json")), reverse=True)
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if _path(str(data.get("eval_dir") or "")) == EXPECTED_EVAL_DIR:
                return path
        except Exception:
            continue
    raise FileNotFoundError("NVIDIA depo setine ait eval sonucu bulunamadi")


def score(eval_path: str, manifest_path: str) -> dict:
    with open(eval_path, encoding="utf-8") as fh:
        evaluation = json.load(fh)
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)

    if _path(str(evaluation.get("eval_dir") or "")) != EXPECTED_EVAL_DIR:
        raise ValueError(f"Yanlis eval_dir: {evaluation.get('eval_dir')!r}")
    if manifest.get("source_revision") != "d5b88d3abcf659f304a107f4336b71b4e2159133":
        raise ValueError("Manifest kaynak revizyonu on kayitla ayni degil")

    meta = {_path(m["path"]): m for m in manifest.get("rows") or []}
    rows = {_path(r["path"]): r for r in evaluation.get("rows") or []}
    missing = sorted(set(meta) - set(rows))
    extra = sorted(set(rows) - set(meta))
    if missing or extra:
        raise ValueError(f"Manifest/eval uyusmuyor: eksik={len(missing)}, fazla={len(extra)}")

    views: list[dict] = []
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for path, m in meta.items():
        row = rows[path]
        high = int(row.get("max_severity") or 0) >= 3 or int(row.get("risk_ord") or 0) >= 3
        claims = _claim_families(row)
        view = {
            "path": path,
            "scenario": m["scenario"],
            "run_id": m["run_id"],
            "camera": m["camera"],
            "match": _scenario_match(m["scenario"], row),
            "high_or_critical": high,
            "dispatch": bool(row.get("triggered") or []),
            "claim_families": claims,
        }
        views.append(view)
        grouped[(m["scenario"], m["run_id"])].append(view)

    runs: list[dict] = []
    for (scenario, run_id), rv in sorted(grouped.items()):
        n = len(rv)
        k = sum(v["match"] for v in rv)
        unsafe = scenario != "box_pickup"
        run = {
            "scenario": scenario,
            "run_id": run_id,
            "n_views": n,
            "matched_views": k,
            "success": (k >= math.ceil(n / 2)) if unsafe else all(v["match"] for v in rv),
            "strict_high_fp": (not unsafe) and any(v["high_or_critical"] for v in rv),
            "majority_high_fp": (not unsafe) and
                sum(v["high_or_critical"] for v in rv) >= math.ceil(n / 2),
            "dispatch_fp": (not unsafe) and any(v["dispatch"] for v in rv),
            "claim_fp": (not unsafe) and any(v["claim_families"] for v in rv),
        }
        runs.append(run)

    scenario_metrics: dict[str, dict] = {}
    for scenario in ("fire", "forklift_collision", "nearmiss", "box_pickup"):
        sv = [v for v in views if v["scenario"] == scenario]
        sr = [r for r in runs if r["scenario"] == scenario]
        scenario_metrics[scenario] = {
            "view_match": rate_from_bools(v["match"] for v in sv),
            "run_success": rate_from_bools(r["success"] for r in sr),
        }

    normal_views = [v for v in views if v["scenario"] == "box_pickup"]
    normal_runs = [r for r in runs if r["scenario"] == "box_pickup"]
    family_counts = Counter(f for v in normal_views for f in v["claim_families"])
    normal = {
        "strict_high_fp_runs": rate_from_bools(r["strict_high_fp"] for r in normal_runs),
        "majority_high_fp_runs": rate_from_bools(r["majority_high_fp"] for r in normal_runs),
        "dispatch_fp_runs": rate_from_bools(r["dispatch_fp"] for r in normal_runs),
        "claim_fp_runs": rate_from_bools(r["claim_fp"] for r in normal_runs),
        "high_fp_views": rate_from_bools(v["high_or_critical"] for v in normal_views),
        "dispatch_fp_views": rate_from_bools(v["dispatch"] for v in normal_views),
        "concrete_claim_views": rate_from_bools(bool(v["claim_families"]) for v in normal_views),
        "claim_family_view_counts": dict(sorted(family_counts.items())),
    }

    acceptance_checks = {
        "fire_run_recall_at_least_4_of_5": scenario_metrics["fire"]["run_success"]["k"] >= 4,
        "collision_run_recall_at_least_4_of_5":
            scenario_metrics["forklift_collision"]["run_success"]["k"] >= 4,
        "nearmiss_run_recall_at_least_4_of_5": scenario_metrics["nearmiss"]["run_success"]["k"] >= 4,
        "box_strict_high_fp_at_most_1_of_5": normal["strict_high_fp_runs"]["k"] <= 1,
        "box_concrete_claim_views_at_most_10pct": normal["concrete_claim_views"]["p"] <= 0.10,
        "box_dispatch_fp_at_most_1_of_5": normal["dispatch_fp_runs"]["k"] <= 1,
    }
    return {
        "protocol": "docs/on_kayit_nvidia_sdg_warehouse_2026-08-27.md",
        "source_eval": os.path.relpath(eval_path, ROOT).replace("\\", "/"),
        "source_manifest": os.path.relpath(manifest_path, ROOT).replace("\\", "/"),
        "source_revision": manifest["source_revision"],
        "independent_runs": len(runs),
        "camera_views": len(views),
        "model_run_config": evaluation.get("kosum"),
        "scenario_metrics": scenario_metrics,
        "normal_hallucination": normal,
        "acceptance_checks": acceptance_checks,
        "verdict": "KABUL" if all(acceptance_checks.values()) else "RED",
        "runs": runs,
        "views": views,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("eval_json", nargs="?", help="eval_clips.py JSON'u; bos ise son uygun sonuc")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--out", help="puanlanmis JSON yolu")
    args = parser.parse_args()

    eval_path = os.path.abspath(args.eval_json) if args.eval_json else _latest_eval()
    result = score(eval_path, os.path.abspath(args.manifest))
    if args.out:
        out = os.path.abspath(args.out)
    else:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        out = os.path.join(RESULTS_DIR, f"nvidia_sdg_score_{stamp}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    print(f"Karar: {result['verdict']}  |  {result['independent_runs']} run / {result['camera_views']} gorus")
    for scenario, metrics in result["scenario_metrics"].items():
        print(f"  {scenario:20s} run={fmt_rate_dict(metrics['run_success'])}  "
              f"gorus={fmt_rate_dict(metrics['view_match'])}")
    normal = result["normal_hallucination"]
    print(f"  normal kati yuksek-FP  : {fmt_rate_dict(normal['strict_high_fp_runs'])}")
    print(f"  normal somut iddia     : {fmt_rate_dict(normal['concrete_claim_views'])}")
    print(f"  normal yanlis sevk     : {fmt_rate_dict(normal['dispatch_fp_runs'])}")
    for name, passed in result["acceptance_checks"].items():
        print(f"  {'GECTI' if passed else 'KALDI'}  {name}")
    print(f"Kaydedildi: {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
