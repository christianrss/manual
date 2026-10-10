"""Real PostgreSQL service test with concurrent OS processes and commit/retry."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid
import psycopg

ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/"examples/python/postgres_checkout.py"

def command(*args, check=True):
    return subprocess.run([sys.executable,str(CLI),*map(str,args)],
                          check=check,capture_output=True,text=True,timeout=20)

@unittest.skipUnless(os.getenv("POSTGRES_DSN"),"POSTGRES_DSN required; configured in CI")
class PostgresIntegration(unittest.TestCase):
    def schema(self):
        name="manual_"+uuid.uuid4().hex
        command("init",name)
        self.addCleanup(self.drop,name)
        return name

    def drop(self,name):
        with psycopg.connect(os.environ["POSTGRES_DSN"],autocommit=True) as conn:
            conn.execute('DROP SCHEMA "'+name+'" CASCADE')

    def counts(self,name):
        with psycopg.connect(os.environ["POSTGRES_DSN"],
                             options=f"-c search_path={name}") as conn:
            return (
                conn.execute("SELECT available FROM stock").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM reservations").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])

    def test_two_os_processes_cannot_oversell(self):
        name=self.schema()
        procs=[subprocess.Popen(
            [sys.executable,str(CLI),"reserve",name,f"buyer{i}","2"],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            for i in (1,2)]
        statuses=[]
        for proc in procs:
            stdout,stderr=proc.communicate(timeout=20)
            self.assertEqual(proc.returncode,0,stderr)
            statuses.append(json.loads(stdout)["status"])
        self.assertEqual(sorted(statuses),["accepted","insufficient"])
        self.assertEqual(self.counts(name),(1,1,1))

    def test_postcommit_crash_replays_without_duplicate(self):
        name=self.schema()
        crashed=command("reserve",name,"txn42","2","--crash",check=False)
        self.assertEqual(crashed.returncode,23,crashed.stderr)
        self.assertEqual(json.loads(command("reserve",name,"txn42","2").stdout)["status"],
                         "replayed")
        self.assertEqual(self.counts(name),(1,1,1))
        conflict=command("reserve",name,"txn42","1",check=False)
        self.assertNotEqual(conflict.returncode,0)
        self.assertEqual(self.counts(name),(1,1,1))

if __name__=="__main__":
    unittest.main()
