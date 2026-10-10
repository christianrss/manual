"""Independent finite oracles for PT/EN descriptor and abstract fsync models.

Reference descriptors use numeric OPEN-DESCRIPTION IDs and immutable bytes,
unlike the article's mutable description objects and bytearray files.
Neither reference is a real OS or filesystem durability test.
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
    mod = types.ModuleType("_file_descriptors_" + lang)
    sys.modules[mod.__name__] = mod
    try:
        article = load_articles()[lang]["file-descriptors-buffering-fsync"]["body"]
        for number, match in enumerate(FENCE.finditer(article), 1):
            exec(compile(match["code"], f"{lang}/files/fence-{number}", "exec"),
                 mod.__dict__, mod.__dict__)
    finally:
        sys.modules.pop(mod.__name__, None)
    return mod

class IndependentDescriptorOracle:
    def __init__(self, content):
        self.content = dict(content)
        self.fds = {}
        self.descriptions = {}  # id -> [path, offset], never Python object aliasing
        self.next_description_id = 0

    def _id(self, fd):
        if type(fd) is not int or fd not in self.fds:
            raise KeyError(fd)
        return self.fds[fd]

    def _fd(self):
        result = 0
        while result in self.fds:
            result += 1
        return result

    def open(self, path):
        if path not in self.content:
            raise FileNotFoundError(path)
        fd = self._fd()
        ident = self.next_description_id
        self.next_description_id += 1
        self.descriptions[ident] = [path, 0]
        self.fds[fd] = ident
        return fd

    def dup(self, fd):
        ident = self._id(fd)
        new_fd = self._fd()
        self.fds[new_fd] = ident
        return new_fd

    def close(self, fd):
        self._id(fd)
        del self.fds[fd]

    def seek(self, fd, offset):
        ident = self._id(fd)
        if type(offset) is not int or offset < 0:
            raise ValueError("bad offset")
        self.descriptions[ident][1] = offset

    def tell(self, fd):
        return self.descriptions[self._id(fd)][1]

    def read(self, fd, count):
        ident = self._id(fd)
        if type(count) is not int or count < 0:
            raise ValueError("bad count")
        path, offset = self.descriptions[ident]
        output = self.content[path][offset:offset + count]
        self.descriptions[ident][1] += len(output)
        return output

    def write(self, fd, payload):
        ident = self._id(fd)
        if type(payload) is not bytes:
            raise ValueError("bad bytes")
        if not payload:
            return 0
        path, offset = self.descriptions[ident]
        before = self.content[path]
        if offset > len(before):
            before = before + bytes(offset - len(before))
        new_end = offset + len(payload)
        after = before[:offset] + payload + before[new_end:]
        self.content[path] = after
        self.descriptions[ident][1] = new_end
        return len(payload)

    def snapshot(self, path):
        return self.content[path]

ACTIONS = (
    ("open", ("f",)),
    ("dup", (0,)),
    ("dup", (1,)),
    ("read", (0, 2)),
    ("read", (1, 1)),
    ("write", (0, b"Z")),
    ("write", (1, b"")),
    ("seek", (1, 5)),
    ("close", (0,)),
    ("close", (1,)),
)

def apply(target, operation):
    name, args = operation
    return getattr(target, name)(*args)

def assert_equivalent(test, actual, oracle):
    test.assertEqual(actual.snapshot("f"), oracle.snapshot("f"))
    test.assertEqual(set(actual.descriptors), set(oracle.fds))
    for fd in oracle.fds:
        test.assertEqual(actual.tell(fd), oracle.tell(fd), fd)
    for first, second in itertools.product(oracle.fds, repeat=2):
        test.assertEqual(
            actual.descriptors[first] is actual.descriptors[second],
            oracle.fds[first] == oracle.fds[second],
            (first, second),
        )

class FileDescriptorContracts(unittest.TestCase):
    def test_exhaustive_finite_fd_operation_sequences(self):
        for lang in ("en", "pt"):
            mod = chapter(lang)
            cases = 0
            for length in range(5):
                for operations in itertools.product(ACTIONS, repeat=length):
                    implementation = mod.DescriptorModel({"f": b"ABC"})
                    oracle = IndependentDescriptorOracle({"f": b"ABC"})
                    for operation in operations:
                        try:
                            expected = apply(oracle, operation)
                        except (KeyError, ValueError, FileNotFoundError) as err:
                            with self.assertRaises(type(err)):
                                apply(implementation, operation)
                        else:
                            actual = apply(implementation, operation)
                            self.assertEqual(actual, expected,
                                             (lang, operations))
                        assert_equivalent(self, implementation, oracle)
                    cases += 1
            self.assertEqual(cases, sum(10 ** n for n in range(5)))

    def test_edge_cases_not_in_small_exhaustion(self):
        for lang in ("en", "pt"):
            mod = chapter(lang)
            for initial in ({"f": bytearray(b"A")}, {"f": "text"}, {"": b"A"}, []):
                with self.assertRaises(ValueError):
                    mod.DescriptorModel(initial)
            machine = mod.DescriptorModel({"f": b"AB", "g": b"xyz"})
            first = machine.open("f")
            copy = machine.dup(first)
            separate = machine.open("f")
            self.assertEqual(machine.read(first, 1), b"A")
            self.assertEqual(machine.tell(copy), 1)
            self.assertEqual(machine.tell(separate), 0)
            for fd in (True, -1, 99, 1.0):
                with self.assertRaises(KeyError):
                    machine.read(fd, 1)
            for invalid in (-1, True, 1.0):
                with self.assertRaises(ValueError):
                    machine.read(first, invalid)
                with self.assertRaises(ValueError):
                    machine.seek(first, invalid)
            with self.assertRaises(ValueError):
                machine.write(first, bytearray(b"data"))
            with self.assertRaises(FileNotFoundError):
                machine.open("unknown")
            machine.seek(copy, 5)
            snapshot = machine.snapshot("f")
            offset = machine.tell(first)
            self.assertEqual(machine.write(first, b""), 0)
            self.assertEqual((machine.snapshot("f"), machine.tell(copy)),
                             (snapshot, offset))
            machine.write(copy, b"Q")
            self.assertEqual(machine.snapshot("f"), b"AB" + bytes(3) + b"Q")
            machine.close(first)
            self.assertEqual(machine.tell(copy), 6)
            machine.close(copy)
            self.assertEqual(machine.open("g"), 0)

    def test_independent_abstract_sync_crash_sequences(self):
        actions = (("append", b"A"), ("append", b"B"),
                   ("fsync", None), ("crash", None))
        for lang in ("en", "pt"):
            cls = chapter(lang).CrashSnapshot
            count = 0
            for length in range(7):
                for events in itertools.product(actions, repeat=length):
                    model = cls(b"X")
                    visible = synced = b"X"
                    for op, value in events:
                        if op == "append":
                            visible += value
                            model.append(value)
                        elif op == "fsync":
                            synced = visible
                            model.fsync()
                        else:
                            visible = synced
                            model.crash()
                        self.assertEqual(model.read(), visible,
                                         (lang, events))
                        self.assertEqual(model.durable_read(), synced,
                                         (lang, events))
                    count += 1
            self.assertEqual(count, sum(4 ** n for n in range(7)))
            model = cls(b"A")
            with self.assertRaises(ValueError):
                model.append("not bytes")
            self.assertEqual((model.read(), model.durable_read()), (b"A", b"A"))
            with self.assertRaises(ValueError):
                cls(bytearray(b"bad"))

if __name__ == "__main__":
    unittest.main()
