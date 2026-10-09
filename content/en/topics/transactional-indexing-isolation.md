---
id: transactional-indexing-isolation
title: "Transactional Indexes: MVCC, Uniqueness and Serializable Isolation"
description: "Explain unique constraints under concurrency, multi-version indexes, predicate locking, write skew, isolation retries and indexing trade-offs."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [database-consistency, sql-query-planning, database-storage-wal]
sources:
  - {title: "PostgreSQL — Transaction Isolation", url: "https://www.postgresql.org/docs/current/transaction-iso.html", kind: "official database documentation"}
  - {title: "PostgreSQL — Indexes and MVCC", url: "https://www.postgresql.org/docs/current/indexes-index-only-scans.html", kind: "official database documentation"}
  - {title: "PostgreSQL — Unique Indexes", url: "https://www.postgresql.org/docs/current/indexes-unique.html", kind: "official database documentation"}
---
An index is not merely a shortcut for SELECT. In a transactional database it participates in insertions, deletions, version visibility and enforcement of constraints. **Concurrency correctness** depends on transaction isolation and database rules, not on executing a fast preliminary query. PostgreSQL offers a useful concrete system: MVCC permits concurrent snapshots, unique indexes coordinate conflicting keys, and Serializable isolation can abort transactions that would otherwise exhibit nonserializable behavior [1][3].

## Separate three independent questions

An index answers: **where might the relevant tuple be?** A visibility rule answers: **is the tuple version visible to this transaction?** A constraint answers: **may the database commit this logical change?** An index scan does not automatically answer all three. A tuple located by a B-tree may be invisible under the querying snapshot; an index-only scan may still need heap visibility checks [2].

A uniqueness constraint is a durable invariant maintained under concurrent modifications, not the query `SELECT NOT EXISTS(...)` executed before a separate INSERT. Two clients can both observe the absence of a key and race to insert it. Only a uniqueness-enforcing database mechanism, or another explicitly correct serialization protocol, makes the invariant robust.

## The time-of-check/time-of-use counterexample

Suppose two transactions T1 and T2 each query `SELECT 1 FROM reservations WHERE seat_id=7` and both see no rows. They then both attempt to reserve seat 7. Without a unique constraint on the appropriate business key, both transactions might commit, violating 'one active reservation per seat'. Putting the check inside an ordinary transaction is **not enough** at every isolation level; the interleaving and allowed anomalies matter [1].

![Two transactions race over the same business key; uniqueness resolves the conflict.](/diagrams/transaction-unique-race.svg)

A unique constraint on seat_id (or a correctly specified partial unique index for **active** reservations) makes the database arbitrate the conflict. One insert may block, fail or require an application retry depending on the competing transaction outcome and statement. Your API must translate the error into a meaningful domain response, not assume the first transaction always wins.

## Uniqueness and null/multi-column semantics

A composite unique index covers a tuple of key values; choosing `(tenant_id, external_id)` instead of `external_id` controls the boundary of uniqueness. Under the common SQL semantics supported by PostgreSQL, NULLs in unique keys can be treated as distinct unless an explicit alternative is selected. Thus `UNIQUE(email)` does not necessarily mean 'there is only one row without email'. Review nullability, case normalization, collation and active/inactive status before claiming the invariant [3].

An active-seat reservation constraint may use a PostgreSQL partial unique index on `seat_id WHERE status IN ('pending','confirmed')`; this expresses one active booking at most. It does not ensure a positive balance, valid transition sequence or tenant authorization. Database constraints protect **particular** invariants and should complement application-level validation.

## MVCC does not remove write skew

Under snapshot-based isolation, two transactions can read the same older state and modify **different rows**, each passing a local check while jointly violating an invariant. Example: two doctors are on call. Each transaction checks that at least one doctor remains, then independently takes one doctor off duty. If both commit, nobody is on call. The distinct write keys mean protecting only duplicate writes to the **same** index entry does not eliminate this anomaly [1].

PostgreSQL's Serializable mode uses Serializable Snapshot Isolation mechanisms, including predicate-lock information to detect patterns dangerous for serializability. This can cause one transaction to receive a serialization failure rather than commit a nonserializable history. Such failures require a safe **retry of the entire transaction**, including all reads and decisions, when business semantics permit [1].

## Concrete SQL and its boundaries

~~~sql
CREATE TABLE reservations (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  seat_id BIGINT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'cancelled'))
);
CREATE UNIQUE INDEX one_active_seat
  ON reservations (tenant_id, seat_id)
  WHERE status IN ('pending', 'confirmed');

BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;
INSERT INTO reservations (tenant_id, seat_id, status)
VALUES (10, 7, 'pending');
COMMIT;
~~~

This SQL is a PostgreSQL illustration, not code executed by the manual's Python CI. It assumes seats are uniquely identified **within each tenant**; if one physical seat is shared by tenants, the key must instead represent global identity. If an application also writes an outbox event, insert it in the same local transaction, and use durable idempotency to handle retried API calls.

## Model the constraint with executable code

The following function tests the **logical key selection**, not SQL locking or transaction execution. It deliberately treats pending and confirmed as active. A real database remains the authority.

~~~python
ACTIVE = {"pending", "confirmed"}

def active_keys(bookings):
    keys = set()
    for row in bookings:
        if row["status"] not in ACTIVE:
            continue
        key = (row["tenant"], row["seat"])
        if key in keys:
            return None
        keys.add(key)
    return keys

valid = [
    {"tenant":10, "seat":7, "status":"pending"},
    {"tenant":10, "seat":7, "status":"cancelled"},
    {"tenant":11, "seat":7, "status":"confirmed"},
]
assert active_keys(valid) == {(10, 7), (11, 7)}
assert active_keys(valid + [
    {"tenant":10, "seat":7, "status":"confirmed"}
]) is None
~~~

For real concurrent clients, test against a database with separate connections and a barrier so both transactions attempt the same invariant simultaneously. Sequential Python set checks cannot reproduce the timing, locks, constraint conflicts and serialization errors of the server.

## Cost and maintenance of indexes

Indexes consume disk, WAL bandwidth and CPU on writes. An UPDATE may create a new tuple version and require index maintenance depending on which indexed values change and whether HOT update conditions hold. An index-only scan is contingent on both covered columns and visibility-map conditions, not merely a query containing an indexed column [2]. A selective index can accelerate reads but may also create contention for a hot key.

Unique indexes should be chosen to encode stable domain identities, while ordinary indexes should be selected using actual query plans and workload. An index on every column is not a universal optimization: insert rate, vacuum load, page splits and backup volume must be measured.

## Retry, idempotency and isolation trade-offs

Serialization failures can be expected under Serializable isolation, particularly when concurrent operations contend. Retrying must repeat all logic in the transaction under a new snapshot. Do **not** send a non-idempotent external charge inside a transaction that might be retried, unless the external side effect has its own stable idempotency and reconciliation mechanism. A retry after uniqueness violation may mean another request already booked the seat, not a transient problem to repeat forever.

| Requirement | Suitable mechanism | Limitation |
| --- | --- | --- |
| No duplicate active seat per tenant | Partial unique index | Predicate/key must match real invariant |
| Prevent write skew | Serializable or explicit invariant-preserving locks | Retries and contention |
| Speed selective reads | B-tree | Still needs visibility and cost assessment |
| Exactly one external charge | Durable idempotency at provider and domain | Not solved by local SQL alone |

## Exercises and verification

1. Demonstrate two read-then-insert transactions that both see no row; explain which constraint stops duplicate commits.
2. Change uniqueness to cross-tenant/global seats and identify the correct index key.
3. Explain why two-row write skew can occur without a direct uniqueness conflict.
4. Why must a serialization failure repeat the **whole** transaction rather than only its last UPDATE?
5. Outline concurrent database integration tests proving active-seat uniqueness, rejected duplicates and retry policy.

**Related chapters:** [Consistency](/en/topics/database-consistency/), [Storage/MVCC](/en/topics/database-storage-wal/) and [Query planning](/en/topics/sql-query-planning/) explain different facets of the same transaction.
