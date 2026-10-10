"""Independent regression checks for documented contracts in EN and PT.

The chapter code is executed in its own namespace, in published order. These
checks deliberately exercise facts beyond each article's selected assertions.
"""
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

PYTHON_FENCE = re.compile(
    r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$"
)

def chapter_namespace(lang, ident):
    source = load_articles()[lang][ident]["body"]
    module = types.ModuleType(f"_contract_{lang}_{ident.replace('-', '_')}")
    for index, match in enumerate(PYTHON_FENCE.finditer(source), 1):
        exec(compile(match.group("code"), f"{lang}/{ident}/block-{index}", "exec"),
             module.__dict__, module.__dict__)
    return module.__dict__


class FoundationalContractTests(unittest.TestCase):
    def test_ascii_filter_must_not_accept_unicode_case_equivalents(self):
        for lang, function in (("en", "filtered_ascii_letters"),
                               ("pt", "apenas_letras_ascii")):
            filter_ascii = chapter_namespace(lang, "arrays-and-strings")[function]
            for input_text, expected in (
                ("AZaz", "azaz"),
                ("İKÅ", ""),
                ("KKk", "kk"),
                ("éΩİABC", "abc"),
                ("", ""),
            ):
                with self.subTest(lang=lang, input=input_text):
                    self.assertEqual(filter_ascii(input_text), expected)
                    self.assertTrue(all("a" <= char <= "z"
                                        for char in filter_ascii(input_text)))

    def test_billable_contract_rejects_nonfinite_and_bad_quantities(self):
        from decimal import Decimal
        for lang, function in (("en", "billed_total"), ("pt", "total_cobrado")):
            bill = chapter_namespace(lang, "testing-strategies")[function]
            self.assertEqual(bill([(Decimal("0.15"), 2)], Decimal("0.10")),
                             Decimal("0.33"))
            for rate in (Decimal("NaN"), Decimal("Infinity"), Decimal("1.01")):
                with self.subTest(lang=lang, rate=rate), self.assertRaises(ValueError):
                    bill([], rate)
            for line in ((Decimal("NaN"), 1), (Decimal("Infinity"), 2),
                         (Decimal("1"), True), (Decimal("1"), 0)):
                with self.subTest(lang=lang, line=line), self.assertRaises(ValueError):
                    bill([line], Decimal("0"))

    def test_decorator_is_success_only_and_preserves_adapter_value(self):
        from decimal import Decimal
        for lang, decorator, adapter, legacy in (
            ("en", "RecordingQuote", "LegacyAdapter", "LegacyQuote"),
            ("pt", "CotacaoRegistrada", "AdaptadorLegado", "CotacaoLegada"),
        ):
            module = chapter_namespace(lang, "refactoring-design-patterns")
            wrapped = module[decorator](module[adapter](module[legacy]()))
            self.assertEqual(wrapped.total(Decimal("0.00")), Decimal("0.25"))
            self.assertEqual(wrapped.total(Decimal("5.00")), Decimal("5.25"))
            with self.assertRaises(ValueError):
                wrapped.total(Decimal("1.234"))
            log = (wrapped.successful_calls if lang == "en"
                   else wrapped.chamadas_bem_sucedidas)
            self.assertEqual(len(log), 2)


if __name__ == "__main__":
    unittest.main()
