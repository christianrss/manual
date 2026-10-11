"""Independent small-domain checks for new foundational chapters.

The examples in each language are executable documentation, not production libraries.
The oracle deliberately scans linearly instead of copying midpoint logic.
"""
from __future__ import annotations

import itertools
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks

FENCE = re.compile(r"(?ms)^(?:`{3}|~{3})python[^\n]*\n(.*?)(?:^`{3}|^~{3})[ \t]*$")


def chapter_namespace(language, article_id):
    body = load_articles()[language][article_id]["body"]
    chunks = FENCE.findall(body)
    if not chunks:
        raise AssertionError(f"{language}/{article_id}: no executable examples")
    namespace = {}
    for code in chunks:
        exec(compile(code, f"{language}/{article_id}", "exec"), namespace)
    return namespace


class FoundationalProofTests(unittest.TestCase):
    def test_topic_registry_and_prerequisites(self):
        modules = load_modules()
        self.assertEqual(modules["logic-proofs-invariants"], "foundations")
        self.assertEqual(modules["programming-semantics-contracts"], "foundations")
        articles = load_articles()
        for lang in ("en", "pt"):
            self.assertEqual(
                articles[lang]["programming-semantics-contracts"]["meta"]["prerequisites"],
                ["logic-proofs-invariants"],
            )
            self.assertIn("logic-proofs-invariants", articles[lang]["complexity-analysis"]["meta"]["prerequisites"])
            self.assertIn("programming-semantics-contracts", articles[lang]["arrays-and-strings"]["meta"]["prerequisites"])
        for track in load_tracks()[:2]:
            ids = [article for section in track["sections"] for article in section["articles"]]
            self.assertLess(ids.index("logic-proofs-invariants"), ids.index("programming-semantics-contracts"))
            self.assertLess(ids.index("programming-semantics-contracts"), ids.index("complexity-analysis"))
            self.assertLess(ids.index("complexity-analysis"), ids.index("arrays-and-strings"))

    def test_lower_bound_against_linear_oracle(self):
        for lang, function_name in (("en", "lower_bound"), ("pt", "limite_inferior")):
            namespace = chapter_namespace(lang, "logic-proofs-invariants")
            fn = namespace[function_name]
            for n in range(7):
                for seq in itertools.combinations_with_replacement((-2, 0, 2), n):
                    for target in range(-3, 4):
                        expected = next((i for i, value in enumerate(seq) if value >= target), len(seq))
                        with self.subTest(lang=lang, seq=seq, target=target):
                            self.assertEqual(fn(seq, target), expected)

    def test_first_occurrence_against_linear_oracle(self):
        for lang, function_name in (("en", "first_index"), ("pt", "primeiro_indice")):
            fn = chapter_namespace(lang, "logic-proofs-invariants")[function_name]
            for n in range(6):
                for seq in itertools.product((0, 1, 2), repeat=n):
                    for target in (-1, 0, 1, 2, 3):
                        expected = next((i for i, x in enumerate(seq) if x == target), -1)
                        self.assertEqual(fn(seq, target), expected)

    def test_semantics_examples_and_contracts(self):
        for lang in ("en", "pt"):
            namespace = chapter_namespace(lang, "programming-semantics-contracts")
            if lang == "en":
                choose, divide = namespace["choose_port"], namespace["divide_by_positive_count"]
            else:
                choose, divide = namespace["escolher_porta"], namespace["dividir_por_contagem_positiva"]
            self.assertEqual(choose(0, 443), 0)
            self.assertEqual(choose(None, 443), 443)
            self.assertEqual(divide(24, 6), 4.0)
            with self.assertRaises(ValueError):
                divide(1, 0)
            with self.assertRaises(TypeError):
                divide(1, "2")


if __name__ == "__main__":
    unittest.main()
