import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmark.isafety_vlm_arm_v3 import _paired

class T(unittest.TestCase):
 def test_pair(self):
  rows=[{"a":True,"b":False},{"a":False,"b":True},{"a":False,"b":True}]
  x=_paired(rows,"a","b");self.assertEqual(x["fixed"],2);self.assertEqual(x["broke"],1)
if __name__=="__main__":unittest.main()
