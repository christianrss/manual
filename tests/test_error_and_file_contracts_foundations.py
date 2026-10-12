"""Independent boundary checks for exception cleanup and validated UTF-8 JSON files."""
from pathlib import Path
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

def example(lang, slug):
    chapter = (ROOT / "content" / lang / "topics" / (slug + ".md")).read_text("utf8")
    snippets = FENCES.findall(chapter)
    if len(snippets) != 1:
        raise AssertionError("Expected one executable Python example")
    module = types.ModuleType("tutorial_" + lang + "_" + slug.replace("-", "_"))
    sys.modules[module.__name__] = module
    try:
        exec(compile(snippets[0], module.__name__, "exec"), module.__dict__)
        return module.__dict__
    finally:
        sys.modules.pop(module.__name__, None)

class ExceptionContractTests(unittest.TestCase):
    def test_canonical_input_and_exception_causes(self):
        for lang in ("en", "pt"):
            ns = example(lang, "python-error-contracts-resource-cleanup")
            parse = ns["parse_count"]
            RecordError = ns["RecordError"]
            for value, result in (("0", 0), ("7", 7), ("999", 999), ("1000", 1000)):
                self.assertEqual(parse(value), result)
            for bad in ("", "07", "000", "-1", "+1", "1001", "1.0",
                        "4 ", " 4", "١", "１２", 4, True, None):
                with self.subTest(lang=lang, bad=bad):
                    with self.assertRaises(RecordError):
                        parse(bad)
            with self.assertRaises(RecordError) as raised:
                ns["total_from_source"](lambda: ns["StringIO"]("3\n02\n"))
            self.assertIn("line 2", str(raised.exception))
            self.assertIsInstance(raised.exception.__cause__, RecordError)

    def test_context_exit_runs_for_success_and_failure(self):
        for lang in ("en", "pt"):
            ns = example(lang, "python-error-contracts-resource-cleanup")
            RecordError = ns["RecordError"]
            class Probe:
                def __init__(self, lines):
                    self.lines = lines
                    self.entered = 0
                    self.exited = 0
                    self.exception_type = None
                def __enter__(self):
                    self.entered += 1
                    return iter(self.lines)
                def __exit__(self, exc_type, exc, traceback):
                    self.exited += 1
                    self.exception_type = exc_type
                    return False
            good = Probe(["1\n", "2\n"])
            self.assertEqual(ns["total_from_source"](lambda: good), 3)
            self.assertEqual((good.entered, good.exited, good.exception_type),
                             (1, 1, None))
            bad = Probe(["1\n", "01\n"])
            with self.assertRaises(RecordError):
                ns["total_from_source"](lambda: bad)
            self.assertEqual((bad.entered, bad.exited), (1, 1))
            self.assertIs(bad.exception_type, RecordError)
            type_error = Probe([123])
            with self.assertRaises(TypeError):
                ns["total_from_source"](lambda: type_error)
            self.assertEqual(type_error.exited, 1)
            self.assertIs(type_error.exception_type, TypeError)
            class BrokenSource:
                def __enter__(self):
                    return self
                def __iter__(self):
                    raise OSError("read failed")
                def __exit__(self, *args):
                    return False
            with self.assertRaises(OSError):
                ns["total_from_source"](BrokenSource)

class FileFormatBoundaryTests(unittest.TestCase):
    def test_round_trip_and_deep_copy(self):
        for lang in ("en", "pt"):
            ns = example(lang, "python-files-utf8-json-validation")
            doc = {"version": 1, "records": [
                {"id": "a-1", "count": 7},
                {"id": "b_2", "count": 1000}]}
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "data.json"
                ns["write_document"](path, doc)
                self.assertEqual(ns["read_document"](path), doc)
                self.assertEqual(json.loads(path.read_text(encoding="utf8")), doc)
                loaded = ns["read_document"](path)
                self.assertIsNot(loaded, doc)
                self.assertIsNot(loaded["records"], doc["records"])
                loaded["records"][0]["count"] = 55
                self.assertEqual(doc["records"][0]["count"], 7)

    def test_invalid_files_rejected_without_laundering_io_errors(self):
        cases = (
            b'{"version":1,"version":1,"records":[]}',
            b'{"version":1,"records":[{"id":"a","count":true}]}',
            b'{"version":1,"records":[{"id":"a","count":NaN}]}',
            b'{"version":1,"records":[{"id":"a","count":1},{"id":"a","count":2}]}',
            b'{"version":1,"records":[],"extra":5}',
            b'{"version":2,"records":[]}',
            b'{"version":1,"records":[{"id":"Bad","count":1}]}',
            b'{"version":1,"records":[{"id":"a","count":1001}]}',
            b'{"version":1,"records":[]',
            b'\xff',
        )
        for lang in ("en", "pt"):
            ns = example(lang, "python-files-utf8-json-validation")
            Error = ns["DocumentError"]
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "data.json"
                for raw in cases:
                    with self.subTest(lang=lang, raw=raw[:45]):
                        path.write_bytes(raw)
                        with self.assertRaises(Error):
                            ns["read_document"](path)
                path.write_bytes(b"x" * (ns["MAX_BYTES"] + 1))
                with self.assertRaises(Error):
                    ns["read_document"](path)
                path.unlink()
                with self.assertRaises(OSError):
                    ns["read_document"](path)

    def test_invalid_document_does_not_truncate_existing_file(self):
        for lang in ("en", "pt"):
            ns = example(lang, "python-files-utf8-json-validation")
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "valid.json"
                path.write_bytes(b"existing data\n")
                for bad in (
                    {"version": 1, "records": [{"id": "x", "count": False}]},
                    {"version": 1, "records": [{"id": "x", "count": 1001}]},
                    {"version": 1, "records": [{"id": "x", "count": 1},
                                               {"id": "x", "count": 2}]},
                    {"version": 1, "records": [{}]},
                ):
                    with self.assertRaises(ns["DocumentError"]):
                        ns["write_document"](path, bad)
                    self.assertEqual(path.read_bytes(), b"existing data\n")

class CurriculumTests(unittest.TestCase):
    def test_pairing_and_track_order(self):
        modules = load_modules()
        chapters = load_articles()
        slugs = ("python-error-contracts-resource-cleanup",
                 "python-files-utf8-json-validation")
        for slug in slugs:
            self.assertEqual(modules[slug], "foundations")
            self.assertEqual(chapters["en"][slug]["meta"]["prerequisites"],
                             chapters["pt"][slug]["meta"]["prerequisites"])
        for track in load_tracks()[:2]:
            names = [slug for section in track["sections"] for slug in section["articles"]]
            for earlier, later in (
                ("modular-programming-interfaces", slugs[0]),
                ("programming-semantics-contracts", slugs[0]),
                (slugs[0], slugs[1]),
                ("data-types-bytes-and-representation", slugs[1]),
                (slugs[1], "testing-maintainability"),
                (slugs[1], "file-descriptors-buffering-fsync"),
            ):
                self.assertLess(names.index(earlier), names.index(later))
            self.assertEqual(len(names), len(set(names)))

if __name__ == "__main__":
    unittest.main()
