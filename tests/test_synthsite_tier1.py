import unittest

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.synthsite_tier1 import _prediction, puanla


class SynthSiteTier1Test(unittest.TestCase):
    def test_prediction_fail_closed(self):
        self.assertEqual(_prediction("IHLAL_VAR"), "IHLAL_VAR")
        self.assertEqual(_prediction(" ihlal_yok \n"), "IHLAL_YOK")
        self.assertEqual(_prediction("aciklama: IHLAL_VAR"), "error")
        self.assertEqual(_prediction(None, "timeout"), "error")

    def test_puanla_abstention_is_not_silent_success(self):
        rows = [
            {"target": "unsafe", "prediction": "IHLAL_VAR"},
            {"target": "unsafe", "prediction": "GORUNMUYOR"},
            {"target": "safe", "prediction": "IHLAL_YOK"},
            {"target": "safe", "prediction": "IHLAL_VAR"},
        ]
        got = puanla(rows)
        self.assertEqual(got["confusion"], {
            "tp": 1,
            "fp": 1,
            "tn": 1,
            "fn_decided": 0,
            "abstain_or_error_positive": 1,
            "abstain_or_error_negative": 0,
        })
        self.assertEqual(got["recall_strict"]["rate"], 0.5)
        self.assertEqual(got["coverage"]["rate"], 0.75)
        self.assertEqual(got["strict_accuracy"]["rate"], 0.5)
        self.assertFalse(got["acceptance"]["pass"])


if __name__ == "__main__":
    unittest.main()
