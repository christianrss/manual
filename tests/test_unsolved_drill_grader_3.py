"""Public contract tests for independent assessment III.

The student functions must remain unsolved. These tests verify quality of the
public grading interface, not completion of any candidate solution.
A brute-force enumeration checks small partition fixtures independently; it is
NOT the target dynamic-programming implementation.
"""
import sys
import unittest
from pathlib import Path
from itertools import product

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "examples" / "python"))
from model import load_articles, load_modules, load_tracks
from unsolved_drills_3 import minimum_partition_penalty, apply_idempotent_events
from drill_grader_3 import (
    PARTITION_CASES, PARTITION_INVALID, EVENT_CASES, EVENT_INVALID, evaluate
)


def enumerate_partition_cuts(values, max_size, overhead):
    """Oracle that enumerates all boundary masks (exponential; tiny n only)."""
    n = len(values)
    if n == 0:
        return 0
    best = None
    for boundary_mask in range(1 << (n - 1)):
        segments = []
        previous = 0
        for ix in range(1, n):
            if (boundary_mask >> (ix - 1)) & 1:
                segments.append(values[previous:ix])
                previous = ix
        segments.append(values[previous:n])
        if any(len(segment) > max_size for segment in segments):
            continue
        cost = sum(sum(segment) ** 2 + overhead for segment in segments)
        best = cost if best is None else min(best, cost)
    if best is None:
        raise AssertionError("Every positive max_size permits singleton groups")
    return best


class ThirdIndependentAssessmentTests(unittest.TestCase):
    def test_curriculum_registration_and_bilingual_pair(self):
        self.assertEqual(
            load_modules()["independent-coding-engineering-assessment-iii"],
            "interview-practice",
        )
        articles = load_articles()
        for language in ("en", "pt"):
            item = articles[language]["independent-coding-engineering-assessment-iii"]
            self.assertEqual(
                item["meta"]["prerequisites"],
                ["dynamic-programming", "testing-strategies",
                 "programming-semantics-contracts", "asynchronous-messaging"],
            )
            self.assertIn("unsolved_drills_3.py", item["body"])
            self.assertIn("drill_grader_3.py", item["body"])
        core = [ref for section in load_tracks()[0]["sections"] for ref in section["articles"]]
        assessment = "independent-coding-engineering-assessment-iii"
        self.assertLess(core.index("independent-coding-assessment-ii"),
                        core.index(assessment))
        for dependency in articles["en"][assessment]["meta"]["prerequisites"]:
            self.assertLess(core.index(dependency), core.index(assessment))

    def test_public_partition_expectations_have_independent_small_oracle(self):
        self.assertGreaterEqual(len(PARTITION_CASES), 12)
        for values, max_size, overhead, expected in PARTITION_CASES:
            with self.subTest(values=values, max_size=max_size, overhead=overhead):
                self.assertEqual(
                    enumerate_partition_cuts(values, max_size, overhead), expected
                )
        self.assertEqual(len(PARTITION_INVALID), len(set(
            (repr(a), b, repr(c)) for a, b, c in PARTITION_INVALID
        )))

    def test_event_fixtures_exercise_semantic_boundaries(self):
        self.assertGreaterEqual(len(EVENT_CASES), 10)
        self.assertGreaterEqual(len(EVENT_INVALID), 12)
        self.assertTrue(any(
            len(events) > len({event[0] for event in events})
            for _, events, _ in EVENT_CASES
        ))
        self.assertTrue(any(
            any(delta < 0 for _, _, delta in events)
            for _, events, _ in EVENT_CASES
        ))
        self.assertTrue(any(
            opening and events and events[0][1] not in opening
            for opening, events in EVENT_INVALID
            if isinstance(events, list) and events and isinstance(events[0], tuple)
              and len(events[0]) == 3
        ))
        self.assertTrue(any(
            isinstance(events, list) and len(events) > 1 and
            all(isinstance(e, tuple) and len(e) == 3 for e in events) and
            events[0][0] == events[1][0] and events[0] != events[1]
            for _, events in EVENT_INVALID
        ))

    def test_starters_remain_unsolved(self):
        with self.assertRaises(NotImplementedError):
            minimum_partition_penalty([2, 1], 2, 3)
        with self.assertRaises(NotImplementedError):
            apply_idempotent_events({"a": 2}, [("x", "a", 1)])
        with self.assertRaises(NotImplementedError):
            evaluate()

    def test_grader_rejects_trivial_and_mutation_prone_candidates(self):
        with self.assertRaises(AssertionError):
            evaluate(lambda *args: 0, lambda *args: {})
        def mutate_partition(values, max_size, overhead):
            values.reverse()
            return 20
        with self.assertRaisesRegex(AssertionError, "modified input"):
            evaluate(mutate_partition, lambda *args: {})

        # Simulate an overfit answer to PUBLIC partitions to reach projection
        # checks. This explicitly demonstrates why published fixtures are not
        # an unseen-solution correctness oracle.
        lookup = {(tuple(a), b, c): expected
                  for a, b, c, expected in PARTITION_CASES}
        invalid = {(repr(a), b, repr(c))
                   for a, b, c in PARTITION_INVALID}
        def fixture_only_partition(values, max_size, overhead):
            if (repr(values), max_size, repr(overhead)) in invalid:
                raise ValueError("invalid")
            return lookup[(tuple(values), max_size, overhead)]
        def mutate_projection(balances, events):
            balances.clear()
            return {} if not events else {"a": 7}
        with self.assertRaisesRegex(AssertionError, "mutated inputs"):
            evaluate(fixture_only_partition, mutate_projection)


if __name__ == "__main__":
    unittest.main()
