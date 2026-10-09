"""Independent SDE II system-design example tests across English and Portuguese."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

FENCES = re.compile(r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def run_chapter(lang, slug):
    article = load_articles()[lang][slug]
    context = {}
    blocks = list(FENCES.finditer(article["body"]))
    assert blocks, (lang, slug, "missing executable example")
    for block in blocks:
        exec(compile(block["code"], f"{lang}/{slug}", "exec"), context, context)
    return context

class SystemDesignContracts(unittest.TestCase):
    def test_capacity_assumptions_and_failover_math(self):
        for language, function in (("en", "estimate"), ("pt", "estimar")):
            f = run_chapter(language, "system-design-process")[function]
            self.assertEqual(f(8_640_000, 5, 200), (100, 500, 3, 4))
            with self.assertRaises(ValueError):
                f(100, 5, 0)

    def test_signed_cursor_scoped_to_owner(self):
        for language, create, read in (
            ("en", "make_cursor", "read_cursor"),
            ("pt", "criar_cursor", "ler_cursor"),
        ):
            namespace = run_chapter(language, "api-contracts-pagination")
            token = namespace[create]("tenantA", 12, 5)
            self.assertEqual(namespace[read](token, "tenantA"), (12, 5))
            with self.assertRaises(ValueError):
                namespace[read](token, "tenantB")
            # Alter the first base64 character in the payload; HMAC must reject it.
            changed = ("A" if token[0] != "A" else "B") + token[1:]
            with self.assertRaises(ValueError):
                namespace[read](changed, "tenantA")

    def test_rendezvous_addition_never_moves_between_old_nodes(self):
        for language, function in (("en", "owner"), ("pt", "destino")):
            route = run_chapter(language, "data-partitioning-sharding")[function]
            old = ["a", "b", "c"]
            new = old + ["d"]
            for k in range(150):
                p, q = route(f"k{k}", old), route(f"k{k}", new)
                self.assertTrue(p == q or q == "d")
            with self.assertRaises(ValueError):
                route("key", [])

    def test_notification_idempotency_and_backlog(self):
        for language, model_name, operation, recovery in (
            ("en", "LocalDeliveryModel", "deliver", "backlog_recovery"),
            ("pt", "ModeloLocalEntrega", "entregar", "recuperar_fila"),
        ):
            ns = run_chapter(language, "system-design-notifications")
            model = ns[model_name]()
            first = getattr(model, operation)("event1", "email")
            second = getattr(model, operation)("event1", "email")
            self.assertNotEqual(first, second)
            calls = model.provider_calls if language == "en" else model.chamadas_provedor
            self.assertEqual(calls, [("event1", "email")])
            self.assertEqual(ns[recovery](10, 10, 15), (100, 20))
            with self.assertRaises(ValueError):
                ns[recovery](10, 10, 10)

if __name__ == "__main__":
    unittest.main()
