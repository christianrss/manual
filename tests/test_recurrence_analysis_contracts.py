"""Independent finite-oracle tests for the bilingual recurrence analysis chapter.

Exact costs are checked against both a *full recursive call tree* and separately
derived closed forms. This is bounded validation, not a universal proof.
"""
from __future__ import annotations

import ast
import re
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks

CODE_FENCE = re.compile(r"(?ms)^~~~python\n(.*?)^~~~[ \t]*$")

FAMILIES = {
    "split-unit": (2, lambda size: 1),
    "split-linear": (2, lambda size: size),
    "split-quadratic": (2, lambda size: size * size),
    "split-log": (2, lambda size: size * (size.bit_length() - 1)),
    "halve-unit": (1, lambda size: 1),
    "halve-linear": (1, lambda size: size),
}


def article_models():
    articles = load_articles()
    result = []
    for language in ("en", "pt"):
        blocks = CODE_FENCE.findall(articles[language]["recurrence-analysis"]["body"])
        if len(blocks) != 1:
            raise AssertionError(f"{language}: expected one Python cost model")
        namespace = {}
        exec(compile(blocks[0], f"{language}/recurrence-analysis", "exec"), namespace)
        result.append((language, blocks[0], namespace))
    return result


def oracle_full_call_tree(n, kind):
    """Traverse *every* recursive branch rather than summing per-level node counts."""
    if n == 1:
        return 1
    count, own_work = FAMILIES[kind]
    return own_work(n) + sum(
        oracle_full_call_tree(n // 2, kind) for _ in range(count)
    )


def algebraic_cost(n, kind):
    k = n.bit_length() - 1
    answers = {
        "split-unit": 2 * n - 1,
        "split-linear": n * (k + 1),
        "split-quadratic": 2 * n * n - n,
        "split-log": n * (1 + k * (k + 1) // 2),
        "halve-unit": k + 1,
        "halve-linear": 2 * n - 1,
    }
    return answers[kind]


def harmonic_oracle(n):
    """Rational recurrence: T(n)=2T(n/2)+n/log2(n), T(1)=1."""
    if n == 1:
        return Fraction(1)
    k = n.bit_length() - 1
    return 2 * harmonic_oracle(n // 2) + Fraction(n, k)


class RecurrenceAnalysisContracts(unittest.TestCase):
    def test_curriculum_and_prerequisites(self):
        self.assertEqual(load_modules()["recurrence-analysis"], "foundations")
        articles = load_articles()
        for language in ("en", "pt"):
            self.assertEqual(
                articles[language]["recurrence-analysis"]["meta"]["prerequisites"],
                ["complexity-analysis", "recursion-call-stack"],
            )
        for track in load_tracks()[:2]:
            ids = [item for section in track["sections"] for item in section["articles"]]
            self.assertLess(ids.index("complexity-analysis"), ids.index("recursion-call-stack"))
            self.assertLess(ids.index("recursion-call-stack"), ids.index("recurrence-analysis"))
            self.assertLess(ids.index("recurrence-analysis"), ids.index("system-design-process"))

    def test_code_equivalence_and_exact_costs(self):
        implementations = article_models()
        self.assertEqual(
            ast.dump(ast.parse(implementations[0][1]), include_attributes=False),
            ast.dump(ast.parse(implementations[1][1]), include_attributes=False),
        )
        for language, _, functions in implementations:
            evaluate = functions["recurrence_work"]
            for k in range(9):
                n = 1 << k
                for kind in FAMILIES:
                    with self.subTest(language=language, power=k, family=kind):
                        observed = evaluate(n, kind)
                        self.assertEqual(observed, oracle_full_call_tree(n, kind))
                        self.assertEqual(observed, algebraic_cost(n, kind))

    def test_arbitrary_n_decrement_recurrence(self):
        for language, _, functions in article_models():
            descending_work = functions["descending_work"]
            for n in range(1, 129):
                with self.subTest(language=language, n=n):
                    self.assertEqual(descending_work(n), sum(range(1, n + 1)))
                    self.assertEqual(descending_work(n), n * (n + 1) // 2)

    def test_boundary_contract_and_power_of_two_restriction(self):
        for language, _, functions in article_models():
            evaluate = functions["recurrence_work"]
            descending = functions["descending_work"]
            for bad_n in (0, -1, -16, True, False, 1.0, "8", 3, 6, 12):
                with self.subTest(language=language, bad_n=bad_n):
                    with self.assertRaises(ValueError):
                        evaluate(bad_n, "split-linear")
            for bad_kind in ("", "other", None, [], 1):
                with self.subTest(language=language, bad_kind=bad_kind):
                    with self.assertRaises(ValueError):
                        evaluate(8, bad_kind)
            for bad_n in (0, -3, True, False, 4.0, "4"):
                with self.subTest(language=language, bad_n=bad_n):
                    with self.assertRaises(ValueError):
                        descending(bad_n)

    def test_harmonic_counterexample_outside_elementary_master_cases(self):
        for k in range(1, 13):
            n = 1 << k
            harmonic = sum((Fraction(1, i) for i in range(1, k + 1)), Fraction(0))
            with self.subTest(k=k):
                self.assertEqual(
                    harmonic_oracle(n),
                    n * (Fraction(1) + harmonic),
                )
                self.assertGreater(harmonic_oracle(n), n)


if __name__ == "__main__":
    unittest.main()
