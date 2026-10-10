"""Run independent OS processes against a real file-backed SQLite database."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "examples/python/sqlite_process_race.py"

def call(*args, check=True):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          check=check, capture_output=True, text=True, timeout=12)

class MultiProcessSQLTest(unittest.TestCase):
    def test_competing_reservations_and_outbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp)/"state.sqlite")
            call("init",path)
            workers = [subprocess.Popen(
                [sys.executable,str(SCRIPT),"reserve",path,str(i),"2"],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True
            ) for i in range(2)]
            results=[]
            for worker in workers:
                stdout,stderr=worker.communicate(timeout=12)
                self.assertEqual(worker.returncode,0,stderr)
                results.append(json.loads(stdout)["status"])
            self.assertEqual(sorted(results),["accepted","insufficient"])
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("SELECT available FROM stock").fetchone(),(1,))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM reservations").fetchone(),(1,))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM outbox").fetchone(),(1,))

    def test_crash_after_commit_then_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp)/"persistent.sqlite")
            call("init",path)
            crash=call("reserve",path,"operation-42","2","--crash-after-commit",
                       check=False)
            self.assertEqual(crash.returncode,23,crash.stderr)
            retry=call("reserve",path,"operation-42","2")
            self.assertEqual(json.loads(retry.stdout)["status"],"replayed")
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("SELECT available FROM stock").fetchone(),(1,))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM reservations").fetchone(),(1,))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM outbox").fetchone(),(1,))
            conflict=call("reserve",path,"operation-42","1",check=False)
            self.assertNotEqual(conflict.returncode,0)

if __name__ == "__main__":
    unittest.main()
