"""Ensure the second unsolved assessment and public grader reject incorrect answers."""
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"examples"/"python"))
from drill_grader_2 import BATCH_CASES,ISLAND_CASES,evaluate
from unsolved_drills_2 import minimum_batch_capacity,islands_after_activation

class UnsolvedAssessmentTwo(unittest.TestCase):
    def test_public_fixture_quality(self):
        self.assertGreaterEqual(len(BATCH_CASES),9)
        self.assertGreaterEqual(len(ISLAND_CASES),9)
        self.assertEqual(BATCH_CASES[0][2],18)
        self.assertEqual(ISLAND_CASES[-1][3], [1,2,3,4,1])
        self.assertTrue(any(not actions for _,_,actions,_ in ISLAND_CASES))
        self.assertTrue(any(any(expected[i]!=expected[i-1]
                                 for i in range(1,len(expected)))
                            for _,_,_,expected in ISLAND_CASES))

    def test_starters_not_implemented_intentionally(self):
        with self.assertRaises(NotImplementedError):
            minimum_batch_capacity([1,2],1)
        with self.assertRaises(NotImplementedError):
            islands_after_activation(1,1,[(0,0)])

    def test_grader_fails_trivial_wrong_implementations(self):
        with self.assertRaises(AssertionError):
            evaluate(lambda values,m: sum(values),
                     lambda rows,cols,ops:[0]*len(ops))
        with self.assertRaises(NotImplementedError):
            evaluate()

if __name__=="__main__":
    unittest.main()
