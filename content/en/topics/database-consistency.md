---
id: database-consistency
title: "Transactions, Isolation and Distributed Consistency"
description: "Distinguish ACID isolation, serializability, linearizability, replication lag and practical consistency anomalies using explicit operation histories."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [complexity-analysis, caching]
sources:
  - {title: 'PostgreSQL — Transaction Isolation', url: 'https://www.postgresql.org/docs/current/transaction-iso.html', kind: official database documentation}
  - {title: 'Jepsen — Consistency Models', url: 'https://jepsen.io/consistency/models', kind: technical reference}
---
A distributed application can return a response while other components have not yet observed the same state. Correct architecture begins by distinguishing **database transaction isolation**, **replica freshness**, and **distributed object consistency**. These are related but not identical requirements [1][2].

## Transactions and anomalies
Atomicity means the effects of a transaction commit together or none commit; isolation controls what concurrent transactions can observe. Durability concerns survival of committed data under the defined failure model. Database products differ in how isolation levels are implemented, so verify each engine's actual guarantees rather than relying on names alone [1].

Consider two transactions reading balance 100 and each subtracting 80 based on that initial read. If both later overwrite the balance with 20, one debit can be lost. This is a **lost update** unless prevented by locking, atomic updates, version checks or stronger isolation.

```sql
-- Example: enforce sufficient funds using one atomic statement.
UPDATE accounts
SET balance = balance - 80
WHERE id = 42 AND balance >= 80;
-- Accept success only if exactly one row was updated.
```

This query expresses the constraint within the database update, but full payment correctness still needs transaction boundaries, idempotency, auditability and a policy for concurrent operations across multiple accounts.

## Serializable is not the same as linearizable
**Serializability** says concurrent *transactions* behave like some serial execution, but does not necessarily preserve real-time order across transactions. **Linearizability** is a real-time constraint often stated for operations on a single logical object: an operation appears atomic between its call and response, respecting the order of non-overlapping operations [2].

For example, if write `x=1` completes before another client begins reading `x`, a linearizable register cannot let that read return the earlier value 0. A lagging replica may do exactly that, unless routing and synchronization enforce an appropriate freshness guarantee. The server may still provide other useful properties, such as eventual convergence, but these must be named explicitly.

## Replication and correctness requirements
Replication improves fault tolerance and can scale reads, but a replica introduces propagation delay. A **read-after-write** requirement might be satisfied by reading from the primary after a user's write, using a version token, or waiting for the relevant replica to catch up. The right mechanism depends on the requested guarantee and measured latency budget.

| Requirement | Example | Consequence |
| --- | --- | --- |
| Eventual convergence | Public like counts | May tolerate briefly stale reads |
| Read your writes | User edits own profile | Must see own committed changes |
| Serializable transactions | Multi-row invariants | Higher coordination or abort/retry cost |
| Linearizable object | Unique resource reservation | Must respect real-time order; availability trade-offs |

Do not invoke CAP as a slogan. CAP speaks about impossible simultaneous guarantees in a particular asynchronous partition model; it does not say that every database is simply "CP" or "AP" for every operation.

## Failure modes and design procedure
1. Write down the invariant, for example: no two confirmed reservations for the same seat.
2. Identify the authority responsible for enforcing it.
3. Specify what response means "committed" and how retried requests are identified.
4. Test concurrent write histories, replica lag and network partitions rather than only sequential examples.
5. Separate the transaction boundary from downstream side effects such as email; event publishing needs a deliberate coordination mechanism.

## Exercises and verification
1. Two writers both observe `version=8`. Describe an update with `WHERE version=8` and why checking the affected row count rejects one stale write.
2. Give a history where an asynchronously replicated read returns old data immediately after a successful write; identify which consistency guarantee is violated.
3. Explain why an ACID transaction in database A does not automatically make a separate queue publish atomic.

Correctness follows the invariant and the failure model. Technology labels are secondary to those definitions.
