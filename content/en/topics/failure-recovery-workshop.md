---
id: failure-recovery-workshop
title: "Fault-Injection Workshop: Durable Outbox, Crashes and Duplicate Delivery"
description: "Test precommit and postcommit crashes, at-least-once outbox publication, receiver deduplication and recovery boundaries."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [testing-strategies, asynchronous-messaging, api-reliability]
sources:
  - {title: "SQLite — UPSERT and conflict handling", url: "https://www.sqlite.org/lang_upsert.html", kind: "official database documentation"}
  - {title: "Amazon Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
---
Reliable systems need tests that deliberately **stop work between durable steps**. A happy-path integration test can pass while an event is silently lost whenever a worker crashes after a database commit but before publishing to a broker. This workshop constructs a small transactional-outbox protocol, injects faults at explicit boundaries, and verifies what remains after restart. The scope is a single SQLite authority and a simulated message receiver; it does not claim atomic delivery to an independent broker or exactly-once external side effects [1][2].

## Define the safety and recovery contracts

A hypothetical order API accepts an operation key and writes a domain record plus an event intent. The **safety invariant** is: every committed order must have exactly one logical outbox intent, enforced within one local transaction. The **idempotency invariant** is: repeating a client key must never create a second order or intent. The recovery target is that an unsent committed intent can be discovered after process restart and retried.

A different goal—every event eventually reaching a receiver—is a **liveness property**. It requires assumptions about a running dispatcher, reachable broker, finite failures and retry policy. Merely storing an outbox does not imply messages progress without workers. End-to-end effects at an external provider require provider idempotency or reconciliation.

## The write-ahead intent and crash points

Create one transaction that inserts the order row and its outbox row. The transaction either commits both or neither. Model fault injection **before commit** by raising an exception and rolling back; the API must not acknowledge acceptance. Model **after commit** by raising only after a successful commit; the client may see a timeout, but retrying the same key must retrieve the existing record rather than create a duplicate.

![Fault boundaries for an order transaction, outbox publication and acknowledgment.](/diagrams/failure-recovery-drill.svg)

The following self-contained Python example creates an in-memory SQLite connection for deterministic local tests. SQLite transaction semantics, UNIQUE constraints and conflict handling are documented by its maintainers [1]. To test real crash durability, use a file-backed database, terminate an independent process and restart against the same files; an in-memory database cannot survive process termination.

~~~python
import sqlite3

db = sqlite3.connect(":memory:", isolation_level=None)
db.executescript("""
CREATE TABLE orders (
  operation_key TEXT PRIMARY KEY, description TEXT NOT NULL
);
CREATE TABLE outbox (
  event_id TEXT PRIMARY KEY, operation_key TEXT NOT NULL UNIQUE,
  delivered INTEGER NOT NULL DEFAULT 0
);
""")

def accept(conn, key, description, fail_at=None):
    if not key or not description:
        raise ValueError("required inputs")
    conn.execute("BEGIN IMMEDIATE")
    try:
        existing = conn.execute(
            "SELECT description FROM orders WHERE operation_key=?", (key,)
        ).fetchone()
        if existing is not None:
            if existing[0] != description:
                raise ValueError("idempotency payload conflict")
            conn.commit()
            return "replayed"
        conn.execute("INSERT INTO orders VALUES (?,?)", (key, description))
        conn.execute("INSERT INTO outbox(event_id,operation_key) VALUES (?,?)",
                     ("event-" + key, key))
        if fail_at == "before_commit":
            raise RuntimeError("injected precommit failure")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    if fail_at == "after_commit":
        raise RuntimeError("injected response loss")
    return "accepted"

try:
    accept(db, "a", "one item", "before_commit")
    assert False
except RuntimeError:
    pass
assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
assert accept(db, "a", "one item") == "accepted"
try:
    accept(db, "b", "two items", "after_commit")
    assert False
except RuntimeError:
    pass
assert accept(db, "b", "two items") == "replayed"
assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 2
assert db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 2
~~~

The code uses operation key as event identity in a **teaching model**. A real system should scope keys to tenant/account and canonical request fingerprint, protect ownership, and use event IDs designed for replay and audit.

## Publish, crash and the unavoidable duplicate

The dispatcher finds undelivered rows, sends them to a broker, then marks them delivered. A crash after successful send and **before** marking the row means it will send again after restart. Reversing the order—marking delivered before sending—creates a loss window instead. Without one distributed transaction spanning database and broker, the outbox normally chooses at-least-once publication with deduplication downstream [2].

A simulation can record provider acceptance as a list; it is deliberately not durable. The point of the test is the call count under a crash schedule, not a claim that a Python list represents production infrastructure.

~~~python
def relay_once(conn, send, fail_after_send=False):
    pending = conn.execute(
        "SELECT event_id FROM outbox WHERE delivered=0 ORDER BY event_id"
    ).fetchall()
    for (event_id,) in pending:
        send(event_id)
        if fail_after_send:
            raise RuntimeError("injected relay crash")
        conn.execute(
            "UPDATE outbox SET delivered=1 WHERE event_id=?", (event_id,)
        )

calls = []
try:
    relay_once(db, calls.append, fail_after_send=True)
    assert False
except RuntimeError:
    pass
assert calls == ["event-a"]
relay_once(db, calls.append)
assert calls.count("event-a") == 2
assert calls.count("event-b") == 1
assert db.execute("SELECT COUNT(*) FROM outbox WHERE delivered=0").fetchone()[0] == 0
~~~

The receiver should persist a unique event ID **in the same authority transaction as its business effect** when that design is available. Even then, an independent payment provider may have an unknown outcome after timeout. The receiver's local deduplication row cannot undo or automatically detect an irreversible external effect.

## Add a receiver-side deduplication model

A tiny inbox table enforces unique event IDs. This proof is local to the inbox database; it models the intended pattern but does not include a real business effect. In production, a separate inbox insert and a balance update in different transactions would still allow duplicate effects after a crash. Keep deduplication and the guarded effect **in the same transaction** or explicitly document the alternative guarantee.

~~~python
receiver = sqlite3.connect(":memory:", isolation_level=None)
receiver.execute("CREATE TABLE inbox(event_id TEXT PRIMARY KEY)")
receiver.execute("CREATE TABLE processed(event_id TEXT PRIMARY KEY)")

def consume(conn, event_id):
    conn.execute("BEGIN IMMEDIATE")
    try:
        inserted = conn.execute(
            "INSERT INTO inbox(event_id) VALUES (?) ON CONFLICT(event_id) DO NOTHING",
            (event_id,)
        ).rowcount
        if inserted:
            conn.execute("INSERT INTO processed VALUES (?)", (event_id,))
        conn.commit()
        return bool(inserted)
    except Exception:
        conn.rollback()
        raise

assert [consume(receiver, event) for event in calls] == [True, False, True]
assert receiver.execute("SELECT COUNT(*) FROM processed").fetchone()[0] == 2
~~~

The broker might deliver out of order and a failure can occur during consumer execution; that is why local transactional boundaries and replay ordering rules matter. A single SQLite connection example cannot verify independent concurrent consumers on a managed broker.

## Build the failure matrix rather than trusting one test

| Crash point | Durable order | Durable intent | Required behavior |
| --- | --- | --- | --- |
| Before transaction begins | No | No | Client can retry |
| After inserts, before commit | No | No | Roll back atomically |
| After commit, before HTTP response | Yes | Yes | Same key returns prior outcome |
| After broker send, before outbox ack | Yes | Yes, unacknowledged | Re-publish, receiver deduplicates |
| After outbox ack | Yes | Yes, acknowledged | Do not re-publish in normal scan |

Also inject a **payload conflict on the same operation key**, two processes racing to create the same key, broker backpressure, and a receiver failing after external payment but before writing its inbox marker. The last case is intentionally not solvable with a local outbox alone; it requires a provider contract and reconciliation [2].

## Backlogs, timeouts and durability boundaries

If accepted work arrives at 400 events/s and a consumer fleet can safely handle 500 events/s, there is 100 events/s of theoretical spare capacity. A ten-minute outage accumulates 240,000 events; at unchanged arrival rate, draining takes 2,400 seconds or 40 minutes. That fluid calculation assumes constant rates, enough storage, zero retries and no downstream quotas. Measure the backlog age and **attempt rate**, not only distinct event count.

Do not use unbounded retry loops or queue capacity. Expiry may be appropriate for certain notifications but unacceptable for money-moving operations; define a terminal state or human reconciliation. Preserve auditability and privacy by choosing payload retention independently from event metadata retention.

## Verify restore, concurrency and operational ownership

A robust test suite creates a file-backed temporary SQLite database, runs a separate process, kills it at controlled points, and validates rows after restart. An even stronger deployment test uses the **actual database and broker**, multi-process workers, network partitions, and documented durability guarantees. The toy examples here establish logical invariants for chosen schedules, not real distributed delivery guarantees.

Operational telemetry should expose oldest pending event, relay throughput, publication failures, duplicate count, receiver deduplication rate, outbox-to-delivery lag and terminal failures. Write a runbook that distinguishes a slow consumer from a broken relay and identifies who can safely replay messages.

## Exercises and verification

1. Point to the transaction step that guarantees an accepted order and outbox intent are committed together.
2. Explain why sending before marking can duplicate, while marking before sending can lose an event.
3. Extend the model with a fingerprint so the same client key and different body returns an explicit conflict.
4. Write a test that persists a file-backed database and reopens it after injecting an after-commit exception.
5. Recalculate backlog drain with 400 arrivals/s, 30 minutes of outage and 600 events/s after recovery.

**Related chapters:** [Asynchronous messaging](/en/topics/asynchronous-messaging/), [transactional outbox notification design](/en/topics/system-design-notifications/), [idempotent APIs](/en/topics/api-reliability/) and [production incidents](/en/topics/production-incident-response/) address related boundaries [1][2].
