"""Deterministically expose write skew and test SERIALIZABLE retry in real PostgreSQL."""
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
import uuid
import psycopg
from psycopg import sql

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"examples"/"python"))
from postgres_serializable_lab import attempt_off_call,retry_off_call

@unittest.skipUnless(os.getenv("POSTGRES_DSN"),"requires real PostgreSQL configured in CI")
class SerializableLab(unittest.TestCase):
    def setUp(self):
        self.dsn=os.environ["POSTGRES_DSN"]
        self.schema="manual_"+uuid.uuid4().hex
        with psycopg.connect(self.dsn,autocommit=True) as conn:
            name=sql.Identifier(self.schema)
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(name))
            conn.execute(sql.SQL("CREATE TABLE {}.oncall("
                "doctor text PRIMARY KEY,active boolean NOT NULL)").format(name))
            conn.execute(sql.SQL("INSERT INTO {}.oncall VALUES"
                "('a',true),('b',true)").format(name))

    def tearDown(self):
        with psycopg.connect(self.dsn,autocommit=True) as db:
            db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))

    def active_doctors(self):
        with psycopg.connect(self.dsn,options=f"-c search_path={self.schema}") as db:
            return db.execute("SELECT doctor FROM oncall WHERE active ORDER BY doctor").fetchall()

    def two_at_same_snapshot(self,isolation):
        barrier=Barrier(2)
        def worker(doctor):
            try:
                return doctor,attempt_off_call(self.dsn,self.schema,doctor,isolation,barrier)
            except psycopg.errors.SerializationFailure:
                return doctor,"40001"
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(worker,"a")
            b=pool.submit(worker,"b")
            return [a.result(timeout=20),b.result(timeout=20)]

    def test_read_committed_allows_write_skew(self):
        results=self.two_at_same_snapshot("READ COMMITTED")
        self.assertEqual(sorted(x[1] for x in results),["left","left"])
        self.assertEqual(len(self.active_doctors()),0)

    def test_serializable_aborts_one_then_full_retry_denies(self):
        results=self.two_at_same_snapshot("SERIALIZABLE")
        self.assertEqual(sorted(x[1] for x in results),["40001","left"])
        self.assertEqual(len(self.active_doctors()),1)
        failed=[doctor for doctor,status in results if status=="40001"][0]
        self.assertEqual(retry_off_call(self.dsn,self.schema,failed),"denied")
        self.assertEqual(len(self.active_doctors()),1)

if __name__=="__main__":
    unittest.main()
