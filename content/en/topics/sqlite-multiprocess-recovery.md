---
id: sqlite-multiprocess-recovery
title: "SQLite Multi-Process Workshop: Atomic Reservations and Crash Recovery"
description: "Test real concurrent processes, file-backed SQLite transactions, stock constraints and replay after hard process termination."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [failure-recovery-workshop, transactional-indexing-isolation]
sources:
  - {title: "SQLite — Isolation In SQLite", url: "https://www.sqlite.org/isolation.html", kind: "official database documentation"}
  - {title: "SQLite — Atomic Commit", url: "https://www.sqlite.org/atomiccommit.html", kind: "official database documentation"}
  - {title: "AWS Builders Library — Idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
---
A one-process SQLite simulation can illustrate a transaction invariant, but **cannot demonstrate what happens when two independent application processes access the same persistent database**. This workshop moves the reservation logic into a standalone Python CLI, starts competing OS processes, injects a hard exit immediately after commit, and reopens the file through another process. It tests a real local SQLite authority, not a clustered datastore or an external message broker. SQLite documents transaction isolation between separate connections and processes, with at most one writer at a time for a database file [1].

## Define the behavior and failure model

A file-backed database begins with **three available units** of one SKU called `seat`. Two clients independently request two units, each with a distinct operation key. The invariant is `available >= 0`, so **only one can be accepted**; the other returns `insufficient`. A successful reservation commits both a reservation row and a unique outbox intent in the **same transaction**. Repeating the accepted key and payload returns `replayed` without changing stock.

A key reused with a different quantity returns a conflict. An **insufficient** response does not store an idempotency result in this teaching protocol: after stock replenishment, repeating that previously rejected operation could succeed. This is a deliberate contract limitation, not a universally correct payment or inventory API. A production design may persist terminal rejections under scoped keys, depending on the business contract.

## Separate processes are not threads

Threads can share one Python Lock, but two CLI processes do not share that lock or Python heap. The shared authority is a **SQLite database file**. Every worker opens its own `sqlite3.connect` connection and executes `BEGIN IMMEDIATE`, which requests the write transaction before reading the current reservation or stock. SQLite serializes writers: one process can finish its critical transaction while another waits or hits a documented busy timeout [1][2].

![Two independent workers compete for one SQLite stock authority; a crash after commit leaves a durable reservation and outbox.](/diagrams/sqlite-process-recovery.svg)

The real demonstration is maintained as [sqlite_process_race.py](https://github.com/christianrss/manual/blob/main/examples/python/sqlite_process_race.py). The tests run this script using `subprocess.Popen` and `subprocess.run`, not a mocked repository. The executable source and the test are published together so a reader can audit the exact behavior.

## Transaction design and correctness argument

The transaction first checks `reservations(op_key)` under the write transaction. If the key already exists, it compares quantity and returns `replayed`. Otherwise it executes a conditional SQL update:

~~~sql
UPDATE stock SET available=available-?
WHERE sku='seat' AND available>=?;
~~~

When the affected row count is one, the worker inserts one reservation and one outbox event, then commits. When the row count is zero it rolls back and returns `insufficient`. The CHECK constraint on available provides an additional safety guard, but does not substitute for matching the correct quantity and operation key.

Because the conditional stock update and inserts are under one transaction, a committed accepted reservation has exactly one associated outbox intent. The primary key/UNIQUE constraints protect key identity. **This is local database atomicity**: a broker might still publish a message twice if a relay crashes after sending and before marking progress, and a payment provider may still return ambiguous results [3].

## Execute a real two-process contention test

From the repository root, the snippet creates a temporary database file and launches two separate Python processes. It does not depend on artificial sleep schedules to force a lost update. Both requests compete for the same transaction authority; the expected multiset of outcomes is exactly one `accepted` and one `insufficient`.

~~~python
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

script = Path("examples/python/sqlite_process_race.py")
assert script.is_file()
with tempfile.TemporaryDirectory() as directory:
    path = str(Path(directory) / "stock.sqlite")
    subprocess.run([sys.executable, str(script), "init", path],
                   check=True, capture_output=True, timeout=10)
    workers = [
        subprocess.Popen([sys.executable, str(script), "reserve", path,
                          f"client-{n}", "2"], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
        for n in (1,2)
    ]
    results = []
    for worker in workers:
        stdout, stderr = worker.communicate(timeout=10)
        assert worker.returncode == 0, stderr
        results.append(json.loads(stdout)["status"])
    assert sorted(results) == ["accepted", "insufficient"]
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT available FROM stock").fetchone() == (1,)
        assert db.execute("SELECT COUNT(*) FROM reservations").fetchone() == (1,)
        assert db.execute("SELECT COUNT(*) FROM outbox").fetchone() == (1,)
~~~

This checks one actual contention execution; it is **not** a proof for all possible operating-system schedules. The correctness argument comes from the SQL authority's serialization and atomic constraints. Run repeatedly and instrument busy errors to evaluate operational reliability under heavier contention.

## Inject an exit after commit and retry elsewhere

An injected `os._exit(23)` terminates the writer process immediately after the database commit. It deliberately skips ordinary Python stack unwinding and cleanup. A separate retry process then uses the **same operation key** and should return `replayed`. A fresh connection verifies the database still holds one reservation and outbox row. The abnormal exit is expected and should **not** be mistaken for an uncommitted transaction.

~~~python
with tempfile.TemporaryDirectory() as directory:
    dbpath = str(Path(directory) / "durable.sqlite")
    subprocess.run([sys.executable, str(script), "init", dbpath],
                   check=True, capture_output=True, timeout=10)
    crashed = subprocess.run(
        [sys.executable, str(script), "reserve", dbpath,
         "checkout-7", "2", "--crash-after-commit"],
        capture_output=True, timeout=10)
    assert crashed.returncode == 23
    retry = subprocess.run(
        [sys.executable, str(script), "reserve", dbpath, "checkout-7", "2"],
        check=True, capture_output=True, text=True, timeout=10)
    assert json.loads(retry.stdout)["status"] == "replayed"
    with sqlite3.connect(dbpath) as db:
        assert db.execute("SELECT available FROM stock").fetchone() == (1,)
        assert db.execute("SELECT COUNT(*) FROM outbox").fetchone() == (1,)
~~~

The demonstration establishes recovery from **a process exit after a completed SQLite commit** on this test filesystem. It does not simulate sudden power loss, damaged storage, network partitions, host failure or full production backups. Durability after physical failures depends on journal mode, `synchronous` setting, filesystem guarantees, and the environment [2].

## Distinguish correctness from availability

`BEGIN IMMEDIATE` makes the critical section safe but can create **write contention**. Another writer may wait until the timeout, and an entire write workload may be constrained by a single SQLite writer. It is therefore wrong to conclude that this design can handle any desired distributed workload. Measure peak transaction time, lock-wait percentiles, busy errors and backlog under representative load.

For horizontally scaled production, you may migrate the authority to PostgreSQL or another database with appropriate constraints and isolation. That does not remove the need for idempotency, unique keys and transaction tests. Do not replace a tested SQLite invariant with an untested repository fake merely because both have a method called `reserve`.

## Failure matrix and counterexamples

| Event | Expected state | What remains unproven |
| --- | --- | --- |
| Two separate processes reserve two of three units | One success, stock remains nonnegative | All schedule/host failures |
| Accepted key repeats with same payload | Replayed, no second outbox | Cross-tenant scope |
| Accepted key repeats with different amount | Rejected as conflict | Request-body canonicalization |
| Process exits after commit | Durable rows remain and retry replays | Power-loss guarantees |
| Publisher crashes after sending | Outbox might publish again | Remote exactly-once effects |
| Database busy timeout | Request may fail transparently | Universal availability |

## Exercises and verification

1. Change initial stock to four and explain how the two competing reservations should behave.
2. Add a third process with the **same** operation key but a different quantity; reason about the conflict outcome.
3. Demonstrate why a mutex inside each worker process cannot coordinate the two clients.
4. Add a fault just before commit and show a new connection observes no reservation or outbox for that operation.
5. Run the test under repeated parallel contention and capture wait times without weakening the SQL invariant.

**Related chapters:** [Fault-injection workshop](/en/topics/failure-recovery-workshop/), [transactional indexes](/en/topics/transactional-indexing-isolation/), [concurrency workshop](/en/topics/concurrency-interview-workshop/) and [orders system design](/en/topics/system-design-order-service/) explain the abstractions.
