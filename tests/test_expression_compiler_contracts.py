"""Independent arithmetic oracle and structural tests for the toy compiler.

The oracle uses Python's own ast.parse with a *restricted* node visitor; no
eval/exec is used. Its parser is separate from the textbook compiler.
"""
import ast
from fractions import Fraction
import operator
from pathlib import Path
import random
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "examples" / "python"))
from model import load_articles, load_modules, load_tracks
from expression_compiler import (
    tokenize, parse_expression, compile_expression, run_bytecode,
    interpret_ast, evaluate, CompileError, MAX_SOURCE, MAX_TOKENS,
)

TOPIC = "lexing-parsing-expression-compiler"


def python_ast_oracle(source):
    """Use only a safe subset of independent CPython expression grammar."""
    arithmetic = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
    }
    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return Fraction(node.value)
        if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.UAdd, ast.USub):
            operand = visit(node.operand)
            return operand if type(node.op) is ast.UAdd else -operand
        if isinstance(node, ast.BinOp) and type(node.op) in arithmetic:
            return arithmetic[type(node.op)](visit(node.left), visit(node.right))
        raise AssertionError("unexpected Python grammar production")
    return visit(ast.parse(source, mode="eval"))


def expression(rng, depth=0):
    if depth >= 4 or rng.randrange(4) == 0:
        return str(rng.randrange(0, 20))
    which = rng.randrange(4)
    if which == 0:
        return rng.choice("+-") + expression(rng, depth + 1)
    first, second = expression(rng, depth + 1), expression(rng, depth + 1)
    if rng.randrange(2):
        second = "(" + second + ")"
    return "(" + first + rng.choice("+-*/") + second + ")"


class ExpressionCompilerContracts(unittest.TestCase):
    def test_tokenization_span_and_rejections(self):
        tokens = tokenize(" 12 +\n003/4 ")
        self.assertEqual([(t.kind, t.text, t.start, t.end) for t in tokens],
            [("INT", "12", 1, 3), ("+", "+", 4, 5),
             ("INT", "003", 6, 9), ("/", "/", 9, 10),
             ("INT", "4", 10, 11), ("EOF", "", 12, 12)])
        for bad in ("a", "１２", "2**3", "2//3", "2_000", "2;3", "3.14", "\u00a0"):
            with self.subTest(bad=bad), self.assertRaises(CompileError):
                tokenize(bad)
        with self.assertRaises(TypeError):
            tokenize(1)
        with self.assertRaises(CompileError):
            tokenize("7" * 101)
        with self.assertRaises(CompileError):
            tokenize(" " * (MAX_SOURCE + 1))
        with self.assertRaises(CompileError):
            tokenize("1+" * (MAX_TOKENS // 2 + 3))

    def test_precedence_associativity_and_exact_rationals(self):
        expected = {
            "1+2*3": 7, "(1+2)*3": 9, "10-3-2": 5,
            "8/4/2": 1, "1/3+1/6": Fraction(1, 2),
            "8/(2+2)+-3": -1, "-2*3+10": 4,
            "1--2": 3, "--5": 5, "0/(1+2)": 0,
            "00012": 12, "\n  6 + 2 \t": 8,
            "1/7*7": 1, "-(1/3)": Fraction(-1, 3),
        }
        for source, answer in expected.items():
            with self.subTest(source=source):
                root = parse_expression(source)
                code = compile_expression(source)
                self.assertEqual(interpret_ast(root), Fraction(answer))
                self.assertEqual(run_bytecode(code), Fraction(answer))
                self.assertEqual(evaluate(source), Fraction(answer))
                self.assertEqual(python_ast_oracle(source), Fraction(answer))
                self.assertEqual(code[-1][0], "PUSH" if source.isdecimal() else code[-1][0])

    def test_seeded_generated_expressions_against_independent_ast(self):
        rng = random.Random(20261011)
        evaluated, divided = 0, 0
        for _ in range(600):
            source = expression(rng)
            try:
                expected = python_ast_oracle(source)
            except ZeroDivisionError:
                divided += 1
                with self.subTest(source=source):
                    with self.assertRaises(ZeroDivisionError):
                        evaluate(source)
                    with self.assertRaises(ZeroDivisionError):
                        interpret_ast(parse_expression(source))
            else:
                evaluated += 1
                with self.subTest(source=source):
                    self.assertEqual(evaluate(source), expected)
                    self.assertEqual(interpret_ast(parse_expression(source)), expected)
        self.assertGreater(evaluated, 350)
        self.assertGreater(divided, 0)

    def test_invalid_syntax_has_offset(self):
        invalid = ("", " ", "+", "1+", "1 2", "()", "(1", "1)",
                   "2*(3+", "1+(2))", "1*/2", "-)", "2(3)",
                   "/1", "3 + * 5")
        for source in invalid:
            with self.subTest(source=source):
                with self.assertRaises(CompileError) as ctx:
                    parse_expression(source)
                self.assertGreaterEqual(ctx.exception.offset, 0)
                self.assertLessEqual(ctx.exception.offset, len(source))
        with self.assertRaises(CompileError):
            parse_expression("(" * 100 + "1" + ")" * 100)
        with self.assertRaises(ZeroDivisionError):
            evaluate("1/(3-3)")

    def test_stack_bytecode_is_finite_and_well_formed(self):
        code = compile_expression("-(2+3)*5/7")
        stack_size = 0
        for op, argument, offset in code:
            self.assertIsInstance(offset, int)
            if op == "PUSH":
                self.assertIsInstance(argument, int)
                stack_size += 1
            elif op in ("NEG", "POS"):
                self.assertGreaterEqual(stack_size, 1)
            else:
                self.assertIn(op, ("ADD", "SUB", "MUL", "DIV"))
                self.assertGreaterEqual(stack_size, 2)
                stack_size -= 1
        self.assertEqual(stack_size, 1)
        self.assertEqual(run_bytecode(code), Fraction(-25, 7))
        for code in ((), (("ADD", None, 0),),
                     (("PUSH", 1, 0), ("PUSH", 2, 2)),
                     (("UNKNOWN", None, 0),)):
            with self.assertRaises(ValueError):
                run_bytecode(code)

    def test_long_flat_expression_does_not_recurse_during_codegen_or_eval(self):
        source = "+".join(["1"] * 1000)
        # Token budget 1,999, AST is deeply left-associated but compiled
        # and interpreted via an explicit postorder work stack.
        self.assertEqual(evaluate(source), Fraction(1000))
        self.assertEqual(interpret_ast(parse_expression(source)), Fraction(1000))

    def test_bilingual_curriculum_and_same_executable_example(self):
        articles = load_articles()
        self.assertEqual(load_modules()[TOPIC], "foundations")
        code_blocks = []
        for lang in ("en", "pt"):
            article = articles[lang][TOPIC]
            self.assertEqual(article["meta"]["prerequisites"],
                ["formal-languages-finite-automata",
                 "context-free-grammars-parsing",
                 "programming-semantics-contracts"])
            for name in ("expression_compiler.py", "tokenize",
                         "compile_expression", "run_bytecode",
                         "interpret_ast", "Fraction"):
                self.assertIn(name, article["body"])
            matches = re.findall(r"(?ms)^~~~python\n(.*?)^~~~[ \t]*$",
                                 article["body"])
            self.assertEqual(len(matches), 1)
            code_blocks.append(matches[0])
        self.assertEqual(code_blocks[0], code_blocks[1])
        for track in load_tracks()[:2]:
            ids = [topic for sec in track["sections"] for topic in sec["articles"]]
            for required in articles["en"][TOPIC]["meta"]["prerequisites"]:
                self.assertLess(ids.index(required), ids.index(TOPIC))


if __name__ == "__main__":
    unittest.main()
