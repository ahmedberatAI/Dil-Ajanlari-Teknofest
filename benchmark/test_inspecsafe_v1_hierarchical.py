#!/usr/bin/env python
"""InspecSafe-V1 hiyerarsik kosucusunun model gerektirmeyen testleri."""
from __future__ import annotations

import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.inspecsafe_v1_hierarchical import (  # noqa: E402
    PHASES,
    TEST_UNSAFE_PRIOR,
    _attach_groups,
    _parse_allowed,
    _phase_for_group,
    _read_lock,
    _resolve_gold,
    _stratified_take,
    evaluate,
    consensus_hybrid_prediction,
    hierarchy_prediction,
    hybrid_prediction,
    non_regression_gate,
    select_threshold,
)
from benchmark.inspecsafe_v1_formatter_smoke import _choose  # noqa: E402


def _row(gold: str, flat: str | None, score: float | None,
         severity: str | None) -> dict:
    return {
        "gold": gold,
        "domain": "power",
        "direct": {"label": None},
        "flat": {"label": flat},
        "binary": {"p_unsafe": score},
        "severity": {"label": severity},
    }


def test_kisitli_cikti_ayristirma() -> None:
    assert _parse_allowed("UNSAFE", ("UNSAFE", "NORMAL")) == "UNSAFE"
    assert _parse_allowed('"UNSAFE"', ("UNSAFE", "NORMAL")) is None
    assert _parse_allowed("LEVEL_ONE", ("LEVEL_ONE", "LEVEL_TWO")) == "LEVEL_ONE"


def test_split_deterministik() -> None:
    first = _phase_for_group("inspection-point-17")
    assert first in PHASES
    assert _phase_for_group("inspection-point-17") == first


def test_resmi_txt_sidecar_yol_etiketine_ustundur() -> None:
    gold, mismatch = _resolve_gold(
        "LEVEL_ONE",
        "There is standing water. The safety level is rated as Level 3.",
    )
    assert gold == "LEVEL_THREE"
    assert mismatch
    gold, mismatch = _resolve_gold(
        "LEVEL_ONE",
        "Personnel are smoking. The safety level is Level One.",
    )
    assert gold == "LEVEL_ONE"
    assert not mismatch
    assert _resolve_gold("LEVEL_ONE", "No unique safety label here.") == (None, False)


def test_dengeli_secim_nadir_seviyeyi_korur_ve_deterministiktir() -> None:
    rows = []
    for index, gold in enumerate(
        ["LEVEL_ONE"] * 7 + ["LEVEL_TWO"] * 2 + ["LEVEL_THREE"]
    ):
        rows.append({"id": f"unsafe-{index}", "gold": gold})
    chosen = _stratified_take(rows, 5)
    assert len(chosen) == 5
    assert {row["gold"] for row in chosen} == {
        "LEVEL_ONE", "LEVEL_TWO", "LEVEL_THREE",
    }
    assert chosen == _stratified_take(list(reversed(rows)), 5)
    counts = Counter(row["gold"] for row in chosen)
    assert counts == Counter({"LEVEL_ONE": 3, "LEVEL_TWO": 1, "LEVEL_THREE": 1})


def test_kilit_model_ve_api_sozlesmesini_kapsar() -> None:
    expected = {
        "runner_sha256": "runner", "manifest_sha256": "manifest",
        "prompt_hashes": {"p": "h"}, "contract": {"algi": "vlm"},
        "private_api": "https://private.invalid/v1", "dataset_revision": "data",
        "official_code_revision": "code", "split_salt": "salt", "revision": "rev",
    }
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "lock.json"
        path.write_text(json.dumps(expected), encoding="utf-8")
        lock, digest = _read_lock(path, expected)
        assert lock == expected and len(digest) == 64
        changed = {**expected, "contract": {"algi": "baska-vlm"}}
        try:
            _read_lock(path, changed)
        except RuntimeError as exc:
            assert "contract" in str(exc)
        else:
            raise AssertionError("model sozlesmesi degisikligi reddedilmedi")


def test_ayni_nokta_ve_duplikalar_tek_grupta() -> None:
    rows = [
        {"relative_path": "DATA_PATH/train/Annotations/A/point-a/1.jpg",
         "image_sha256": "sha-a"},
        {"relative_path": "DATA_PATH/train/Annotations/A/point-a/2.jpg",
         "image_sha256": "sha-b"},
        {"relative_path": "DATA_PATH/train/Annotations/A/point-b/3.jpg",
         "image_sha256": "sha-a"},
        {"relative_path": "DATA_PATH/train/Annotations/A/point-c/4.jpg",
         "image_sha256": "sha-c"},
    ]
    _attach_groups(rows)
    assert rows[0]["group_id"] == rows[1]["group_id"] == rows[2]["group_id"]
    assert rows[3]["group_id"] != rows[0]["group_id"]
    assert rows[0]["phase"] == rows[2]["phase"]


def test_hiyerarsik_esik() -> None:
    row = _row("LEVEL_ONE", "NO_ABNORMALITY", 0.70, "LEVEL_ONE")
    assert hierarchy_prediction(row, 0.70) == "LEVEL_ONE"
    assert hierarchy_prediction(row, 0.71) == "NO_ABNORMALITY"
    row["binary"]["p_unsafe"] = None
    assert hierarchy_prediction(row, 0.50) is None


def test_hibrit_veto_ve_rescue() -> None:
    unsafe = _row("LEVEL_ONE", "LEVEL_ONE", 0.10, "LEVEL_TWO")
    assert hybrid_prediction(unsafe, 0.20, 0.80) == "NO_ABNORMALITY"
    unsafe["binary"]["p_unsafe"] = 0.30
    assert hybrid_prediction(unsafe, 0.20, 0.80) == "LEVEL_ONE"
    normal = _row("LEVEL_TWO", "NO_ABNORMALITY", 0.90, "LEVEL_TWO")
    assert hybrid_prediction(normal, 0.20, 0.80) == "LEVEL_TWO"
    normal["binary"]["p_unsafe"] = 0.70
    assert hybrid_prediction(normal, 0.20, 0.80) == "NO_ABNORMALITY"


def test_hibrit_yardimci_hatada_duz_karara_doner() -> None:
    row = _row("LEVEL_ONE", "LEVEL_ONE", None, None)
    row["binary"]["error"] = "timeout"
    assert hybrid_prediction(row, 0.20, 0.80) == "LEVEL_ONE"
    row["flat"]["label"] = "NO_ABNORMALITY"
    assert hybrid_prediction(row, 0.20, 0.80) == "NO_ABNORMALITY"


def test_uzlasi_hibriti_iki_kanit_ister() -> None:
    row = _row("LEVEL_TWO", "NO_ABNORMALITY", 0.90, "LEVEL_TWO")
    row["direct"]["label"] = "NO_ABNORMALITY"
    assert consensus_hybrid_prediction(row, 0.20, 0.80) == "NO_ABNORMALITY"


def test_formatter_ornek_secimi_gold_kullanmaz() -> None:
    rows = []
    for index, flat in enumerate(("LEVEL_ONE", "NO_ABNORMALITY", "LEVEL_TWO")):
        row = _row("LEVEL_THREE", flat, 0.60, "LEVEL_ONE")
        row.update({"id": f"id-{index}", "observation": "visible equipment"})
        rows.append(row)
    chosen = _choose(rows, {
        "architecture": "hybrid", "veto_threshold": 0.10, "rescue_threshold": 0.90,
    }, 3)
    assert {row["id"] for row in chosen} == {"id-0", "id-1", "id-2"}
    row["direct"]["label"] = "LEVEL_ONE"
    assert consensus_hybrid_prediction(row, 0.20, 0.80) == "LEVEL_TWO"
    row = _row("NO_ABNORMALITY", "LEVEL_ONE", 0.10, "LEVEL_TWO")
    row["direct"]["label"] = "LEVEL_ONE"
    assert consensus_hybrid_prediction(row, 0.20, 0.80) == "LEVEL_ONE"
    row["direct"]["label"] = "NO_ABNORMALITY"
    assert consensus_hybrid_prediction(row, 0.20, 0.80) == "NO_ABNORMALITY"


def test_gecersiz_adversarial_sayilir() -> None:
    rows = [
        _row("LEVEL_ONE", None, None, None),
        _row("NO_ABNORMALITY", None, None, None),
    ]
    metrics = evaluate(rows, lambda row: row["flat"]["label"])
    assert metrics["binary"]["fn"] == 1
    assert metrics["binary"]["fp"] == 1
    assert metrics["coverage"]["k"] == 0


def test_prior_precision_formulu() -> None:
    rows = [
        _row("LEVEL_ONE", "LEVEL_ONE", 0.9, "LEVEL_ONE"),
        _row("NO_ABNORMALITY", "LEVEL_ONE", 0.9, "LEVEL_ONE"),
        _row("NO_ABNORMALITY", "NO_ABNORMALITY", 0.1, "LEVEL_ONE"),
    ]
    metrics = evaluate(rows, lambda row: row["flat"]["label"])
    expected = TEST_UNSAFE_PRIOR / (TEST_UNSAFE_PRIOR + 0.5 * (1 - TEST_UNSAFE_PRIOR))
    assert abs(metrics["binary"]["test_prior_precision"] - expected) < 1e-8


def test_calibration_dominant_esik_bulur() -> None:
    rows = [
        _row("LEVEL_ONE", "NO_ABNORMALITY", 0.80, "LEVEL_ONE"),
        _row("LEVEL_ONE", "LEVEL_ONE", 0.70, "LEVEL_ONE"),
        _row("LEVEL_TWO", "NO_ABNORMALITY", 0.75, "LEVEL_TWO"),
        _row("LEVEL_THREE", "LEVEL_THREE", 0.72, "LEVEL_THREE"),
        _row("NO_ABNORMALITY", "LEVEL_ONE", 0.40, "LEVEL_ONE"),
        _row("NO_ABNORMALITY", "NO_ABNORMALITY", 0.30, "LEVEL_ONE"),
        _row("NO_ABNORMALITY", "NO_ABNORMALITY", 0.20, "LEVEL_TWO"),
        _row("NO_ABNORMALITY", "NO_ABNORMALITY", 0.10, "LEVEL_THREE"),
    ]
    selection = select_threshold(rows)
    assert selection["selected"] is not None
    assert selection["selected"]["gate"]["pass"]
    spec = selection["selected"]["spec"]
    assert spec["architecture"] in {"hierarchy", "hybrid", "consensus_hybrid"}
    if spec["architecture"] == "hierarchy":
        assert 0.40 < spec["threshold"] <= 0.70
    else:
        assert 0.01 <= spec["veto_threshold"] <= 0.50
        assert 0.50 <= spec["rescue_threshold"] <= 0.99
    assert non_regression_gate(
        selection["baseline"], selection["selected"]["metrics"])["pass"]


def test_en_kotu_alan_gerilemesi_kapida_yakalanir() -> None:
    rows = [
        {**_row("LEVEL_ONE", "LEVEL_ONE", 0.9, "LEVEL_ONE"),
         "domain": "power", "candidate": "LEVEL_ONE"},
        {**_row("NO_ABNORMALITY", "NO_ABNORMALITY", 0.1, "LEVEL_ONE"),
         "domain": "power", "candidate": "NO_ABNORMALITY"},
        {**_row("LEVEL_ONE", "LEVEL_ONE", 0.9, "LEVEL_ONE"),
         "domain": "tunnel", "candidate": "NO_ABNORMALITY"},
        {**_row("NO_ABNORMALITY", "LEVEL_ONE", 0.1, "LEVEL_ONE"),
         "domain": "tunnel", "candidate": "NO_ABNORMALITY"},
    ]
    baseline = evaluate(rows, lambda row: row["flat"]["label"])
    candidate = evaluate(rows, lambda row: row["candidate"])
    gate = non_regression_gate(baseline, candidate)
    assert not gate["checks"]["worst_domain_recall_non_decreasing"]
    assert not gate["pass"]


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
