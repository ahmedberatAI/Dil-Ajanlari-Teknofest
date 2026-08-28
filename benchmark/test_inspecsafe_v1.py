#!/usr/bin/env python
"""InspecSafe-V1 kosucusunun model gerektirmeyen sozlesme testleri."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.inspecsafe_v1 import (  # noqa: E402
    LABELS,
    OFFICIAL_PROMPT_SHA256,
    _annotation_level,
    _binary,
    _load_official_prompt,
    _multiclass,
    parse_choice,
    parse_formatted,
    parse_official_level,
    prompt_hashes,
    summarize,
)


def _row(gold: str, direct: str | None, system: str | None,
         formatted: bool = True) -> dict:
    return {
        "gold": gold,
        "domain": "power",
        "latency_s": 1.0,
        "calls": [{"latency_s": 0.25}],
        "direct": {"label": direct, "correct": direct == gold},
        "system": {
            "label": system,
            "observe_error": None if system else "failed",
            "correct": system == gold,
            "end_to_end_valid": bool(formatted and system),
            "end_to_end_correct": bool(formatted and system == gold),
        },
    }


def test_prompt_sabiti() -> None:
    prompt = _load_official_prompt()
    assert len(prompt.encode("utf-8")) == 2802
    assert prompt_hashes(prompt)["official"] == OFFICIAL_PROMPT_SHA256


def test_resmi_cikti_ayristirma() -> None:
    assert parse_official_level(
        "[Image Description]\nVisible pipe.\n[Safety Level]\n[Level one]"
    ) == "LEVEL_ONE"
    assert parse_official_level(
        "[Image Description]\nRoutine scene.\n[Safety Level]\nno abnormalities observed"
    ) == "NO_ABNORMALITY"
    # Resmi kod yalniz son satirin son sozcugunu okur; burada "two" secilir.
    assert parse_official_level("[Safety Level]\nLevel one / Level two") == "LEVEL_TWO"
    assert parse_official_level("Level one") == "LEVEL_ONE"
    assert parse_official_level("Unrecognizable") is None


def test_anotasyon_ayristirma() -> None:
    assert _annotation_level("Scene text\n[Safety Level]\nLevel I") == "LEVEL_ONE"
    assert _annotation_level("The safety level is Grade One.") == "LEVEL_ONE"
    assert _annotation_level("The safety level is grade three.") == "LEVEL_THREE"
    assert _annotation_level("The safety level is Grade 2.") == "LEVEL_TWO"
    assert _annotation_level("Safety Level: IV") == "NO_ABNORMALITY"
    assert _annotation_level("Safety Level\nno abnormalities observed") == "NO_ABNORMALITY"
    assert _annotation_level("Level I and Level II") is None


def test_yapilandirilmis_cikti() -> None:
    assert parse_choice("LEVEL_TWO") == "LEVEL_TWO"
    assert parse_choice('"LEVEL_TWO"') is None
    raw = '{"image_description":"visible water","safety_level":"LEVEL_TWO"}'
    assert parse_formatted(raw, "LEVEL_TWO") == {
        "image_description": "visible water", "safety_level": "LEVEL_TWO"}
    assert parse_formatted(raw, "LEVEL_ONE") is None


def test_strict_invalid_politikasi() -> None:
    rows = [
        _row("LEVEL_ONE", None, None, False),
        _row("NO_ABNORMALITY", None, None, False),
    ]
    binary = _binary(rows, "direct")["strict"]
    assert (binary["tp"], binary["fp"], binary["fn"], binary["tn"]) == (0, 1, 1, 0)
    multi = _multiclass(rows, "direct")
    assert multi["accuracy_strict"]["k"] == 0
    assert multi["coverage"]["k"] == 0


def test_tam_sistem_birincil_kapi() -> None:
    rows = [_row(label, label, label, True) for label in LABELS]
    # Semantik karar dogru olsa da formatter arizasi tam sistemi bozmalidir.
    rows[0]["system"]["end_to_end_valid"] = False
    rows[0]["system"]["end_to_end_correct"] = False
    result = summarize(rows)
    assert result["arms"]["system"]["multiclass"]["accuracy_strict"]["k"] == 4
    assert result["arms"]["end_to_end"]["multiclass"]["accuracy_strict"]["k"] == 3
    assert result["paired_direct_vs_system"]["system_broke"] == 1
    assert not result["non_regression_gate"]["pass"]


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
