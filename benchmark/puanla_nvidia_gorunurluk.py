#!/usr/bin/env python
"""NVIDIA depo sonucunu onceden dondurulmus kamera gorunurlugune gore puanla.

Bu puanlayici senaryo klasorunu her kamera icin otomatik gercek etiket saymaz.
Beklenen olay, ``nvidia_sdg_dev_visibility.json`` icindeki model-koru elle
gorunurluk notundan gelir. Kapali gozlem olaylari serbest metin yerine ``isg_kod``
ile birebir eslestirilir.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.stats_utils import rate_from_bools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KODLAR = (
    "Warehouse_Visible_Fire",
    "Forklift_Shelf_Collision",
    "Forklift_Human_NearMiss",
)

# Normal kutu alma kliplerinde gorulen rutin egilme/uzanma, olay degildir.
# Bu aile yalniz raporlama icindir; ana karar deterministik kod ve sevk uzerindendir.
KRITIK_IDDIA = re.compile(
    r"(?:\b(?:yaral[ıi]|bilin[çc]siz|hareketsiz|yerde\s+(?:yatan|sürün|surun)|"
    r"emekle|zorlukla\s+aya[ğg]a|denge\s+kayb|tak[ıi]l|panik|ka[çc][ıi][şs]|"
    r"yetkisiz\s+eri[şs]im|kkd\s+eksik)|\bd[üu]ş(?![üu]k|[üu]n))",
    re.IGNORECASE,
)


def _oku(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _rate(values: list[bool]) -> dict:
    return rate_from_bools(values)


def _kodlar(row: dict) -> set[str]:
    return {
        str(e.get("isg_kod"))
        for e in row.get("events", [])
        if e.get("isg_kod") in KODLAR
    }


def puanla(result: dict, manifest: dict, visibility: dict,
           allow_subset: bool = False, codes=None) -> dict:
    active_codes = tuple(codes or KODLAR)
    if not active_codes or any(code not in KODLAR for code in active_codes):
        raise ValueError(f"Gecersiz/boş kod kapsamı: {active_codes}")
    result_rows = {_norm(r["path"]): r for r in result.get("rows", [])}
    manifest_rows = {_norm(r["path"]): r for r in manifest.get("rows", [])}

    if allow_subset:
        # Odak dilimi ayri kokte hard-link olabilir. Yalniz BENZERSIZ dosya
        # adiyla esle; bilinmeyen/fazla dosyayi sessizce kabul etme.
        by_name: dict[str, tuple[str, dict]] = {}
        duplicates: set[str] = set()
        for path, meta in manifest_rows.items():
            name = os.path.basename(path)
            if name in by_name:
                duplicates.add(name)
            by_name[name] = (path, meta)
        selected_result: dict[str, dict] = {}
        unknown: list[str] = []
        for result_path, row in result_rows.items():
            name = os.path.basename(result_path)
            if name in duplicates or name not in by_name:
                unknown.append(result_path)
                continue
            manifest_path, _ = by_name[name]
            selected_result[manifest_path] = row
        if unknown:
            raise ValueError(
                f"Alt-kume sonucunda manifestte benzersiz eslesmeyen yol: {unknown[:3]}"
            )
        result_rows = selected_result
        manifest_rows = {path: manifest_rows[path] for path in selected_result}

    eksik = sorted(set(manifest_rows) - set(result_rows))
    fazla = sorted(set(result_rows) - set(manifest_rows))
    if eksik or fazla:
        raise ValueError(
            f"Sonuc/manifest yolu uyusmuyor: eksik={len(eksik)}, fazla={len(fazla)}"
        )

    visible_by_run = visibility["visible_cameras_by_run"]
    scenario_code = visibility["scenario_code"]
    details: list[dict] = []
    code_tp: dict[str, list[bool]] = defaultdict(list)
    code_fp: dict[str, list[bool]] = defaultdict(list)
    normal_high_fp: list[bool] = []
    normal_any_fp: list[bool] = []
    normal_dispatch_fp: list[bool] = []
    normal_claim_fp: list[bool] = []
    run_visible: dict[tuple[str, str], list[bool]] = defaultdict(list)

    for path, meta in manifest_rows.items():
        row = result_rows[path]
        scenario = meta["scenario"]
        run_id = meta["run_id"]
        camera = meta["camera"]
        expected_code = scenario_code.get(scenario)
        visible = camera in set(visible_by_run.get(run_id, []))
        got_codes = _kodlar(row)

        for code in active_codes:
            expected = bool(visible and code == expected_code)
            if expected:
                code_tp[code].append(code in got_codes)
            else:
                code_fp[code].append(code in got_codes)

        if visible and expected_code in active_codes:
            run_visible[(scenario, run_id)].append(expected_code in got_codes)

        is_normal = scenario in visibility.get("normal_scenarios", [])
        text = " ".join(
            [str(row.get("summary") or "")]
            + [str(e.get("event") or "") for e in row.get("events", [])]
        )
        if is_normal:
            high = bool(row.get("max_severity", 0) >= 3 or row.get("risk_ord", 0) >= 3)
            any_event = bool(row.get("n_events", 0) or row.get("triggered"))
            dispatched = bool(row.get("triggered"))
            normal_high_fp.append(high)
            normal_any_fp.append(any_event)
            normal_dispatch_fp.append(dispatched)
            normal_claim_fp.append(bool(KRITIK_IDDIA.search(text)))

        details.append({
            "path": path,
            "scenario": scenario,
            "run_id": run_id,
            "camera": camera,
            "visible_positive": visible,
            "expected_code": expected_code if visible else None,
            "got_codes": sorted(got_codes),
            "n_events": row.get("n_events"),
            "risk_level": row.get("risk_level"),
            "triggered": row.get("triggered", []),
        })

    recall = {code: _rate(code_tp.get(code, [])) for code in active_codes}
    false_positive = {code: _rate(code_fp.get(code, [])) for code in active_codes}
    runs = []
    for (scenario, run_id), values in sorted(run_visible.items()):
        correct = sum(values)
        n = len(values)
        runs.append({
            "scenario": scenario,
            "run_id": run_id,
            "correct": correct,
            "eligible_views": n,
            "success": bool(n and correct * 2 >= n),
        })

    # Geliştirme eşiği: pozitif örneği olan her kodda >=%80 recall; kod-bazlı
    # negatiflerde <=%5 FP. Görünür pozitif bulunmayan yangında recall TANIMSIZ,
    # fakat 62 negatif görünümde yanlış yangın kodu yine ölçülür.
    recall_ok = all(v["n"] == 0 or v["p"] >= 0.80 for v in recall.values())
    fp_ok = all(v["p"] <= 0.05 for v in false_positive.values())
    run_ok = all(r["success"] for r in runs)
    normal = {
        "high_fp": _rate(normal_high_fp),
        "operational_fp": _rate(normal_any_fp),
        "dispatch_fp": _rate(normal_dispatch_fp),
        "critical_claim_fp": _rate(normal_claim_fp),
    }
    normal_ok = (
        normal["high_fp"]["k"] <= 1
        and normal["operational_fp"]["k"] <= 2
        and normal["dispatch_fp"]["k"] == 0
        and normal["critical_claim_fp"]["k"] <= 1
    )

    return {
        "schema_version": 1,
        "subset": bool(allow_subset),
        "codes": list(active_codes),
        "scored_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "n_views": len(details),
        "recall_by_code": recall,
        "false_positive_by_code": false_positive,
        "visible_run_results": runs,
        "normal": normal,
        "acceptance": {
            "recall_ge_0_80": recall_ok,
            "code_fp_le_0_05": fp_ok,
            "all_visible_runs_majority": run_ok,
            "normal_limits": normal_ok,
            "pass": bool(recall_ok and fp_ok and run_ok and normal_ok),
        },
        "details": details,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("result", help="benchmark/results/eval_*.json")
    ap.add_argument(
        "--manifest",
        default=os.path.join(ROOT, "data", "dev_nvidia_warehouse", "manifest.json"),
    )
    ap.add_argument(
        "--visibility",
        default=os.path.join(ROOT, "benchmark", "nvidia_sdg_dev_visibility.json"),
    )
    ap.add_argument("--out", default="")
    ap.add_argument(
        "--allow-subset", action="store_true",
        help="Odak koşusunu manifestte benzersiz dosya adına göre puanla.",
    )
    ap.add_argument(
        "--only-code", action="append", choices=KODLAR,
        help="Yalnız belirtilen olay kodunu ölç; raporda kapsam açıkça yazılır.",
    )
    args = ap.parse_args()

    score = puanla(
        _oku(args.result), _oku(args.manifest), _oku(args.visibility),
        allow_subset=args.allow_subset, codes=args.only_code,
    )
    out = args.out or os.path.join(
        ROOT, "benchmark", "results", f"nvidia_visibility_score_{time.strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(out, "w", encoding="utf-8") as f:
        json.dump(score, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "n_views": score["n_views"],
        "recall_by_code": score["recall_by_code"],
        "false_positive_by_code": score["false_positive_by_code"],
        "normal": score["normal"],
        "visible_run_results": score["visible_run_results"],
        "acceptance": score["acceptance"],
        "out": os.path.relpath(out, ROOT).replace("\\", "/"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
