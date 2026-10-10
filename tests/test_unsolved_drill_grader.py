"""The public grader is executable and rejects bad answers without giving a solution."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
EXAMPLES=ROOT/"examples"/"python"
sys.path.insert(0,str(EXAMPLES))
from drill_grader import COUPON_CASES, RELEASE_CASES, evaluate
from unsolved_drills import cheapest_route_with_coupon, parallel_release_rounds

class UnsolvedAssessmentTest(unittest.TestCase):
    def test_starters_are_intentionally_unsolved(self):
        with self.assertRaises(NotImplementedError):
            cheapest_route_with_coupon(1,[])
        with self.assertRaises(NotImplementedError):
            parallel_release_rounds(0,[])

    def test_baselines_and_wrong_implementations(self):
        self.assertGreaterEqual(len(COUPON_CASES),6)
        self.assertGreaterEqual(len(RELEASE_CASES),6)
        self.assertEqual(COUPON_CASES[0][2],9)
        self.assertEqual(RELEASE_CASES[0][2],3)
        with self.assertRaises(AssertionError):
            evaluate(lambda n,e: 0, lambda n,e: 0)
        with self.assertRaises(NotImplementedError):
            evaluate()

if __name__=="__main__":
    unittest.main()
