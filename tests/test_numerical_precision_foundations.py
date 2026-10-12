"""Independent oracles for floating-point summation and one-pass variance."""
from fractions import Fraction
from itertools import product
from pathlib import Path
import math
import re
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks

PYTHON_FENCES = re.compile(r"(?ms)^~~~python[^\n]*\n(.*?)^~~~[ \t]*$")

def load_example(lang, slug):
    article = (ROOT / "content" / lang / "topics" /
               (slug + ".md")).read_text(encoding="utf-8")
    blocks = PYTHON_FENCES.findall(article)
    if not blocks:
        raise AssertionError("article lacks executable Python")
    module = types.ModuleType("test_" + lang + "_" + slug.replace("-", "_"))
    for block in blocks:
        exec(compile(block, slug, "exec"), module.__dict__)
    return module.__dict__

class FloatingPointContracts(unittest.TestCase):
    def test_representation_and_cancellation(self):
        for lang in ("en", "pt"):
            ns = load_example(lang, "floating-point-error-compensated-summation")
            naive, corrected = ns["naive_sum"], ns["neumaier_sum"]
            self.assertNotEqual(Fraction.from_float(0.1), Fraction(1, 10))
            data = [1e16, 1.0, -1e16]
            reference = float(sum(map(Fraction.from_float, data)))
            self.assertEqual(reference, 1.0)
            self.assertEqual(naive(data), 0.0)
            self.assertEqual(corrected(data), reference)
            self.assertEqual(math.fsum(data), reference)
            for size in range(5):
                for items in product((-2.0, -0.25, 0.0, 0.25, 2.0),
                                     repeat=size):
                    correct = float(sum(map(Fraction.from_float, items),
                                        Fraction(0)))
                    self.assertEqual(corrected(items), correct)
                    self.assertEqual(naive(items), correct)
            for invalid in ([1], [True], [math.inf], [-math.inf], [math.nan]):
                with self.assertRaises(ValueError):
                    naive(invalid)
                with self.assertRaises(ValueError):
                    corrected(invalid)
            for method in (naive, corrected):
                with self.assertRaises(OverflowError):
                    method([1e308, 1e308])

    def test_welford_exact_reference_and_atomic_failure(self):
        for lang in ("en", "pt"):
            cls = load_example(lang, "online-mean-variance-welford")["OnlineMoments"]
            empty = cls()
            with self.assertRaises(ValueError):
                empty.summary()
            for size in range(1, 5):
                for values in product((-1.0, -0.25, 0.0, 0.5, 2.0),
                                      repeat=size):
                    stream = cls()
                    for value in values:
                        stream.add(value)
                    result = stream.summary()
                    exact = list(map(Fraction.from_float, values))
                    mean = sum(exact, Fraction(0)) / size
                    m2 = sum(((v - mean) ** 2 for v in exact), Fraction(0))
                    self.assertEqual(result["count"], size)
                    self.assertTrue(math.isclose(
                        result["mean"], float(mean), rel_tol=1e-12,
                        abs_tol=1e-12))
                    self.assertTrue(math.isclose(
                        result["population_variance"], float(m2 / size),
                        rel_tol=1e-12, abs_tol=1e-12))
                    if size == 1:
                        self.assertIsNone(result["sample_variance"])
                    else:
                        self.assertTrue(math.isclose(
                            result["sample_variance"], float(m2 / (size - 1)),
                            rel_tol=1e-12, abs_tol=1e-12))
                    old = dict(result)
                    for invalid in (0, True, "1.0", math.inf, math.nan):
                        with self.assertRaises(ValueError):
                            stream.add(invalid)
                        self.assertEqual(stream.summary(), old)
            stream = cls()
            values = [1e12 + 0.25, 1e12 + 0.5, 1e12 + 0.75]
            for value in values:
                stream.add(value)
            out = stream.summary()
            self.assertEqual(out["mean"], 1e12 + 0.5)
            self.assertTrue(math.isclose(out["population_variance"], 1 / 24,
                                         rel_tol=1e-14))
            self.assertEqual(out["sample_variance"], 1 / 16)
            naive = sum(x*x for x in values)/3 - (sum(values)/3)**2
            self.assertGreater(abs(naive - 1/24), 0.01)
            overflow = cls()
            overflow.add(1e308)
            saved = dict(overflow.summary())
            with self.assertRaises(OverflowError):
                overflow.add(-1e308)
            self.assertEqual(overflow.summary(), saved)

    def test_prerequisite_order_in_both_tracks(self):
        modules = load_modules()
        topics = ("floating-point-error-compensated-summation",
                  "online-mean-variance-welford")
        articles = load_articles()
        for slug in topics:
            self.assertEqual(modules[slug], "foundations")
            self.assertEqual(articles["en"][slug]["meta"]["prerequisites"],
                             articles["pt"][slug]["meta"]["prerequisites"])
        for track in load_tracks()[:2]:
            names = [slug for section in track["sections"]
                     for slug in section["articles"]]
            for first, second in (
                ("data-types-bytes-and-representation", topics[0]),
                ("complexity-analysis", topics[0]),
                ("discrete-counting-probability", topics[1]),
                (topics[0], topics[1]),
                (topics[1], "algorithmic-problem-solving-method"),
            ):
                self.assertLess(names.index(first), names.index(second))
            self.assertEqual(len(names), len(set(names)))

if __name__ == "__main__":
    unittest.main()
