#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""İSG non-regression kapısının salt arşiv mantığı."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from benchmark import isg_nonregression_gate as gate


def _row(
    sample_id: str,
    class_name: str | None,
    unsafe: bool,
    predicted: str | None,
    *,
    triggered: list[str] | None = None,
    error: str | None = None,
) -> dict:
    events = []
    if predicted:
        events.append({
            "event": predicted,
            "category": "Güvenlik",
            "isg_kod": predicted,
        })
    row = {
        "path": sample_id,
        "category": "Anomali" if unsafe else "Normal",
        "is_anomaly": unsafe,
        "isg_sinif": class_name,
        "n_events": len(events),
        "events": events,
        "summary": "",
        "triggered": list(triggered or []),
    }
    if error:
        row["error"] = error
    return row


def _archive(rows: list[dict], *, revision: str = "A", eval_dir: str = "data/eval_fixture") -> dict:
    return {
        "eval_dir": eval_dir,
        "dedup": {"enabled": True, "n_input": len(rows), "n_unique": len(rows), "skipped": []},
        "kosum": {"pipeline_revision": revision, "model": "fixed"},
        "rows": rows,
    }


def _write_pair(tmp_path: Path, base: dict, cand: dict) -> tuple[str, str]:
    a, b = tmp_path / "base.json", tmp_path / "candidate.json"
    a.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    b.write_text(json.dumps(cand, ensure_ascii=False), encoding="utf-8")
    return str(a), str(b)


def _balanced_rows() -> list[dict]:
    return [
        _row("data/x/Anomali/Safe_Walkway_Violation/p1.mp4",
             "Safe_Walkway_Violation", True, "Safe_Walkway_Violation"),
        _row("data/x/Anomali/Safe_Walkway_Violation/p2.mp4",
             "Safe_Walkway_Violation", True, "Safe_Walkway_Violation"),
        _row("data/x/Normal/Safe_Walkway/n1.mp4", "Safe_Walkway", False, None),
        _row("data/x/Anomali/Unauthorized_Intervention/u1.mp4",
             "Unauthorized_Intervention", True, "Unauthorized_Intervention"),
        _row("data/x/Normal/Authorized_Intervention/a1.mp4",
             "Authorized_Intervention", False, None),
    ]


class NonRegressionGateTests(unittest.TestCase):
    def _compare(self, base: dict, cand: dict, **kwargs) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            a, b = _write_pair(Path(tmp), base, cand)
            return gate.compare_archives(a, b, **kwargs)

    def test_identical_coverage_and_metrics_pass(self) -> None:
        rows = _balanced_rows()
        report = self._compare(
            _archive(rows, revision="base"),
            _archive(copy.deepcopy(rows), revision="candidate"),
        )
        self.assertEqual(report["status"], gate.PASS)
        self.assertTrue(report["coverage"]["same_sample_ids"])
        self.assertNotEqual(
            report["run_manifest_sha256"]["baseline"],
            report["run_manifest_sha256"]["candidate"],
        )
        self.assertEqual(report["general"]["baseline"]["tp"], 3)
        self.assertEqual(report["general"]["baseline"]["fp"], 0)

    def test_recall_drop_fails_even_when_precision_stays_one(self) -> None:
        base_rows = _balanced_rows()
        cand_rows = copy.deepcopy(base_rows)
        cand_rows[1]["events"] = []
        cand_rows[1]["n_events"] = 0
        report = self._compare(_archive(base_rows), _archive(cand_rows, revision="B"))
        self.assertEqual(report["status"], gate.FAIL)
        self.assertEqual(report["general"]["checks"]["precision_not_lower"], gate.PASS)
        self.assertEqual(report["general"]["checks"]["recall_not_lower"], gate.FAIL)

    def test_class_false_positive_and_operational_fp_increase_fail(self) -> None:
        base_rows = _balanced_rows()
        cand_rows = copy.deepcopy(base_rows)
        cand_rows[2]["events"] = [{
            "event": "Safe_Walkway_Violation",
            "category": "Güvenlik",
            "isg_kod": "Safe_Walkway_Violation",
        }]
        cand_rows[2]["n_events"] = 1
        report = self._compare(_archive(base_rows), _archive(cand_rows, revision="B"))
        self.assertEqual(report["status"], gate.FAIL)
        class_report = report["classes"]["Safe_Walkway_Violation"]
        self.assertEqual(class_report["candidate"]["fp"], 1)
        self.assertEqual(class_report["checks"]["precision_not_lower"], gate.FAIL)
        self.assertEqual(report["false_positives"]["operational"]["not_higher"], gate.FAIL)

    def test_dispatch_fp_and_error_count_are_independent_guards(self) -> None:
        base_rows = _balanced_rows()
        cand_rows = copy.deepcopy(base_rows)
        cand_rows[2]["triggered"] = ["guvenlik_ekibi_uyar"]
        cand_rows[4]["error"] = "timeout"
        report = self._compare(_archive(base_rows), _archive(cand_rows, revision="B"))
        self.assertEqual(report["status"], gate.FAIL)
        self.assertEqual(report["errors"]["not_higher"], gate.FAIL)
        self.assertEqual(report["false_positives"]["dispatch"]["not_higher"], gate.FAIL)

    def test_operational_fp_is_guarded_even_without_class_claim(self) -> None:
        base_rows = _balanced_rows()
        cand_rows = copy.deepcopy(base_rows)
        cand_rows[2]["events"] = [{
            "event": "Belirsiz düşük önem gözlemi",
            "category": "Diğer",
            "isg_kod": None,
        }]
        cand_rows[2]["n_events"] = 1
        report = self._compare(_archive(base_rows), _archive(cand_rows, revision="B"))
        self.assertEqual(report["status"], gate.FAIL)
        self.assertEqual(report["general"]["checks"]["precision_not_lower"], gate.FAIL)
        self.assertEqual(report["false_positives"]["operational"]["not_higher"], gate.FAIL)
        self.assertEqual(report["false_positives"]["dispatch"]["not_higher"], gate.PASS)

    def test_generic_hazard_normal_manifest_has_binary_precision_recall_gate(self) -> None:
        rows = [
            _row("data/generic/Anomali/Hazard/a1.mp4", None, True, None),
            _row("data/generic/Anomali/Hazard/a2.mp4", None, True, None),
            _row("data/generic/Normal/Normal/n1.mp4", None, False, None),
            _row("data/generic/Normal/Normal/n2.mp4", None, False, None),
        ]
        rows[0]["events"] = [{"event": "kayma", "category": "Anomali", "isg_kod": None}]
        rows[0]["n_events"] = 1
        candidate = copy.deepcopy(rows)
        report = self._compare(_archive(rows), _archive(candidate, revision="B"))
        self.assertEqual(report["status"], gate.PASS)
        self.assertEqual(report["general"]["baseline"]["tp"], 1)
        self.assertEqual(report["general"]["baseline"]["fn"], 1)
        self.assertEqual(report["general"]["baseline"]["fp"], 0)
        self.assertEqual(report["classes"], {})

    def test_zero_precision_denominator_is_insufficient_not_pass(self) -> None:
        rows = [
            _row("data/x/Anomali/Safe_Walkway_Violation/p.mp4",
                 "Safe_Walkway_Violation", True, None),
            _row("data/x/Normal/Safe_Walkway/n.mp4", "Safe_Walkway", False, None),
        ]
        report = self._compare(_archive(rows), _archive(copy.deepcopy(rows), revision="B"))
        self.assertEqual(report["status"], gate.INSUFFICIENT)
        self.assertEqual(
            report["general"]["checks"]["precision_not_lower"], gate.INSUFFICIENT
        )

    def test_different_sample_ids_or_manifest_are_insufficient(self) -> None:
        rows = _balanced_rows()
        cand_rows = copy.deepcopy(rows[:-1])
        report = self._compare(
            _archive(rows),
            _archive(cand_rows, revision="B", eval_dir="data/other"),
        )
        self.assertEqual(report["status"], gate.INSUFFICIENT)
        self.assertFalse(report["coverage"]["same_sample_ids"])
        self.assertTrue(
            any("manifest alanı farklı: eval_dir" in x for x in report["insufficient_reasons"])
        )

    def test_required_missing_class_is_insufficient(self) -> None:
        rows = _balanced_rows()[:3]
        report = self._compare(
            _archive(rows),
            _archive(copy.deepcopy(rows), revision="B"),
            required_classes=["Unauthorized_Intervention"],
        )
        self.assertEqual(report["status"], gate.INSUFFICIENT)
        self.assertTrue(
            any("zorunlu sınıf manifestte yok" in x for x in report["insufficient_reasons"])
        )

    def test_smoke_rows_are_excluded_without_hiding_non_smoke_gate(self) -> None:
        rows = _balanced_rows()
        rows.append({
            "path": "data/x/Smoke/s1.mp4",
            "category": "Smoke",
            "is_anomaly": True,
            "isg_sinif": "Smoke",
            "n_events": 0,
            "events": [],
            "summary": "",
            "triggered": [],
        })
        report = self._compare(_archive(rows), _archive(copy.deepcopy(rows), revision="B"))
        self.assertEqual(report["status"], gate.PASS)
        self.assertEqual(report["excluded"]["smoke"], 1)


if __name__ == "__main__":
    unittest.main()
