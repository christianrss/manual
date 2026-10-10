"""Independent bitmap-owner oracle for both published heap allocator variants.

No free-list algorithm from the article is reused by this reference model.
We compare all observable allocation addresses, canonical free spans, allocated
ranges and per-operation state preservation across finite action sequences.
"""
import itertools
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

FENCE = re.compile(r"(?ms)^(?P<fence>\x60{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def published(lang):
    mod = types.ModuleType("_heap_allocation_" + lang)
    sys.modules[mod.__name__] = mod
    try:
        body = load_articles()[lang]["heap-allocation-fragmentation"]["body"]
        for number, match in enumerate(FENCE.finditer(body), 1):
            exec(compile(match["code"], f"{lang}/heap/fence-{number}", "exec"),
                 mod.__dict__, mod.__dict__)
    finally:
        sys.modules.pop(mod.__name__, None)
    return mod

class BitmapReference:
    def __init__(self, size, policy):
        self.slots = [None] * size
        self.live = {}
        self.policy = policy

    def free_spans(self):
        result = []
        start = None
        for index in range(len(self.slots) + 1):
            vacant = index < len(self.slots) and self.slots[index] is None
            if vacant and start is None:
                start = index
            if not vacant and start is not None:
                result.append((start, index - start))
                start = None
        return result

    def allocate(self, label, count):
        if label in self.live:
            raise ValueError("already allocated")
        spans = [(start, length) for start, length in self.free_spans()
                 if length >= count]
        if not spans:
            return None
        if self.policy == "first":
            start, _ = spans[0]
        else:
            start, _ = min(spans, key=lambda pair: (pair[1], pair[0]))
        for index in range(start, start + count):
            assert self.slots[index] is None
            self.slots[index] = label
        self.live[label] = (start, count)
        return start

    def release(self, label):
        if label not in self.live:
            raise KeyError(label)
        start, count = self.live.pop(label)
        for index in range(start, start + count):
            assert self.slots[index] == label
            self.slots[index] = None

ACTIONS = (
    ("alloc", "A", 2),
    ("alloc", "B", 3),
    ("alloc", "C", 1),
    ("alloc", "A", 4),
    ("free", "A", 0),
    ("free", "B", 0),
    ("alloc", "B", 2),
    ("free", "C", 0),
)

def apply_action(target, action):
    verb, label, amount = action
    return (target.allocate(label, amount) if verb == "alloc"
            else target.release(label))

def observed(target):
    return (tuple(target.free_blocks),
            tuple(sorted(target.allocated.items())),
            target.stats())

def oracle_observed(target):
    spans = tuple(target.free_spans())
    total = sum(length for _, length in spans)
    largest = max((length for _, length in spans), default=0)
    return (spans, tuple(sorted(target.live.items())),
            (total, largest, total - largest))

class HeapAllocatorContracts(unittest.TestCase):
    def test_all_short_operation_histories(self):
        # Exhaust all histories up to four actions from 8 distinct operations.
        # This covers double frees, duplicate handles, coalescing and failures.
        for lang in ("en", "pt"):
            mod = published(lang)
            examined = 0
            for policy in ("first", "best"):
                for length in range(5):
                    for operations in itertools.product(ACTIONS, repeat=length):
                        actual = mod.ArenaAllocator(8, policy)
                        expected = BitmapReference(8, policy)
                        for action in operations:
                            before = observed(actual)
                            try:
                                oracle_result = apply_action(expected, action)
                            except (KeyError, ValueError) as err:
                                with self.assertRaises(type(err)):
                                    apply_action(actual, action)
                                self.assertEqual(observed(actual), before)
                            else:
                                self.assertEqual(apply_action(actual, action),
                                                 oracle_result,
                                                 (lang, policy, operations))
                            self.assertEqual(observed(actual), oracle_observed(expected),
                                             (lang, policy, operations))
                        examined += 1
            self.assertEqual(examined, 2 * sum(8 ** n for n in range(5)))

    def test_fragmentation_and_policy_differences(self):
        for lang in ("en", "pt"):
            mod = published(lang)
            for policy, expected_position in (("first", 0), ("best", 9)):
                allocator = mod.ArenaAllocator(20, policy)
                for label, size in (("A", 7), ("B", 2), ("C", 5),
                                    ("D", 2), ("E", 4)):
                    allocator.allocate(label, size)
                allocator.release("A")
                allocator.release("C")
                self.assertEqual(allocator.stats(), (12, 7, 5))
                self.assertEqual(allocator.allocate("F", 4), expected_position)
            arena = mod.ArenaAllocator(16)
            for label in "ABCD":
                arena.allocate(label, 4)
            arena.release("A")
            arena.release("C")
            before = observed(arena)
            self.assertIsNone(arena.allocate("E", 5))
            self.assertEqual(observed(arena), before)
            arena.release("B")
            self.assertEqual(arena.free_blocks, [(0, 12)])
            self.assertEqual(arena.allocate("E", 8), 0)

    def test_invalid_arguments_and_rounding(self):
        for lang in ("en", "pt"):
            mod = published(lang)
            for capacity in (0, -1, True, 1.25):
                with self.assertRaises(ValueError):
                    mod.ArenaAllocator(capacity)
            with self.assertRaises(ValueError):
                mod.ArenaAllocator(5, "worst")
            arena = mod.ArenaAllocator(6)
            for bad in (0, -1, True, 1.5):
                with self.assertRaises(ValueError):
                    arena.allocate("Z", bad)
            for bad in ("", " A ", None):
                with self.assertRaises(ValueError):
                    arena.allocate(bad, 1)
            self.assertEqual(arena.stats(), (6, 6, 0))
            with self.assertRaises(KeyError):
                arena.release("unknown")
            for granularity in range(1, 13):
                for payload in range(1, 65):
                    rounded, unused = mod.rounded_reservation(payload, granularity)
                    self.assertTrue(payload <= rounded < payload + granularity)
                    self.assertEqual(rounded % granularity, 0)
                    self.assertEqual(rounded - payload, unused)
            for bad in ((0, 8), (3, 0), (True, 8), (4, True), (1.5, 2)):
                with self.assertRaises(ValueError):
                    mod.rounded_reservation(*bad)

if __name__ == "__main__":
    unittest.main()
