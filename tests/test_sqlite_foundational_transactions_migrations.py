"""Independent SQLite file-backed tests for parameterized CRUD and schema migrations."""
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles, load_modules, load_tracks

FENCES = re.compile(r"(?ms)^~~~python[^\n]*\n(.*?)^~~~[ \t]*$")

def load_code(lang, slug):
    path = ROOT / "content" / lang / "topics" / (slug + ".md")
    blocks = FENCES.findall(path.read_text(encoding="utf8"))
    if not blocks:
        raise AssertionError(f"Missing executable example: {lang} / {slug}")
    module = types.ModuleType("sqlite_lesson_" + lang + "_" + slug.replace("-", "_"))
    sys.modules[module.__name__] = module
    try:
        for block in blocks:
            exec(compile(block, str(path), "exec"), module.__dict__)
        return dict(module.__dict__)
    finally:
        sys.modules.pop(module.__name__, None)

class SqliteTransferContracts(unittest.TestCase):
    def test_success_rollback_limits_and_real_persistence(self):
        for lang in ("en", "pt"):
            ns = load_code(lang, "sqlite-parameterized-crud-transactions")
            connect, create, get, transfer = (ns[k] for k in
                                              ("open_db", "create_account", "balance", "transfer"))
            with tempfile.TemporaryDirectory() as folder:
                file = Path(folder) / "accounts.db"
                conn = connect(file)
                try:
                    create(conn, "ada", 900)
                    create(conn, "grace", 100)
                    create(conn, "full", ns["MAX_CENTS"])
                    self.assertEqual(get(conn, "missing"), None)
                    with self.assertRaises(sqlite3.IntegrityError):
                        create(conn, "ada", 1)
                    transfer(conn, "ada", "grace", 250)
                    self.assertEqual((get(conn, "ada"), get(conn, "grace")),
                                     (650, 350))
                    baseline = (get(conn, "ada"), get(conn, "grace"),
                                get(conn, "full"))
                    for src, dst, amount in (
                        ("ada", "missing", 2),
                        ("missing", "grace", 2),
                        ("ada", "grace", 651),
                        ("ada", "full", 10),
                        ("ada", "ada", 1),
                        ("ada", "grace", 0),
                        ("ada", "grace", True),
                        ("ada", "grace", -1),
                    ):
                        with self.subTest(lang=lang, source=src, target=dst, value=amount):
                            with self.assertRaises(ValueError):
                                transfer(conn, src, dst, amount)
                            self.assertEqual((get(conn, "ada"), get(conn, "grace"),
                                              get(conn, "full")), baseline)
                            self.assertFalse(conn.in_transaction)
                    suspicious = "' OR 1=1 --"
                    self.assertIsNone(get(conn, suspicious))
                    create(conn, suspicious, 9)
                    self.assertEqual(get(conn, suspicious), 9)
                    self.assertEqual(get(conn, "ada"), 650)
                    for bad_owner, bad_amount in (("", 0), ("a", False),
                                                  ("a", -1), ("a", 1000001)):
                        with self.assertRaises(ValueError):
                            create(conn, bad_owner, bad_amount)
                finally:
                    conn.close()
                reopened = connect(file)
                try:
                    self.assertEqual((get(reopened, "ada"), get(reopened, "grace"),
                                      get(reopened, "full")), (650, 350, 1000000))
                    self.assertEqual(get(reopened, "' OR 1=1 --"), 9)
                finally:
                    reopened.close()

    def test_transfer_conservation_against_arithmetic_oracle(self):
        for lang in ("en", "pt"):
            ns = load_code(lang, "sqlite-parameterized-crud-transactions")
            for source in (0, 1, 10, 100):
                for destination in (0, 3, 90, 999999):
                    for amount in (1, 2, 50):
                        with self.subTest(lang=lang, s=source, d=destination, x=amount):
                            db = ns["open_db"](":memory:")
                            try:
                                ns["create_account"](db, "source", source)
                                ns["create_account"](db, "destination", destination)
                                good = source >= amount and destination + amount <= 1000000
                                if good:
                                    ns["transfer"](db, "source", "destination", amount)
                                    expected = (source-amount, destination+amount)
                                else:
                                    with self.assertRaises(ValueError):
                                        ns["transfer"](db, "source", "destination", amount)
                                    expected = (source, destination)
                                self.assertEqual((ns["balance"](db, "source"),
                                                  ns["balance"](db, "destination")),
                                                 expected)
                                self.assertEqual(sum(expected), source + destination)
                            finally:
                                db.close()

class SchemaMigrationContracts(unittest.TestCase):
    def test_v0_v1_to_v2_persistence_and_idempotence(self):
        for lang in ("en", "pt"):
            ns = load_code(lang, "sqlite-schema-migrations-user-version")
            migrate = ns["migrate"]
            for initial in (0, 1):
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / "inventory.db"
                    db = sqlite3.connect(path, isolation_level=None)
                    try:
                        if initial == 1:
                            db.execute("""CREATE TABLE inventory(
                                sku TEXT PRIMARY KEY NOT NULL,
                                quantity INTEGER NOT NULL
                                  CHECK(typeof(quantity)='integer' AND quantity>=0))""")
                            db.execute("INSERT INTO inventory VALUES (?,?)", ("a", 5))
                            db.execute("PRAGMA user_version=1")
                        migrate(db)
                        self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
                        names = [r[1] for r in db.execute("PRAGMA table_info(inventory)")]
                        self.assertEqual(names, ["sku", "quantity", "description"])
                        if initial == 1:
                            self.assertEqual(db.execute(
                                "SELECT sku,quantity,description FROM inventory").fetchall(),
                                [("a", 5, "")])
                        else:
                            db.execute("INSERT INTO inventory(sku,quantity) VALUES (?,?)", ("a", 5))
                        migrate(db)
                        self.assertEqual(db.execute("SELECT COUNT(*) FROM inventory").fetchone()[0], 1)
                        with self.assertRaises(sqlite3.IntegrityError):
                            db.execute("INSERT INTO inventory(sku,quantity) VALUES (?,?)",
                                       ("float", 1.5))
                    finally:
                        db.close()
                    reopened = sqlite3.connect(path, isolation_level=None)
                    try:
                        self.assertEqual(reopened.execute("PRAGMA user_version").fetchone()[0], 2)
                        self.assertEqual(reopened.execute(
                            "SELECT sku,quantity,description FROM inventory").fetchall(),
                            [("a", 5, "")])
                        migrate(reopened)
                    finally:
                        reopened.close()

    def test_reject_unknown_versions_and_rollback_failed_schema(self):
        for lang in ("en", "pt"):
            migrate = load_code(lang, "sqlite-schema-migrations-user-version")["migrate"]
            for version in (1, 2, 99):
                db = sqlite3.connect(":memory:", isolation_level=None)
                try:
                    db.execute(f"PRAGMA user_version = {version}")
                    with self.assertRaises((ValueError, sqlite3.OperationalError)):
                        migrate(db)
                    self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0],
                                     version)
                    self.assertFalse(db.in_transaction)
                finally:
                    db.close()
            db = sqlite3.connect(":memory:", isolation_level=None)
            try:
                db.execute("CREATE TABLE inventory(unexpected TEXT)")
                with self.assertRaises(sqlite3.OperationalError):
                    migrate(db)
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 0)
                self.assertEqual([row[1] for row in db.execute(
                    "PRAGMA table_info(inventory)")], ["unexpected"])
            finally:
                db.close()

class CurriculumContracts(unittest.TestCase):
    def test_parity_and_track_order(self):
        modules, articles = load_modules(), load_articles()
        first = "sqlite-parameterized-crud-transactions"
        second = "sqlite-schema-migrations-user-version"
        for slug in (first, second):
            self.assertEqual(modules[slug], "databases")
            self.assertEqual(articles["en"][slug]["meta"]["prerequisites"],
                             articles["pt"][slug]["meta"]["prerequisites"])
        for track in load_tracks()[:2]:
            ids = [slug for sec in track["sections"] for slug in sec["articles"]]
            self.assertLess(ids.index("relational-model-sql-basics"), ids.index(first))
            self.assertLess(ids.index("python-error-contracts-resource-cleanup"), ids.index(first))
            self.assertLess(ids.index(first), ids.index(second))
            self.assertLess(ids.index(second), ids.index("database-consistency"))
            self.assertEqual(len(ids), len(set(ids)))

if __name__ == "__main__":
    unittest.main()
