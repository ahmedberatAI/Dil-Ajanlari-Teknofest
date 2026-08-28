import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmark.isafety_ensemble_v4 import _candidates
class T(unittest.TestCase):
 def test_unique_candidates(self):
  self.assertEqual(_candidates({"direct_letter":"A","vlm_letter":"A","cascade_letter":"B"}),("A","B"))
if __name__=="__main__":unittest.main()
