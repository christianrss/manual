"""Executable independent contract checks for sequential state and C pointer foundations."""
from itertools import product
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks

PYTHON = re.compile(r"(?ms)^~~~python[^\n]*\n(.*?)^~~~[ \t]*$")
C_SNIPPET = re.compile(r"(?ms)^~~~c[^\n]*\n(.*?)^~~~[ \t]*$")

def chapter(lang, slug):
    return (ROOT / "content" / lang / "topics" / (slug + ".md")).read_text(encoding="utf-8")

def python_example(lang, slug):
    matches = PYTHON.findall(chapter(lang, slug))
    if not matches:
        raise AssertionError("missing executable Python example")
    name = "foundation_" + lang + "_" + slug.replace("-", "_")
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        for snippet in matches:
            exec(compile(snippet, name, "exec"), module.__dict__)
        return module.__dict__
    finally:
        sys.modules.pop(name, None)

class BasicHardwareLanguageTests(unittest.TestCase):
    def test_register_edge_and_counter_truth_table(self):
        for lang in ("en", "pt"):
            ns = python_example(lang, "sequential-logic-registers-state-machines")
            Register = ns["ClockedRegister"]
            counter = ns["counter_tick"]
            for width in range(1, 5):
                reg = Register(width)
                self.assertEqual(reg.read(), (0,) * width)
                for bits in product((0, 1), repeat=width):
                    old = reg.read()
                    self.assertEqual(reg.tick(bits, False), old)
                    self.assertEqual(reg.read(), old)
                    self.assertEqual(reg.tick(bits, True), bits)
                    self.assertEqual(reg.read(), bits)
                old = reg.read()
                invalid = (0,) * (width - 1) + (2,)
                with self.assertRaises(ValueError):
                    reg.tick(invalid, True)
                self.assertEqual(reg.read(), old)
                with self.assertRaises(ValueError):
                    reg.tick((0,) * (width - 1), False)
                self.assertEqual(reg.read(), old)
                for state in range(1 << width):
                    for reset, enable in product((False, True), repeat=2):
                        expected = 0 if reset else ((state + 1) % (1 << width)
                                                     if enable else state)
                        with self.subTest(lang=lang, width=width, state=state,
                                          reset=reset, enable=enable):
                            self.assertEqual(counter(state, width, reset, enable),
                                             expected)
            for bad in ((0, 1, False, False), (1, 1, 0, False),
                        (-1, 1, False, False), (0, 2, True, 1)):
                with self.assertRaises(ValueError):
                    counter(*bad)
            with self.assertRaises(ValueError):
                Register(True)

    def test_c11_pointer_example_compiles_and_runs(self):
        compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if compiler is None:
            self.skipTest("C11 compiler not available")
        for lang in ("en", "pt"):
            matches = C_SNIPPET.findall(chapter(lang, "c-pointers-arrays-object-lifetimes"))
            self.assertEqual(len(matches), 1)
            with tempfile.TemporaryDirectory() as tmp:
                src = Path(tmp) / "example.c"
                binary = Path(tmp) / "example"
                src.write_text(matches[0], encoding="utf-8")
                built = subprocess.run(
                    [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                     "-pedantic", str(src), "-o", str(binary)],
                    text=True, capture_output=True, timeout=15, check=False
                )
                self.assertEqual(built.returncode, 0, built.stderr)
                executed = subprocess.run(
                    [str(binary)], text=True, capture_output=True, timeout=15,
                    check=False
                )
                self.assertEqual(executed.returncode, 0, executed.stderr)
                self.assertEqual(executed.stdout, "sum=24\n")

    def test_bilingual_placement_and_prerequisites(self):
        modules = load_modules()
        self.assertEqual(modules["sequential-logic-registers-state-machines"],
                         "computer-architecture")
        self.assertEqual(modules["c-pointers-arrays-object-lifetimes"], "foundations")
        chapters = load_articles()
        for slug in ("sequential-logic-registers-state-machines",
                     "c-pointers-arrays-object-lifetimes"):
            self.assertEqual(chapters["en"][slug]["meta"]["prerequisites"],
                             chapters["pt"][slug]["meta"]["prerequisites"])
        for track in load_tracks()[:2]:
            titles = [x for sec in track["sections"] for x in sec["articles"]]
            for left, right in (
                ("digital-logic-gates-binary-adders",
                 "sequential-logic-registers-state-machines"),
                ("sequential-logic-registers-state-machines",
                 "machine-representation-isa-cache"),
                ("program-memory-references-lifetimes",
                 "c-pointers-arrays-object-lifetimes"),
                ("c-pointers-arrays-object-lifetimes", "heap-allocation-fragmentation"),
            ):
                self.assertLess(titles.index(left), titles.index(right))
            self.assertEqual(len(titles), len(set(titles)))

if __name__ == "__main__":
    unittest.main()
