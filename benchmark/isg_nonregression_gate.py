#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""İSG arşivleri için eşleştirilmiş precision/recall non-regression kapısı.

Bu araç model veya API çalıştırmaz. ``benchmark/eval_clips.py`` biçimindeki iki
JSON arşivini örnek kimliği ve gerçek etiket manifesti üzerinde eşler; yalnızca
arşivlenmiş çıktıları yeniden puanlar.

Varsayılan karar:
  * örnek kapsamı ve gerçek etiket manifesti birebir aynı olmalı,
  * aday koşumun hata sayısı artmamalı,
  * genel ve her sınıfta precision ile recall ayrı ayrı azalmamalı,
  * sınıf FP, operasyonel FP ve dispatch FP sayıları artmamalı.

Sıfır payda, eksik sınıf/alan veya farklı manifest PASS sayılmaz;
``INSUFFICIENT`` döner. Wilson aralıkları yalnız raporlayıcıdır; karar daima
ham sayım/oran karşılaştırmasıyla verilir.

Çıkış kodları: PASS=0, FAIL=1, INSUFFICIENT=2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from benchmark.labels import (  # type: ignore
        ISG_SINIFLAR,
        isg_guvensiz,
        isg_matched_siniflar,
        isg_sinif_from_path,
        row_text,
    )
except ImportError:  # benchmark/ içinden doğrudan çalıştırma
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from labels import (  # type: ignore
        ISG_SINIFLAR,
        isg_guvensiz,
        isg_matched_siniflar,
        isg_sinif_from_path,
        row_text,
    )


PASS = "PASS"
FAIL = "FAIL"
INSUFFICIENT = "INSUFFICIENT"
SCHEMA_VERSION = 1

# ``kosum`` özellikle burada yoktur: A/B değişkeni o künyede farklı olmalıdır.
# Veri/örnek manifestini tanımlayan mevcut üst-seviye alanlar karşılaştırılır.
MANIFEST_KEYS: Tuple[str, ...] = (
    "manifest",
    "manifest_id",
    "manifest_sha256",
    "dataset_manifest",
    "eval_manifest",
    "eval_dir",
    "dedup",
)


class ArchiveError(ValueError):
    """Arşiv karşılaştırmaya elverişli değil."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _load_archive(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchiveError(f"{path}: JSON okunamadı: {type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict):
        raise ArchiveError(f"{path}: üst düzey JSON nesne olmalı")
    if not isinstance(data.get("rows"), list):
        raise ArchiveError(f"{path}: rows listesi yok")
    return data


def _sample_id(row: Mapping[str, Any]) -> str:
    for key in ("sample_id", "id", "path"):
        value = row.get(key)
        if value is not None and str(value).strip():
            out = str(value).strip().replace("\\", "/")
            while out.startswith("./"):
                out = out[2:]
            return out
    return ""


def _row_map(data: Mapping[str, Any], label: str) -> Tuple[Dict[str, dict], List[str]]:
    out: Dict[str, dict] = {}
    issues: List[str] = []
    for index, raw in enumerate(data.get("rows") or []):
        if not isinstance(raw, dict):
            issues.append(f"{label}: rows[{index}] nesne değil")
            continue
        sample_id = _sample_id(raw)
        if not sample_id:
            issues.append(f"{label}: rows[{index}] örnek kimliği yok")
            continue
        if sample_id in out:
            issues.append(f"{label}: yinelenen örnek kimliği: {sample_id}")
            continue
        out[sample_id] = raw
    return out, issues


def _truth_class(row: Mapping[str, Any], sample_id: str) -> Tuple[Optional[str], Optional[str]]:
    explicit = str(row.get("isg_sinif") or "").strip() or None
    parsed = isg_sinif_from_path(sample_id)
    if explicit and parsed and explicit != parsed:
        return None, f"isg_sinif/path çelişkisi: {explicit!r} != {parsed!r}"
    return explicit or parsed, None


def _normalise_name(value: Any) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


def _is_smoke_row(row: Mapping[str, Any], sample_id: str, truth_class: Optional[str]) -> bool:
    """Yalnız duman ailesini dışlar; ``Fire`` otomatik olarak dışlanmaz."""
    values = [truth_class, row.get("category"), *sample_id.replace("\\", "/").split("/")]
    for value in values:
        name = _normalise_name(value)
        if name == "smoke" or "duman" in name or name.startswith("smoke_") or name.endswith("_smoke"):
            return True
    return False


def _row_has_error(row: Mapping[str, Any]) -> bool:
    for key in ("error", "errors", "hata", "hatalar", "_hata"):
        if row.get(key):
            return True
    traces: List[str] = []
    for key in ("isg_trace", "decision_trace", "trace"):
        value = row.get(key)
        if isinstance(value, list):
            traces.extend(str(x) for x in value)
        elif value:
            traces.append(str(value))
    upper = "\n".join(traces).upper()
    return "__HATA__" in upper or "OLCULEMEDI" in upper or "ÖLÇÜLEMEDİ" in upper


def _validate_metric_row(row: Mapping[str, Any], sample_id: str, truth_class: Optional[str]) -> List[str]:
    issues: List[str] = []
    if not isinstance(row.get("is_anomaly"), bool):
        issues.append(f"{sample_id}: is_anomaly bool değil/yok")
    # Genel Hazard/Normal regresyon ceplerinde ince-taneli sınıf bulunmayabilir.
    # Bu satırlar ikili precision/recall ve FP için yine tam değerlendirilebilir;
    # sınıf kapısı yalnız sınıf manifesti gerçekten varsa açılır.
    if truth_class and truth_class not in ISG_SINIFLAR:
        issues.append(f"{sample_id}: bilinmeyen İSG sınıfı: {truth_class}")
    events = row.get("events")
    if not isinstance(events, list):
        issues.append(f"{sample_id}: events listesi yok")
    n_events = row.get("n_events")
    if not isinstance(n_events, int) or isinstance(n_events, bool) or n_events < 0:
        issues.append(f"{sample_id}: n_events geçerli tamsayı değil")
    elif isinstance(events, list) and n_events != len(events):
        issues.append(f"{sample_id}: n_events={n_events}, len(events)={len(events)}")
    if not isinstance(row.get("triggered"), list):
        issues.append(f"{sample_id}: triggered listesi yok")
    if "summary" not in row:
        issues.append(f"{sample_id}: summary alanı yok")
    return issues


def _predicted_classes(row: Mapping[str, Any]) -> Set[str]:
    """Arşivden tehlike sınıfı tahmini türetir.

    Tipli deterministik olay kodu öncelikle korunur; serbest anlatı için iki
    arşive de aynı anda uygulanan sabit ``benchmark.labels`` eşleştiricisi
    kullanılır. Güvenli satırdaki kayıtlı ``isg_match`` kullanılmaz; o alan
    kendi güvenli sınıfına karşı daima false olduğundan sınıf FP'sini ölçemez.
    """
    out: Set[str] = set()
    for event in row.get("events") or []:
        if isinstance(event, dict):
            code = str(event.get("isg_kod") or "").strip()
            if code in ISG_SINIFLAR and isg_guvensiz(code):
                out.add(code)
    text = " . ".join(row_text(dict(row), with_summary=True))
    if text:
        out.update(s for s in isg_matched_siniflar(text) if isg_guvensiz(s))
    return out


def _wilson(k: int, n: int, z: float = 1.959963984540054) -> Optional[List[float]]:
    if n <= 0:
        return None
    p = k / n
    den = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / den
    half = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n) / den
    return [round(max(0.0, centre - half), 6), round(min(1.0, centre + half), 6)]


def _rate(k: int, n: int) -> dict:
    return {
        "k": k,
        "n": n,
        "value": (round(k / n, 8) if n else None),
        "wilson95": _wilson(k, n),
    }


def _confusion(truth: Sequence[bool], pred: Sequence[bool]) -> dict:
    if len(truth) != len(pred):
        raise ValueError("truth/pred uzunluğu farklı")
    tp = fp = fn = tn = 0
    for actual, guessed in zip(truth, pred):
        if actual and guessed:
            tp += 1
        elif (not actual) and guessed:
            fp += 1
        elif actual and (not guessed):
            fn += 1
        else:
            tn += 1
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": _rate(tp, tp + fp),
        "recall": _rate(tp, tp + fn),
    }


def _ratio_not_lower(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> Optional[bool]:
    cn, cd = candidate.get("k"), candidate.get("n")
    bn, bd = baseline.get("k"), baseline.get("n")
    if not all(isinstance(x, int) for x in (cn, cd, bn, bd)) or cd == 0 or bd == 0:
        return None
    return cn * bd >= bn * cd


def _metric_checks(base: Mapping[str, Any], cand: Mapping[str, Any]) -> Tuple[dict, List[str], List[str]]:
    checks: Dict[str, str] = {}
    failures: List[str] = []
    insufficient: List[str] = []
    for metric in ("precision", "recall"):
        verdict = _ratio_not_lower(cand[metric], base[metric])
        if verdict is None:
            checks[f"{metric}_not_lower"] = INSUFFICIENT
            insufficient.append(f"{metric} paydası sıfır")
        elif verdict:
            checks[f"{metric}_not_lower"] = PASS
        else:
            checks[f"{metric}_not_lower"] = FAIL
            failures.append(f"{metric} azaldı")
    if int(cand["fp"]) <= int(base["fp"]):
        checks["fp_not_higher"] = PASS
    else:
        checks["fp_not_higher"] = FAIL
        failures.append(f"FP arttı ({base['fp']} -> {cand['fp']})")
    return checks, failures, insufficient


def _manifest_fields(data: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: data[key] for key in MANIFEST_KEYS if key in data}


def _run_hash(data: Mapping[str, Any]) -> Optional[str]:
    return _sha256(data["kosum"]) if "kosum" in data else None


def _truth_manifest(rows: Mapping[str, dict]) -> Tuple[List[dict], List[str]]:
    manifest: List[dict] = []
    issues: List[str] = []
    for sample_id, row in sorted(rows.items()):
        truth_class, conflict = _truth_class(row, sample_id)
        if conflict:
            issues.append(f"{sample_id}: {conflict}")
        manifest.append({
            "id": sample_id,
            "is_anomaly": row.get("is_anomaly"),
            "isg_sinif": truth_class,
            "category": row.get("category"),
        })
    return manifest, issues


def compare_archives(
    baseline_path: str,
    candidate_path: str,
    *,
    include_smoke: bool = False,
    required_classes: Optional[Iterable[str]] = None,
) -> dict:
    """İki arşivi karşılaştırıp makine-okunur karar raporu döndürür."""
    base_data = _load_archive(baseline_path)
    cand_data = _load_archive(candidate_path)
    base_rows, base_map_issues = _row_map(base_data, "baseline")
    cand_rows, cand_map_issues = _row_map(cand_data, "candidate")

    insufficient: List[str] = [*base_map_issues, *cand_map_issues]
    failures: List[str] = []

    base_ids, cand_ids = set(base_rows), set(cand_rows)
    missing_candidate = sorted(base_ids - cand_ids)
    extra_candidate = sorted(cand_ids - base_ids)
    if missing_candidate or extra_candidate:
        insufficient.append(
            "örnek kimliği kapsamı farklı: "
            f"candidate eksik={len(missing_candidate)}, fazla={len(extra_candidate)}"
        )

    base_manifest_fields = _manifest_fields(base_data)
    cand_manifest_fields = _manifest_fields(cand_data)
    for key in sorted(set(base_manifest_fields) | set(cand_manifest_fields)):
        if key not in base_manifest_fields or key not in cand_manifest_fields:
            insufficient.append(f"manifest alanı yalnız bir arşivde var: {key}")
        elif _canonical_json(base_manifest_fields[key]) != _canonical_json(cand_manifest_fields[key]):
            insufficient.append(f"manifest alanı farklı: {key}")

    base_truth_manifest, base_truth_issues = _truth_manifest(base_rows)
    cand_truth_manifest, cand_truth_issues = _truth_manifest(cand_rows)
    insufficient.extend(base_truth_issues)
    insufficient.extend(cand_truth_issues)
    base_truth_hash = _sha256(base_truth_manifest)
    cand_truth_hash = _sha256(cand_truth_manifest)
    if base_truth_hash != cand_truth_hash:
        insufficient.append("türetilmiş gerçek-etiket manifesti farklı")

    report: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": INSUFFICIENT,
        "baseline": os.path.abspath(baseline_path),
        "candidate": os.path.abspath(candidate_path),
        "run_manifest_sha256": {
            "baseline": _run_hash(base_data),
            "candidate": _run_hash(cand_data),
            "note": "kosum künyeleri A/B değişkenini taşıdığı için eşitlik kapısı değildir",
        },
        "data_manifest": {
            "baseline_sha256": base_truth_hash,
            "candidate_sha256": cand_truth_hash,
            "explicit_fields": sorted(set(base_manifest_fields) | set(cand_manifest_fields)),
        },
        "coverage": {
            "baseline": len(base_ids),
            "candidate": len(cand_ids),
            "same_sample_ids": not missing_candidate and not extra_candidate,
            "missing_candidate": missing_candidate[:20],
            "extra_candidate": extra_candidate[:20],
        },
        "excluded": {"smoke": 0},
        "errors": {},
        "general": None,
        "classes": {},
        "false_positives": {},
        "failures": failures,
        "insufficient_reasons": insufficient,
    }

    # Farklı manifestte kısmi satır puanlayıp karşılaştırılabilirlik izlenimi verme.
    if insufficient:
        report["status"] = INSUFFICIENT
        return report

    sample_ids = sorted(base_ids)
    selected: List[Tuple[
        str, dict, dict, Optional[str], bool, Set[str], Set[str]
    ]] = []
    base_errors = cand_errors = excluded_smoke = 0
    validation_issues: List[str] = []
    for sample_id in sample_ids:
        base_row, cand_row = base_rows[sample_id], cand_rows[sample_id]
        base_class, _ = _truth_class(base_row, sample_id)
        cand_class, _ = _truth_class(cand_row, sample_id)
        if base_class != cand_class or base_row.get("is_anomaly") != cand_row.get("is_anomaly"):
            validation_issues.append(f"{sample_id}: arşivler arasında gerçek etiket farklı")
            continue
        if not include_smoke and _is_smoke_row(base_row, sample_id, base_class):
            excluded_smoke += 1
            continue
        validation_issues.extend(
            f"baseline {issue}" for issue in _validate_metric_row(base_row, sample_id, base_class)
        )
        validation_issues.extend(
            f"candidate {issue}" for issue in _validate_metric_row(cand_row, sample_id, cand_class)
        )
        if base_class and base_class not in ISG_SINIFLAR:
            continue
        truth_unsafe = bool(base_row.get("is_anomaly"))
        base_pred = _predicted_classes(base_row)
        cand_pred = _predicted_classes(cand_row)
        selected.append((sample_id, base_row, cand_row, base_class, truth_unsafe, base_pred, cand_pred))
        base_errors += int(_row_has_error(base_row))
        cand_errors += int(_row_has_error(cand_row))

    report["excluded"]["smoke"] = excluded_smoke
    report["coverage"]["non_smoke_evaluable"] = len(selected)
    if validation_issues:
        report["insufficient_reasons"].extend(validation_issues)
        report["status"] = INSUFFICIENT
        return report
    if not selected:
        report["insufficient_reasons"].append("duman dışı değerlendirilebilir İSG örneği yok")
        report["status"] = INSUFFICIENT
        return report

    report["errors"] = {
        "baseline": base_errors,
        "candidate": cand_errors,
        "not_higher": PASS if cand_errors <= base_errors else FAIL,
    }
    if cand_errors > base_errors:
        failures.append(f"hata sayısı arttı ({base_errors} -> {cand_errors})")

    class_items = [item for item in selected if item[3] is not None]
    ground_classes = {item[3] for item in class_items if item[4]}
    predicted_classes: Set[str] = set()
    for item in class_items:
        predicted_classes.update(item[5])
        predicted_classes.update(item[6])
    expected_classes = (
        set(ground_classes) | predicted_classes | set(required_classes or [])
        if class_items or required_classes else set()
    )
    expected_classes = {
        c for c in expected_classes
        if c in ISG_SINIFLAR and isg_guvensiz(c)
    }
    for required in required_classes or []:
        if required not in ground_classes:
            report["insufficient_reasons"].append(f"zorunlu sınıf manifestte yok: {required}")

    base_general = _confusion(
        [item[4] for item in selected],
        [bool(item[1]["n_events"] > 0 or item[1]["triggered"]) for item in selected],
    )
    cand_general = _confusion(
        [item[4] for item in selected],
        [bool(item[2]["n_events"] > 0 or item[2]["triggered"]) for item in selected],
    )
    general_checks, general_fail, general_insufficient = _metric_checks(base_general, cand_general)
    failures.extend(f"genel: {x}" for x in general_fail)
    report["insufficient_reasons"].extend(f"genel: {x}" for x in general_insufficient)
    report["general"] = {
        "baseline": base_general,
        "candidate": cand_general,
        "checks": general_checks,
    }

    for class_name in sorted(expected_classes):
        truth = [item[3] == class_name for item in class_items]
        base_metric = _confusion(truth, [class_name in item[5] for item in class_items])
        cand_metric = _confusion(truth, [class_name in item[6] for item in class_items])
        checks, class_fail, class_insufficient = _metric_checks(base_metric, cand_metric)
        class_status = FAIL if class_fail else (INSUFFICIENT if class_insufficient else PASS)
        if not any(truth):
            class_status = INSUFFICIENT
            class_insufficient.append("gerçek pozitif sınıf örneği yok")
        failures.extend(f"{class_name}: {x}" for x in class_fail)
        report["insufficient_reasons"].extend(
            f"{class_name}: {x}" for x in class_insufficient
        )
        report["classes"][class_name] = {
            "status": class_status,
            "baseline": base_metric,
            "candidate": cand_metric,
            "checks": checks,
        }

    safe_items = [item for item in selected if not item[4]]
    if not safe_items:
        report["insufficient_reasons"].append("operasyonel/dispatch FP için güvenli örnek yok")
    else:
        base_operational = sum(
            int(item[1]["n_events"] > 0 or bool(item[1]["triggered"])) for item in safe_items
        )
        cand_operational = sum(
            int(item[2]["n_events"] > 0 or bool(item[2]["triggered"])) for item in safe_items
        )
        base_dispatch = sum(int(bool(item[1]["triggered"])) for item in safe_items)
        cand_dispatch = sum(int(bool(item[2]["triggered"])) for item in safe_items)
        operational_check = PASS if cand_operational <= base_operational else FAIL
        dispatch_check = PASS if cand_dispatch <= base_dispatch else FAIL
        report["false_positives"] = {
            "operational": {
                "definition": "güvenli örnekte n_events>0 veya triggered dolu",
                "baseline": _rate(base_operational, len(safe_items)),
                "candidate": _rate(cand_operational, len(safe_items)),
                "not_higher": operational_check,
            },
            "dispatch": {
                "definition": "güvenli örnekte triggered dolu",
                "baseline": _rate(base_dispatch, len(safe_items)),
                "candidate": _rate(cand_dispatch, len(safe_items)),
                "not_higher": dispatch_check,
            },
        }
        if operational_check == FAIL:
            failures.append(
                f"operasyonel FP arttı ({base_operational} -> {cand_operational})"
            )
        if dispatch_check == FAIL:
            failures.append(f"dispatch FP arttı ({base_dispatch} -> {cand_dispatch})")

    # Liste nesneleri başta rapora bağlandı; son eklemeleri yansıtmak için yinele.
    report["failures"] = failures
    if failures:
        report["status"] = FAIL
    elif report["insufficient_reasons"]:
        report["status"] = INSUFFICIENT
    else:
        report["status"] = PASS
    return report


def _fmt_rate(metric: Mapping[str, Any]) -> str:
    value = metric.get("value")
    return "INSUFFICIENT" if value is None else f"{metric['k']}/{metric['n']}={value:.4f}"


def _fmt_confusion(metric: Mapping[str, Any]) -> str:
    return (
        f"TP={metric['tp']} FP={metric['fp']} FN={metric['fn']} TN={metric['tn']} "
        f"P={_fmt_rate(metric['precision'])} R={_fmt_rate(metric['recall'])}"
    )


def print_report(report: Mapping[str, Any]) -> None:
    print(f"STATUS: {report['status']}")
    cov = report.get("coverage") or {}
    print(
        "COVERAGE: "
        f"baseline={cov.get('baseline')} candidate={cov.get('candidate')} "
        f"same_ids={cov.get('same_sample_ids')} "
        f"non_smoke={cov.get('non_smoke_evaluable', 'n/a')}"
    )
    errors = report.get("errors") or {}
    if errors:
        print(
            f"ERRORS: baseline={errors.get('baseline')} candidate={errors.get('candidate')} "
            f"gate={errors.get('not_higher')}"
        )
    general = report.get("general")
    if general:
        print(f"GENERAL A: {_fmt_confusion(general['baseline'])}")
        print(f"GENERAL B: {_fmt_confusion(general['candidate'])}")
    for name, item in sorted((report.get("classes") or {}).items()):
        print(f"CLASS {name} [{item['status']}] A: {_fmt_confusion(item['baseline'])}")
        print(f"CLASS {name} [{item['status']}] B: {_fmt_confusion(item['candidate'])}")
    for name, item in sorted((report.get("false_positives") or {}).items()):
        print(
            f"{name.upper()} FP [{item['not_higher']}]: "
            f"A={_fmt_rate(item['baseline'])} B={_fmt_rate(item['candidate'])}"
        )
    for issue in report.get("failures") or []:
        print(f"FAIL: {issue}")
    for issue in report.get("insufficient_reasons") or []:
        print(f"INSUFFICIENT: {issue}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", help="referans eval JSON arşivi")
    parser.add_argument("candidate", help="aday eval JSON arşivi")
    parser.add_argument(
        "--include-smoke",
        action="store_true",
        help="varsayılan duman dışlamasını kapat",
    )
    parser.add_argument(
        "--require-class",
        action="append",
        default=[],
        help="manifestte bulunması zorunlu tehlike sınıfı (tekrarlanabilir)",
    )
    parser.add_argument("--json", action="store_true", help="insan raporu yerine JSON bas")
    parser.add_argument("--report-json", help="raporu ayrıca bu JSON dosyasına yaz")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = compare_archives(
            args.baseline,
            args.candidate,
            include_smoke=args.include_smoke,
            required_classes=args.require_class,
        )
    except ArchiveError as exc:
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": INSUFFICIENT,
            "baseline": os.path.abspath(args.baseline),
            "candidate": os.path.abspath(args.candidate),
            "failures": [],
            "insufficient_reasons": [str(exc)],
        }
    if args.report_json:
        with open(args.report_json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
    return {PASS: 0, FAIL: 1, INSUFFICIENT: 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
