"""Integrated collector contracts against name VM and independent AST oracle."""
from fractions import Fraction
from pathlib import Path
import random
import re
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"tests"))
from model import load_articles,load_modules,load_tracks
from test_mutable_recursion_compiler_contracts import CASES,direct_eval
from examples.python.stateful_function_compiler import parse_stateful
from examples.python.lexical_slot_verifier import (
    compile_slots,run_slots,SlotCode,VerifiedProgram,BytecodeError,
)
from examples.python.managed_slot_vm import (
    run_managed,evaluate_managed,ManagedRef,ManagedResult,
)

TOPIC="integrated-vm-mark-sweep-gc"


class IntegratedGCContracts(unittest.TestCase):
    def test_executable_semantics_match_independent_oracles(self):
        for source,typ,expected in CASES:
            with self.subTest(source=source[:70]):
                old=run_slots(compile_slots(source))
                new=run_managed(compile_slots(source),gc_interval=1)
                tree=direct_eval(parse_stateful(source))
                self.assertEqual(new.value,old)
                self.assertEqual(new.value,tree)
                self.assertEqual(new.value,expected)
                self.assertGreaterEqual(new.collections,1)
                self.assertEqual(new.live_objects,0)
                self.assertEqual(new.allocated_objects,
                                 new.reclaimed + new.live_objects)

    def test_gc_preserves_shared_cell_during_calls(self):
        source=("let make:Fn(Int)->Fn()->Int="
                "fn(seed:Int)->Fn()->Int=>var x:Int=seed in "
                "fn()->Int=>set x=x+1 in "
                "let f:Fn()->Int=make(5) in f()+f()")
        results=[]
        for frequency in (1,2,3,8,1000):
            info=run_managed(compile_slots(source),gc_interval=frequency)
            results.append(info.value)
            self.assertEqual(info.value,Fraction(13))
            self.assertGreater(info.reclaimed,0)
            self.assertEqual(info.live_objects,0)
            self.assertGreater(info.allocated_objects,0)
        self.assertEqual(len(set(results)),1)

    def test_gc_reclaims_unreachable_recursive_cycles(self):
        source=("let rec f:Fn(Int)->Int="
                "fn(n:Int)->Int=>if n<2 then 1 else n*f(n-1) in f(7)")
        for frequency in (1,7,1000):
            output=run_managed(compile_slots(source),gc_interval=frequency)
            self.assertEqual(output.value,Fraction(5040))
            self.assertEqual(output.live_objects,0)
            self.assertEqual(output.reclaimed,output.allocated_objects)
            self.assertGreaterEqual(output.allocated_objects,2)

    def test_collector_retains_top_level_closure_result(self):
        program=compile_slots("fn(x:Int)->Int=>x+1")
        result=run_managed(program,gc_interval=1)
        self.assertIsInstance(result.value,ManagedRef)
        self.assertEqual(result.live_objects,1)
        self.assertEqual(result.allocated_objects,1)
        self.assertEqual(result.reclaimed,0)

    def test_mutable_capture_across_lexical_shadowing(self):
        source=("var x:Int=2 in let f:Fn(Int)->Int="
                "fn(y:Int)->Int=>set x=x+y in "
                "let x:Int=999 in f(3)+f(4)")
        output=run_managed(compile_slots(source),gc_interval=1)
        self.assertEqual(output.value,Fraction(14))
        self.assertGreater(output.collections,1)
        self.assertEqual(output.live_objects,0)

    def test_small_heap_budget_and_collection(self):
        source=("var x:Int=1 in let inc:Fn()->Int="
                "fn()->Int=>set x=x+1 in inc()+inc()")
        with self.assertRaises(MemoryError):
            run_managed(compile_slots(source),capacity=1,gc_interval=1)
        result=run_managed(compile_slots(source),capacity=3,gc_interval=1)
        self.assertEqual(result.value,Fraction(5))
        self.assertLessEqual(result.peak_objects,3)
        self.assertEqual(result.live_objects,0)
        with self.assertRaises(ValueError):
            run_managed(compile_slots(source),capacity=0)

    def test_runtime_limits_and_static_verification_gate(self):
        source=("let rec f:Fn(Int)->Int=fn(n:Int)->Int=>"
                "f(n+1) in f(0)")
        code=compile_slots(source)
        with self.assertRaisesRegex(RuntimeError,"call-frame limit"):
            run_managed(code,max_frames=7,gc_interval=1)
        with self.assertRaisesRegex(RuntimeError,"step limit"):
            run_managed(code,max_steps=20,gc_interval=1)
        for invalid in (0,-1,True,3.1,None):
            for keyword in ("gc_interval","max_steps","max_frames"):
                with self.subTest(value=invalid,key=keyword):
                    with self.assertRaises(ValueError):
                        run_managed(code,**{keyword:invalid})
        forged=VerifiedProgram("Int",SlotCode((),(),"Int",(
            ("ADD",None,0),("RETURN",None,1)
        )))
        with self.assertRaises(BytecodeError):
            run_managed(forged)

    def test_seeded_mutable_graph_lifetimes(self):
        rng=random.Random(12102026)
        for _ in range(140):
            a,b,c=(rng.randrange(0,70) for _ in range(3))
            source=(f"var x:Int={a} in let f:Fn(Int)->Int="
                    f"fn(y:Int)->Int=>set x=x+y in f({b})+f({c})")
            expected=Fraction(2*a+2*b+c)
            value=evaluate_managed(source,gc_interval=rng.randrange(1,13))[1]
            self.assertEqual(value.value,expected)
            self.assertEqual(value.live_objects,0)
            self.assertEqual(value.allocated_objects,
                             value.live_objects+value.reclaimed)

    def test_bilingual_chapters_and_track_sequence(self):
        chapters=load_articles()
        self.assertEqual(load_modules()[TOPIC],"foundations")
        code=[]
        for language in ("en","pt"):
            item=chapters[language][TOPIC]
            self.assertEqual(item["meta"]["prerequisites"],
                             ["versioned-bytecode-serialization",
                              "tracing-garbage-collection-reachability"])
            for marker in ("managed_slot_vm.py","run_managed","ManagedRef",
                           "gc_interval","Cell","mark-and-sweep"):
                self.assertIn(marker,item["body"])
            samples=re.findall(r"(?ms)^~~~python\n(.*?)^~~~[ \t]*$",item["body"])
            self.assertEqual(len(samples),1)
            code.append(samples[0])
        self.assertEqual(code[0],code[1])
        for track in load_tracks()[:2]:
            entries=[a for section in track["sections"] for a in section["articles"]]
            for req in chapters["en"][TOPIC]["meta"]["prerequisites"]:
                self.assertLess(entries.index(req),entries.index(TOPIC))


if __name__=="__main__":
    unittest.main()
