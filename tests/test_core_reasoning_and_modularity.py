"""Independent oracles for algorithm derivation and modular programming contracts."""
from decimal import Decimal
import itertools
from pathlib import Path
import re
import sys
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from model import load_articles,load_modules,load_tracks

PATTERN=re.compile(r"(?ms)^~~~python[^\n]*\n(.*?)^~~~[ \t]*$")

def load(lang,slug):
    text=(ROOT/"content"/lang/"topics"/(slug+".md")).read_text(encoding="utf-8")
    chunks=PATTERN.findall(text)
    if not chunks:
        raise AssertionError("missing Python snippets")
    name="test_foundation_"+lang+"_"+slug.replace("-","_")
    module=types.ModuleType(name)
    sys.modules[name]=module
    try:
        for block in chunks:
            exec(compile(block,slug,"exec"),module.__dict__)
        return dict(module.__dict__)
    finally:
        sys.modules.pop(name,None)

def exhaustive_trade(prices):
    best=None
    for buy in range(len(prices)):
        for sell in range(buy+1,len(prices)):
            profit=prices[sell]-prices[buy]
            if profit > 0 and (best is None or profit>best[2]):
                best=(buy,sell,profit)
    return best

class CoreLearningContracts(unittest.TestCase):
    def test_algorithm_matches_independent_quadratic_oracle(self):
        for lang in ("en","pt"):
            impl=load(lang,"algorithmic-problem-solving-method")["best_trade"]
            for n in range(7):
                for seq in itertools.product((0,1,3),repeat=n):
                    with self.subTest(lang=lang,input=seq):
                        self.assertEqual(impl(seq),exhaustive_trade(seq))
            for invalid in ([1,True,3],[-1,1],["1",2]):
                with self.assertRaises(ValueError):
                    impl(invalid)
            with self.assertRaises(TypeError):
                impl(None)

    def test_pure_module_contracts(self):
        for lang in ("en","pt"):
            ns=load(lang,"modular-programming-interfaces")
            parse=ns["parse_readings"]
            summarize=ns["summarize_readings"]
            render=ns["render_summary"]
            report=ns["run_report"]
            self.assertEqual(parse(["1.0","3.0"]), (Decimal("1.0"),Decimal("3.0")))
            self.assertEqual(summarize(parse(["1","3"])),
                             (Decimal("1"),Decimal("3"),Decimal("2")))
            self.assertEqual(render(summarize(parse(["1","3"]))),
                             "min=1; max=3; mean=2")
            for bad in ([""],["nan"],["Infinity"],["what"],[None]):
                with self.subTest(lang=lang,bad=bad),self.assertRaises(ValueError):
                    parse(bad)
            writes=[]
            with self.assertRaises(ValueError):
                report(lambda: ["invalid"],writes.append)
            self.assertEqual(writes,[])
            result=report(lambda: ["1","3"],writes.append)
            self.assertEqual(writes,[result])

    def test_curricular_prerequisites_and_placement(self):
        mods=load_modules()
        self.assertEqual(mods["algorithmic-problem-solving-method"],"foundations")
        self.assertEqual(mods["modular-programming-interfaces"],"engineering")
        chapters=load_articles()
        for lang in ("en","pt"):
            self.assertEqual(chapters[lang]["algorithmic-problem-solving-method"]["meta"]["prerequisites"],
                             ["programming-control-flow-functions","logic-proofs-invariants","complexity-analysis"])
            self.assertEqual(chapters[lang]["modular-programming-interfaces"]["meta"]["prerequisites"],
                             ["programming-control-flow-functions","programming-semantics-contracts"])
        for track in load_tracks()[:2]:
            ids=[i for s in track["sections"] for i in s["articles"]]
            self.assertEqual(len(ids),len(set(ids)))
            for dependency in chapters["en"]["algorithmic-problem-solving-method"]["meta"]["prerequisites"]:
                self.assertLess(ids.index(dependency),ids.index("algorithmic-problem-solving-method"))
            for dependency in chapters["en"]["modular-programming-interfaces"]["meta"]["prerequisites"]:
                self.assertLess(ids.index(dependency),ids.index("modular-programming-interfaces"))
            self.assertLess(ids.index("modular-programming-interfaces"),ids.index("object-oriented-design"))
            self.assertLess(ids.index("algorithmic-problem-solving-method"),ids.index("binary-search"))

if __name__=="__main__":
    unittest.main()
