---
id: postgresql-streaming-promotion
title: "PostgreSQL Physical Replication Lab: Standby Replay and Manual Promotion"
description: "Exercise real PostgreSQL 17 primary/standby replication using pg_basebackup, observe replay, stop the primary and promote the standby."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [database-replication-failover, postgresql-concurrency-integration]
sources:
  - {title: "PostgreSQL 17 — pg_basebackup", url: "https://www.postgresql.org/docs/17/app-pgbasebackup.html", kind: "official database documentation"}
  - {title: "PostgreSQL 17 — Log-Shipping Standby Servers", url: "https://www.postgresql.org/docs/17/warm-standby.html", kind: "official replication documentation"}
  - {title: "PostgreSQL 17 — Failover", url: "https://www.postgresql.org/docs/17/warm-standby-failover.html", kind: "official failover documentation"}
---
PostgreSQL replication can preserve data on a **standby** and allow a controlled **promotion**, but neither operation automatically solves primary election, application reconnection, split-brain prevention or transaction loss. This laboratory builds a real PostgreSQL 17 primary and physical standby in separate Docker containers, creates the standby using `pg_basebackup -R`, verifies that a specific committed row has been replayed, stops the original primary, promotes the standby, and commits a new row on the promoted server. It is a measured failover **building block**, not a turnkey high-availability platform [1][2].

## Scope and failure contract

Two PostgreSQL processes run in isolated containers on a Docker network, with separate named data volumes. The initial primary is the only writable database; the standby is read-only while `pg_is_in_recovery()` is true. A record with ID one is committed on the primary, and the test **waits until a query on the standby returns that exact record** before stopping the primary. This waiting step is essential: under asynchronous streaming replication, a committed change may not yet be replayed on standby [2].

The failover operation is explicitly **manual**. The test does not run Patroni, repmgr, an external leader-election service or a client-side failover proxy. Promotion only occurs after the script has stopped the old primary, avoiding two writers in the tested scenario. It does not establish automatic fencing or protection against an old server unexpectedly returning on an independent network.

## Prepare the physical replica

The script starts a disposable PostgreSQL primary with `wal_level=replica` and enough WAL sender slots for a physical base backup. The primary permits replication connections from the isolated network. A new data volume is initialized by `pg_basebackup`, which copies the primary cluster and, with `-R`, writes `standby.signal` and connection settings instructing the standby to follow the upstream server [1].

![Physical PostgreSQL standby replays the primary's WAL before manual promotion.](/diagrams/postgresql-streaming-promotion.svg)

Physical replication works at database-cluster level, not as a message-by-message copy of application API calls. WAL records carry database changes, and standby replay makes them visible once applied. `pg_basebackup` must run against a compatible PostgreSQL server, and a production implementation needs correct authentication, storage permissions, retention of WAL segments and monitoring of replication lag [1][2].

## Observe replay rather than assume it

After the standby is running, the test first verifies `pg_is_in_recovery()` is true. Then it creates a probe table on the primary and inserts one marker row. It repeatedly queries the standby until it sees the **expected payload**. That is stronger than merely checking whether port 5432 is reachable or whether a replication connection exists: it proves this particular transaction became visible to the standby.

The check is still **not a general zero-data-loss guarantee**. A later transaction may commit on the asynchronous primary but not reach the standby before a sudden primary failure. The test deliberately waits for one known record, and only that record's replay is established. Synchronous replication with appropriate commit and standby settings can provide stronger acknowledgment conditions, but it imposes its own availability and latency costs [2][3].

## Stop the old primary and promote the standby

Once the row is visible, the test issues `docker stop` against the primary container. It then calls PostgreSQL's `pg_promote(true, 40)` on the standby. The successful return should indicate promotion completed within the supplied wait period; a subsequent `pg_is_in_recovery()` check must be false. The test inserts another row, proving that the promoted server can now execute writes.

The two-row verification matters: the old row confirms **previously replayed data survived**, while the new row confirms **write authority was established on the new primary**. It does not prove client traffic was automatically rerouted or that the application was available throughout the transition. Explicit downtime and endpoints are visible in this exercise.

## Reproduction and CI evidence

The executable [scripts/verify_postgres_promotion.py](https://github.com/christianrss/manual/blob/main/scripts/verify_postgres_promotion.py) provisions PostgreSQL 17 containers, copies data using the real `pg_basebackup` binary, queries both servers through psycopg, performs a manual promotion and cleans up containers, volumes and network in a `finally` block. The GitHub Actions workflow runs this lab on its disposable Linux Docker runner **after normal unit and integration tests**.

It requires Docker permissions and a disposable environment. It intentionally stops a database process, so it must not be pointed at a shared production cluster. The test does not copy application credentials, data or user files into the public repository. The account, password and marker exist only inside ephemeral CI infrastructure.

## Reason about committed writes and replica lag

If the primary commits 100 writes/s and the standby briefly falls ten seconds behind, up to approximately 1,000 writes may be pending for replay, **under that simplified constant-rate model**. A standby that has replayed some but not all of those writes cannot be treated as a universal durable replacement for the latest committed primary state.

~~~python
def approximate_unreplayed_writes(rate_per_second, lag_seconds):
    if rate_per_second < 0 or lag_seconds < 0:
        raise ValueError("nonnegative rates and lag required")
    return rate_per_second * lag_seconds

assert approximate_unreplayed_writes(100, 10) == 1000
assert approximate_unreplayed_writes(0, 100) == 0
~~~

This is a capacity illustration rather than PostgreSQL's exact WAL lag metric. Actual lag depends on bytes, network throughput, WAL generation and replay costs. Monitor commit, write, flush and replay LSN distances as appropriate; distinguish latency from the count of business transactions [2].

## Split brain and fencing are separate requirements

A real primary might become unreachable from a failover controller while continuing to accept writes from some clients. Promoting a standby during that partition can create **two conflicting primaries**, known as split brain. A production failover design needs **fencing** or equivalent robust leadership control so the old primary cannot resume writes when a new primary has been promoted [3].

An old primary cannot simply rejoin as a standby using its earlier timeline and data directory. Rejoin typically involves reinitialization from the new primary or appropriate recovery tooling, with timeline and WAL history handled correctly. This exercise intentionally destroys the disposable volumes afterward rather than implementing a potentially unsafe rejoin protocol.

## Failure matrix and engineering review

| Scenario | Observed or required property | Test coverage |
| --- | --- | --- |
| Standby starts | It reports in recovery | Actual SQL assertion |
| Marker committed on primary | Row becomes visible on standby | Actual replay observation |
| Old primary deliberately stops | No concurrent writer in this schedule | Docker stop, not fencing |
| Standby promoted | Recovery ends and new insert commits | Actual promotion |
| Sudden primary power failure | Unknown unreplicated commits | Not tested |
| Network partition | Potential split brain without fencing | Not tested |
| Automatic client reconnection | Needs routing and discovery | Not tested |

## Exercises and verification

1. Explain why successful `pg_basebackup` does not itself show that the standby is caught up after new transactions.
2. Compare asynchronous and synchronous commit policies and their possible effect on write availability.
3. Define a safe fencing mechanism and show which failure it prevents during promotion.
4. Extend the script to measure replay-LSN lag without interpreting a byte count as a transaction count.
5. Describe steps necessary to rejoin the old primary after the standby has accepted new writes on a different timeline.

**Related chapters:** [Database replication and failover](/en/topics/database-replication-failover/), [transaction isolation](/en/topics/transactional-indexing-isolation/), [PostgreSQL concurrency lab](/en/topics/postgresql-concurrency-integration/) and [incident response](/en/topics/production-incident-response/) supply surrounding concepts [1][2][3].
