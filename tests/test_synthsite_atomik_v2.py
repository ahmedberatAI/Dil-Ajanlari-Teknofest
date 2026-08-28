import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.synthsite_atomik_v2 import _development_subset, _prediction
from dilajan.isg_kanit import KanitSonucu, Hukum


class AtomicV2Test(unittest.TestCase):
    def test_prediction_is_fail_closed(self):
        self.assertEqual(_prediction(KanitSonucu("x", Hukum.SUPPORTED, {}, {})), "IHLAL_VAR")
        self.assertEqual(_prediction(KanitSonucu("x", Hukum.REFUTED, {}, {})), "IHLAL_YOK")
        self.assertEqual(_prediction(KanitSonucu("x", Hukum.INSUFFICIENT, {}, {})), "GORUNMUYOR")
        self.assertEqual(_prediction(KanitSonucu("x", Hukum.SUPPORTED, {}, {"a": "hata"})), "error")

    def test_subset_is_balanced_and_deterministic(self):
        rows = ([{"filename": f"u{i}.mp4", "target": "unsafe"} for i in range(10)]
                + [{"filename": f"s{i}.mp4", "target": "safe"} for i in range(10)])
        a = _development_subset(rows, 8)
        b = _development_subset(list(reversed(rows)), 8)
        self.assertEqual(a, b)
        self.assertEqual(sum(x["target"] == "unsafe" for x in a), 4)
        self.assertEqual(sum(x["target"] == "safe" for x in a), 4)


if __name__ == "__main__":
    unittest.main()
