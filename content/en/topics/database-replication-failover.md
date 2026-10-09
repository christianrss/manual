---
id: database-replication-failover
title: "Database Replication, Failover and Data Loss Boundaries"
description: "Explain WAL shipping, asynchronous and synchronous standby acknowledgments, replica lag, read consistency, retention slots and safe failover."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [database-storage-wal, database-consistency, raft-consensus]
sources:
  - {title: "PostgreSQL — Log-Shipping Standby Servers", url: "https://www.postgresql.org/docs/current/warm-standby.html", kind: "database documentation"}
  - {title: "PostgreSQL — Streaming Replication Protocol", url: "https://www.postgresql.org/docs/current/protocol-replication.html", kind: "database documentation"}
  - {title: "PostgreSQL — Replication Slots", url: "https://www.postgresql.org/docs/current/view-pg-replication-slots.html", kind: "database documentation"}
---
A database with one writable primary and one or more standby servers can replicate committed changes for availability and read scaling. Replication is not backup, not automatically global consensus, and not automatically lossless failover. To evaluate a design, specify when a write is acknowledged, where its log is durable, how far replicas have applied it, and which node is allowed to accept new writes after a failure. PostgreSQL's physical WAL streaming provides a concrete example [1].

## Separate log generation, transport, flush and replay

The primary produces write-ahead log (WAL) records as transactions modify database state. A streaming standby receives WAL and replays changes to reconstruct database pages. Those events are **distinct**: a log record can be generated, sent, received, durably flushed on a standby and applied for query visibility at different moments [1][2]. A byte position in the log, commonly represented by an LSN, helps compare progression. Higher receive position does not by itself prove that reads on the standby already reflect the record.

![Primary WAL production and standby receipt, flush and replay.](/diagrams/replication-lsn.svg)

For a particular transaction, choose exactly which durability boundary the client requires. A request that only needs local crash durability can use a different acknowledgment policy from one requiring a synchronously flushed remote copy. This decision changes both latency and available failure modes.

## Asynchronous replication and bounded claims

In PostgreSQL, ordinary streaming replication is asynchronous by default. A primary may acknowledge a locally committed transaction before a standby receives its WAL. If that primary fails permanently and an out-of-date standby is promoted, the promoted system may lack transactions that clients already considered successful [1]. This is a nonzero **recovery point objective** (RPO) risk, not merely a read latency issue. Real loss depends on the precise stored log positions, storage survival and failover procedure.

Replica lag can arise from transport delay, slow disk, replay conflicts or workload spikes. A single lag time number may be misleading during idle periods; verify whether it measures transport, durable flush, applied state or a wall-clock approximation. The byte gap between primary current WAL and standby applied WAL is a different quantity from elapsed replay delay, and converting bytes to seconds requires a measured workload rate.

## Synchronous replication: specify what was acknowledged

PostgreSQL synchronous replication can wait for selected standby acknowledgments according to configuration and commit mode; receipt, remote flush and apply/visibility are not interchangeable guarantees [1]. A write that waits for a standby to durably flush a WAL record is better protected against permanent primary loss than one acknowledged only locally, **assuming** the standby's durable storage survives and it is selected correctly during failover. A remote flush is not proof that every replica has applied the data or that any arbitrary read on any replica is up-to-date.

Synchronous waiting increases commit latency and can reduce write availability if required standbys cannot respond. With asynchronous mode, the primary may remain responsive but expose a potential window of acknowledged data loss. Neither option makes a complete disaster-recovery plan optional. For cross-region synchronization, physical network latency can become a substantial component of the commit budget.

## Read consistency and session guarantees

A client may write to the primary and immediately read from a standby that has not replayed the corresponding WAL. The read returns an older value even though the write completed. If the product promises **read-your-writes**, route that session to the primary or hold the read until the chosen standby has applied at least the write's LSN, with a bounded timeout and fallback policy. This is a contract at the application routing and replication layer, not a property of the HTTP API's JSON format.

A read replica can scale suitable stale-tolerant queries, but it does not necessarily allow writes, and standby queries can conflict with recovery. Caching can add further staleness beyond replica lag. Define which operations tolerate stale reads and which require an authoritative view or explicitly synchronized position.

## A small, testable replication-position model

The following program models *integer byte offsets*, not PostgreSQL's full LSN syntax or protocol. It distinguishes three monotone positions and refuses impossible ordering.

~~~python
def replica_positions(primary, received, flushed, applied):
    if not 0 <= applied <= flushed <= received <= primary:
        raise ValueError("invalid WAL position ordering")
    return {
        "receive_gap_bytes": primary - received,
        "durability_gap_bytes": primary - flushed,
        "visibility_gap_bytes": primary - applied
    }

example = replica_positions(120000, 119200, 119000, 118500)
assert example["receive_gap_bytes"] == 800
assert example["durability_gap_bytes"] == 1000
assert example["visibility_gap_bytes"] == 1500
assert replica_positions(8,8,8,8)["visibility_gap_bytes"] == 0
try:
    replica_positions(100,90,80,95)
    assert False
except ValueError:
    pass
~~~

These inequalities describe a simplified single-stream snapshot with mutually comparable positions. Actual servers can report multiple timelines, configuration changes, checkpoints and observations taken at different instants; never combine unsynchronized measurements into a guaranteed ordering. A zero lag snapshot does not prove the replica will remain caught up during subsequent writes.

## Replication slots and disk-exhaustion risk

Replication slots retain information needed by downstream consumers; in physical streaming replication they can prevent premature removal of WAL still required by a standby [1][3]. This protects continuity but creates a **resource liability**: an abandoned or stalled slot can cause WAL retention to grow until storage fills. Monitor retention by slot and set safe operational limits. The correct response to a stale slot might require resynchronizing a replica, not deleting log segments blindly.

A backup and WAL archive serve different recovery purposes from a running standby. Replication can faithfully transmit accidental deletions or application corruption to every follower. Offline/immutable backups and restore drills are needed to recover from those events. RTO (time to restore service) and RPO (acceptable lost committed data) must be independently specified; faster failover does not guarantee lower loss.

## Promotion, fencing and split brain

When the primary becomes unreachable, **unreachable is not the same as dead**. Promoting a standby while the old primary still accepts writes creates split brain and conflicting histories. Safe failover requires a mechanism that prevents the old primary from remaining writable, such as effective fencing or a properly designed authority/lease protocol, along with controlled client routing. A DNS change without reliable old-primary fencing is insufficient.

Promotion also involves choosing a standby with an appropriate durable log position, verifying timeline compatibility, and reattaching or rebuilding other replicas. An **automated** switchover needs health evidence and quorum/authority assumptions; a naïve script that promotes after a short timeout can sacrifice correctness for apparent speed.

## Worked disaster-recovery decision

Imagine primary at WAL byte position 120,000, standby applied 118,500 and standby flushed 119,000 when the primary storage is permanently lost. The standby has a 1,000-byte **durability gap** relative to that observation; it might replay 500 received-but-not-flushed bytes only if they actually survived, which must not be assumed. The logical consequences for transactions depend on record boundaries and which transactions had been acknowledged, not simply the number of bytes. A valid incident report distinguishes *estimated potential loss* from confirmed lost transactions.

| Scenario | Risk | Explicit safeguard |
| --- | --- | --- |
| Async primary permanently lost | Acknowledged writes absent on standby | Defined RPO and WAL/backups |
| Replica query shortly after write | Stale data | LSN wait or primary read |
| Required sync standby disconnected | Write stalls | Document degraded-mode decision |
| Standby slot abandoned | WAL fills disk | Slot retention monitoring |
| Former primary still writable | Diverging timelines | Fence before promotion |

## Exercises and verification

1. Explain why standby WAL **received** is not necessarily visible to queries.
2. Under async replication, construct a timeline where an acknowledged transaction is absent after failover.
3. With primary 10,000, flush 9,900 and replay 9,700, calculate gaps and identify which one directly affects read visibility.
4. Design read-your-writes routing after a write and describe timeout/fallback when the replica never catches up.
5. Justify why failover automation must fence the former primary before sending writable traffic to a promoted standby.

**Related reading:** [WAL and storage pages](/en/topics/database-storage-wal/), [consistency models](/en/topics/database-consistency/) and [Raft consensus](/en/topics/raft-consensus/) address different layers of the durability and authority problem.
