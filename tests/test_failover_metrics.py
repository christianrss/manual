"""Failover timing interpretation and ordering contracts."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from failover_metrics import FailoverTiming

class FailoverTimingTests(unittest.TestCase):
    def test_ordered_observations(self):
        metrics=FailoverTiming(10,12,17,18.5).phases()
        self.assertEqual(metrics["observed_recovery_s"],8.5)
        self.assertEqual(metrics["stop_s"],2)
        self.assertEqual(metrics["promotion_s"],5)
        self.assertEqual(metrics["new_write_s"],1.5)

    def test_refuse_invalid_order(self):
        with self.assertRaises(ValueError):
            FailoverTiming(1,2,1.5,3).phases()
        with self.assertRaises(ValueError):
            FailoverTiming(4,3,5,6).phases()

if __name__=="__main__":
    unittest.main()
