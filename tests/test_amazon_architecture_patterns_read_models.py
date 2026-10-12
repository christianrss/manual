"""Independent adversarial checks for Amazon-core architecture, patterns and read models."""
from __future__ import annotations

import re
import sys
import types
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_modules, load_tracks  # noqa: E402


def execute_examples(lang: str, slug: str):
    source = (ROOT / "content" / lang / "topics" / (slug + ".md")).read_text(encoding="utf-8")
    chunks = re.findall(r"(?ms)^~~~python[^\n]*\n(.*?)^~~~[ \t]*$", source)
    if not chunks:
        raise AssertionError("missing executable example: " + slug)
    name = "_manual_contract_" + lang + "_" + slug.replace("-", "_")
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        for chunk in chunks:
            exec(compile(chunk, slug, "exec"), module.__dict__)
        return module.__dict__.copy()
    finally:
        sys.modules.pop(name, None)


class AmazonArchitectureContracts(unittest.TestCase):
    def test_module_boundaries(self):
        for lang in ("en", "pt"):
            ns = execute_examples(lang, "architecture-dependency-boundaries")
            checker = ns["check_imports"]
            self.assertTrue(checker({"domain": set(), "ports": {"domain"}}))
            for invalid in ({"domain": {"sql_adapter"}}, {"bootstrap": {"secret"}},
                            {"other": {"domain"}}, {"http": {"domain"}}):
                with self.subTest(lang=lang, invalid=invalid), self.assertRaises(ValueError):
                    checker(invalid)

    def test_state_and_command_transitions(self):
        for lang in ("en", "pt"):
            ns = execute_examples(lang, "state-command-design-patterns")
            Document, Command = ns["Document"], ns["TransitionCommand"]
            for first in ("submit", "publish"):
                for second in ("submit", "publish"):
                    d = Document()
                    actions = (first, second)
                    expected_version = 0
                    expected_phase = "draft"
                    for action in actions:
                        before = (d.state.name, d.version)
                        try:
                            d.apply(action)
                        except ValueError:
                            self.assertEqual((d.state.name, d.version), before)
                        else:
                            expected_version += 1
                            expected_phase = d.state.name
                    self.assertEqual(d.version, expected_version)
                    self.assertEqual(d.state.name, expected_phase)
            with self.assertRaises(ValueError):
                Command("submit", -1).execute(Document())
            d = Document()
            self.assertEqual(Command("submit", 0).execute(d), "review")
            with self.assertRaises(ValueError):
                Command("submit", 0).execute(d)
            self.assertEqual(d.version, 1)

    def test_projection_against_recomputed_totals(self):
        for lang in ("en", "pt"):
            ns = execute_examples(lang, "system-design-read-write-models")
            projector = ns["Projector"]()
            reference = {}
            # An independent state oracle recomputes current totals from replacements.
            for i in range(1, 61):
                key = "store-" + str(i % 7)
                value = Decimal(i * 3) / Decimal("10")
                old = reference.get(key)
                version = 1 if old is None else old[0] + 1
                self.assertTrue(projector.apply(key, version, value))
                reference[key] = (version, value)
                self.assertFalse(projector.apply(key, version, value))
                self.assertEqual(projector.total(), sum((v for _, v in reference.values()), Decimal(0)))
                self.assertEqual(projector.orders, reference)
            snapshot = dict(projector.orders)
            with self.assertRaises(ValueError):
                projector.apply("store-0", 100, Decimal(1))
            with self.assertRaises(ValueError):
                projector.apply("store-0", snapshot["store-0"][0], Decimal(987))
            with self.assertRaises(ValueError):
                projector.apply("store-0", snapshot["store-0"][0] + 1, Decimal("NaN"))
            self.assertEqual(projector.orders, snapshot)

    def test_core_track_follows_concepts(self):
        modules = load_modules()
        self.assertEqual(modules["architecture-dependency-boundaries"], "engineering")
        self.assertEqual(modules["state-command-design-patterns"], "engineering")
        self.assertEqual(modules["system-design-read-write-models"], "system-design")
        track = load_tracks()[0]
        core = [x for section in track["sections"] for x in section["articles"]]
        self.assertEqual(len(core), len(set(core)))
        for a, b in (
            ("solid-dependency-inversion", "architecture-dependency-boundaries"),
            ("design-pattern-families", "state-command-design-patterns"),
            ("asynchronous-messaging", "system-design-read-write-models"),
            ("database-consistency", "system-design-read-write-models"),
        ):
            self.assertLess(core.index(a), core.index(b))
        self.assertTrue(track["sections"][-1]["title"]["en"].startswith("Optional"))
        self.assertNotIn("integrated-vm-mark-sweep-gc", track["sections"][0]["articles"])


if __name__ == "__main__":
    unittest.main()
