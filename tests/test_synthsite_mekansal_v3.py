import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmark.synthsite_mekansal_v3 import _combine


class SpatialV3Test(unittest.TestCase):
    def test_deterministic_and(self):
        self.assertEqual(_combine("IHLAL_VAR", "DOGRUDAN_DUSUM_BOLGESI"), "IHLAL_VAR")
        self.assertEqual(_combine("IHLAL_VAR", "FARKLI_DERINLIK"), "IHLAL_YOK")
        self.assertEqual(_combine("IHLAL_YOK", "DOGRUDAN_DUSUM_BOLGESI"), "IHLAL_YOK")
        self.assertEqual(_combine("IHLAL_VAR", "GORUNMUYOR"), "GORUNMUYOR")
        self.assertEqual(_combine("error", "DOGRUDAN_DUSUM_BOLGESI"), "error")


if __name__ == "__main__":
    unittest.main()
