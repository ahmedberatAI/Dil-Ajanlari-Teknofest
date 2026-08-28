#!/usr/bin/env python
"""InspecSafe EPV veto kararinin modelsiz testleri."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.inspecsafe_epv_veto import epv_prediction, epv_should_veto  # noqa: E402


SPEC = {"architecture": "hierarchy", "threshold": 0.5}


def _row(flat: str = "NO_ABNORMALITY", score: float = 0.8) -> dict:
    return {
        "id": "r1",
        "flat": {"label": flat},
        "binary": {"p_unsafe": score, "error": None},
        "severity": {"label": "LEVEL_TWO"},
        "observe_error": None,
    }


def _record(algi: str = "NOT_SUPPORTED", olay: str = "NOT_SUPPORTED") -> dict:
    return {
        "factors": ["WATER_POOLING"],
        "factor_error": None,
        "video_error": None,
        "verifications": {
            "WATER_POOLING": {
                "algi": algi, "olay": olay,
                "algi_error": None, "olay_error": None,
            },
        },
    }


def test_iki_acik_curutme_rescue_veto_eder() -> None:
    record = _record()
    assert epv_should_veto(record)
    assert epv_prediction(_row(), SPEC, {"r1": record}) == "NO_ABNORMALITY"


def test_destek_belirsizlik_ve_hata_fail_open() -> None:
    for record in (
        _record("SUPPORTED", "NOT_SUPPORTED"),
        _record("UNCERTAIN", "NOT_SUPPORTED"),
        {**_record(), "factor_error": "timeout"},
        {**_record(), "factors": []},
        None,
    ):
        assert not epv_should_veto(record)
        records = {} if record is None else {"r1": record}
        assert epv_prediction(_row(), SPEC, records) == "LEVEL_TWO"


def test_duz_unsafe_karar_asla_veto_edilmez() -> None:
    record = _record()
    assert epv_prediction(_row(flat="LEVEL_ONE"), SPEC, {"r1": record}) == "LEVEL_TWO"


def test_binary_normal_aynen_kalir() -> None:
    assert epv_prediction(_row(score=0.2), SPEC, {"r1": _record()}) == "NO_ABNORMALITY"


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
