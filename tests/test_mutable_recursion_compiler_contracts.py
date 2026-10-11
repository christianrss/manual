"""Independent finite contracts for lexical mutable cells and let-rec closures.

The reference interpreter walks typed ASTs directly. It never calls the
bytecode generator or VM. Tests bound all recursion and arithmetic cases.
"""
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import random
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks
from examples.python.expression_compiler import Literal, Unary, Binary, tokenize, CompileError, evaluate
from examples.python.typed_expression_compiler import Boolean, Name, Let, If, TypeCheckError, evaluate_typed
from examples.python.typed_function_compiler import (
    FunctionType, Lambda, Call, Program, Code, compile_functions,
    evaluate_functions, format_type, run_functions, Var, LetRec, SetVar,
)
from examples.python.stateful_function_compiler import (
    parse_stateful, compile_stateful, evaluate_stateful,
)

TOPIC = "mutable-cells-recursive-functions"


@dataclass
class ReferenceCell:
    value: object
    writable: bool = True


@dataclass(frozen=True)
class DirectClosure:
    node: Lambda
    env: tuple


def direct_eval(node, frames=()):
    """Independent big-step tree evaluator with shared lexical cells."""
    if isinstance(node, Literal):
        return Fraction(node.value)
    if isinstance(node, Boolean):
        return node.value
    if isinstance(node, Name):
        for frame in reversed(frames):
            if node.identifier in frame:
                bound = frame[node.identifier]
                if isinstance(bound, ReferenceCell):
                    if bound.value is None:
                        raise AssertionError("uninitialized recursive reference")
                    return bound.value
                return bound
        raise AssertionError("unbound name passed static checker")
    if isinstance(node, Unary):
        value = direct_eval(node.operand, frames)
        return -value if node.op == "-" else value
    if isinstance(node, Binary):
        a = direct_eval(node.left, frames)
        b = direct_eval(node.right, frames)
        if node.op == "+": return a + b
        if node.op == "-": return a - b
        if node.op == "*": return a * b
        if node.op == "/": return a / b
        if node.op == "<": return a < b
        raise AssertionError("unexpected binary operator")
    if isinstance(node, If):
        return direct_eval(node.yes if direct_eval(node.condition, frames)
                           else node.no, frames)
    if isinstance(node, Let):
        value = direct_eval(node.initializer, frames)
        return direct_eval(node.body, frames + ({node.identifier: value},))
    if isinstance(node, Var):
        value = direct_eval(node.initializer, frames)
        cell = ReferenceCell(value)
        return direct_eval(node.body, frames + ({node.identifier: cell},))
    if isinstance(node, SetVar):
        value = direct_eval(node.expression, frames)
        for frame in reversed(frames):
            if node.identifier in frame:
                cell = frame[node.identifier]
                if not isinstance(cell, ReferenceCell) or not cell.writable:
                    raise AssertionError("static checker accepted immutable set")
                cell.value = value
                return value
        raise AssertionError("static checker accepted unbound set")
    if isinstance(node, LetRec):
        slot = ReferenceCell(None, False)
        extended = frames + ({node.identifier: slot},)
        slot.value = direct_eval(node.initializer, extended)
        return direct_eval(node.body, extended)
    if isinstance(node, Lambda):
        # An environment snapshot duplicates maps while retaining cell refs.
        return DirectClosure(node, tuple(dict(f) for f in frames))
    if isinstance(node, Call):
        closure = direct_eval(node.function, frames)
        args = tuple(direct_eval(a, frames) for a in node.arguments)
        if not isinstance(closure, DirectClosure):
            raise AssertionError("nonfunction call passed static checker")
        parameters = (p for p, _ in closure.node.parameters)
        bindings = dict(zip(parameters, args))
        return direct_eval(closure.node.body, closure.env + (bindings,))
    raise AssertionError("unexpected AST class")


CASES = (
    ("var x:Int=1 in (set x=x+1)+x", "Int", Fraction(4)),
    ("var x:Int=1 in let inc:Fn()->Int=fn()->Int=>set x=x+1 in inc()+inc()",
     "Int", Fraction(5)),
    ("var x:Int=1 in let a:Fn()->Int=fn()->Int=>set x=x+1 in "
     "let b:Fn()->Int=fn()->Int=>set x=x+10 in a()+b()",
     "Int", Fraction(14)),
    ("var x:Int=3 in let read:Fn()->Int=fn()->Int=>x in (set x=9)+read()",
     "Int", Fraction(18)),
    ("var x:Int=1 in (if false then set x=99 else 0)+x",
     "Int", Fraction(1)),
    ("var x:Int=1 in (if true then set x=3 else set x=20)+x",
     "Int", Fraction(6)),
    ("var x:Int=2 in let f:Fn()->Int=fn()->Int=>x in "
     "var x:Int=8 in (set x=12)+f()", "Int", Fraction(14)),
    ("let make:Fn(Int)->Fn()->Int=fn(seed:Int)->Fn()->Int=>"
     "var counter:Int=seed in fn()->Int=>set counter=counter+1 in "
     "let f:Fn()->Int=make(5) in f()+f()", "Int", Fraction(13)),
    ("let rec fact:Fn(Int)->Int=fn(n:Int)->Int=>"
     "if n<2 then 1 else n*fact(n-1) in fact(5)",
     "Int", Fraction(120)),
    ("let rec count:Fn(Int)->Int=fn(n:Int)->Int=>"
     "if n<1 then 0 else 1+count(n-1) in count(8)",
     "Int", Fraction(8)),
    ("let rec halve:Fn(Int)->Rat=fn(n:Int)->Rat=>"
     "if n<2 then 1/2 else halve(n-1)/2 in halve(4)",
     "Rat", Fraction(1,16)),
    ("let rec test:Fn(Int)->Bool=fn(n:Int)->Bool=>"
     "if n<2 then true else test(n-1) in test(6)",
     "Bool", True),
    ("let rec f:Fn(Int)->Int=fn(n:Int)->Int=>"
     "if n<1 then 0 else f(n-1) in "
     "let f:Fn()->Int=fn()->Int=>11 in f()", "Int", Fraction(11)),
)


class MutableRecursionContracts(unittest.TestCase):
    def test_hand_derived_mutation_and_recursion_against_direct_interpreter(self):
        for source, kind, expected in CASES:
            with self.subTest(source=source[:70]):
                program = compile_stateful(source)
                self.assertEqual(format_type(program.result_type), kind)
                self.assertEqual(run_functions(program), expected)
                self.assertEqual(evaluate_stateful(source),
                                 (program.result_type, expected))
                self.assertEqual(direct_eval(parse_stateful(source)), expected)

    def test_generated_factorials_and_mutable_counters(self):
        rng = random.Random(20261011)
        for _ in range(140):
            n = rng.randrange(0, 9)
            source = ("let rec f:Fn(Int)->Int=fn(n:Int)->Int=>"
                      "if n<2 then 1 else n*f(n-1) in f("+str(n)+")")
            product = 1
            for k in range(2,n+1):
                product *= k
            self.assertEqual(evaluate_stateful(source)[1], Fraction(product))
            self.assertEqual(direct_eval(parse_stateful(source)), Fraction(product))
        for _ in range(140):
            x, a, b = (rng.randrange(0, 90) for _ in range(3))
            source = (f"var x:Int={x} in let inc:Fn(Int)->Int="
                      f"fn(y:Int)->Int=>set x=x+y in inc({a})+inc({b})")
            expected = Fraction((x+a)+(x+a+b))
            self.assertEqual(evaluate_stateful(source)[1], expected)
            self.assertEqual(direct_eval(parse_stateful(source)), expected)

    def test_static_rejection_of_immutable_and_ill_typed_assignments(self):
        invalid = [
            ("set x=1", "unbound assignment"),
            ("let x:Int=1 in set x=2", "immutable"),
            ("var x:Int=1 in set x=true", "assignment type"),
            ("var x:Int=1 in set x=1/2", "assignment type"),
            ("var x:Bool=true in set x=1", "assignment type"),
            ("var x:Int=1 in let x:Int=2 in set x=3", "immutable"),
            ("let rec f:Fn(Int)->Int=fn(x:Int)->Int=>"
             "set f=fn(y:Int)->Int=>y in f(2)", "immutable"),
            ("let rec x:Int=1 in x", "let rec requires"),
            ("let rec f:Fn(Int)->Int=fn(x:Int)->Bool=>true in f(2)",
             "recursive function type"),
            ("let rec f:Fn(Int)->Int=fn(x:Int)->Int=>"
             "f(true) in f(1)", "argument type"),
            ("var x:Int=1 in let f:Fn()->Bool=fn()->Bool=>"
             "set x=2 in f()", "return type"),
        ]
        for source, reason in invalid:
            with self.subTest(source=source[:80]):
                with self.assertRaises(TypeCheckError) as caught:
                    compile_stateful(source)
                self.assertIn(reason, str(caught.exception))

    def test_parser_lexing_and_mode_isolation(self):
        for source in ("var x:Int=1 in x", "set x=1",
                       "let rec f:Fn()->Int=fn()->Int=>1 in f()"):
            with self.assertRaises(CompileError):
                compile_functions(source)
            compile_stateful(source) if not source.startswith("set ") else None
        self.assertEqual(tokenize("var set rec", extended=True, functions=True)[0].kind,
                         "IDENT")
        self.assertEqual(
            [t.kind for t in tokenize("var set rec", extended=True,
                                     functions=True, stateful=True)],
            ["var","set","rec","EOF"])
        with self.assertRaises(ValueError):
            tokenize("var", stateful=True)
        for source in ("var x:Int=1 x", "var:Int=3 in x",
                       "set x 2", "let rec :Fn()->Int=fn()->Int=>1 in 1",
                       "let rec f:Fn()->Int=fn()->Int=>1 f()"):
            with self.subTest(source=source), self.assertRaises(CompileError):
                compile_stateful(source)
        self.assertEqual(evaluate("1+2*3"), Fraction(7))
        self.assertEqual(evaluate_typed("let x:Int=4 in x+1"),
                         ("Int", Fraction(5)))
        self.assertEqual(evaluate_functions(
            "let f:Fn(Int)->Int=fn(x:Int)->Int=>x+3 in f(4)")[1], Fraction(7))

    def test_recursion_limits_and_invalid_vm_bytecode(self):
        source = ("let rec f:Fn(Int)->Int=fn(n:Int)->Int=>"
                  "f(n+1) in f(0)")
        compiled = compile_stateful(source)
        with self.assertRaisesRegex(RuntimeError, "call-frame limit"):
            run_functions(compiled, max_frames=12)
        with self.assertRaisesRegex(RuntimeError, "step limit"):
            run_functions(compiled, max_steps=23)
        for operations in (
            (("ENTER",None,0),("DECLARE_REC","f",0),("LOAD","f",0),("RETURN",None,0)),
            (("ENTER",None,0),("DECLARE_REC","f",0),
             ("PUSH_INT",1,0),("INIT_REC","f",0),("RETURN",None,0)),
            (("ENTER",None,0),("PUSH_INT",1,0),("STORE","ghost",0),("RETURN",None,0)),
            (("ENTER",None,0),("PUSH_INT",1,0),("BIND","x",0),
             ("PUSH_INT",2,0),("STORE","x",0),("RETURN",None,0)),
        ):
            with self.subTest(operations=operations):
                with self.assertRaises(ValueError):
                    run_functions(Program("Int", Code((), operations)))

    def test_bilingual_chapters_and_curriculum_sequence(self):
        articles = load_articles()
        self.assertEqual(load_modules()[TOPIC], "foundations")
        snippets = []
        for lang in ("en", "pt"):
            article = articles[lang][TOPIC]
            self.assertEqual(article["meta"]["prerequisites"],
                             ["typed-functions-call-frames-closures"])
            for term in ("stateful_function_compiler.py", "compile_stateful",
                         "evaluate_stateful", "Cell", "let rec",
                         "DECLARE_REC", "STORE"):
                self.assertIn(term, article["body"])
            blocks = re.findall(r"(?ms)^~~~python\n(.*?)^~~~[ \t]*$",
                                article["body"])
            self.assertEqual(len(blocks), 1)
            snippets.append(blocks[0])
        self.assertEqual(snippets[0], snippets[1])
        for track in load_tracks()[:2]:
            ordered = [item for section in track["sections"]
                       for item in section["articles"]]
            self.assertLess(ordered.index("typed-functions-call-frames-closures"),
                            ordered.index(TOPIC))


if __name__ == "__main__":
    unittest.main()
