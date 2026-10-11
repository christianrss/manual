"""Independent bounded contracts for context-free recognition and syntax trees.

The Dyck oracle uses an explicit stack; the a^n b^n oracle counts symbols.
Neither invokes Earley chart construction or recursive syntax-tree parsing.
Finite enumeration is not a substitute for the published correctness argument.
"""
from itertools import product
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "examples" / "python"))
from model import load_articles, load_modules, load_tracks
from context_free_parser import (
    earley_accepts, parse_balanced, pushdown_accepts, BALANCED_GRAMMAR, ANBN_GRAMMAR,
)

TOPIC = "context-free-grammars-parsing"


def stack_dyck(word):
    stack = []
    for c in word:
        if c == "(":
            stack.append(c)
        elif c == ")":
            if not stack:
                return False
            stack.pop()
        else:
            return False
    return not stack


def render_tree(tree):
    if tree is None:
        return ""
    if type(tree) is not tuple or len(tree) != 2:
        raise AssertionError("invalid structural syntax tree")
    inner, tail = tree
    return "(" + render_tree(inner) + ")" + render_tree(tail)


def words(chars, length):
    return map("".join, product(chars, repeat=length))


class ContextFreeContracts(unittest.TestCase):
    def test_balanced_against_independent_stack_oracle_and_round_trip(self):
        for n in range(12):
            for word in words("()", n):
                expected = stack_dyck(word)
                with self.subTest(word=word):
                    self.assertEqual(earley_accepts(BALANCED_GRAMMAR, "S", word),
                                     expected)
                    if expected:
                        self.assertEqual(render_tree(parse_balanced(word)), word)
                    else:
                        with self.assertRaises(ValueError):
                            parse_balanced(word)

    def test_pushdown_two_types_independent_reduction_oracle(self):
        # Delete adjacent matched pairs until none remain: no simulated stack.
        for n in range(8):
            for word in words("()[]", n):
                reduced = word
                while True:
                    next_reduced = reduced.replace("()", "").replace("[]", "")
                    if next_reduced == reduced:
                        break
                    reduced = next_reduced
                self.assertEqual(pushdown_accepts(word), reduced == "",
                                 (n, word))
        for invalid in (None, "a", "([]) ", 7):
            with self.assertRaises(ValueError):
                pushdown_accepts(invalid)
        self.assertFalse(pushdown_accepts("([)]"))
        self.assertTrue(pushdown_accepts("([][()])"))

    def test_nonregular_anbn_against_counting_oracle(self):
        for n in range(10):
            for word in words("ab", n):
                half = len(word) // 2
                valid = (len(word) % 2 == 0
                         and word == "a" * half + "b" * half)
                self.assertEqual(earley_accepts(ANBN_GRAMMAR, "S", word), valid)

    def test_left_recursion_nullable_and_ambiguous_grammars(self):
        grammars = (
            {"S": (("S", "a"), ())},  # left-recursive a*
            {"S": (("a", "S"), ())},  # right-recursive a*
            {"S": (("S", "S"), ("a",), ())},  # ambiguous, epsilon and recursion
            {"S": (("S",), ())},  # epsilon cycle, only the empty word
        )
        for index, grammar in enumerate(grammars):
            for n in range(8):
                for word in words("ab", n):
                    expected = (all(c == "a" for c in word)
                                if index != 3 else word == "")
                    with self.subTest(grammar=index, word=word):
                        self.assertEqual(earley_accepts(grammar, "S", word), expected)

    def test_nullable_across_nonterminal_boundaries(self):
        grammar = {"S": (("A", "B"),),
                   "A": (("a",), ()),
                   "B": (("b",), ())}
        for word, expected in (("", True), ("a", True), ("b", True),
                               ("ab", True), ("ba", False), ("aa", False)):
            self.assertEqual(earley_accepts(grammar, "S", word), expected)

    def test_invalid_contracts_and_empty_language(self):
        invalid = [
            ({}, "S", ""), ({"S": ((),)}, "X", ""),
            ({"S": ()}, "S", ""), ({"S": (("Unknown",),)}, "S", ""),
            ({"S": (("A",),)}, "S", ""), # A single-character symbol is a valid terminal
        ]
        # Single-letter terminal "A" is valid even though uppercase.
        self.assertFalse(earley_accepts(*invalid.pop()))
        for args in invalid:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    earley_accepts(*args)
        self.assertFalse(earley_accepts({"S": (("a",),)}, "S", ""))
        self.assertFalse(earley_accepts({"S": (("a",),)}, "S", "b"))
        for wrong in (None, 5, True, [")"], "a", " )"):
            with self.assertRaises(ValueError):
                parse_balanced(wrong)
        with self.assertRaises(ValueError):
            earley_accepts(BALANCED_GRAMMAR, "S", None)
        for wrong in (({"S": ("a",)}, "S", "a"),
                      ({"S": (("a",),), "A": 5}, "S", "a"),
                      ({"S": (((None,),))}, "S", "")):
            with self.assertRaises(ValueError):
                earley_accepts(*wrong)

    def test_site_bilingual_metadata_curriculum_and_code(self):
        articles = load_articles()
        self.assertEqual(load_modules()[TOPIC], "foundations")
        bodies = []
        for lang in ("en", "pt"):
            article = articles[lang][TOPIC]
            self.assertEqual(article["meta"]["prerequisites"],
                ["formal-languages-finite-automata", "recursion-call-stack"])
            for token in ("context_free_parser", "earley_accepts",
                          "parse_balanced", "a^n",
                          "stack" if lang == "en" else "pilha"):
                self.assertIn(token, article["body"])
            bodies.append(article["body"])
        for track in load_tracks()[:2]:
            ids = [topic for section in track["sections"]
                   for topic in section["articles"]]
            self.assertLess(ids.index("formal-languages-finite-automata"),
                            ids.index(TOPIC))
            self.assertLess(ids.index("recursion-call-stack"), ids.index(TOPIC))
        # The same executable demonstration is embedded in both languages.
        import re
        pattern = re.compile(r"(?ms)^~~~python\n(.*?)^~~~[ \t]*$")
        self.assertEqual(pattern.findall(bodies[0]), pattern.findall(bodies[1]))
        self.assertEqual(len(pattern.findall(bodies[0])), 1)


if __name__ == "__main__":
    unittest.main()
