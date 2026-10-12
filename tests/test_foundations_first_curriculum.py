"""Foundation-first checks independent of the published example assertions."""
import itertools
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks

FENCES = re.compile(r"(?ms)^~~~python[^\n]*\n(.*?)^~~~[ \t]*$")

def load_example(lang, slug):
    text = (ROOT / "content" / lang / "topics" / (slug + ".md")).read_text(encoding="utf-8")
    snippets = FENCES.findall(text)
    if not snippets:
        raise AssertionError("missing executable example for " + slug)
    module = types.ModuleType("foundation_" + lang + "_" + slug.replace("-", "_"))
    sys.modules[module.__name__] = module
    try:
        for snippet in snippets:
            exec(compile(snippet, slug, "exec"), module.__dict__)
        return dict(module.__dict__)
    finally:
        sys.modules.pop(module.__name__, None)

def slow_longest_run(values):
    if not values:
        return (0, 0)
    best = (0, 1)
    for start in range(len(values)):
        for end in range(start + 1, len(values) + 1):
            part = values[start:end]
            if all(part[i] >= part[i - 1] for i in range(1, len(part))):
                if len(part) > best[1]:
                    best = (start, len(part))
            else:
                break
    return best

class FoundationsFirstTests(unittest.TestCase):
    def test_control_flow_matches_brute_force(self):
        for lang in ("en", "pt"):
            run = load_example(lang, "programming-control-flow-functions")["longest_non_decreasing_run"]
            for count in range(7):
                for seq in itertools.product((0, 1, 2), repeat=count):
                    with self.subTest(lang=lang, seq=seq):
                        self.assertEqual(run(seq), slow_longest_run(seq))
            with self.assertRaises(TypeError):
                run(None)

    def test_relational_sql_examples_run(self):
        for lang in ("en", "pt"):
            ns = load_example(lang, "relational-model-sql-basics")
            self.assertEqual(ns["result"], [("Ada", 100, 3100), ("Grace", 101, 0)])

    def test_http_methods_are_distinct(self):
        for lang in ("en", "pt"):
            Service = load_example(lang, "http-client-server-fundamentals")["NotesService"]
            svc = Service()
            status, created = svc.handle("POST", "/notes", "Original")
            self.assertEqual(status, 201)
            ident = created["id"]
            self.assertEqual(svc.handle("GET", "/notes/" + str(ident))[0], 200)
            self.assertEqual(svc.handle("PUT", "/notes/" + str(ident), ""), (400, None))
            self.assertEqual(svc.handle("GET", "/notes/" + str(ident))[1]["text"], "Original")
            for _ in range(4):
                self.assertEqual(svc.handle("PUT", "/notes/" + str(ident), "Replaced")[0], 200)
            self.assertEqual(len(svc.notes), 1)
            self.assertEqual(svc.handle("DELETE", "/notes/" + str(ident)), (204, None))
            self.assertEqual(svc.handle("DELETE", "/notes/" + str(ident)), (404, None))
            self.assertEqual(svc.handle("GET", "/notes/" + str(ident)), (404, None))

    def test_track_requires_basics_before_specialization(self):
        modules = load_modules()
        self.assertEqual(modules["programming-control-flow-functions"], "foundations")
        self.assertEqual(modules["relational-model-sql-basics"], "databases")
        self.assertEqual(modules["http-client-server-fundamentals"], "networking")
        articles = load_articles()
        for slug in ("programming-control-flow-functions", "relational-model-sql-basics",
                     "http-client-server-fundamentals"):
            self.assertEqual(articles["en"][slug]["meta"]["prerequisites"],
                             articles["pt"][slug]["meta"]["prerequisites"])
        for track in load_tracks()[:2]:
            sections = track["sections"]
            flattened = [a for section in sections for a in section["articles"]]
            self.assertLess(flattened.index("programming-control-flow-functions"),
                            flattened.index("logic-proofs-invariants"))
            self.assertLess(flattened.index("programming-control-flow-functions"),
                            flattened.index("programming-semantics-contracts"))
            for slug in ("relational-model-sql-basics", "http-client-server-fundamentals"):
                self.assertIn(slug, flattened)
                self.assertLess(flattened.index("programming-control-flow-functions"),
                                flattened.index(slug))
        amazon = load_tracks()[0]
        core_design = next(s for s in amazon["sections"] if s["title"]["en"].startswith("System design from"))
        optional = next(s for s in amazon["sections"] if s["title"]["en"].startswith("Optional: advanced"))
        self.assertNotIn("system-design-ticket-reservations", core_design["articles"])
        self.assertIn("system-design-ticket-reservations", optional["articles"])
        self.assertNotIn("system-design-order-service", core_design["articles"])
        self.assertIn("system-design-order-service", optional["articles"])

if __name__ == "__main__":
    unittest.main()
