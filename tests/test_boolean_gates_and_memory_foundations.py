"""Verify Boolean adders and immutable copy-on-write reference contracts."""
from pathlib import Path
import re
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks

PYTHON_FENCES = re.compile(r"(?ms)^~~~python[^\n]*\n(.*?)^~~~[ \t]*$")

def load_example(lang, slug):
    text = (ROOT / "content" / lang / "topics" / (slug + ".md")).read_text(encoding="utf8")
    chunks = PYTHON_FENCES.findall(text)
    if not chunks:
        raise AssertionError("no executable code")
    name = "foundations_" + lang + "_" + slug.replace("-", "_")
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        for snippet in chunks:
            exec(compile(snippet, name, "exec"), module.__dict__)
        return dict(module.__dict__)
    finally:
        sys.modules.pop(name, None)

class FoundationalHardwareMemoryTests(unittest.TestCase):
    def test_truth_tables_and_full_adder(self):
        for lang in ("en", "pt"):
            ns = load_example(lang, "digital-logic-gates-binary-adders")
            for a in (0, 1):
                self.assertEqual(ns["gate_not"](a), 1 - a)
                for b in (0, 1):
                    self.assertEqual(ns["gate_and"](a, b), a & b)
                    self.assertEqual(ns["gate_or"](a, b), a | b)
                    self.assertEqual(ns["gate_xor"](a, b), a ^ b)
                    sm, carry = ns["half_adder"](a, b)
                    self.assertEqual((sm, carry), ((a+b)%2, (a+b)//2))
                    for cin in (0, 1):
                        sm, carry = ns["full_adder"](a, b, cin)
                        self.assertEqual(sm + 2*carry, a + b + cin)
            for invalid in (True, -1, 2, 0.0):
                with self.assertRaises(ValueError):
                    ns["bit"](invalid)

    def test_unsigned_fixed_width_addition(self):
        for lang in ("en", "pt"):
            add = load_example(lang, "digital-logic-gates-binary-adders")["add_fixed_width"]
            for width in range(1, 7):
                limit = 1 << width
                for a in range(limit):
                    for b in range(limit):
                        with self.subTest(lang=lang, width=width, a=a, b=b):
                            self.assertEqual(add(a, b, width),
                                             ((a+b)%limit, (a+b)//limit))
            for args in ((1, 1, 0), (1, 1, True), (0, -1, 4),
                         (16, 0, 4), (True, 0, 4), (1.5, 0, 4)):
                with self.assertRaises(ValueError):
                    add(*args)

    def test_copy_on_write_vs_full_grid_reference(self):
        for lang in ("en", "pt"):
            ns = load_example(lang, "program-memory-references-lifetimes")
            freeze, replace = ns["freeze_grid"], ns["replace_cell"]
            self.assertEqual(freeze([]), ())
            for rows in range(1, 4):
                for cols in range(1, 4):
                    source = [[i*cols+j for j in range(cols)] for i in range(rows)]
                    frozen = freeze(source)
                    expected = tuple(tuple(row) for row in source)
                    self.assertEqual(frozen, expected)
                    for i in range(rows):
                        for j in range(cols):
                            candidate = replace(frozen, i, j, -7)
                            oracle = [list(row) for row in source]
                            oracle[i][j] = -7
                            self.assertEqual(candidate, tuple(map(tuple, oracle)))
                            self.assertEqual(frozen, expected)
                            for row_index in range(rows):
                                if row_index != i:
                                    self.assertIs(candidate[row_index], frozen[row_index])
                    source[0][0] = 999
                    self.assertEqual(frozen, expected)
            for invalid in ([[1], [1, 2]], [[]], [[1, True]], [3]):
                with self.assertRaises(ValueError):
                    freeze(invalid)
            with self.assertRaises(TypeError):
                freeze(None)
            for coord in ((-1, 0), (0, -1), (2, 0), (0, 2), (True, 0)):
                with self.assertRaises(IndexError):
                    replace(((1, 2), (3, 4)), coord[0], coord[1], 0)
            with self.assertRaises(ValueError):
                replace(((1, 2),), 0, 0, False)

    def test_curriculum_order_and_bilingual_prerequisites(self):
        mods = load_modules()
        self.assertEqual(mods["digital-logic-gates-binary-adders"], "computer-architecture")
        self.assertEqual(mods["program-memory-references-lifetimes"], "foundations")
        chapters = load_articles()
        for slug in ("digital-logic-gates-binary-adders", "program-memory-references-lifetimes"):
            self.assertEqual(chapters["en"][slug]["meta"]["prerequisites"],
                             chapters["pt"][slug]["meta"]["prerequisites"])
        for track in load_tracks()[:2]:
            ids = [slug for section in track["sections"] for slug in section["articles"]]
            self.assertLess(ids.index("data-types-bytes-and-representation"),
                            ids.index("digital-logic-gates-binary-adders"))
            self.assertLess(ids.index("digital-logic-gates-binary-adders"),
                            ids.index("machine-representation-isa-cache"))
            self.assertLess(ids.index("programming-semantics-contracts"),
                            ids.index("program-memory-references-lifetimes"))
            self.assertLess(ids.index("program-memory-references-lifetimes"),
                            ids.index("object-oriented-design"))
            self.assertEqual(len(ids), len(set(ids)))

if __name__ == "__main__":
    unittest.main()
