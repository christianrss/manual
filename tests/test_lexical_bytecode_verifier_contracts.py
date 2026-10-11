"""Structural bytecode verifier, lexical slot addressing, and VM equivalence.

Use explicit arithmetic oracles, the previous independent AST interpreter
and adversarial malformed instruction fixtures. Finite tests, not a proof.
"""
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import random
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from model import load_articles, load_modules, load_tracks
from test_mutable_recursion_compiler_contracts import direct_eval, CASES
from examples.python.stateful_function_compiler import (
    parse_stateful, compile_stateful,
)
from examples.python.typed_function_compiler import run_functions, FunctionType
from examples.python.lexical_slot_verifier import (
    SlotInfo, SlotCode, VerifiedProgram, BytecodeError,
    compile_slots, verify_slots, run_slots, evaluate_slots,
)

TOPIC = "lexical-addresses-bytecode-verification"


def walk_blocks(block):
    yield block
    for op, value, _ in block.instructions:
        if op == "CLOSURE_SLOT":
            yield from walk_blocks(value)


class LexicalVerifierContracts(unittest.TestCase):
    def test_previous_stateful_suite_matches_new_backend_and_direct_oracle(self):
        for source, kind, expected in CASES:
            with self.subTest(source=source[:65]):
                program = compile_slots(source)
                self.assertEqual(program.result_type, kind)
                self.assertTrue(verify_slots(program))
                self.assertEqual(run_slots(program), expected)
                self.assertEqual(run_functions(compile_stateful(source)), expected)
                self.assertEqual(direct_eval(parse_stateful(source)), expected)
                self.assertEqual(evaluate_slots(source), (kind, expected))

    def test_resolved_loads_and_shared_mutable_capture(self):
        text = ("var x:Int=2 in let inc:Fn(Int)->Int="
                "fn(y:Int)->Int=>set x=x+y in "
                "let x:Int=100 in inc(3)+inc(4)")
        program = compile_slots(text)
        self.assertEqual(run_slots(program), Fraction(14))
        opcodes = [op for b in walk_blocks(program.code)
                   for op, _, _ in b.instructions]
        self.assertIn("LOAD_SLOT", opcodes)
        self.assertIn("STORE_SLOT", opcodes)
        self.assertIn("CLOSURE_SLOT", opcodes)
        self.assertNotIn("LOAD", opcodes)
        self.assertNotIn("STORE", opcodes)
        for block in walk_blocks(program.code):
            for op, arg, _ in block.instructions:
                if op in ("LOAD_SLOT", "STORE_SLOT"):
                    self.assertIsInstance(arg, tuple)
                    self.assertEqual(len(arg), 2)
                    self.assertTrue(all(type(n) is int and n >= 0
                                        for n in arg))

    def test_manual_slot_depth_and_shadowing(self):
        text = ("let x:Int=10 in let f:Fn(Int)->Int="
                "fn(y:Int)->Int=>x+y in let x:Int=99 in f(2)")
        program = compile_slots(text)
        self.assertEqual(run_slots(program), Fraction(12))
        lambda_blocks = [b for b in walk_blocks(program.code)
                         if b.parameters]
        self.assertEqual(len(lambda_blocks), 1)
        function = lambda_blocks[0]
        self.assertEqual([(op, value) for op, value, _ in
                          function.instructions if op=="LOAD_SLOT"],
                         [("LOAD_SLOT",(1,0)), ("LOAD_SLOT",(0,0))])
        self.assertEqual(function.parameters[0].name, "y")

    def test_immutable_and_mutable_binding_modes(self):
        self.assertEqual(evaluate_slots("let x:Int=2 in x+1"),
                         ("Int", Fraction(3)))
        self.assertEqual(evaluate_slots("let f:Fn()->Bool=fn()->Bool=>true in f()"),
                         ("Bool", True))
        self.assertEqual(evaluate_slots("var x:Int=1 in (set x=7)+x"),
                         ("Int", Fraction(14)))
        self.assertEqual(evaluate_slots("if true then 1/2 else 1/0"),
                         ("Rat", Fraction(1,2)))
        with self.assertRaises(ZeroDivisionError):
            evaluate_slots("if false then 1/2 else 1/0")

    def test_finite_generated_counters_and_factorials(self):
        rng = random.Random(20261011)
        for _ in range(200):
            seed, increment, extra = [rng.randrange(0,30) for _ in range(3)]
            source = (f"var x:Int={seed} in let f:Fn(Int)->Int="
                      f"fn(y:Int)->Int=>set x=x+y in f({increment})+f({extra})")
            answer = Fraction(2*(seed+increment)+extra)
            self.assertEqual(evaluate_slots(source)[1], answer)
            self.assertEqual(run_functions(compile_stateful(source)), answer)
        for n in range(11):
            source = (f"let rec f:Fn(Int)->Int=fn(n:Int)->Int=>"
                      f"if n<2 then 1 else n*f(n-1) in f({n})")
            factorial = 1
            for k in range(2,n+1):
                factorial *= k
            self.assertEqual(evaluate_slots(source)[1], Fraction(factorial))

    def test_verify_rejects_invalid_lexical_addresses(self):
        for address in ((0,0),(-1,0),(1,0),(0,-1),("0",0),
                        (True,0),(0,0,0), "x"):
            block = SlotCode((),(), "Int",
                             (("LOAD_SLOT",address,0),("RETURN",None,1)))
            with self.subTest(address=address), self.assertRaises(BytecodeError):
                verify_slots(VerifiedProgram("Int",block))

    def test_verify_rejects_stack_underflow_and_type_errors(self):
        forged = (
            (("ADD",None,0),("RETURN",None,0)),
            (("PUSH_BOOL",True,0),("NEG",None,0),("RETURN",None,0)),
            (("PUSH_BOOL",True,0),("PUSH_INT",1,0),
             ("ADD",None,0),("RETURN",None,0)),
            (("PUSH_INT",1,0),("JUMP_IF_FALSE",3,0),
             ("PUSH_INT",2,0),("RETURN",None,0)),
            (("PUSH_INT",1,0),("PUSH_INT",2,0),("RETURN",None,0)),
            (("PUSH_INT",1,0),("CALL",0,0),("RETURN",None,0)),
            (("PUSH_BOOL",True,0),("RETURN",None,0)),
            (("PUSH_INT",1,0),("ENTER",None,0),("RETURN",None,0)),
            (("JUMP",0,0),("RETURN",None,0)),
            (("NO_OP",None,0),("RETURN",None,0)),
        )
        for instructions in forged:
            program = VerifiedProgram("Int", SlotCode((),(),"Int",instructions))
            with self.subTest(instructions=instructions):
                with self.assertRaises(BytecodeError):
                    verify_slots(program)
                with self.assertRaises(BytecodeError):
                    run_slots(program)

    def test_verify_rejects_branch_join_mismatch(self):
        candidate = SlotCode((),(),"Int", (
            ("PUSH_BOOL",True,0),
            ("JUMP_IF_FALSE",4,1),
            ("PUSH_INT",3,2),
            ("JUMP",5,3),
            ("ENTER",None,4),
            ("RETURN",None,5),
        ))
        with self.assertRaises(BytecodeError):
            verify_slots(VerifiedProgram("Int", candidate))

    def test_verify_rejects_recursion_initialization_order_and_bad_capture(self):
        info = SlotInfo("f",FunctionType((), "Int"),False,True,False)
        forged = SlotCode((),(),"Int", (
            ("ENTER",None,0),
            ("DECLARE_REC_SLOT",info,0),
            ("LOAD_SLOT",(0,0),0),
            ("INIT_REC_SLOT",0,0),
            ("PUSH_INT",2,0),
            ("LEAVE",None,0),
            ("RETURN",None,0),
        ))
        with self.assertRaises(BytecodeError):
            verify_slots(VerifiedProgram("Int",forged))
        bad_child = SlotCode(((),),(),"Int",
                             (("PUSH_INT",1,0),("RETURN",None,1)))
        wrong_capture = SlotCode((),(),"Int",(
            ("CLOSURE_SLOT",bad_child,0),
            ("RETURN",None,0),
        ))
        with self.assertRaises(BytecodeError):
            verify_slots(VerifiedProgram("Int",wrong_capture))

    def test_execution_limits_and_budget_validation(self):
        source = ("let rec f:Fn(Int)->Int=fn(n:Int)->Int=>"
                  "f(n+1) in f(0)")
        program = compile_slots(source)
        with self.assertRaisesRegex(RuntimeError, "call-frame limit"):
            run_slots(program,max_frames=9)
        with self.assertRaisesRegex(RuntimeError, "step limit"):
            run_slots(program,max_steps=15)
        for limit in (0,-1,True):
            with self.assertRaises(ValueError):
                run_slots(program,max_steps=limit)
        with self.assertRaises(BytecodeError):
            verify_slots(replace(program, result_type="Bool"))

    def test_bilingual_contracts_and_track_positions(self):
        articles = load_articles()
        self.assertEqual(load_modules()[TOPIC], "foundations")
        code=[]
        for lang in ("en","pt"):
            chapter=articles[lang][TOPIC]
            self.assertEqual(chapter["meta"]["prerequisites"],
                             ["mutable-cells-recursive-functions"])
            for term in ("lexical_slot_verifier.py","LOAD_SLOT","STORE_SLOT",
                         "verify_slots","compile_slots","run_slots",
                         "SlotInfo","BytecodeError"):
                self.assertIn(term,chapter["body"])
            snippets=re.findall(r"(?ms)^~~~python\n(.*?)^~~~[ \t]*$",
                                chapter["body"])
            self.assertEqual(len(snippets),1)
            code.append(snippets[0])
        self.assertEqual(code[0],code[1])
        for track in load_tracks()[:2]:
            ids=[topic for sec in track["sections"] for topic in sec["articles"]]
            self.assertLess(ids.index("mutable-cells-recursive-functions"),
                            ids.index(TOPIC))


if __name__ == "__main__":
    unittest.main()
