"""Finite, independent contract checks of the bilingual Clean Code example."""
import itertools
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

FENCE = re.compile(r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def load_sample(lang):
    body = load_articles()[lang]["clean-code-cohesion-coupling"]["body"]
    name = f"_clean_code_{lang}"
    namespace = types.ModuleType(name)
    sys.modules[name] = namespace
    try:
        for fence in FENCE.finditer(body):
            exec(compile(fence["code"], name, "exec"), namespace.__dict__, namespace.__dict__)
    finally:
        sys.modules.pop(name, None)
    return namespace


class CleanCodeContracts(unittest.TestCase):
    def test_all_small_snapshots_match_independent_arithmetic_oracle(self):
        for lang in ("en", "pt"):
            mod = load_sample(lang)
            en = lang == "en"
            Row = mod.Stock if en else mod.Estoque
            fn = mod.plan_reorders if en else mod.planejar_reposicao
            for available, minimum in itertools.product(range(5), repeat=2):
                row = Row("SKU", available, minimum)
                plan = fn([row])
                expected = max(0, minimum - available)
                self.assertEqual(tuple(x.quantity if en else x.quantidade for x in plan),
                                 (expected,) if expected else ())
            # A separate expected-value construction, not invoking the planner recursively.
            for data in itertools.product(range(3), repeat=4):
                first = Row("A", data[0], data[1])
                second = Row("B", data[2], data[3])
                lines = fn([first, second])
                expected = [(code, max(0, threshold - present))
                            for code, present, threshold in [
                                ("A", data[0], data[1]), ("B", data[2], data[3])]]
                expected = [(code, gap) for code, gap in expected if gap]
                actual = [(x.sku, x.quantity) if en else (x.codigo, x.quantidade)
                          for x in lines]
                self.assertEqual(actual, expected)
            self.assertEqual(fn([]), ())

    def test_invalid_inputs_never_trigger_submission(self):
        for lang in ("en", "pt"):
            mod = load_sample(lang)
            en = lang == "en"
            Row = mod.Stock if en else mod.Estoque
            Sink = mod.RecordingSink if en else mod.ColetorEnvios
            execute = mod.execute_plan if en else mod.executar_plano
            sink = Sink()
            bad_inputs = [
                [Row("A", 0, 1), Row("A", 0, 1)],
                [Row(" A ", 0, 1)],
                [Row("", 0, 1)],
                [Row("A", True, 1)],
                [Row("A", -1, 1)],
                [Row("A", 1.5, 2)],
                [object()],
            ]
            for items in bad_inputs:
                with self.subTest(lang=lang, items=str(items)):
                    with self.assertRaises(ValueError):
                        execute(items, sink)
            self.assertEqual(sink.submissions if en else sink.envios, [])

    def test_monotone_stock_increase_and_failing_sink(self):
        for lang in ("en", "pt"):
            mod = load_sample(lang)
            en = lang == "en"
            Row = mod.Stock if en else mod.Estoque
            planner = mod.plan_reorders if en else mod.planejar_reposicao
            for threshold in range(7):
                previous = threshold
                for available in range(7):
                    result = planner([Row("A", available, threshold)])
                    missing = result[0].quantity if en and result else (
                        result[0].quantidade if result else 0)
                    self.assertLessEqual(missing, previous)
                    previous = missing

            class FailingSink:
                def submit(self, plan):
                    raise OSError("uncertain remote result")
                def enviar(self, plan):
                    raise OSError("resultado remoto incerto")

            with self.assertRaises(OSError):
                (mod.execute_plan if en else mod.executar_plano)([Row("A", 0, 2)], FailingSink())


if __name__ == "__main__":
    unittest.main()
