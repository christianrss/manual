"""File-backed SQLite reservation experiment with independent CLI processes.

Commands:
    python examples/python/sqlite_process_race.py init DB_FILE
    python examples/python/sqlite_process_race.py reserve DB_FILE OP_KEY QTY [--crash-after-commit]

An abnormal exit code 23 is an intentionally injected crash after durable commit.
"""
import argparse
import json
import os
import sqlite3

def connect(path):
    conn = sqlite3.connect(path, timeout=8, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=8000")
    return conn

def initialize(path):
    with connect(path) as db:
        db.executescript("""
        CREATE TABLE stock (
          sku TEXT PRIMARY KEY,
          available INTEGER NOT NULL CHECK (available >= 0)
        );
        CREATE TABLE reservations (
          op_key TEXT PRIMARY KEY,
          sku TEXT NOT NULL,
          qty INTEGER NOT NULL CHECK(qty > 0)
        );
        CREATE TABLE outbox (
          op_key TEXT PRIMARY KEY REFERENCES reservations(op_key),
          event_id TEXT NOT NULL UNIQUE
        );
        INSERT INTO stock VALUES ('seat', 3);
        """)

def reserve(path, key, qty, crash_after_commit=False):
    if not key or not isinstance(qty, int) or qty <= 0:
        raise ValueError("positive quantity and nonempty key required")
    conn = connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        previous = conn.execute(
            "SELECT sku,qty FROM reservations WHERE op_key=?", (key,)
        ).fetchone()
        if previous is not None:
            if previous != ("seat", qty):
                raise ValueError("operation key reused with different payload")
            conn.commit()
            return "replayed"
        updated = conn.execute(
            "UPDATE stock SET available=available-? "
            "WHERE sku='seat' AND available>=?", (qty, qty)
        ).rowcount
        if updated != 1:
            conn.rollback()
            return "insufficient"
        conn.execute(
            "INSERT INTO reservations(op_key,sku,qty) VALUES (?,?,?)",
            (key, "seat", qty)
        )
        conn.execute(
            "INSERT INTO outbox(op_key,event_id) VALUES (?,?)",
            (key, "reservation-" + key)
        )
        conn.commit()
        if crash_after_commit:
            os._exit(23)  # Hard process exit: deliberately skips Python cleanup.
        return "accepted"
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["init", "reserve"])
    parser.add_argument("path")
    parser.add_argument("key", nargs="?")
    parser.add_argument("qty", nargs="?", type=int)
    parser.add_argument("--crash-after-commit", action="store_true")
    args = parser.parse_args()
    if args.action == "init":
        initialize(args.path)
        print(json.dumps({"status": "initialized"}))
    elif args.key is None or args.qty is None:
        parser.error("reserve requires key and quantity")
    else:
        print(json.dumps({
            "status": reserve(args.path, args.key, args.qty,
                              args.crash_after_commit)
        }))
