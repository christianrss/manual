"""PostgreSQL-backed reservation CLI; each invocation is a distinct process.

Usage:
  python examples/python/postgres_checkout.py init SCHEMA
  python examples/python/postgres_checkout.py reserve SCHEMA OP_KEY QUANTITY [--crash]
The CLI deliberately requires POSTGRES_DSN and an existing PostgreSQL server.
"""
import argparse
import json
import os
import re
import psycopg
from psycopg import sql

DSN = os.environ["POSTGRES_DSN"]

def safe_schema(value):
    if not re.fullmatch(r"manual_[a-f0-9]{32}", value):
        raise ValueError("expected a generated manual_ + UUID hex schema")
    return value

def initialize(name):
    name=safe_schema(name)
    with psycopg.connect(DSN, autocommit=True) as conn:
        s=sql.Identifier(name)
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(s))
        conn.execute(sql.SQL(
            "CREATE TABLE {}.stock (sku text PRIMARY KEY,"
            " available integer NOT NULL CHECK(available >= 0))").format(s))
        conn.execute(sql.SQL(
            "CREATE TABLE {}.reservations (op_key text PRIMARY KEY,"
            " qty integer NOT NULL CHECK(qty > 0))").format(s))
        conn.execute(sql.SQL(
            "CREATE TABLE {}.outbox (op_key text PRIMARY KEY REFERENCES"
            " {}.reservations(op_key), event_id text NOT NULL UNIQUE)"
        ).format(s,s))
        conn.execute(sql.SQL("INSERT INTO {}.stock VALUES ('seat',3)").format(s))

def reserve(name, key, qty, crash=False):
    name=safe_schema(name)
    if not key or qty<=0:
        raise ValueError("nonempty key and positive quantity required")
    # Search path is a strictly validated local generated schema, not user input.
    with psycopg.connect(DSN, options=f"-c search_path={name}") as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO reservations(op_key,qty) VALUES (%s,%s)"
                " ON CONFLICT(op_key) DO NOTHING RETURNING op_key", (key,qty))
            if cur.fetchone() is None:
                cur.execute("SELECT qty FROM reservations WHERE op_key=%s",(key,))
                previous=cur.fetchone()
                if previous is None or previous[0]!=qty:
                    raise ValueError("idempotency key collision")
                result="replayed"
            else:
                cur.execute(
                    "UPDATE stock SET available=available-%s"
                    " WHERE sku='seat' AND available >= %s RETURNING available",
                    (qty,qty))
                if cur.fetchone() is None:
                    conn.rollback()
                    return "insufficient"
                cur.execute("INSERT INTO outbox(op_key,event_id) VALUES (%s,%s)",
                            (key, "reserve-"+key))
                result="accepted"
    # Commit is complete when the context manager exits.
    if crash and result=="accepted":
        os._exit(23)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("init","reserve"))
    p.add_argument("schema")
    p.add_argument("key",nargs="?")
    p.add_argument("quantity",nargs="?",type=int)
    p.add_argument("--crash",action="store_true")
    a=p.parse_args()
    if a.action=="init":
        initialize(a.schema)
        result="initialized"
    else:
        if a.key is None or a.quantity is None:
            p.error("reserve requires KEY and QUANTITY")
        result=reserve(a.schema,a.key,a.quantity,a.crash)
    print(json.dumps({"status":result}))

if __name__=="__main__":
    main()
