"""Independently verify elementary integer-number-theory foundations."""
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
    content = (ROOT / "content" / lang / "topics" / (slug + ".md")).read_text(encoding="utf8")
    blocks = PYTHON_FENCES.findall(content)
    if not blocks:
        raise AssertionError("missing runnable Python example")
    name = "test_" + lang + "_" + slug.replace("-", "_")
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        for block in blocks:
            exec(compile(block, name, "exec"), module.__dict__)
        return dict(module.__dict__)
    finally:
        sys.modules.pop(name, None)

def brute_gcd(a, b):
    if not a and not b:
        return 0
    return max(k for k in range(1, max(abs(a), abs(b)) + 1)
               if a % k == 0 and b % k == 0)

class NumberTheoryFoundationsTests(unittest.TestCase):
    def test_euclid_and_bezout_against_independent_oracle(self):
        for lang in ("en", "pt"):
            ns = load_example(lang, "number-theory-divisibility-euclid")
            gcd, coeff, lcm = ns["euclid_gcd"], ns["bezout"], ns["least_common_multiple"]
            for a in range(-25, 26):
                for b in range(-25, 26):
                    with self.subTest(lang=lang, a=a, b=b):
                        self.assertEqual(gcd(a, b), brute_gcd(a, b))
                        self.assertEqual(gcd(a, b), math.gcd(a, b))
                        g, x, y = coeff(a, b)
                        self.assertEqual(g, gcd(a, b))
                        self.assertEqual(a*x + b*y, g)
                        reference_lcm = 0 if not a or not b else abs(a*b)//g
                        self.assertEqual(lcm(a, b), reference_lcm)
            for invalid in ((True, 3), (3, 1.0), ("3", 4)):
                with self.assertRaises(TypeError):
                    gcd(*invalid)
                with self.assertRaises(TypeError):
                    coeff(*invalid)

    def test_inverse_and_fast_power_against_python_builtins(self):
        for lang in ("en", "pt"):
            ns = load_example(lang, "modular-arithmetic-inverses-exponentiation")
            inverse, power = ns["mod_inverse"], ns["modular_power"]
            for modulus in range(2, 21):
                for base in range(-20, 21):
                    with self.subTest(lang=lang, mod=modulus, base=base):
                        if math.gcd(base, modulus) == 1:
                            self.assertEqual(inverse(base, modulus),
                                             pow(base, -1, modulus))
                        else:
                            with self.assertRaises(ValueError):
                                inverse(base, modulus)
                    for exponent in range(0, 21):
                        self.assertEqual(power(base, exponent, modulus),
                                         pow(base, exponent, modulus))
            for invalid in ((1, 0, 0), (1, -1, 7), (1, 3, 1),
                            (1, 3, True), (1.0, 3, 7), (2, False, 7)):
                with self.assertRaises(ValueError):
                    power(*invalid)
            for invalid in ((3, 1), (3, 0), (True, 11), (1.0, 11)):
                with self.assertRaises(ValueError):
                    inverse(*invalid)

    def test_mathematical_prerequisite_order(self):
        modules = load_modules()
        for slug in ("number-theory-divisibility-euclid",
                     "modular-arithmetic-inverses-exponentiation"):
            self.assertEqual(modules[slug], "foundations")
        articles = load_articles()
        for slug in ("number-theory-divisibility-euclid",
                     "modular-arithmetic-inverses-exponentiation"):
            self.assertEqual(articles["en"][slug]["meta"]["prerequisites"],
                             articles["pt"][slug]["meta"]["prerequisites"])
        for track in load_tracks()[:2]:
            slugs = [slug for section in track["sections"] for slug in section["articles"]]
            self.assertLess(slugs.index("logic-proofs-invariants"),
                            slugs.index("number-theory-divisibility-euclid"))
            self.assertLess(slugs.index("complexity-analysis"),
                            slugs.index("number-theory-divisibility-euclid"))
            self.assertLess(slugs.index("number-theory-divisibility-euclid"),
                            slugs.index("modular-arithmetic-inverses-exponentiation"))
            self.assertLess(slugs.index("modular-arithmetic-inverses-exponentiation"),
                            slugs.index("algorithmic-problem-solving-method"))
            self.assertEqual(len(slugs), len(set(slugs)))

if __name__ == "__main__":
    unittest.main()
