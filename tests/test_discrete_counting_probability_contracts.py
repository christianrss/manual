"""Independent finite oracles for counting and exact probability in PT/EN.

Counting uses itertools enumeration, not the article's multiplicative recurrence.
Collision expectations enumerate the entire equally likely product space.
Bayes tests calculate weighted two-stage outcomes without calling the article's
closed-form function.
"""
import itertools
import re
import sys
import types
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

FENCE = re.compile(r"(?ms)^(?P<fence>\x60{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def chapter(lang):
    module = types.ModuleType("_discrete_probability_" + lang)
    sys.modules[module.__name__] = module
    try:
        body = load_articles()[lang]["discrete-counting-probability"]["body"]
        matches = tuple(FENCE.finditer(body))
        if len(matches) != 2:
            raise AssertionError("expected two executable examples")
        for number, match in enumerate(matches, 1):
            exec(compile(match["code"], f"{lang}/discrete/fence-{number}", "exec"),
                 module.__dict__, module.__dict__)
    finally:
        sys.modules.pop(module.__name__, None)
    return module

def enumerated_count(n, k, ordered):
    universe = tuple(range(n))
    iterator = (itertools.permutations(universe, k) if ordered
                else itertools.combinations(universe, k))
    return sum(1 for _ in iterator)

def product_statistics(days, draws):
    outcomes = tuple(itertools.product(range(days), repeat=draws))
    collisions = sum(len(set(row)) != len(row) for row in outcomes)
    total_distinct = sum(len(set(row)) for row in outcomes)
    return (Fraction(collisions, len(outcomes)),
            Fraction(total_distinct, len(outcomes)))

def weighted_posterior(p, s, f):
    """Enumerate actual-state and observed-result weights explicitly."""
    four_cases = (
        (True, True, p * s),
        (True, False, p * (1 - s)),
        (False, True, (1 - p) * f),
        (False, False, (1 - p) * (1 - f)),
    )
    positives = sum(weight for _, positive, weight in four_cases if positive)
    numerator = sum(weight for actual, positive, weight in four_cases
                    if actual and positive)
    if positives == 0:
        raise ValueError("conditioning on an impossible event")
    return numerator / positives

class DiscreteCountingProbabilityContracts(unittest.TestCase):
    def test_combinations_and_arrangements_against_enumeration(self):
        for lang in ("en", "pt"):
            module = chapter(lang)
            for n in range(9):
                for k in range(n + 3):
                    self.assertEqual(module.choose(n, k),
                                     enumerated_count(n, k, False), (lang, n, k))
                    self.assertEqual(module.arrangements(n, k),
                                     enumerated_count(n, k, True), (lang, n, k))
                self.assertEqual(sum(module.choose(n, k) for k in range(n + 1)),
                                 2 ** n)
                for k in range(n + 1):
                    self.assertEqual(module.choose(n, k),
                                     module.choose(n, n - k))
            for bad in ((-1, 1), (1, -1), (True, 1),
                        (5, False), (2.5, 1), ("5", 2)):
                with self.assertRaises(ValueError):
                    module.choose(*bad)
                with self.assertRaises(ValueError):
                    module.arrangements(*bad)

    def test_all_small_pairs_of_sets_by_membership_masks(self):
        for lang in ("en", "pt"):
            method = chapter(lang).union_cardinality
            for n in range(6):
                universe = range(n)
                subsets = [
                    {i for i in universe if mask & (1 << i)}
                    for mask in range(1 << n)
                ]
                for a, b in itertools.product(subsets, repeat=2):
                    # Independent per-element membership scan, not |A|+|B|-|A&B|.
                    expected = sum((i in a) or (i in b) for i in universe)
                    self.assertEqual(method(a, b), expected)
            for bad in (([1], {1}), ({1}, [1]), (None, {1})):
                with self.assertRaises(ValueError):
                    method(*bad)

    def test_collisions_and_distinct_expectation_by_full_product_space(self):
        for lang in ("en", "pt"):
            mod = chapter(lang)
            for days in range(1, 6):
                for people in range(7):
                    expected_collision, expected_distinct = product_statistics(
                        days, people)
                    self.assertEqual(mod.collision_probability(days, people),
                                     expected_collision, (lang, days, people))
                    self.assertEqual(mod.expected_distinct(days, people),
                                     expected_distinct, (lang, days, people))
            for bad in ((0, 0), (-1, 2), (2, -1), (True, 1),
                        (3, True), (3.2, 1)):
                with self.assertRaises(ValueError):
                    mod.collision_probability(*bad)
                with self.assertRaises(ValueError):
                    mod.expected_distinct(*bad)

    def test_bayes_against_weighted_outcomes(self):
        grid = tuple(Fraction(i, 4) for i in range(5))
        for lang in ("en", "pt"):
            mod = chapter(lang)
            for p, s, f in itertools.product(grid, repeat=3):
                try:
                    expected = weighted_posterior(p, s, f)
                except ValueError:
                    with self.assertRaises(ValueError):
                        mod.posterior_positive(p, s, f)
                else:
                    self.assertEqual(mod.posterior_positive(p, s, f), expected)
            for params in ((Fraction(-1), Fraction(1), Fraction(0)),
                           (Fraction(0), Fraction(2), Fraction(0)),
                           (Fraction(0), Fraction(1), Fraction(2)),
                           (0.25, Fraction(1), Fraction(0)),
                           (True, Fraction(1), Fraction(0))):
                with self.assertRaises(ValueError):
                    mod.posterior_positive(*params)

    def test_conditional_probability_by_explicit_counts(self):
        for lang in ("en", "pt"):
            method = chapter(lang).conditional_probability
            for n in range(1, 5):
                universe = set(range(n))
                sets = [{v for v in universe if mask & (1 << v)}
                        for mask in range(1 << n)]
                for event in sets:
                    for given in sets[1:]:
                        expected = Fraction(
                            sum(v in event for v in given), len(given))
                        self.assertEqual(method(universe, event, given),
                                         expected)
            for space, event, given in (
                ({1, 2}, {1}, set()),
                ({1, 2}, {3}, {1}),
                ({1, 2}, {1}, {3}),
                ([1, 2], {1}, {1}),
            ):
                with self.assertRaises(ValueError):
                    method(space, event, given)

if __name__ == "__main__":
    unittest.main()
