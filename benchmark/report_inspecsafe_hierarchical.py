#!/usr/bin/env python
"""InspecSafe-V1 hiyerarsik calibration/development/holdout JSON raporlayicisi."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


HIGH_PERFORMANCE_MIN_COVERAGE = 0.99
HIGH_PERFORMANCE_MIN_TEST_PRIOR_PRECISION = 0.80
HIGH_PERFORMANCE_MAX_FPR = 0.05


def _pct(value: float) -> str:
    return f"{100.0 * float(value):.1f}%"


def _rate(value: dict[str, Any]) -> str:
    return (
        f"{_pct(value['p'])} ({value['k']}/{value['n']}; "
        f"95% GA {_pct(value['ci_low'])}-{_pct(value['ci_high'])})"
    )


def _metric_rows(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    pairs = [
        ("4-sinif test-onculu accuracy", baseline["test_prior_weighted_accuracy"],
         candidate["test_prior_weighted_accuracy"], "pct"),
        ("4-sinif empirical accuracy", baseline["empirical_accuracy"],
         candidate["empirical_accuracy"], "rate"),
        ("Unsafe precision (test onculu)", baseline["binary"]["test_prior_precision"],
         candidate["binary"]["test_prior_precision"], "pct"),
        ("Unsafe recall", baseline["binary"]["recall"],
         candidate["binary"]["recall"], "rate"),
        ("Unsafe F1 (test onculu)", baseline["binary"]["test_prior_f1"],
         candidate["binary"]["test_prior_f1"], "pct"),
        ("Normal FPR", baseline["binary"]["fpr"], candidate["binary"]["fpr"], "rate"),
        ("Macro recall", baseline["macro_recall"], candidate["macro_recall"], "pct"),
        ("Kapsama", baseline["coverage"], candidate["coverage"], "rate"),
    ]
    lines = ["| Metrik | Duz taban | Aday |", "|---|---:|---:|"]
    for name, left, right, kind in pairs:
        if kind == "rate":
            left_text, right_text = _rate(left), _rate(right)
        else:
            left_text, right_text = _pct(left), _pct(right)
        lines.append(f"| {name} | {left_text} | {right_text} |")
    return lines


def high_performance_gate(metrics: dict[str, Any]) -> dict[str, Any]:
    """Kullanici tarafindan calibration bitmeden secilen birincil profil."""
    checks = {
        "coverage_at_least_99pct": (
            float(metrics["coverage"]["p"]) >= HIGH_PERFORMANCE_MIN_COVERAGE),
        "test_prior_precision_at_least_80pct": (
            float(metrics["binary"]["test_prior_precision"])
            >= HIGH_PERFORMANCE_MIN_TEST_PRIOR_PRECISION),
        "normal_fpr_at_most_5pct": (
            float(metrics["binary"]["fpr"]["p"]) <= HIGH_PERFORMANCE_MAX_FPR),
    }
    return {"checks": checks, "pass": all(checks.values())}


def select_high_performance(summary: dict[str, Any]) -> dict[str, Any] | None:
    feasible = [
        candidate for candidate in summary.get("candidates", [])
        if high_performance_gate(candidate["metrics"])["pass"]
    ]
    return max(
        feasible,
        key=lambda candidate: (
            float(candidate["metrics"]["binary"]["test_prior_f1"]),
            float(candidate["metrics"]["test_prior_weighted_accuracy"]),
            float(candidate["metrics"]["binary"]["recall"]["p"]),
            -float(candidate["severity_call_rate"]),
        ),
        default=None,
    )


def render(result: dict[str, Any]) -> str:
    meta = result["meta"]
    summary = result["summary"]
    phase = meta["protocol"]["phase"]
    if phase == "calibration":
        high_performance = select_high_performance(summary)
        selected = summary.get("selected")
        if selected is None:
            spec = None
            candidate = None
            gate = None
            call_rate = None
        else:
            spec = selected["spec"]
            candidate = selected["metrics"]
            gate = selected["gate"]
            call_rate = selected["severity_call_rate"]
        baseline = summary["baseline"]
        search_note = (
            f"Aranan aday: {len(summary['candidates'])}; "
            f"kapidan gecen: {sum(row['gate']['pass'] for row in summary['candidates'])}."
        )
    else:
        high_performance = None
        spec = summary["spec"]
        baseline = summary["baseline"]
        candidate = summary["candidate"]
        gate = summary["gate"]
        call_rate = summary["severity_call_rate"]
        search_note = "Karar tanimi calibration kilidinden okunmustur; bu bolmede esik aranmadi."

    lines = [
        f"# InspecSafe-V1 hiyerarsik {phase} sonucu",
        "",
        f"- Kosum anahtari: `{meta['run_key']}`",
        f"- Manifest SHA-256: `{meta['protocol']['manifest_sha256']}`",
        f"- Runner SHA-256: `{meta['protocol']['runner_sha256']}`",
        f"- Tamamlanma: `{meta['completed_at']}`",
        f"- Secili ornek: **{len(result['rows'])}** inspection grubu",
        f"- Karar tanimi: `{json.dumps(spec, sort_keys=True) if spec else 'YOK'}`",
        "",
        search_note,
        "",
    ]
    if phase == "calibration":
        lines += ["## Birincil yuksek-performans profili", ""]
        if high_performance is None:
            lines += [
                "**KALDI:** coverage >= %99, test-onculu precision >= %80 ve "
                "FPR <= %5 kosullarini birlikte saglayan aday yok.",
                "",
            ]
        else:
            high_metrics = high_performance["metrics"]
            high_gate = high_performance_gate(high_metrics)
            lines += [
                f"- Karar tanimi: `{json.dumps(high_performance['spec'], sort_keys=True)}`",
                f"- Severity ek-cagri orani: **{_pct(high_performance['severity_call_rate'])}**",
                f"- Kapi: **{'GECTI' if high_gate['pass'] else 'KALDI'}**",
                "",
            ]
            lines += _metric_rows(summary["baseline"], high_metrics)
            lines += [""]

        lines += ["## Ikincil kati gerilemesizlik profili", ""]
    if candidate is None:
        lines += ["**CALIBRATION KALDI:** gerilemesizlik kosullarini saglayan aday yok.", ""]
        return "\n".join(lines)

    lines += _metric_rows(baseline, candidate)
    lines += [
        "",
        f"Severity ek-cagri orani: **{_pct(call_rate)}**.",
        "",
        f"## Kapi — {'GECTI' if gate['pass'] else 'KALDI'}",
        "",
    ]
    for name, passed in gate["checks"].items():
        lines.append(f"- {'GECTI' if passed else 'KALDI'} — `{name}`")

    lines += ["", "## Sinif recall", "", "| Sinif | Duz | Aday | Destek |",
              "|---|---:|---:|---:|"]
    for label in ("LEVEL_ONE", "LEVEL_TWO", "LEVEL_THREE", "NO_ABNORMALITY"):
        left = baseline["per_class"][label]
        right = candidate["per_class"][label]
        lines.append(
            f"| {label} | {_pct(left['recall'])} | {_pct(right['recall'])} | {right['support']} |")

    lines += ["", "## Alan bazinda binary", "",
              "| Alan | Recall duz | Recall aday | FPR duz | FPR aday |",
              "|---|---:|---:|---:|---:|"]
    for domain in sorted(baseline["by_domain"]):
        left = baseline["by_domain"][domain]
        right = candidate["by_domain"][domain]
        lines.append(
            f"| {domain} | {_pct(left['recall']['p'])} | {_pct(right['recall']['p'])} | "
            f"{_pct(left['fpr']['p'])} | {_pct(right['fpr']['p'])} |")

    execution = summary["execution"]
    lines += [
        "", "## Yurutme", "",
        f"- Observe/direct/flat/binary/severity hata: `{execution['observe_errors']}` / "
        f"`{execution['direct_errors']}` / "
        f"`{execution['flat_errors']}` / `{execution['binary_errors']}` / "
        f"`{execution['severity_errors']}`",
        f"- Logprob hard-choice fallback: `{execution['score_fallbacks']}`",
        f"- Retry alan cagri: `{execution['retry_calls']}`; azami retry: "
        f"`{execution['max_retries']}`",
        "",
    ]
    if "paired" in summary:
        paired = summary["paired"]
        lines += [
            "## Eslesik fark", "",
            f"- Adayin duzelttigi: **{paired['candidate_fixed']}**",
            f"- Adayin bozdugu: **{paired['candidate_broke']}**",
            f"- Exact McNemar p: **{paired['mcnemar_exact_p']:.6g}**",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.loads(args.result.read_text(encoding="utf-8"))
    phase = result["meta"]["protocol"]["phase"]
    run_key = result["meta"]["run_key"]
    output = args.output or (
        Path(__file__).resolve().parents[1] / "docs"
        / f"rapor_inspecsafe_hier_{phase}_{run_key}_2026-08-28.md"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(result), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
