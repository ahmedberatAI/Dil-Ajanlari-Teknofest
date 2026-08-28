#!/usr/bin/env python
"""InspecSafe yuksek-performans profil secicisinin yerel testleri."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.report_inspecsafe_hierarchical import (  # noqa: E402
    high_performance_gate,
    select_high_performance,
)


def _candidate(name: str, f1: float, accuracy: float, recall: float,
               precision: float = 0.80, fpr: float = 0.05,
               coverage: float = 0.99, calls: float = 0.5) -> dict:
    return {
        "spec": {"architecture": name},
        "metrics": {
            "coverage": {"p": coverage},
            "test_prior_weighted_accuracy": accuracy,
            "binary": {
                "test_prior_precision": precision,
                "test_prior_f1": f1,
                "recall": {"p": recall},
                "fpr": {"p": fpr},
            },
        },
        "severity_call_rate": calls,
    }


def test_sinirlar_dahil_edilir() -> None:
    gate = high_performance_gate(_candidate("hierarchy", 0.8, 0.8, 0.8)["metrics"])
    assert gate["pass"]


def test_precision_fpr_coverage_kapilari_fail_closed() -> None:
    for candidate in (
        _candidate("p", 0.9, 0.9, 0.9, precision=0.7999),
        _candidate("f", 0.9, 0.9, 0.9, fpr=0.0501),
        _candidate("c", 0.9, 0.9, 0.9, coverage=0.9899),
    ):
        assert not high_performance_gate(candidate["metrics"])["pass"]


def test_f1_sonra_accuracy_recall_ve_maliyet_sirasi() -> None:
    candidates = [
        _candidate("low_f1", 0.89, 0.99, 0.99),
        _candidate("low_accuracy", 0.90, 0.80, 0.99),
        _candidate("low_recall", 0.90, 0.81, 0.90, calls=0.1),
        _candidate("expensive", 0.90, 0.81, 0.91, calls=0.8),
        _candidate("winner", 0.90, 0.81, 0.91, calls=0.4),
    ]
    selected = select_high_performance({"candidates": candidates})
    assert selected is not None
    assert selected["spec"]["architecture"] == "winner"


def main() -> int:
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"[GECTI] {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"[KALDI] {test.__name__}: {exc}")
    print(f"{len(tests) - failed}/{len(tests)} test gecti")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
