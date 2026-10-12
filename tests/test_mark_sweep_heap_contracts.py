"""Independent reference reachability oracle for heap mark/sweep simulation."""
from pathlib import Path
import random
import re
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from model import load_articles,load_modules,load_tracks
from examples.python.mark_sweep_heap import (
    HeapModel,HeapObject,Collection,closure_lifetime_example,
    cyclic_collection_example,
)

TOPIC="tracing-garbage-collection-reachability"


def independent_fixpoint(objects,roots):
    """Set relaxation oracle, deliberately without a DFS or queue."""
    live=set(roots)
    while True:
        expanded=set(live)
        for oid in tuple(live):
            expanded.update(objects[oid].references)
        if expanded==live:
            return live
        live=expanded


class HeapReachabilityContracts(unittest.TestCase):
    def test_returned_closure_keeps_cell_alive_until_root_removed(self):
        first,last=closure_lifetime_example()
        self.assertEqual(len(first.reachable),3)
        self.assertEqual(len(first.reclaimed),1)
        self.assertEqual(last.remaining,0)
        self.assertEqual(len(last.reclaimed),3)

    def test_unreachable_cycle_reclamation(self):
        report=cyclic_collection_example()
        self.assertEqual(len(report.reclaimed),2)
        self.assertEqual(report.remaining,0)

    def test_two_roots_sharing_one_cell(self):
        heap=HeapModel()
        cell=heap.allocate("cell")
        env=heap.allocate("environment",(cell,))
        left=heap.allocate("closure",(env,))
        right=heap.allocate("closure",(env,))
        unrelated=heap.allocate("value")
        self.assertEqual(heap.collect((left,right)).reclaimed,(unrelated,))
        self.assertEqual(heap.collect((right,)).reclaimed,(left,))
        self.assertEqual(heap.mark((right,)),(cell,env,right))
        self.assertEqual(heap.collect(()).reclaimed,(cell,env,right))

    def test_self_reference_and_missing_root(self):
        heap=HeapModel()
        a=heap.allocate("pair")
        heap.set_references(a,(a,))
        self.assertEqual(heap.collect((a,)).reachable,(a,))
        self.assertEqual(heap.collect(()).reclaimed,(a,))
        with self.assertRaises(ValueError):
            heap.mark((a,))
        with self.assertRaises(ValueError):
            heap.get(a)

    def test_reassignment_changes_reachability(self):
        heap=HeapModel()
        cell=heap.allocate("cell")
        value1=heap.allocate("value")
        value2=heap.allocate("value")
        heap.set_references(cell,(value1,))
        self.assertEqual(heap.mark((cell,)),(cell,value1))
        heap.set_references(cell,(value2,))
        self.assertEqual(heap.collect((cell,)).reclaimed,(value1,))
        self.assertEqual(heap.collect(()).remaining,0)

    def test_invalid_heap_operations_and_budget(self):
        for capacity in (0,-1,True,9000):
            with self.assertRaises(ValueError):
                HeapModel(capacity=capacity)
        heap=HeapModel(capacity=2)
        a=heap.allocate("value")
        b=heap.allocate("pair",(a,))
        with self.assertRaises(MemoryError):
            heap.allocate("value")
        with self.assertRaises(ValueError):
            heap.allocate("pair",(999,))
        for invalid in (True,-1,0,999,"1"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    heap.set_references(a,(invalid,))
        with self.assertRaises(ValueError):
            heap.allocate("not-a-kind")
        with self.assertRaises(ValueError):
            heap.mark("not-roots")
        with self.assertRaises(ValueError):
            heap.set_references(999,(a,))
        heap.collect((b,))
        self.assertEqual(heap.get(b),HeapObject("pair",(a,)))

    def test_random_graphs_match_independent_fixedpoint(self):
        rng=random.Random(1102026)
        for n in (1,2,4,8,16,32):
            for _ in range(30):
                heap=HeapModel()
                addresses=[heap.allocate(rng.choice(("value","cell","closure","pair")))
                           for i in range(n)]
                for oid in addresses:
                    refs=rng.sample(addresses,rng.randint(0,min(n,5)))
                    heap.set_references(oid,refs)
                roots=rng.sample(addresses,rng.randrange(0,n+1))
                before=dict(heap.objects)
                expected=independent_fixpoint(before,roots)
                self.assertEqual(set(heap.mark(roots)),expected)
                report=heap.collect(roots)
                self.assertEqual(set(report.reachable),expected)
                self.assertEqual(set(report.reclaimed),set(before)-expected)
                self.assertEqual(set(heap.objects),expected)
                self.assertEqual(heap.collect(roots).reclaimed,())

    def test_bilingual_documentation_and_track(self):
        articles=load_articles()
        self.assertEqual(load_modules()[TOPIC],"foundations")
        examples=[]
        for lang in ("en","pt"):
            article=articles[lang][TOPIC]
            self.assertEqual(article["meta"]["prerequisites"],
                             ["mutable-cells-recursive-functions"])
            for name in ("mark_sweep_heap.py","HeapModel","collect",
                         "closure_lifetime_example","cyclic_collection_example"):
                self.assertIn(name,article["body"])
            matches=re.findall(r"(?ms)^~~~python\n(.*?)^~~~[ \t]*$",
                               article["body"])
            self.assertEqual(len(matches),1)
            examples.append(matches[0])
        self.assertEqual(examples[0],examples[1])
        for track in load_tracks()[:2]:
            ordered=[x for sec in track["sections"] for x in sec["articles"]]
            self.assertLess(ordered.index("mutable-cells-recursive-functions"),
                            ordered.index(TOPIC))


if __name__=="__main__":
    unittest.main()
