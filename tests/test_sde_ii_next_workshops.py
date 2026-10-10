"""Independent behavioral oracles for the latest three bilingual SDE II workshops."""
from __future__ import annotations
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model import load_articles

FENCES = re.compile(r"(?ms)^(?P<fence>`{3}|~{3})python[^\n]*\n(?P<code>.*?)^(?P=fence)[ \t]*$")

def context(lang, slug):
    article = load_articles()[lang][slug]
    ns = {}
    blocks = list(FENCES.finditer(article["body"]))
    assert blocks, (lang,slug,"missing executable examples")
    for block in blocks:
        exec(compile(block["code"],f"{lang}/{slug}","exec"),ns,ns)
    return ns

class NextWorkshopContracts(unittest.TestCase):
    def test_two_workers_all_schedules_cas_vs_lost_update(self):
        for lang, names in (
            ("en",("all_schedules","guarded_model","broken_schedule","Seat","reserve_if_version")),
            ("pt",("todas_sequencias","modelo_protegido","sequencia_defeituosa","Assento","reservar_se_versao")),
        ):
            ns = context(lang,"concurrency-interview-workshop")
            schedules = list(ns[names[0]]())
            self.assertEqual(len(schedules),6)
            self.assertTrue(all(len(ns[names[1]](s)[1])==1 for s in schedules))
            self.assertTrue(any(len(ns[names[2]](s)[1])==2 for s in schedules))
            seat = ns[names[3]]()
            reserve = getattr(seat,names[4])
            self.assertFalse(reserve("A",-1))
            self.assertTrue(reserve("B",0))
            self.assertFalse(reserve("A",0))
            self.assertFalse(reserve("B",1))

    def test_outbox_commit_and_payload_conflict(self):
        for lang, name, replay in (
            ("en","accept","replayed"),
            ("pt","aceitar","repetido"),
        ):
            ns=context(lang,"failure-recovery-workshop")
            db=ns["db"] if lang=="en" else ns["banco"]
            fn=ns[name]
            before=db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            with self.assertRaises(RuntimeError):
                fn(db,"new","payload","before_commit")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],before)
            with self.assertRaises(RuntimeError):
                fn(db,"new","payload","after_commit")
            self.assertEqual(fn(db,"new","payload"),replay)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],before+1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0],before+1)
            with self.assertRaises(ValueError):
                fn(db,"new","different")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],before+1)

    def test_token_bucket_refills_saturation_and_rejects(self):
        for lang, bucket_cls, clock_cls, allow, advance in (
            ("en","TokenBucket","ManualClock","allow","advance"),
            ("pt","BaldeTokens","RelogioManual","permitir","avancar"),
        ):
            ns=context(lang,"maintainable-implementation-workshop")
            clock=ns[clock_cls]()
            bucket=ns[bucket_cls](3,2,clock)
            decision=getattr(bucket,allow)
            move=getattr(clock,advance)
            self.assertTrue(all(decision() for _ in range(3)))
            self.assertFalse(decision())
            move(.49)
            self.assertFalse(decision())
            move(.01)
            self.assertTrue(decision())
            move(100)
            self.assertFalse(decision(4))
            self.assertTrue(decision(3))
            with self.assertRaises(ValueError):
                decision(0)

if __name__=="__main__":
    unittest.main()
