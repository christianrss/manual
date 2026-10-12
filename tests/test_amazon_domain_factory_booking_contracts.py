"""Independent checks for domain values, factory families and ticket-booking contracts."""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import types
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks  # noqa: E402

EXAMPLES = re.compile(r"(?ms)^~~~python[^\n]*\n(.*?)^~~~[ \t]*$")


def run_examples(lang, slug):
    article = (ROOT / "content" / lang / "topics" / (slug + ".md")).read_text(encoding="utf-8")
    chunks = EXAMPLES.findall(article)
    if not chunks:
        raise AssertionError("no executable examples: " + slug)
    module = types.ModuleType("manual_check_" + lang + "_" + slug.replace("-", "_"))
    sys.modules[module.__name__] = module
    try:
        for snippet in chunks:
            exec(compile(snippet, lang + "/" + slug, "exec"), module.__dict__)
        return dict(module.__dict__)
    finally:
        sys.modules.pop(module.__name__, None)


class DomainFactoryBookingTests(unittest.TestCase):
    def test_domain_invariants_and_immutability(self):
        for lang in ("en", "pt"):
            ns = run_examples(lang, "domain-modeling-aggregates-invariants")
            Order, Line, Money = ns["Order"], ns["OrderLine"], ns["Money"]
            order = Order("INV-1", "BRL")
            errors = [
                lambda: Line("A", True, Money(Decimal("1"), "BRL")),
                lambda: Line("A", 0, Money(Decimal("1"), "BRL")),
                lambda: Money(Decimal("NaN"), "BRL"),
                lambda: Money(Decimal("1.234"), "BRL"),
                lambda: Money(Decimal("-1"), "BRL"),
                lambda: Money(Decimal("1"), "brl"),
            ]
            for bad in errors:
                with self.subTest(lang=lang, bad=bad), self.assertRaises(ValueError):
                    bad()
            line = Line("A", 3, Money(Decimal("1.15"), "BRL"))
            order.add(line)
            snapshot = order.lines
            with self.assertRaises(ValueError):
                order.add(Line("A", 1, Money(Decimal("0"), "BRL")))
            with self.assertRaises(ValueError):
                order.add(Line("B", 1, Money(Decimal("0"), "USD")))
            self.assertEqual(order.lines, snapshot)
            self.assertEqual(order.place(), Money(Decimal("3.45"), "BRL"))
            with self.assertRaises(ValueError):
                order.add(Line("B", 1, Money(Decimal("0"), "BRL")))
            self.assertEqual(order.lines, snapshot)

    def test_factory_roundtrip_and_family(self):
        for lang in ("en", "pt"):
            ns = run_examples(lang, "factory-method-abstract-factory")
            data = [("comma,quote\"and\nnewline", 5), ("José", 0)]
            csv_data = ns["CsvExport"]().run(data)
            parsed = list(csv.reader(io.StringIO(csv_data)))
            self.assertEqual(parsed[0], ["name", "count"])
            self.assertEqual(parsed[1:], [[name, str(count)] for name, count in data])
            self.assertEqual(
                json.loads(ns["JsonExport"]().run(data)),
                [{"name": name, "count": count} for name, count in data]
            )
            for family, suffix in (
                (ns["CsvFamily"](), ".csv"), (ns["JsonFamily"](), ".json")
            ):
                path, contents = ns["export_package"](family, data, "quarter_1")
                self.assertTrue(path.endswith(suffix))
                self.assertIn("José", contents)
            with self.assertRaises(ValueError):
                ns["simple_factory"]("xml")
            with self.assertRaises(ValueError):
                ns["export_package"](ns["JsonFamily"](), data, "../bad")

    def test_booking_replay_and_expiry_fencing(self):
        for lang in ("en", "pt"):
            ns = run_examples(lang, "system-design-ticket-reservations")
            Model = ns["ReservationModel"]
            for expiry in (1, 10, 100):
                model = Model(["X"])
                token = f"first-{expiry}"
                other = f"second-{expiry}"
                model.hold("X", "alice", token, 0, expiry)
                with self.assertRaises(ValueError):
                    model.hold("X", "bob", other, expiry - 1, 10)
                self.assertEqual(model.status(token, expiry), "expired")
                model.hold("X", "bob", other, expiry, 10)
                self.assertEqual(model.hold("X", "alice", token, expiry + 1, expiry), token)
                self.assertEqual(model.status(token, expiry + 1), "expired")
                with self.assertRaises(ValueError):
                    model.confirm(token, expiry + 1)
                self.assertEqual(model.confirm(other, expiry + 1), "confirmed")
                with self.assertRaises(ValueError):
                    model.hold("X", "cara", "third", expiry + 1, 10)
                self.assertEqual(len(model.sold), 1)

    def test_booking_conflict_and_exact_deadline(self):
        for lang in ("en", "pt"):
            model = run_examples(lang, "system-design-ticket-reservations")["ReservationModel"](["A1"])
            model.hold("A1", "alice", "k1", 10, 5)
            with self.assertRaises(ValueError):
                model.hold("A1", "bob", "k1", 11, 5)
            with self.assertRaises(ValueError):
                model.confirm("k1", 15)
            self.assertEqual(model.status("k1", 15), "expired")
            self.assertEqual(model.hold("A1", "bob", "k2", 15, 5), "k2")
            self.assertEqual(model.confirm("k2", 16), "confirmed")

    def test_curriculum_order(self):
        mods = load_modules()
        self.assertEqual(mods["domain-modeling-aggregates-invariants"], "engineering")
        self.assertEqual(mods["factory-method-abstract-factory"], "engineering")
        self.assertEqual(mods["system-design-ticket-reservations"], "system-design")
        articles = load_articles()
        for slug in ("domain-modeling-aggregates-invariants",
                     "factory-method-abstract-factory",
                     "system-design-ticket-reservations"):
            self.assertEqual(articles["en"][slug]["meta"]["prerequisites"],
                             articles["pt"][slug]["meta"]["prerequisites"])
        amazon, cs = load_tracks()[:2]
        for track, expected in (
            (amazon, ("domain-modeling-aggregates-invariants",
                      "factory-method-abstract-factory",
                      "system-design-ticket-reservations")),
            (cs, ("domain-modeling-aggregates-invariants",
                  "factory-method-abstract-factory")),
        ):
            flattened = [slug for section in track["sections"] for slug in section["articles"]]
            for slug in expected:
                self.assertIn(slug, flattened)
                for dependency in articles["en"][slug]["meta"]["prerequisites"]:
                    if dependency in flattened:
                        self.assertLess(flattened.index(dependency), flattened.index(slug))


if __name__ == "__main__":
    unittest.main()
