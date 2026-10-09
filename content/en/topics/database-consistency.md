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


![Two concurrent transactions each disable a different on-call doctor after observing both doctors active, causing write skew.](/diagrams/database-consistency-invariant.svg)

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

## Two levels of concurrency that must not be confused

Within one database, **transaction isolation** controls anomalies between concurrent transactions. Between nodes or replicated services, a **consistency model** describes which histories of reads and writes are permitted. The word 'strong' alone specifies neither. Serializability concerns an ordering equivalent to some serial transaction execution; **strict serializability** additionally respects real-time precedence. Linearizability applies a real-time atomicity condition to operations on an object. Each guarantee must be attached to a specific interface and failure model [1][2].

## Derive write skew with a concrete invariant

Suppose two doctors, A and B, are on call. The invariant is **at least one doctor must remain on call**. Each transaction reads both rows and sees A=true, B=true. Transaction T1 turns A off; T2 turns B off. If their isolation allows both to commit based on the same snapshot without detecting the cross-row constraint, the final state is A=false, B=false. There were no writes to the same row, so preventing only *lost updates* is insufficient. An enforcement mechanism may use a serializable execution with proper retry handling, or a schema/locking strategy encoding the invariant [1].

## MVCC, isolation levels and actual database behavior

Multi-version concurrency control (MVCC) allows readers and writers to observe different committed versions according to transaction snapshots. It improves some concurrency patterns but does **not** imply serializability by itself. PostgreSQL's Repeatable Read provides a stable snapshot with its documented guarantees; Serializable adds protection against serialization anomalies and may abort transactions with a serialization failure. Applications must safely retry such transactions when appropriate [1].

| Requirement | Failure if missing | Candidate mechanism |
| --- | --- | --- |
| Do not overwrite a newer version | Lost update | Conditional update on version |
| At least one resource remains active | Write skew | Serializable or invariant-preserving locks/constraints |
| Read must observe a completed write | Stale replica read | Authoritative read or version-based synchronization |
| Effect across DB and broker | Partial publication | Transactional outbox plus idempotent consumer |

## A history and a counterexample

Client A completes write `x=1` at time `t1`; client B starts read at `t2>t1` and receives `0` from a lagging replica. This violates linearizability of a single logical register under the assumption that the completed write promised visibility. The same history might be permitted by an eventually consistent read model. If the service instead promises 'read your own writes' **only within a sticky session**, another client's stale observation might remain allowed. Clearly scope the guarantee [2].

## Distributed transactions and the dual-write problem

Saving an order in a database and publishing its event to a broker are two distinct side effects. If the database commits before the publish and the process crashes, the event may be missing. If the event is published first and the database later rolls back, consumers may act on nonexistent business state. An **outbox** writes the business change and event record in the *same local transaction*; a publisher later sends the event, possibly more than once, and the consumer must be idempotent. This is not a magical global atomic transaction and does not automatically provide total ordering across partitions.

## Verification through adversarial histories

Write down operations with invocation time, response time, keys and observed values. Test simultaneous operations with barriers, replica delays and induced disconnects; compare histories to the actual promised model instead of judging solely by final values. For critical unique reservations, enforce a durable uniqueness constraint, not a read-then-write 'availability check'. A test with two sequential clients cannot reveal concurrency anomalies. Consistency is an application contract, not a marketing property of a database.

## Exercises and verification
1. Two writers both observe `version=8`. Describe an update with `WHERE version=8` and why checking the affected row count rejects one stale write.
2. Give a history where an asynchronously replicated read returns old data immediately after a successful write; identify which consistency guarantee is violated.
3. Explain why an ACID transaction in database A does not automatically make a separate queue publish atomic.

Correctness follows the invariant and the failure model. Technology labels are secondary to those definitions.
