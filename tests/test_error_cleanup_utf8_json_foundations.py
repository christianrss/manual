"""Independent contract checks for exception cleanup and bounded JSON/UTF-8 I/O."""
from io import StringIO
from pathlib import Path
import itertools
import json
import re
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks

FENCES = re.compile(r"(?ms)^~~~python[^\n]*\n(.*?)^~~~[ \t]*$")

def load_example(lang, topic):
    path = ROOT / "content" / lang / "topics" / (topic + ".md")
    fragments = FENCES.findall(path.read_text(encoding="utf-8"))
    if not fragments:
        raise AssertionError(f"Missing Python code: {lang} {topic}")
    name = f"_manual_{lang}_{topic.replace('-', '_')}"
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        for fragment in fragments:
            exec(compile(fragment, str(path), "exec"), module.__dict__)
        return module.__dict__
    finally:
        sys.modules.pop(name, None)

class ErrorCleanupTests(unittest.TestCase):
    def test_parser_against_explicit_integer_contract(self):
        for lang in ("en", "pt"):
            env = load_example(lang, "python-error-contracts-resource-cleanup")
            parse = env["parse_count"]
            Error = env["RecordError"]
            for number in range(1001):
                self.assertEqual(parse(str(number)), number)
            for item in ("", "00", "01", "1.0", " 1", "+1", "-1", "1001",
                         "９", "٢", "1a", "0000", "10000", "1\n", "\x00", None,
                         1, True, 1.0):
                with self.subTest(lang=lang, item=item):
                    with self.assertRaises(Error):
                        parse(item)

    def test_cleanup_chaining_and_unrelated_failure(self):
        for lang in ("en", "pt"):
            env = load_example(lang, "python-error-contracts-resource-cleanup")
            Error = env["RecordError"]
            load = env["total_from_source"]
            opened = []
            def factory(data):
                def build():
                    stream = StringIO(data)
                    opened.append(stream)
                    return stream
                return build
            self.assertEqual(load(factory("3\r\n0\n999\n")), 1002)
            self.assertTrue(opened[-1].closed)
            self.assertEqual(load(factory("")), 0)
            self.assertTrue(opened[-1].closed)
            for text in ("4\n01\n", "1\n1001\n", "2\nx\n"):
                with self.assertRaises(Error) as caught:
                    load(factory(text))
                self.assertIn("line 2:", str(caught.exception))
                self.assertIsInstance(caught.exception.__cause__, Error)
                self.assertTrue(opened[-1].closed)
            class Failing:
                closed = False
                def __enter__(self): return self
                def __exit__(self, typ, exc, tb):
                    self.closed = True
                    return False
                def __iter__(self):
                    yield "1\n"
                    raise OSError("read failed")
            resource = Failing()
            with self.assertRaisesRegex(OSError, "read failed"):
                load(lambda: resource)
            self.assertTrue(resource.closed)

class JsonBoundedFileTests(unittest.TestCase):
    def test_schema_and_roundtrip(self):
        for lang in ("en", "pt"):
            env = load_example(lang, "python-files-utf8-json-validation")
            check = env["validate_document"]
            read = env["read_document"]
            write = env["write_document"]
            for records in ([], [{"id": "a-1", "count": 0}],
                            [{"id": "abc_12", "count": 1000},
                             {"id": "z-9", "count": 12}]):
                data = {"version": 1, "records": records}
                self.assertEqual(check(data), data)
                with tempfile.TemporaryDirectory() as folder:
                    file = Path(folder) / "data.json"
                    write(file, data)
                    self.assertEqual(read(file), data)
                    self.assertTrue(file.read_bytes().endswith(b"\n"))
                    self.assertLessEqual(len(file.read_bytes()), env["MAX_BYTES"])

    def test_invalid_inputs_do_not_replace_existing_file(self):
        for lang in ("en", "pt"):
            env = load_example(lang, "python-files-utf8-json-validation")
            Error, write = env["DocumentError"], env["write_document"]
            with tempfile.TemporaryDirectory() as folder:
                file = Path(folder) / "record.json"
                original = b"unchanged sentinel bytes"
                file.write_bytes(original)
                bad = [
                    {"version": True, "records": []},
                    {"version": 2, "records": []},
                    {"version": 1, "records": [{"id": "hello", "count": True}]},
                    {"version": 1, "records": [{"id": "upper", "count": -1}]},
                    {"version": 1, "records": [{"id": "UPPER", "count": 5}]},
                    {"version": 1, "records": [{"id": "a", "count": 1001}]},
                    {"version": 1, "records": [{"id": "same", "count": 1},
                                              {"id": "same", "count": 2}]},
                    {"version": 1, "records": [{"id": "", "count": 1}]},
                    {"version": 1, "records": [{"id": "x", "count": 1, "extra": 2}]},
                    {"version": 1, "records": "invalid"},
                    {"version": 1, "records": [] , "unknown": 1},
                    {"version": 1, "records": [{"id": "a", "count": 1}] * 101},
                ]
                for doc in bad:
                    with self.subTest(lang=lang, data=str(doc)[:75]):
                        with self.assertRaises(Error):
                            write(file, doc)
                        self.assertEqual(file.read_bytes(), original)

    def test_reject_noncanonical_json_and_bounded_input(self):
        for lang in ("en", "pt"):
            env = load_example(lang, "python-files-utf8-json-validation")
            Error, read = env["DocumentError"], env["read_document"]
            invalid = (
                b'{"version":1,"version":1,"records":[]}',
                b'{"version":1,"records":[{"id":"x","id":"x","count":0}]}',
                b'{"version":1,"records":[{"id":"x","count":NaN}]}',
                b'{"version":1,"records":[{"id":"x","count":Infinity}]}',
                b'{"version":1,"records":[{"id":"x","count":true}]}',
                b'{"version":1,"records":[],"extra":1}',
                b'{"version":1,"records":[]',
                b'\xff\xfe',
                b'\xef\xbb\xbf{"version":1,"records":[]}',
                b' ' * (env["MAX_BYTES"] + 1),
            )
            with tempfile.TemporaryDirectory() as folder:
                file = Path(folder) / "invalid.json"
                for blob in invalid:
                    with self.subTest(lang=lang, blob=blob[:40]):
                        file.write_bytes(blob)
                        with self.assertRaises(Error):
                            read(file)

class TeachingSequenceTests(unittest.TestCase):
    def test_bilingual_parity_and_prerequisite_order(self):
        modules = load_modules()
        articles = load_articles()
        topics = ("python-error-contracts-resource-cleanup",
                  "python-files-utf8-json-validation")
        for topic in topics:
            self.assertEqual(modules[topic], "foundations")
            self.assertEqual(articles["en"][topic]["meta"]["prerequisites"],
                             articles["pt"][topic]["meta"]["prerequisites"])
        for track in load_tracks()[:2]:
            ids = [slug for section in track["sections"] for slug in section["articles"]]
            for earlier, later in (
                ("programming-semantics-contracts", topics[0]),
                ("modular-programming-interfaces", topics[0]),
                ("data-types-bytes-and-representation", topics[1]),
                (topics[0], topics[1]),
                (topics[1], "testing-maintainability"),
            ):
                self.assertLess(ids.index(earlier), ids.index(later))
            self.assertEqual(len(ids), len(set(ids)))

if __name__ == "__main__":
    unittest.main()
