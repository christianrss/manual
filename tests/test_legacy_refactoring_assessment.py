"""Legacy refactoring assessment IV: prove existing defects and grade the new contract.

Do not rewrite the intentionally defective baseline. This test suite explicitly
separates observed behavior (characterization) from required behavior (contract).
"""
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples" / "python"))
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks
from legacy_ticket_search import legacy_search_tickets
from refactor_ticket_search import search_tickets
from ticket_search_grader import (
    BASE, VALID_CASES, INVALID_CASES,
    ticket, evaluate, check_valid, check_invalid
)


class CharacterizationOfDefectiveLegacy(unittest.TestCase):
    def test_observed_pagination_occurs_before_scoping(self):
        tickets = deepcopy(BASE)
        observed = legacy_search_tickets(tickets, "a", None, 0, 1)
        self.assertEqual(observed, {"items": [], "total": 0})
        # The contract instead requires 3 matching records and the first a2.
        self.assertEqual(VALID_CASES[2][-1]["total"], 3)
        self.assertEqual(VALID_CASES[2][-1]["items"][0]["id"], "a2")

    def test_legacy_mutates_order_and_exposes_private_fields(self):
        tickets = deepcopy(BASE)
        original = deepcopy(tickets)
        observed = legacy_search_tickets(tickets, "a", None, 0, 10)
        self.assertNotEqual(tickets, original)
        self.assertEqual([r["id"] for r in tickets], ["b1", "a3", "a2", "a1"])
        self.assertIn("private_phone", observed["items"][0])
        self.assertIn("internal_note", observed["items"][1])
        self.assertEqual(observed["total"], 3)

    def test_legacy_fails_grader(self):
        with self.assertRaises(AssertionError):
            evaluate(legacy_search_tickets)

    def test_legacy_tie_sort_stays_in_source_order(self):
        tickets = [ticket("z", "a", "open", 7), ticket("a", "a", "open", 7)]
        self.assertEqual(
            [row["id"] for row in legacy_search_tickets(tickets, "a")["items"]],
            ["z", "a"],
        )
        # New contract breaks timestamp ties by id ascending.
        self.assertEqual([row["id"] for row in VALID_CASES[10][-1]["items"]], ["a", "z"])


class AssessmentContractQuality(unittest.TestCase):
    def test_starter_remains_unsolved(self):
        with self.assertRaises(NotImplementedError):
            search_tickets([], "a")
        with self.assertRaises(NotImplementedError):
            evaluate()

    def test_public_grader_has_valid_and_invalid_coverage(self):
        self.assertGreaterEqual(len(VALID_CASES), 15)
        self.assertGreaterEqual(len(INVALID_CASES), 20)
        self.assertTrue(any(c[-1]["total"] > len(c[-1]["items"]) for c in VALID_CASES))
        self.assertTrue(any(c[-1]["items"] == [] and c[-1]["total"] > 0 for c in VALID_CASES))
        self.assertTrue(any(any("internal_note" in row for row in case[0])
                            for case in VALID_CASES if case[0]))
        self.assertTrue(any(c[0] and isinstance(c[0], list) and
                            len(c[0]) == 2 and c[0][0]["id"] == c[0][1]["id"]
                            for c in INVALID_CASES
                            if isinstance(c[0], list) and len(c[0]) == 2))

    def test_grader_detects_input_mutation_even_with_correct_result(self):
        case = VALID_CASES[1]
        expected = deepcopy(case[-1])
        def mutate(source, tenant, status, offset, limit):
            source.reverse()
            return deepcopy(expected)
        with self.assertRaisesRegex(AssertionError, "mutated caller-owned"):
            check_valid(mutate, case)

    def test_grader_detects_output_alias_and_invalid_input_mutation(self):
        case = ([ticket("only", "a", "open", 8)], "a", None, 0, 1,
                {"items": [{"id": "only", "status": "open", "created_at": 8}], "total": 1})
        def leak_record(source, tenant, status, offset, limit):
            return {"items": source, "total": 1}
        with self.assertRaises(AssertionError):
            check_valid(leak_record, case)

        invalid = INVALID_CASES[-1]
        def mutate_then_raise(source, *_):
            source.clear()
            raise ValueError("invalid")
        with self.assertRaisesRegex(AssertionError, "mutated invalid caller"):
            check_invalid(mutate_then_raise, invalid)

    def test_curriculum_bilingual_contracts(self):
        key = "legacy-refactoring-assessment"
        self.assertEqual(load_modules()[key], "interview-practice")
        articles = load_articles()
        for language in ("en", "pt"):
            chapter = articles[language][key]
            self.assertEqual(chapter["meta"]["prerequisites"],
                ["refactoring-design-patterns", "testing-strategies", "api-security",
                 "api-contracts-pagination"])
            for file in ("legacy_ticket_search.py", "refactor_ticket_search.py",
                         "ticket_search_grader.py"):
                self.assertIn(file, chapter["body"])
        amazon = [key2 for sec in load_tracks()[0]["sections"] for key2 in sec["articles"]]
        for dependency in articles["en"][key]["meta"]["prerequisites"]:
            self.assertLess(amazon.index(dependency), amazon.index(key))
        self.assertLess(amazon.index("independent-coding-engineering-assessment-iii"),
                        amazon.index(key))


if __name__ == "__main__":
    unittest.main()
