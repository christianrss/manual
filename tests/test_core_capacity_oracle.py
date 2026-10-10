"""Independent exhaustive oracle for the capacity-search example in both manuals.

This test intentionally enumerates all contiguous day partitions instead of
reusing the chapter's greedy feasibility checker. Enumeration is deliberately
small and establishes evidence only for the stated finite test domain.
"""
import itertools
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

PYTHON_FENCE = re.compile(
    r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$"
)

def partition_oracle(jobs, max_days):
    """Enumerate cuts; the answer is the lowest maximum segment sum."""
    n = len(jobs)
    optimum = sum(jobs)
    for days in range(1, min(max_days, n) + 1):
        for cuts in itertools.combinations(range(1, n), days - 1):
            bounds = (0,) + cuts + (n,)
            largest = max(sum(jobs[bounds[i]:bounds[i + 1]]) for i in range(days))
            optimum = min(optimum, largest)
    return optimum

class IndependentCapacityOracleTests(unittest.TestCase):
    def test_all_small_positive_cases_both_languages(self):
        docs = load_articles()
        for lang, name in (("en", "minimum_capacity"), ("pt", "capacidade_minima")):
            namespace = {}
            for match in PYTHON_FENCE.finditer(docs[lang]["binary-search"]["body"]):
                exec(compile(match.group("code"), f"{lang}/binary-search", "exec"),
                     namespace, namespace)
            self.assertIn(name, namespace)
            solver = namespace[name]
            for n in range(1, 6):
                for jobs in itertools.product(range(1, 4), repeat=n):
                    for days in range(1, n + 2):
                        result = solver(list(jobs), days)
                        expected = partition_oracle(jobs, days)
                        self.assertEqual(result, expected, (lang, jobs, days))

    def test_invalid_contracts(self):
        docs = load_articles()
        for lang, name in (("en", "minimum_capacity"), ("pt", "capacidade_minima")):
            namespace = {}
            for match in PYTHON_FENCE.finditer(docs[lang]["binary-search"]["body"]):
                exec(compile(match.group("code"), f"{lang}/binary-search", "exec"),
                     namespace, namespace)
            solver = namespace[name]
            for jobs, days in (([], 1), ([1], 0), ([1, 0], 2), ([-1, 2], 1)):
                with self.subTest(lang=lang, jobs=jobs, days=days):
                    with self.assertRaises(ValueError):
                        solver(jobs, days)

if __name__ == "__main__":
    unittest.main()
