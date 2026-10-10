---
id: postgresql-concurrency-integration
title: "PostgreSQL Integration Lab: Concurrent Reservations and Crash Recovery"
description: "Use independent processes and a real PostgreSQL service to test conditional stock updates, idempotency and durable outbox commits."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [sqlite-multiprocess-recovery, transactional-indexing-isolation]
sources:
  - {title: "PostgreSQL — Transaction Isolation", url: "https://www.postgresql.org/docs/current/transaction-iso.html", kind: "official database documentation"}
  - {title: "Amazon Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
---
PostgreSQL concurrency is a **property of transactions and their shared authority**, not of an application's in-process lock. Two separate API processes can both observe an apparently available product unless the write itself enforces the inventory invariant. This workshop builds on the SQLite multiprocess exercise but replaces the embedded database with a **real PostgreSQL 17 service container** in CI. The accompanying executable source runs as independent Python processes and uses a PostgreSQL transaction for the reservation and its outbox intent [1][2].

## Contract and safety property

One stock row holds three available units of SKU `seat`. Two independent customers each attempt to reserve two units, using different operation keys. Exactly one may succeed; the other must receive `insufficient`, and **available must never become negative** after a committed reservation. An accepted request must store one reservation and one corresponding outbox intent in the same transaction. When a client retries an accepted key with the same quantity, it receives `replayed`. Reusing a key with a different quantity is an error.

This example deliberately does not persist unsuccessful `insufficient` outcomes as idempotency records. That distinction matters if stock is replenished: the same previously rejected operation may succeed on a later attempt. A production contract may instead persist an explicit terminal rejection, scoped by authenticated tenant and canonical request fingerprint.

## Why SELECT then UPDATE can be unsafe

A naive implementation selects `available=3`, sees enough for quantity two, and later updates the stock without a conditional guard. Another transaction may make the same observation before the first commits. If both decisions are treated as independent, they could authorize four units from three. Merely putting a SELECT and UPDATE in the same transaction does not automatically prove safety under every isolation level; check the database's actual concurrent update semantics [1].

Our implementation uses the conditional statement below. Under PostgreSQL's **READ COMMITTED** behavior, a concurrent UPDATE waits for a conflicting row update, then re-evaluates the update condition against the current row version as documented by PostgreSQL [1].

~~~sql
UPDATE stock
SET available = available - $1
WHERE sku = 'seat' AND available >= $1
RETURNING available;
~~~

Zero returned rows means insufficient stock. This row-level condition and a database CHECK constraint jointly protect the stock property. The transaction also inserts the reservation and outbox intent so that an accepted order cannot commit without its event intent.

## Operation keys and concurrent retries

A unique `reservations(op_key)` constraint must cover the same request identity as the API contract. The example **inserts the reservation key first**, using `ON CONFLICT DO NOTHING RETURNING`. If another process is already inserting the same key, PostgreSQL resolves the uniqueness race; the losing caller then reads the previously committed quantity and returns `replayed` or a payload conflict. This avoids relying on a process-local lookup followed by an unprotected INSERT.

For distinct keys, the later conditional stock UPDATE serializes the conflict on the stock row. If the update fails, the whole transaction rolls back, including the provisional reservation key. That makes the reservation record and outbox intent consistent with stock. The database is the authority for these invariants—not the worker's memory, a cache or an event broker.

![Two independent PostgreSQL clients compete for a conditional stock update inside their transactions.](/diagrams/postgres-concurrency-integration.svg)

## Reproduce the test against an actual server

The complete source is [examples/python/postgres_checkout.py](https://github.com/christianrss/manual/blob/main/examples/python/postgres_checkout.py). The integration test [tests/test_postgres_integration.py](https://github.com/christianrss/manual/blob/main/tests/test_postgres_integration.py) creates a fresh schema per test, initializes the stock row, then launches two independent operating-system processes with the `subprocess` module. It verifies that the multiset of results is one `accepted` and one `insufficient`, followed by stock one, one reservation and one outbox row.

Unlike a mocked repository, the test sends SQL through separate PostgreSQL connections to a running server. However, it captures a finite set of executions rather than all possible schedules. The correctness argument also relies on atomic row UPDATE, transactional inserts and uniqueness constraints. The test is a regression check that these guarantees are being used as intended.

## Crash after commit: ambiguous response, durable answer

A second test starts a worker that commits a reservation and then exits with `os._exit(23)` before writing an HTTP-like response. Another process repeats the same operation key and gets `replayed`; a new connection confirms the stock and outbox rows remain. This demonstrates **process-exit recovery after commit** in the CI environment, not resilience to arbitrary disk corruption, loss of the database host, network partitions or misconfigured replication.

The same mechanism explains why a client timeout is not evidence that an operation failed. Sending a fresh operation key after a timeout can create another logical request. With an external payment provider, a PostgreSQL transaction still cannot atomically include the provider's independent state: it needs provider idempotency and reconciliation [2].

## Estimate contention and identify the bottleneck

Assume a **hypothetical** 600 reservations/s on one hot SKU, with each stock-row critical section taking a measured 2 ms on average. A single serialized resource whose service time truly remains 2 ms has a nominal upper limit near 500 updates/s; arrivals at 600/s would make its queue grow if sustained, ignoring implementation overhead and changes in service time.

~~~python
def nominal_capacity_per_second(critical_ms):
    if critical_ms <= 0:
        raise ValueError("positive critical section required")
    return 1000.0 / critical_ms

assert nominal_capacity_per_second(2) == 500.0
assert nominal_capacity_per_second(4) == 250.0
~~~

This is a **single-resource bottleneck approximation**, not a PostgreSQL benchmark. In reality, lock wait, IO, transaction overhead and varying work affect throughput. Sharding users across processes cannot parallelize updates to the **same hot stock row** without changing the business allocation model. Possible approaches include warehouse-local quotas, reserved inventory pools or a changed oversell/backorder policy, each with explicit trade-offs.

## CI, limitations and failure table

The GitHub Actions build provisions PostgreSQL using a Linux service container, installs the PostgreSQL Python driver, runs the normal editorial and article-example tests, and then discovers the integration tests. The workflow deliberately requires the database: on CI, a broken connection causes failure. Local developers can run the tests with `POSTGRES_DSN` pointing to their own disposable database; without that variable the integration class is skipped outside CI.

| Scenario | Protected property | Not proven |
| --- | --- | --- |
| Two processes reserve two of three | No oversell in the exercised database | Arbitrary distributed failover |
| Same accepted key retries | One reservation and outbox intent | Cross-tenant identity scoping |
| Same key, different quantity | Conflict rather than silent reuse | Full payload canonicalization |
| Process exits after commit | Retry reads durable committed state | Power-loss durability settings |
| Hot SKU under high traffic | Single-row atomicity | Acceptable latency at any scale |

Do not mistake a green integration test for a guarantee of exactly-once delivery to a queue or payment provider. It establishes a real database boundary and its tested failure behavior; subsequent components need their own evidence.

## Exercises and verification

1. Explain why checking stock in the UPDATE predicate changes the concurrency argument compared with a preliminary SELECT.
2. Trace two identical operation keys arriving simultaneously and locate where the unique constraint resolves the race.
3. Modify the quantity from two to one and derive how many of three distinct requests can succeed.
4. Describe a realistic failure that `os._exit(23)` does not simulate and the additional infrastructure necessary to test it.
5. Propose a benchmark for one hot row that records contention, lock-wait percentiles and errors—not merely aggregate throughput.

**Related chapters:** [Transaction isolation](/en/topics/transactional-indexing-isolation/), [SQLite multiprocess lab](/en/topics/sqlite-multiprocess-recovery/), [order system design](/en/topics/system-design-order-service/) and [fault injection](/en/topics/failure-recovery-workshop/) provide context.
