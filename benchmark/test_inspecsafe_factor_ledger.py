#!/usr/bin/env python
"""InspecSafe faktor defteri icin modelsiz testler."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.inspecsafe_factor_ledger import (  # noqa: E402
    FACTOR_CHOICES,
    FACTOR_EVIDENCE,
    FACTORS,
    SCENARIOS,
    SCENARIO_FACTOR_LEVELS,
    parse_factors,
    severity_for,
    verification_prompt,
)


def test_resmi_tablo_kritik_ornekleri() -> None:
    assert severity_for("OIL_GAS_CHEMICAL", ["NO_MASK"]) == "LEVEL_ONE"
    assert severity_for("COAL_CONVEYOR", ["WATER_POOLING"]) == "LEVEL_THREE"
    assert severity_for("TUNNEL", ["MOBILE_PHONE"]) == "LEVEL_THREE"
    assert severity_for("POWER", ["MOBILE_PHONE"]) == "LEVEL_TWO"
    assert severity_for("METALLURGY", ["SMOKING"]) == "LEVEL_TWO"


def test_en_agir_destekli_faktor_kazanir() -> None:
    assert severity_for(
        "TUNNEL", ["WATER_POOLING", "NO_HARD_HAT", "SMOKE"]
    ) == "LEVEL_ONE"
    assert severity_for("UNKNOWN", ["SMOKE"]) is None
    assert severity_for("POWER", []) is None


def test_kapali_faktor_secimi_strict() -> None:
    assert parse_factors("NONE") == ()
    assert parse_factors("FLAME") == ("FLAME",)
    assert parse_factors("FLAME|SMOKE") == ("FLAME", "SMOKE")
    assert parse_factors("SMOKE|FLAME") is None
    assert parse_factors('"SMOKE"') is None
    assert len(FACTOR_CHOICES) == 1 + len(FACTORS) + len(FACTORS) * (len(FACTORS) - 1) // 2


def test_her_faktorun_kanit_tanimi_ve_tablo_karsiligi_var() -> None:
    assert set(FACTOR_EVIDENCE) == set(FACTORS)
    used = {factor for table in SCENARIO_FACTOR_LEVELS.values() for factor in table}
    assert used <= set(FACTORS)
    assert set(SCENARIO_FACTOR_LEVELS) == set(SCENARIOS)
    assert "mere dampness" in FACTOR_EVIDENCE["WATER_POOLING"]
    assert "lens spot" in FACTOR_EVIDENCE["SMOKE"]
    assert "stain" in FACTOR_EVIDENCE["OIL_LEAK"]
    assert "UNCERTAIN" in verification_prompt("WATER_POOLING")


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
