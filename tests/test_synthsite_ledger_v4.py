import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmark.synthsite_ledger_v4 import _combine, _rotated_choices


class LedgerV4Test(unittest.TestCase):
    def test_fail_closed_composition(self):
        self.assertEqual(_combine("IHLAL_VAR", "KANIT_UYUMLU"), "IHLAL_VAR")
        self.assertEqual(_combine("IHLAL_VAR", "ACIK_KARSI_KANIT"), "IHLAL_YOK")
        self.assertEqual(_combine("IHLAL_VAR", "KANIT_YETERSIZ"), "GORUNMUYOR")
        self.assertEqual(_combine("IHLAL_YOK", "KANIT_UYUMLU"), "IHLAL_YOK")

    def test_choice_order_is_deterministic_per_file(self):
        self.assertEqual(_rotated_choices("a.mp4"), _rotated_choices("a.mp4"))
        self.assertEqual(set(_rotated_choices("a.mp4")),
                         {"KANIT_UYUMLU", "ACIK_KARSI_KANIT", "KANIT_YETERSIZ"})


if __name__ == "__main__":
    unittest.main()
