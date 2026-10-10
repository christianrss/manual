"""Independent finite oracles for PT/EN inode/block and metadata redo examples.

The namespace oracle stores name->(inode_id, immutable bytes) and calculates
block demand from file lengths; it does not share the article's slots/inodes
allocation algorithm. The journal oracle calculates final dictionaries from
staged records, without calling the article's replay algorithm.
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

def chapter(lang):
    module = types.ModuleType("_filesystem_" + lang)
    sys.modules[module.__name__] = module
    try:
        body = load_articles()[lang]["inode-directories-journaling-recovery"]["body"]
        matches = tuple(FENCE.finditer(body))
        if len(matches) != 2:
            raise AssertionError("expected independent filesystem and journal examples")
        for n, match in enumerate(matches, 1):
            exec(compile(match["code"], f"{lang}/filesystem/fence-{n}", "exec"),
                 module.__dict__, module.__dict__)
    finally:
        sys.modules.pop(module.__name__, None)
    return module

def blocks_needed(data, block_size):
    return (len(data) + block_size - 1) // block_size

class IndependentNamespace:
    def __init__(self, capacity, block_size):
        self.capacity = capacity
        self.block_size = block_size
        self.files = {}
        self.next_inode = 1

    def create(self, name):
        if name in self.files:
            raise FileExistsError(name)
        inode = self.next_inode
        self.next_inode += 1
        self.files[name] = (inode, b"")
        return inode

    def append(self, name, payload):
        if name not in self.files:
            raise KeyError(name)
        inode, before = self.files[name]
        after = before + payload
        others = sum(blocks_needed(data, self.block_size)
                     for other, (_, data) in self.files.items() if other != name)
        if others + blocks_needed(after, self.block_size) > self.capacity:
            return False
        self.files[name] = (inode, after)
        return True

    def read(self, name):
        if name not in self.files:
            raise KeyError(name)
        return self.files[name][1]

    def rename(self, old, new):
        if old not in self.files:
            raise KeyError(old)
        if new in self.files:
            raise FileExistsError(new)
        self.files[new] = self.files.pop(old)

    def unlink(self, name):
        if name not in self.files:
            raise KeyError(name)
        del self.files[name]

    def usage(self):
        count = sum(blocks_needed(data, self.block_size)
                    for _, data in self.files.values())
        return (count, self.capacity - count)

def snapshot(fs):
    return (
        tuple(fs.slots),
        tuple(sorted(fs.directory.items())),
        tuple(sorted((ident, inode["size"], tuple(inode["blocks"]))
                     for ident, inode in fs.inodes.items())),
        fs.next_inode,
    )

def verify_fs(test, actual, ref):
    test.assertEqual(actual.usage(), ref.usage())
    test.assertEqual(set(actual.directory), set(ref.files))
    test.assertEqual(set(actual.inodes), {id for id, _ in ref.files.values()})
    all_referenced = []
    for name, (inode_id, content) in ref.files.items():
        test.assertEqual(actual.directory[name], inode_id)
        test.assertEqual(actual.read(name), content)
        inode = actual.inodes[inode_id]
        test.assertEqual(inode["size"], len(content))
        test.assertEqual(len(inode["blocks"]),
                         blocks_needed(content, actual.block_size))
        for block_id in inode["blocks"]:
            test.assertTrue(0 <= block_id < len(actual.slots))
            all_referenced.append(block_id)
            test.assertIsNotNone(actual.slots[block_id])
            test.assertEqual(len(actual.slots[block_id]), actual.block_size)
    test.assertEqual(len(all_referenced), len(set(all_referenced)))
    test.assertEqual(set(all_referenced),
                     {index for index, data in enumerate(actual.slots)
                      if data is not None})

ACTIONS = (
    ("create", ("a",)),
    ("create", ("b",)),
    ("append", ("a", b"A")),
    ("append", ("a", b"XYZ")),
    ("append", ("b", b"Q")),
    ("rename", ("a", "c")),
    ("unlink", ("a",)),
    ("unlink", ("b",)),
)

def invoke(machine, op):
    name, args = op
    return getattr(machine, name)(*args)

class FilesystemInodeContracts(unittest.TestCase):
    def test_finite_exhaustive_namespace_operation_sequences(self):
        for lang in ("en", "pt"):
            cls = chapter(lang).TinyBlockFS
            count = 0
            for size in (2, 3):
                for n in range(5):
                    for actions in itertools.product(ACTIONS, repeat=n):
                        actual = cls(3, size)
                        reference = IndependentNamespace(3, size)
                        for action in actions:
                            before = snapshot(actual)
                            try:
                                expected = invoke(reference, action)
                            except (KeyError, FileExistsError) as exc:
                                with self.assertRaises(type(exc)):
                                    invoke(actual, action)
                                self.assertEqual(snapshot(actual), before)
                            else:
                                result = invoke(actual, action)
                                self.assertEqual(result, expected,
                                                 (lang, size, actions))
                                if result is False:
                                    self.assertEqual(snapshot(actual), before)
                            verify_fs(self, actual, reference)
                        count += 1
            self.assertEqual(count, 2 * sum(8 ** n for n in range(5)))

    def test_capacity_and_invalid_names(self):
        for lang in ("en", "pt"):
            cls = chapter(lang).TinyBlockFS
            for bad in ((0, 4), (4, 0), (True, 4), (4, 1.5)):
                with self.assertRaises(ValueError):
                    cls(*bad)
            machine = cls(4, 4)
            for name in ("", " ", " a ", "a/b", ".", "..", 5):
                with self.assertRaises(ValueError):
                    machine.create(name)
            self.assertEqual(machine.create("a"), 1)
            for invalid in ("raw text", bytearray(b"oops"), None):
                before = snapshot(machine)
                with self.assertRaises(ValueError):
                    machine.append("a", invalid)
                self.assertEqual(snapshot(machine), before)
            self.assertTrue(machine.append("a", b""))
            machine.create("b")
            self.assertTrue(machine.append("a", b"abcdefghij"))
            self.assertTrue(machine.append("b", b"1234"))
            before = snapshot(machine)
            self.assertFalse(machine.append("b", b"5"))
            self.assertEqual(snapshot(machine), before)
            machine.unlink("a")
            self.assertTrue(machine.append("b", b"5"))
            ident = machine.directory["b"]
            machine.rename("b", "c")
            self.assertEqual(machine.directory["c"], ident)
            with self.assertRaises(FileExistsError):
                machine.rename("c", "c")
            with self.assertRaises(KeyError):
                machine.unlink("missing")

class MetadataJournalContracts(unittest.TestCase):
    def test_all_small_transaction_payloads_and_crash_windows(self):
        # Every 1..3 record list over two keys and three integer values.
        # Independently build final expected dictionary in record order.
        possibilities = tuple(itertools.product(("size", "used"), range(3)))
        initial = {"size": 0, "used": 0}
        for lang in ("en", "pt"):
            cls = chapter(lang).MetadataRedoLog
            checked = 0
            for count in range(1, 4):
                for records in itertools.product(possibilities, repeat=count):
                    oracle = dict(initial)
                    for key, value in records:
                        oracle[key] = value
                    # Before marker: no home writes are permitted.
                    before = cls(initial)
                    for key, value in records:
                        before.stage(key, value)
                    with self.assertRaises(RuntimeError):
                        before.install_one()
                    before.recover()
                    self.assertEqual(before.home, initial)
                    self.assertEqual(before.records, [])
                    # After marker: replay must be complete after ANY prefix.
                    for installed in range(count + 1):
                        candidate = cls(initial)
                        for key, value in records:
                            candidate.stage(key, value)
                        candidate.commit()
                        for _ in range(installed):
                            self.assertTrue(candidate.install_one())
                        if installed != count:
                            with self.assertRaises(RuntimeError):
                                candidate.finish()
                        candidate.recover()
                        self.assertEqual(candidate.home, oracle,
                                         (lang, records, installed))
                        self.assertEqual(candidate.records, [])
                        candidate.recover()
                        self.assertEqual(candidate.home, oracle)
                    # A completed checkpoint is retained after a new crash.
                    checkpoint = cls(initial)
                    for key, value in records:
                        checkpoint.stage(key, value)
                    checkpoint.commit()
                    for _ in records:
                        checkpoint.install_one()
                    self.assertFalse(checkpoint.install_one())
                    checkpoint.finish()
                    checkpoint.recover()
                    self.assertEqual(checkpoint.home, oracle)
                    checked += 1
            self.assertEqual(checked, sum(6 ** n for n in range(1, 4)))

    def test_transaction_validation_and_after_commit_rejection(self):
        for lang in ("en", "pt"):
            cls = chapter(lang).MetadataRedoLog
            for initial in ({"a": True}, {"a": -1}, {"": 1}, [], {"a": 1.5}):
                with self.assertRaises(ValueError):
                    cls(initial)
            txn = cls({"a": 1})
            with self.assertRaises(RuntimeError):
                txn.commit()
            with self.assertRaises(RuntimeError):
                txn.finish()
            for key, value in (("", 3), ("b", -1), ("b", True)):
                with self.assertRaises(ValueError):
                    txn.stage(key, value)
            self.assertEqual(txn.records, [])
            txn.stage("a", 2)
            txn.commit()
            with self.assertRaises(RuntimeError):
                txn.stage("a", 3)
            with self.assertRaises(RuntimeError):
                txn.commit()
            self.assertTrue(txn.install_one())
            txn.finish()
            self.assertEqual(txn.home, {"a": 2})

if __name__ == "__main__":
    unittest.main()
