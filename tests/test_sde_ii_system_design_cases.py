"""Independent tests for the three SDE II system-design articles (EN/PT)."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

FENCE = re.compile(r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def context(lang, slug):
    article = load_articles()[lang][slug]
    ns = {}
    blocks = list(FENCE.finditer(article["body"]))
    assert blocks, (lang, slug, "missing executable examples")
    for block in blocks:
        exec(compile(block["code"], f"{lang}/{slug}", "exec"), ns, ns)
    return ns

class SDEIISystemDesignCases(unittest.TestCase):
    def test_storage_capacity_units_and_inputs(self):
        for lang, fn_name in (("en", "raw_growth_gib"),
                              ("pt", "crescimento_gib")):
            fn = context(lang, "storage-selection")[fn_name]
            expected = 250000 * 1536 * 365 / (1024 ** 3)
            self.assertAlmostEqual(fn(250000, 1536), expected)
            self.assertEqual(fn(0, 99), 0)
            with self.assertRaises(ValueError):
                fn(10, -1)

    def test_checkout_preserves_inventory_and_outbox_on_replay(self):
        for lang, name, accepted, replay, insufficient in (
            ("en", "reserve", "accepted", "replayed", "out_of_stock"),
            ("pt", "reservar", "aceito", "repetido", "sem_estoque"),
        ):
            ns = context(lang, "system-design-order-service")
            conn = ns["db"] if lang == "en" else ns["banco"]
            reserve = ns[name]
            # The chapter's examples already reserved three of four units.
            self.assertEqual(reserve(conn, "order-3", "sku-A", 1),
                             ("order-3", accepted))
            self.assertEqual(reserve(conn, "order-3", "sku-A", 1),
                             ("order-3", replay))
            self.assertEqual(reserve(conn, "order-4", "sku-A", 1),
                             (None, insufficient))
            self.assertEqual(conn.execute(
                "SELECT available FROM stock WHERE sku='sku-A'").fetchone(), (0,))
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM orders").fetchone(), (2,))
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM outbox").fetchone(), (2,))
            with self.assertRaises(ValueError):
                reserve(conn, "order-3", "sku-A", 2)
            self.assertEqual(conn.execute(
                "SELECT available FROM stock").fetchone(), (0,))

    def test_feed_composite_cursor_unfollow_and_deduplication(self):
        for lang, build_name, page_name in (
            ("en", "build_inboxes", "home_page"),
            ("pt", "construir_caixas", "pagina_feed"),
        ):
            ns = context(lang, "system-design-feed")
            build, page = ns[build_name], ns[page_name]
            graph = {"alice": {"bob"}}
            posts = [(10, 1, "alice"), (10, 2, "alice"),
                     (10, 2, "alice")]
            inbox = build(posts, graph, 3)
            follow = {"bob": {"alice"}}
            first, cursor = page("bob", follow, graph, posts, inbox, 3, 1)
            second, other = page("bob", follow, graph, posts, inbox, 3, 1,
                                 cursor)
            self.assertEqual(first, [2])
            self.assertEqual(second, [1])
            self.assertEqual(other, (10, 1))
            follow["bob"] = set()
            self.assertEqual(page("bob", follow, graph, posts, inbox, 3, 10)[0], [])
            with self.assertRaises(ValueError):
                page("bob", follow, graph, posts, inbox, 3, 0)

if __name__ == "__main__":
    unittest.main()
