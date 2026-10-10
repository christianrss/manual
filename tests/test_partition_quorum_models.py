"""Independent exhaustive network partition checks."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"examples"/"python"))
from network_partition_quorum import (
    components,eligible_majority_components,check_all_partitions)

class PartitionModels(unittest.TestCase):
    def test_all_three_and_five_member_link_graphs(self):
        self.assertEqual(check_all_partitions(3),8)
        self.assertEqual(check_all_partitions(5),1024)

    def test_majority_and_isolated_minority(self):
        self.assertEqual(set(eligible_majority_components(3,[(0,1)])),
                         {frozenset({0,1})})
        self.assertEqual(eligible_majority_components(3,[]),[])
        self.assertEqual(set(eligible_majority_components(5,[(0,1),(1,2)])),
                         {frozenset({0,1,2})})

    def test_no_majority_after_two_two_one_split(self):
        groups=components(5,[(0,1),(2,3)])
        self.assertEqual(sorted(map(len,groups)),[1,2,2])
        self.assertFalse(eligible_majority_components(5,[(0,1),(2,3)]))

    def test_invalid_and_repaired_topologies(self):
        with self.assertRaises(ValueError):
            components(0,[])
        with self.assertRaises(ValueError):
            components(3,[(0,3)])
        self.assertEqual(len(eligible_majority_components(5,[])),0)
        links=[(0,1),(2,3)]
        self.assertFalse(eligible_majority_components(5,links))
        self.assertEqual(len(eligible_majority_components(5,links+[(1,2)])),1)

if __name__=="__main__":
    unittest.main()
