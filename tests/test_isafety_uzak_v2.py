import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmark.isafety_uzak_v2 import _items, _letter, _metrics, _paired


class ISafetyV2Test(unittest.TestCase):
    def test_parser_is_exact(self):
        self.assertEqual(_letter("A", None, 16), "A")
        self.assertIsNone(_letter("A. explanation", None, 16))
        self.assertIsNone(_letter("A", "timeout", 16))

    def test_selection_is_deterministic_unique(self):
        a = _items("hazard", 10, 2026); b = _items("hazard", 10, 2026)
        self.assertEqual(a, b)
        self.assertEqual(len({x["video_name"] for x in a}), 10)

    def test_metrics_and_pairing(self):
        rows = [{"direct_letter": "A", "direct_correct": True,
                 "cascade_letter": "B", "cascade_correct": False},
                {"direct_letter": "A", "direct_correct": False,
                 "cascade_letter": "B", "cascade_correct": True}]
        self.assertEqual(_metrics(rows, "direct")["coverage"]["k"], 2)
        self.assertEqual(_paired(rows)["cascade_fixed"], 1)
        self.assertEqual(_paired(rows)["cascade_broke"], 1)


if __name__ == "__main__": unittest.main()
