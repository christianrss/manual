"""Independent contract checks for type representation and ADT invariants."""
from itertools import product
from pathlib import Path
import re
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks

PYTHON_FENCES = re.compile(r"(?ms)^~~~python[^\n]*\n(.*?)^~~~[ \t]*$")

def run_article(lang, slug):
    source = (ROOT / "content" / lang / "topics" / (slug + ".md")).read_text(encoding="utf-8")
    blocks = PYTHON_FENCES.findall(source)
    if not blocks:
        raise AssertionError("missing runnable code for " + slug)
    name = "standalone_" + lang + "_" + slug.replace("-", "_")
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        for block in blocks:
            exec(compile(block, name, "exec"), module.__dict__)
        return dict(module.__dict__)
    finally:
        sys.modules.pop(name, None)

class FoundationsRepresentationTests(unittest.TestCase):
    def test_all_record_values_round_trip(self):
        for lang in ("en", "pt"):
            funcs = run_article(lang, "data-types-bytes-and-representation")
            encode, decode = funcs["encode_record"], funcs["decode_record"]
            for label in ("a", "Ação", "☃", "e\u0301", "x" * 255):
                for count in (0, 1, 255, 256, 513, 65535):
                    with self.subTest(lang=lang, label=label[:8], count=count):
                        wire = encode(label, count)
                        self.assertEqual(wire[0], len(label.encode("utf-8")))
                        self.assertEqual(len(wire), 1 + wire[0] + 2)
                        self.assertEqual(decode(wire), (label, count))
            for invalid in (b"", b"\x00\x00\x00", b"\x01\xff\x00\x00",
                            b"\x01A\x01", b"\x01A\x01\x00\xff"):
                with self.subTest(lang=lang, invalid=invalid), self.assertRaises(ValueError):
                    decode(invalid)
            for bad in (True, -1, 65536, 1.5):
                with self.assertRaises(ValueError):
                    encode("item", bad)
            with self.assertRaises(ValueError):
                encode("é" * 128, 1)  # 128 code points but 256 UTF-8 bytes
            with self.assertRaises(ValueError):
                encode(" ", 1)

    def test_queue_against_independent_fifo_reference(self):
        actions = ("enq-a", "enq-none", "deq", "peek")
        for lang in ("en", "pt"):
            Queue = run_article(lang, "abstract-data-types-representation-invariants")["BoundedQueue"]
            for capacity in (1, 2, 3):
                for steps in range(6):
                    for sequence in product(actions, repeat=steps):
                        queue, expected = Queue(capacity), []
                        for action in sequence:
                            previous = tuple(expected)
                            if action.startswith("enq"):
                                value = "A" if action == "enq-a" else None
                                if len(expected) == capacity:
                                    with self.assertRaises(OverflowError):
                                        queue.enqueue(value)
                                else:
                                    expected.append(value)
                                    self.assertIsNone(queue.enqueue(value))
                            elif action == "deq":
                                if expected:
                                    self.assertEqual(queue.dequeue(), expected.pop(0))
                                else:
                                    with self.assertRaises(IndexError):
                                        queue.dequeue()
                            else:
                                if expected:
                                    self.assertEqual(queue.peek(), expected[0])
                                else:
                                    with self.assertRaises(IndexError):
                                        queue.peek()
                            with self.subTest(lang=lang, capacity=capacity, sequence=sequence,
                                              step=action, before=previous):
                                self.assertEqual(len(queue), len(expected))
                                self.assertEqual(queue.snapshot(), tuple(expected))
                                self.assertGreaterEqual(queue._head, 0)
                                self.assertLess(queue._head, capacity)
                                self.assertGreaterEqual(queue._size, 0)
                                self.assertLessEqual(queue._size, capacity)
            for bad_capacity in (0, -1, True, 1.5):
                with self.assertRaises(ValueError):
                    Queue(bad_capacity)

    def test_foundations_before_dependent_chapters(self):
        modules = load_modules()
        self.assertEqual(modules["data-types-bytes-and-representation"], "foundations")
        self.assertEqual(modules["abstract-data-types-representation-invariants"], "algorithms")
        chapters = load_articles()
        for lang in ("en", "pt"):
            self.assertEqual(chapters[lang]["data-types-bytes-and-representation"]["meta"]["prerequisites"],
                             ["programming-control-flow-functions"])
            self.assertEqual(chapters[lang]["abstract-data-types-representation-invariants"]["meta"]["prerequisites"],
                             ["data-types-bytes-and-representation", "arrays-and-strings", "complexity-analysis"])
        for track in load_tracks()[:2]:
            ids = [name for section in track["sections"] for name in section["articles"]]
            self.assertLess(ids.index("programming-control-flow-functions"),
                            ids.index("data-types-bytes-and-representation"))
            self.assertLess(ids.index("data-types-bytes-and-representation"),
                            ids.index("programming-semantics-contracts"))
            self.assertLess(ids.index("arrays-and-strings"),
                            ids.index("abstract-data-types-representation-invariants"))
            self.assertLess(ids.index("abstract-data-types-representation-invariants"),
                            ids.index("stacks-queues"))

if __name__ == "__main__":
    unittest.main()
