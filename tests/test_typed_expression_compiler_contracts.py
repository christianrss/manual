"""Contracts for typed lexical binding, static judgments and VM branches.

Reference answers derive from simple arithmetic and an independent direct
AST evaluator; tests never interpret the source through Python eval/exec.
"""
from fractions import Fraction
from pathlib import Path
import random
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "examples" / "python"))
from model import load_articles, load_modules, load_tracks
from examples.python.expression_compiler import tokenize, CompileError, evaluate
from examples.python.typed_expression_compiler import (
    parse_typed, typecheck, compile_typed, run_typed, evaluate_typed,
    TypeCheckError, Let, If, Name, Boolean, TypedProgram,
)

TOPIC = "static-types-lexical-scopes"
EXAMPLES = (
    ("let x: Int = 5 in let x: Int = x+1 in x", "Int", Fraction(6)),
    ("let x: Int = 2 in let y: Rat = x/3 in if y<1 then y+1 else y",
     "Rat", Fraction(5, 3)),
    ("let x: Bool = true in if x then 2 else 3", "Int", Fraction(2)),
    ("if false then 1/(2-2) else 1/2", "Rat", Fraction(1, 2)),
    ("if 2<3 then 9 else 4", "Int", Fraction(9)),
    ("let x: Int = 2 in (let x: Int = 5 in x)+x",
     "Int", Fraction(7)),
    ("let a: Rat = 1/3 in let b: Rat = a+1/6 in b",
     "Rat", Fraction(1, 2)),
    ("let x: Int = 3 in x < 4", "Bool", True),
    ("let x: Bool = false in if x then true else false", "Bool", False),
    ("1+2*3", "Int", Fraction(7)),
)


def independent_ast_evaluator(node, frames=()):
    """Direct tree semantics: deliberately no bytecode compiler or VM."""
    if isinstance(node, Boolean):
        return node.value
    if isinstance(node, Name):
        for scope in reversed(frames):
            if node.identifier in scope:
                return scope[node.identifier]
        raise AssertionError("unbound reference should fail before evaluation")
    from examples.python.expression_compiler import Literal, Unary, Binary
    if isinstance(node, Literal):
        return Fraction(node.value)
    if isinstance(node, Unary):
        result = independent_ast_evaluator(node.operand, frames)
        return -result if node.op == "-" else result
    if isinstance(node, Binary):
        a = independent_ast_evaluator(node.left, frames)
        b = independent_ast_evaluator(node.right, frames)
        if node.op == "+": return a+b
        if node.op == "-": return a-b
        if node.op == "*": return a*b
        if node.op == "/": return a/b
        if node.op == "<": return a<b
        raise AssertionError("unexpected operator")
    if isinstance(node, Let):
        initial = independent_ast_evaluator(node.initializer, frames)
        return independent_ast_evaluator(
            node.body, frames+({node.identifier: initial},))
    if isinstance(node, If):
        cond = independent_ast_evaluator(node.condition, frames)
        return independent_ast_evaluator(
            node.yes if cond else node.no, frames)
    raise AssertionError("unexpected node")


class TypedCompilerContracts(unittest.TestCase):
    def test_default_arithmetic_lexer_has_no_regression(self):
        self.assertEqual(evaluate("1/3 + 1/6"), Fraction(1, 2))
        for source in ("let x:Int=1 in x", "x", "true", "2<3", "a_1"):
            with self.assertRaises(CompileError):
                tokenize(source)
        tokens = tokenize("let x_2: Int = 2 in if x_2 < 3 then true else false",
                          extended=True)
        self.assertEqual([t.kind for t in tokens], [
            "let", "IDENT", ":", "Int", "=", "INT", "in", "if",
            "IDENT", "<", "INT", "then", "true", "else",
            "false", "EOF",
        ])
        self.assertEqual(tokens[1].text, "x_2")
        self.assertEqual(tokens[-1].start, len("let x_2: Int = 2 in if x_2 < 3 then true else false"))
        for malformed in ("x$", "π", "let_é"):
            with self.assertRaises(CompileError):
                tokenize(malformed, extended=True)
        # An integer followed immediately by an identifier can tokenize,
        # but it cannot form one legal expression.
        self.assertEqual([t.kind for t in tokenize("100_000", extended=True)],
                         ["INT", "IDENT", "EOF"])
        with self.assertRaises(CompileError):
            compile_typed("100_000")

    def test_typejudgments_and_runtime_expected_results(self):
        for source, typ, value in EXAMPLES:
            with self.subTest(source=source):
                ast = parse_typed(source)
                self.assertEqual(typecheck(ast), typ)
                program = compile_typed(source)
                self.assertEqual(program.result_type, typ)
                self.assertEqual(run_typed(program), value)
                self.assertEqual(independent_ast_evaluator(ast), value)
                self.assertEqual(evaluate_typed(source), (typ, value))

    def test_static_rejection_even_in_unreachable_branches(self):
        failures = [
            ("x+1", "unbound"),
            ("let x: Int = x+1 in x", "unbound"),
            ("let x: Rat = 3 in x", "initializer"),
            ("let x: Int = 1/2 in x", "initializer"),
            ("let x: Bool = 0 in x", "initializer"),
            ("let x: Int = true in x", "initializer"),
            ("if 1 then 2 else 3", "condition"),
            ("if true then 2 else false", "branches"),
            ("if false then unknown else 2", "unbound"),
            ("if true then 1 else false+2", "arithmetic"),
            ("true+false", "arithmetic"),
            ("-true", "unary"),
            ("true<false", "numbers"),
            ("let x: Int = 2 in (let y: Int = x in y)+y", "unbound"),
        ]
        for source, phrase in failures:
            with self.subTest(source=source):
                with self.assertRaises(TypeCheckError) as context:
                    compile_typed(source)
                self.assertIn(phrase, str(context.exception))
                self.assertGreaterEqual(context.exception.offset, 0)
                self.assertLessEqual(context.exception.offset, len(source))

    def test_parse_errors_and_reserved_identifiers(self):
        invalid = [
            "let x = 2 in x", "let x: Num = 2 in x",
            "let let: Int = 1 in let", "let a: Int = 1 x",
            "if true 2 else 3", "if true then 2",
            "if true then 2 else", "let x: Int = 1 in",
            "let x: Int = 2 in x junk", "1=2", "()",
            "let x: Int = 3 in x==3",
        ]
        for source in invalid:
            with self.subTest(source=source):
                with self.assertRaises(CompileError):
                    compile_typed(source)
        with self.assertRaises(CompileError):
            compile_typed("(" * 100 + "1" + ")" * 100)
        with self.assertRaises(CompileError):
            compile_typed("1+" * 100)

    def test_generated_shadowing_arithmetic_and_conditions(self):
        rng = random.Random(220611)
        for _ in range(450):
            a, b, c = (rng.randrange(0, 100) for _ in range(3))
            expression = (
                f"let x: Int = {a} in let x: Int = x+{b} in "
                f"if x<{c} then x*2 else x-3")
            x = a + b
            expected = Fraction(x*2 if x < c else x-3)
            self.assertEqual(evaluate_typed(expression), ("Int", expected))
            self.assertEqual(independent_ast_evaluator(parse_typed(expression)),
                             expected)
        for _ in range(100):
            a, b, c = (rng.randrange(1, 99) for _ in range(3))
            expression = (
                f"let p: Rat = {a}/{b} in "
                f"if p<{c} then p+1 else p-1")
            p = Fraction(a, b)
            expected = p+1 if p < c else p-1
            self.assertEqual(evaluate_typed(expression), ("Rat", expected))

    def test_branch_is_lazy_and_unselected_failure_is_not_executed(self):
        self.assertEqual(evaluate_typed("if true then 1/2 else 1/0"),
                         ("Rat", Fraction(1, 2)))
        self.assertEqual(evaluate_typed("if false then 1/0 else 3/2"),
                         ("Rat", Fraction(3, 2)))
        with self.assertRaises(ZeroDivisionError):
            evaluate_typed("if false then 1/2 else 1/0")
        compiled = compile_typed("if true then 3 else 4")
        jumps = [(i, op, target) for i, (op, target, _) in enumerate(
            compiled.instructions) if op.startswith("JUMP")]
        self.assertEqual(len(jumps), 2)
        self.assertTrue(all(i < target <= len(compiled.instructions)
                            for i, _, target in jumps))

    def test_type_vs_runtime_and_scope_stack_invariants(self):
        sample = compile_typed(
            "let x: Int = 5 in let x: Int = x+1 in if x<10 then x else 0")
        ops = [op for op, _, _ in sample.instructions]
        self.assertEqual(ops.count("ENTER"), 2)
        self.assertEqual(ops.count("LEAVE"), 2)
        self.assertEqual(ops.count("BIND"), 2)
        self.assertEqual(run_typed(sample), Fraction(6))
        for forged in (
            TypedProgram("Int", (("LEAVE", None, 0),)),
            TypedProgram("Int", (("LOAD", "ghost", 0),)),
            TypedProgram("Int", (("JUMP_IF_FALSE", 1, 0),)),
            TypedProgram("Int", (("UNKNOWN", None, 0),)),
            TypedProgram("Int", (("PUSH_BOOL", True, 0),)),
        ):
            with self.assertRaises(ValueError):
                run_typed(forged)
        with self.assertRaises(TypeError):
            run_typed("not bytecode")

    def test_bilingual_curriculum_and_executable_parity(self):
        articles = load_articles()
        self.assertEqual(load_modules()[TOPIC], "foundations")
        samples = []
        for lang in ("en", "pt"):
            article = articles[lang][TOPIC]
            self.assertEqual(article["meta"]["prerequisites"],
                ["lexing-parsing-expression-compiler",
                 "programming-semantics-contracts"])
            for token in ("typed_expression_compiler", "TypeCheckError",
                          "typecheck", "compile_typed", "run_typed", "Bool"):
                self.assertIn(token, article["body"])
            matches = re.findall(r"(?ms)^~~~python\n(.*?)^~~~[ \t]*$",
                                 article["body"])
            self.assertEqual(len(matches), 1)
            samples.append(matches[0])
        self.assertEqual(samples[0], samples[1])
        for track in load_tracks()[:2]:
            ids = [topic for section in track["sections"]
                   for topic in section["articles"]]
            for prereq in articles["en"][TOPIC]["meta"]["prerequisites"]:
                self.assertLess(ids.index(prereq), ids.index(TOPIC))


if __name__ == "__main__":
    unittest.main()
