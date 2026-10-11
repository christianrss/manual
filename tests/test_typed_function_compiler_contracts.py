"""Independent interpreter and contract tests for typed lexical closures.

Reference interpretation traverses parsed AST using nested immutable maps;
it does not invoke emitted bytecode, VM frames, or compile_functions.
"""
from fractions import Fraction
from pathlib import Path
import random
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks
from examples.python.expression_compiler import (
    Literal, Unary, Binary, tokenize, CompileError, evaluate,
)
from examples.python.typed_expression_compiler import (
    Boolean, Name, Let, If, TypeCheckError, evaluate_typed,
)
from examples.python.typed_function_compiler import (
    FunctionType, Lambda, Call, Code, Program, Closure,
    parse_functions, typecheck_functions, compile_functions,
    run_functions, evaluate_functions, format_type,
)

TOPIC = "typed-functions-call-frames-closures"


def independent_tree_eval(node, scopes=()):
    """Reference semantics without VM instructions or a bytecode compiler."""
    if isinstance(node, Literal):
        return Fraction(node.value)
    if isinstance(node, Boolean):
        return node.value
    if isinstance(node, Name):
        for env in reversed(scopes):
            if node.identifier in env:
                return env[node.identifier]
        raise LookupError(node.identifier)
    if isinstance(node, Unary):
        v = independent_tree_eval(node.operand, scopes)
        return -v if node.op == "-" else v
    if isinstance(node, Binary):
        a = independent_tree_eval(node.left, scopes)
        b = independent_tree_eval(node.right, scopes)
        if node.op == "+": return a + b
        if node.op == "-": return a - b
        if node.op == "*": return a * b
        if node.op == "/": return a / b
        if node.op == "<": return a < b
        raise AssertionError(node.op)
    if isinstance(node, Let):
        value = independent_tree_eval(node.initializer, scopes)
        return independent_tree_eval(
            node.body, scopes + ({node.identifier: value},))
    if isinstance(node, If):
        if independent_tree_eval(node.condition, scopes):
            return independent_tree_eval(node.yes, scopes)
        return independent_tree_eval(node.no, scopes)
    if isinstance(node, Lambda):
        return (node, tuple(dict(env) for env in scopes))
    if isinstance(node, Call):
        function = independent_tree_eval(node.function, scopes)
        args = tuple(independent_tree_eval(a, scopes)
                     for a in node.arguments)
        if not (isinstance(function, tuple) and
                isinstance(function[0], Lambda)):
            raise AssertionError("ill-typed function call")
        target, captured = function
        frame = dict(zip((name for name, _ in target.parameters), args))
        return independent_tree_eval(target.body, captured + (frame,))
    raise AssertionError(type(node))


CASES = (
    ("let add: Fn(Int,Int)->Int = fn(x:Int,y:Int)->Int => x+y in add(2,3)",
     "Int", Fraction(5)),
    ("let x:Int=10 in let f:Fn(Int)->Int=fn(y:Int)->Int=>x+y in "
     "let x:Int=99 in f(2)", "Int", Fraction(12)),
    ("let make:Fn(Int)->Fn(Int)->Int=fn(x:Int)->Fn(Int)->Int=>"
     "fn(y:Int)->Int=>x+y in let f:Fn(Int)->Int=make(3) in f(4)",
     "Int", Fraction(7)),
    ("let f:Fn()->Int=fn()->Int=>11 in f()", "Int", Fraction(11)),
    ("let twice:Fn(Fn(Int)->Int,Int)->Int="
     "fn(f:Fn(Int)->Int,n:Int)->Int=>f(f(n)) in "
     "let plus:Fn(Int)->Int=fn(x:Int)->Int=>x+1 in twice(plus,4)",
     "Int", Fraction(6)),
    ("let make:Fn(Int)->Fn()->Int=fn(x:Int)->Fn()->Int=>"
     "fn()->Int=>x in let get:Fn()->Int=make(8) in get()",
     "Int", Fraction(8)),
    ("let f:Fn(Bool)->Rat=fn(flag:Bool)->Rat=>"
     "if flag then 1/2 else 1/3 in f(false)", "Rat", Fraction(1,3)),
    ("if false then 1/0 else 7/2", "Rat", Fraction(7,2)),
    ("let x:Int=2 in let f:Fn(Int)->Bool="
     "fn(y:Int)->Bool=>x<y in f(4)", "Bool", True),
    ("let outer:Fn(Int)->Fn(Int)->Int="
     "fn(x:Int)->Fn(Int)->Int=>fn(x:Int)->Int=>x+1 in "
     "let f:Fn(Int)->Int=outer(99) in f(6)", "Int", Fraction(7)),
    ("let f:Fn()->Int=fn()->Int=>1 in "
     "let f:Fn()->Int=fn()->Int=>f()+1 in f()", "Int", Fraction(2)),
)


class TypedFunctionContracts(unittest.TestCase):
    def test_reference_examples_and_direct_ast_oracle(self):
        for source, expected_type, expected in CASES:
            with self.subTest(source=source):
                root = parse_functions(source)
                ty = typecheck_functions(root)
                self.assertEqual(format_type(ty), expected_type)
                code = compile_functions(source)
                self.assertEqual(code.result_type, ty)
                self.assertEqual(run_functions(code), expected)
                self.assertEqual(independent_tree_eval(root), expected)
                self.assertEqual(evaluate_functions(source), (ty, expected))

    def test_lexical_capture_vs_dynamic_scoping(self):
        # No late binding: the closure's definition-time x remains visible,
        # not the caller's shadowing x.
        source = ("let x:Int=10 in let f:Fn()->Int=fn()->Int=>x in "
                  "let x:Int=99 in f()")
        self.assertEqual(evaluate_functions(source)[1], Fraction(10))
        # Closure survives return of its defining activation frame.
        source = ("let make:Fn(Int)->Fn()->Int="
                  "fn(x:Int)->Fn()->Int=>fn()->Int=>x in "
                  "let f:Fn()->Int=make(27) in "
                  "let x:Int=999 in f()")
        self.assertEqual(evaluate_functions(source)[1], Fraction(27))

    def test_seeded_arithmetic_lexical_functions(self):
        rng = random.Random(11102026)
        for _ in range(350):
            a,b,c = (rng.randrange(0,50) for _ in range(3))
            source = (f"let x:Int={a} in "
                      f"let f:Fn(Int,Int)->Int=fn(u:Int,v:Int)->Int=>"
                      f"u*2+v+x in let x:Int={c} in f({b},{c})")
            expected = Fraction(2*b + c + a)
            self.assertEqual(evaluate_functions(source)[1], expected)
            self.assertEqual(independent_tree_eval(parse_functions(source)),
                             expected)

    def test_static_invalid_calls_annotations_and_scope(self):
        bad = (
            ("1(2)", "call target"),
            ("let f:Fn(Int)->Int=fn(x:Int)->Int=>x in f()", "number of arguments"),
            ("let f:Fn(Int)->Int=fn(x:Int)->Int=>x in f(1,2)", "number of arguments"),
            ("let f:Fn(Int)->Int=fn(x:Int)->Int=>x in f(true)", "argument type"),
            ("fn(x:Int)->Bool=>x+1", "return type"),
            ("fn(x:Int)->Int=>missing", "unbound"),
            ("fn(x:Int)->Int=>x+true", "numbers"),
            ("fn(x:Int)->Int=>f(x)", "unbound"),
            ("let f:Fn(Int)->Int=fn(x:Int)->Bool=>true in f(3)", "annotation"),
            ("let f:Fn(Int)->Int=fn(x:Int)->Int=>x in "
             "let y:Int=f(true) in y", "argument type"),
            ("if true then fn()->Int=>3 else fn()->Bool=>false",
             "branches"),
            ("let g:Fn()->Int=fn()->Int=>2 in let x:Int=g in x",
             "annotation"),
            ("let x:Int=2 in (fn()->Int=>x)()+x", None),
        )
        for source, fragment in bad:
            if fragment is None:
                self.assertEqual(evaluate_functions(source)[1], 4)
                continue
            with self.subTest(source=source):
                with self.assertRaises(TypeCheckError) as caught:
                    compile_functions(source)
                self.assertIn(fragment, str(caught.exception))

    def test_syntactic_invalid_function_declarations(self):
        bad = (
            "fn(x:Int,x:Bool)->Int=>x",
            "fn(x)->Int=>x",
            "fn(x:Int) Int=>x",
            "fn(x:Int)->Int x",
            "fn(x:Int)->Unknown=>x",
            "fn(x:Int)->Int=>",
            "let f:Fn(Int)Int=fn(x:Int)->Int=>x in f(1)",
            "let f:Fn(Int,)->Int=fn(x:Int)->Int=>x in f(1)",
            "let x:Int=1 in x(1,)",
            "fn(x:Int)->Int=>x(2",
        )
        for source in bad:
            with self.subTest(source=source):
                with self.assertRaises(CompileError):
                    compile_functions(source)

    def test_partial_backward_compatibility_and_distinct_modes(self):
        self.assertEqual(evaluate("1/3+1/6"), Fraction(1,2))
        self.assertEqual(evaluate_typed("let x:Int=2 in x+3"),
                         ("Int", Fraction(5)))
        self.assertEqual([t.kind for t in tokenize("fn Fn -> => ,",
                         extended=True, functions=True)],
                         ["fn","Fn","->","=>",",","EOF"])
        self.assertEqual(tokenize("fn", extended=True)[0].kind, "IDENT")
        with self.assertRaises(CompileError):
            tokenize("fn", extended=False)
        with self.assertRaises(ValueError):
            tokenize("fn", functions=True)
        for source in ("let x:Int=2 in x+3", "if true then 2 else 7", "1/3+1/6"):
            self.assertEqual(evaluate_functions(source), evaluate_typed(source))

    def test_vm_frames_returns_and_budget_fail_closed(self):
        compiled = compile_functions(
            "let f:Fn(Int)->Int=fn(x:Int)->Int=>x+5 in f(2)")
        self.assertEqual(run_functions(compiled), Fraction(7))
        self.assertEqual(sum(op=="CALL" for op,_,_ in compiled.code.instructions),1)
        self.assertEqual(sum(op=="CLOSURE" for op,_,_ in compiled.code.instructions),1)
        with self.assertRaises(RuntimeError):
            run_functions(compiled, max_steps=3)
        with self.assertRaises(RuntimeError):
            run_functions(compiled, max_frames=1)
        with self.assertRaises(ValueError):
            run_functions(Program("Int", Code((), (("CALL",0,0),
                                                  ("RETURN",None,0)))))
        with self.assertRaises(ValueError):
            run_functions(Program("Int", Code((), (("LEAVE",None,0),
                                                  ("RETURN",None,0)))))
        with self.assertRaises(ValueError):
            run_functions(Program("Int", Code((), (("JUMP",-1,0),
                                                  ("RETURN",None,0)))))
        with self.assertRaises(TypeError):
            run_functions("not a compiler output")
        for limit in (0,-1,True):
            with self.assertRaises(ValueError):
                run_functions(compiled, max_steps=limit)

    def test_bilingual_evidence_and_learning_sequence(self):
        articles=load_articles()
        self.assertEqual(load_modules()[TOPIC], "foundations")
        examples=[]
        for lang in ("en","pt"):
            item=articles[lang][TOPIC]
            self.assertEqual(item["meta"]["prerequisites"],
                             ["static-types-lexical-scopes"])
            for marker in ("typed_function_compiler.py", "compile_functions",
                           "run_functions", "Fn(", "Closure"):
                self.assertIn(marker, item["body"])
            matches=re.findall(r"(?ms)^~~~python\n(.*?)^~~~[ \t]*$",
                               item["body"])
            self.assertEqual(len(matches),1)
            examples.append(matches[0])
        self.assertEqual(*examples)
        for track in load_tracks()[:2]:
            ids=[x for section in track["sections"] for x in section["articles"]]
            self.assertLess(ids.index("static-types-lexical-scopes"),
                            ids.index(TOPIC))


if __name__ == "__main__":
    unittest.main()
