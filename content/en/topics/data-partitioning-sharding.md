---
id: data-partitioning-sharding
title: "Data Partitioning and Sharding: Keys, Hotspots and Rebalancing"
description: "Design partitions and shards from access patterns, quantify hotspots, model stable hashing, handle migration and global constraints."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [system-design-process, database-consistency, database-replication-failover]
sources:
  - {title: "DynamoDB — Best practices for partition keys", url: "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html", kind: "official vendor documentation"}
  - {title: "PostgreSQL — Table partitioning", url: "https://www.postgresql.org/docs/current/ddl-partitioning.html", kind: "official database documentation"}
  - {title: "Google SRE Workbook — Implementing SLOs", url: "https://sre.google/workbook/implementing-slos/", kind: "engineering workbook"}
---
**Partitioning** assigns subsets of data to distinct storage units; **sharding** commonly refers to distributing those subsets across independent database nodes or instances. The objective is to scale reads, writes, storage or operational management while preserving data ownership and access correctness. Adding shards does not make an individual hot key faster, does not automatically increase availability, and does not solve cross-shard transactions. The correct design follows access patterns, skew and consistency requirements—not a predetermined number of database servers [1].

## Clarify physical partitions versus shards

A relational database can divide one logical table into partitions **within the same database system**, for example by month. PostgreSQL supports declarative range, list and hash partitioning; query **partition pruning** can skip physical partitions whose bounds cannot satisfy a filter [2]. This can improve management and some workloads, but it is not the same as placing customer records across independently operated database clusters.

A distributed sharding layer maps each entity to a particular storage authority. The mapper may be part of application code, a database router or the datastore itself. A client should not choose arbitrary shard identity and thereby bypass tenant authorization. Data locality decisions must be stable and reproducible across services or mediated by one authoritative routing layer.

## Design by query shape and cardinality

Suppose a multi-tenant notes service frequently performs (1) read by note ID **within tenant**, (2) list newest notes within tenant, and (3) write notes for one tenant. Sharding by tenant_id helps localize operations for a tenant and can support transactional invariants inside that tenant's shard. But one unusually large tenant may dominate traffic and become a **hot shard**. A random note-ID hash spreads writes more evenly, but owner-scoped lists now need to query several shards and merge results.

Range sharding by creation time helps prune old archive data but concentrates today's writes in the latest range—a **moving hotspot**. Hashing distributes keys if their workload is not too skewed; hashing tenant_id still sends every operation for one tenant to the same shard. Cloud database documentation explicitly warns that low-cardinality keys and uneven read/write activity can create hot partitions even when total capacity remains available [1].

![Partitioning routes keys to data authorities; a hot key can remain skewed.](/diagrams/sharding-key-distribution.svg)

## Capacity model and its falsifiable assumptions

Imagine a **hypothetical** workload peaking at 6,000 writes/s. Load tests find each independent shard can safely sustain 1,000 writes/s with the intended record size, indexes and latency target. Under perfectly even distribution, at least six active shards are needed; reserve a seventh if you require the system to tolerate losing one shard **and** have a proven failover/rebalancing plan. This arithmetic describes theoretical aggregate capacity, not an availability guarantee.

Now assume one tenant alone produces 3,000 writes/s. Tenant-based sharding sends all 3,000 to its home shard, exceeding the measured safe 1,000 writes/s capacity. Increasing shard count from 7 to 14 does not spread that tenant automatically. You need to change the partition key—perhaps (tenant_id, bucket)—or isolate that tenant with its own capacity, queue/admission controls or a different storage plan. The read path then needs scatter/gather across buckets or a derived index.

## Key distribution strategies and trade-offs

| Choice | Benefit | Cost or failure case |
| --- | --- | --- |
| Hash(tenant_id) | Local tenant transactions and lists | One large tenant stays hot |
| Hash(note_id) | Potentially uniform per-note activity | Tenant listing scatters |
| Range(created_at) | Time-bound archival/pruning | Current write hotspot |
| (tenant_id, bucket) | Split heavy tenant traffic | Scatter reads and ordered merge |
| Directory mapping tenant→shard | Explicit placement and relocation | Directory availability and updates |

A shard count should be estimated from **observed peak I/O and hot-key distribution**, not only total bytes. Include indexes, replication, backfills, transaction coordination and operational failure domains. Physical disk may increase well before average CPU is saturated, or vice versa.

## Why changing a simple modulo map is disruptive

A naïve mapping shard=hash(key) % N is deterministic for fixed N but changing N typically remaps many existing keys. The data do not teleport when routing changes: until records have been copied and writes reconciled, requests can be routed to nodes that do not contain the latest value. Python's built-in hash() is also deliberately unsuitable as a stable external shard assignment across processes in general because its randomized seed and type behaviors can vary.

**Rendezvous hashing** scores each (key,node) pair with a stable hash and chooses the highest-scoring node. When adding a new node, a key either stays on its previous highest-scoring node or moves to the new node. This property reduces movement relative to a broad modulo remap, although real traffic balancing depends on key frequency and node weights.

~~~python
from hashlib import sha256

def owner(key, nodes):
    if not nodes:
        raise ValueError("at least one node required")
    if len(set(nodes)) != len(nodes):
        raise ValueError("node identifiers must be distinct")
    def score(node):
        raw = (str(key) + "|" + str(node)).encode("utf-8")
        return int.from_bytes(sha256(raw).digest(), "big")
    return max(nodes, key=score)

before = ["s0", "s1", "s2", "s3"]
after = before + ["s4"]
keys = [f"note-{n}" for n in range(1000)]
changed = [k for k in keys if owner(k, before) != owner(k, after)]
assert 0 < len(changed) < len(keys)
assert all(owner(k, after) == "s4" for k in changed)
assert all(owner(k, before) == owner(k, after) for k in keys if k not in changed)
assert owner("fixed", before) == owner("fixed", before)
~~~

The demonstration models routing **only**. Its concatenation with a pipe delimiter is unsafe for ambiguous unconstrained identifier formats in a real protocol: encode keys and nodes with length prefixes or canonical structured serialization. A production router also needs versioned membership, stable key encoding, weighted nodes, failure handling and migration tooling. Consistent placement does not itself copy records or replicate writes.

## Resharding is a data migration protocol

A safe redistribution needs an explicit **source of truth** during migration. One workable plan is: create target capacity; snapshot source ranges; copy records with version metadata; capture intervening mutations through a durable change stream; verify counts, checksums and key-level versions; drain or redirect writes using a controlled cutover barrier; switch routing generation; and retain a rollback plan. Dual writes without idempotency or an ordering protocol can diverge, especially during crashes.

The cutover condition must prevent an older copied value from overwriting a newer mutation. Use monotonically increasing versions or a proven transactional/stream offset guarantee inside the chosen data model. Publish metrics for copy lag, unresolved conflicts, duplicate processing and query errors. Changing the mapping table without verified data movement is not resharding—it is an outage.

## Uniqueness, joins and transaction boundaries

A database's UNIQUE index normally protects keys **within its own authority**. If the business requires globally unique usernames but users reside on different shards, local UNIQUE(username) indexes cannot enforce that global invariant by themselves. Options include a separate globally authoritative name registry, a placement rule derived from the unique key, or distributed coordination with explicit failure semantics.

PostgreSQL partitioned tables impose additional restrictions for uniqueness: a unique or primary key constraint on the partitioned parent generally must include all partition-key columns so each local index can enforce the correct scope [2]. That is not equivalent to global uniqueness across independent databases.

Cross-shard joins may need fanout, distributed execution or precomputed read models. Cross-shard transactions add latency and failure modes: a local ACID transaction does not magically atomically commit to other shards. The more invariants you can keep under one clear authority, the easier your correctness argument.

## Replication is a separate axis

**Partitioning splits different data**; **replication copies overlapping data** for availability and/or read scaling. A system may have four shards each replicated three ways—twelve copies/nodes in one simple accounting model—but operational reality depends on placement, failure domains and leader policies. Replication can improve availability yet introduce lag and consistency choices. A replica accepting stale reads cannot always satisfy read-your-writes after an acknowledged update [3].

Backups are not replicas: accidental deletion can be copied to replicas immediately. Capacity plans need recovery point objective (RPO), recovery time objective (RTO), restore testing, and storage reserved for WAL, snapshots and backfill.

## Operational verification and counterexamples

Test uniform synthetic keys **and** realistic Zipf-like/skewed accesses; the former can hide hotspots. Monitor per-shard peak writes, queue delay, CPU, storage, request p99, replication lag and relocation progress. Inject a shard failure during a write, during a backfill and just after routing cutover. Verify cross-tenant authorization still applies when a key is routed or moved.

Do not shard prematurely: an indexed single relational database with replicas or table partitions may meet the workload with fewer coordination failures. Conversely, reaching physical storage or write limits with a validated hotspot model may justify sharding. Document the trigger, not just the proposed topology.

## Exercises and verification

1. With 6,000 peak writes/s and safe 1,000 writes/s per shard, compute minimum uniform active shards and explain why an N+1 number is not a failover guarantee.
2. Explain why a tenant producing 3,000 writes/s remains hot under hash(tenant_id) regardless of adding more shards.
3. Compare query complexity for listing one tenant's latest notes under tenant sharding versus hash(note_id) sharding.
4. From the rendezvous model, prove that keys moved after adding s4 must move **to s4**, not between two old nodes.
5. Outline a cutover safety invariant preventing an old backfill snapshot from overwriting a newer committed write.

**Related chapters:** [System design method](/en/topics/system-design-process/) establishes requirements; [transactional indexes](/en/topics/transactional-indexing-isolation/) explains uniqueness; [replication and failover](/en/topics/database-replication-failover/) covers RPO/RTO.
