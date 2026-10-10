---
id: database-storage-wal
title: "Database Storage: Pages, MVCC, B-Trees and Write-Ahead Logs"
description: "Trace tuple storage, B-tree page splits, MVCC version visibility and write-ahead crash recovery using documented PostgreSQL internals."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [database-consistency, processes-virtual-memory]
sources:
  - {title: "PostgreSQL — Database Page Layout", url: "https://www.postgresql.org/docs/current/storage-page-layout.html", kind: "official documentation"}
  - {title: "PostgreSQL — B-Tree Indexes", url: "https://www.postgresql.org/docs/current/btree.html", kind: "official documentation"}
  - {title: "PostgreSQL — Write-Ahead Logging (WAL)", url: "https://www.postgresql.org/docs/current/wal-intro.html", kind: "official documentation"}
  - {title: "PostgreSQL — Index-Only Scans", url: "https://www.postgresql.org/docs/current/indexes-index-only-scans.html", kind: "official documentation"}
---
A relational database is not just a set of tables represented as dictionaries. It is a **storage engine** maintaining pages, transaction metadata, indexes and a recovery log under concurrency. Understanding its structures explains why a query with an index may still be slow, why updates produce more I/O than expected, and how a committed change can survive a process crash. PostgreSQL is a concrete reference here; details differ among database engines [1]. The [file-descriptor and fsync chapter](/en/topics/file-descriptors-buffering-fsync/) establishes visibility versus durability, while [filesystem journaling](/en/topics/inode-directories-journaling-recovery/) explains metadata consistency; database WAL adds transaction-specific ordering and recovery above both.

## Storage pages and tuple identity

PostgreSQL organizes persistent relations into files containing fixed-size pages; the default page size for typical builds is 8 KiB, although a different build can use another size. A page contains a header, an array of item identifiers, tuple payloads and free space. Item identifiers point to tuples inside the page. A physical tuple identifier (CTID) identifies a page number and an item offset; it is not an immutable application-level primary key [1].

A SQL row is a *logical entity*. Under updates, its physical representation may change, and multiple physical tuple versions can correspond to the logical row. Treating CTID as an everlasting object ID is a bug. A primary key is an application-visible identity backed by a constraint; its persistence guarantees differ from a physical storage locator.

![Storage pages, B-tree index pointers and the write-ahead log.](/diagrams/database-pages-wal.svg)

## MVCC and visibility of row versions

Multi-version concurrency control (MVCC) supports snapshots in which concurrent transactions can see different committed versions. PostgreSQL tuples carry transaction identity and visibility-related metadata; the server evaluates visibility against a snapshot and transaction state. An UPDATE often creates a newer tuple version rather than overwriting the only representation in place. Readers on an older snapshot may still need the preceding version while newer transactions use the latest permitted version [1].

Consequently, a physical scan may encounter versions that are not visible to the querying transaction. Vacuum processing can eventually reclaim obsolete tuples after no relevant snapshot requires them. Long-running transactions may delay cleanup. This explains an important distinction: a physical row version in a page is not automatically a valid row in a particular SQL query result.

## How B-tree indexes narrow the search

A B-tree index maintains ordered separator keys that guide searches through internal pages to leaf entries. Unlike a binary tree with at most two children, a database B-tree uses many child pointers per page to reduce page traversals. A simple idealized tree with effective branching factor b and N entries requires roughly log_b(N) levels, with real costs affected by occupancy, cache and index layout. PostgreSQL's B-tree implementation handles page splits and concurrent changes rather than behaving like an immutable sorted array [2].

A leaf index entry generally guides the executor to a heap tuple location. An **index scan** may require additional heap-page reads and MVCC visibility checks. An **index-only scan** can avoid some heap fetches when the index includes required data and the visibility map can establish that a heap page's tuples are visible as required. It is not enough that a SELECT statement lists only indexed columns [4].

## Page splits, index order and write amplification

When a leaf page lacks room for another entry, a B-tree may split that page and update a parent downlink. Splits may propagate upward; even the root may split, increasing tree height [2]. New index entries, page modifications and recovery records create **write amplification** relative to one logical INSERT. Randomly distributed keys can trigger different locality and split patterns from sequential keys. A nonselective predicate may still favor a sequential scan because jumping to many heap pages costs more than reading the table in order.

An index on (tenant_id, created_at) can efficiently serve many queries filtering by a tenant and ranging over creation times. It does not imply equally efficient lookup by created_at alone: the composite key's leading-prefix ordering matters. Always inspect the actual execution plan, row estimate and heap fetches rather than assuming that an index name proves the desired query cost.

## The WAL ordering invariant

Write-ahead logging (WAL) preserves the principle **log the page modification before making the associated changed data page durable**. More precisely, the required WAL records describing the change must reach durable storage before the modified data page is written back. Then after a crash the engine can replay durable log records to redo changes not yet reflected in data pages [3].

The log-before-data rule allows a database to commit without forcing every changed heap and index page immediately. Yet WAL alone does not promise the durability of a client acknowledgment under every possible configuration: policies such as synchronous commit, fsync and replication acknowledgments affect what has been persisted and what failure domains are tolerated. Durability also depends on storage honoring flush requests. A crash-recovery log is not a substitute for backups or geographical disaster recovery.

## A reproducible page-capacity model

~~~python
def page_occupancy(page_bytes, header_bytes, item_bytes, tuple_bytes):
    if page_bytes <= 0 or min(header_bytes, item_bytes, tuple_bytes) <= 0:
        raise ValueError("sizes must be positive")
    if header_bytes >= page_bytes:
        return 0
    return (page_bytes - header_bytes) // (item_bytes + tuple_bytes)

assert page_occupancy(8192, 24, 4, 96) == 81
assert page_occupancy(4096, 24, 4, 96) == 40

def btree_ideal_levels(entries, branching_factor):
    if entries < 0 or branching_factor < 2:
        raise ValueError("invalid values")
    leaves, levels = max(1, entries), 0
    while leaves > 1:
        leaves = (leaves + branching_factor - 1) // branching_factor
        levels += 1
    return levels

assert btree_ideal_levels(1000000, 100) == 3
~~~

This is an **illustrative arithmetic model**, not PostgreSQL's tuple or page allocator. Real pages contain variable-length headers, line pointers, alignment, null maps, free-space requirements and often TOAST-managed values. The ideal levels function describes repeated grouping, not an exact B-tree height prediction.

## Crash sequence and recovery reasoning

Imagine transaction T writes a page change and corresponding WAL record; the WAL is durably flushed, but the dirty data page is still only in memory. A crash destroys the in-memory data page. On restart, recovery reads the persisted log and can reapply the missing modification. If the data page was already safely written, redo processing must avoid incorrectly applying the same operation twice, using the engine's recovery metadata and log sequence positions [3].

Now reverse the ordering: if the modified page reached storage while its required log record did not, the recovery mechanism would lack sufficient log history to establish a consistent state. That is why **ordering** is a correctness condition, not merely a performance preference.

## Failure modes, tuning and architecture boundaries

| Symptom | Candidate explanation | Validation |
| --- | --- | --- |
| Fast indexed query slows | Many heap fetches or stale statistics | Query plan, buffers, row estimates |
| Disk use grows after UPDATE | Old MVCC versions and indexes | Vacuum health and version churn |
| Insert spikes in latency | Page splits, WAL flush or contention | WAL, I/O and lock metrics |
| Replica lags behind | Log transmission or replay delay | Replay position and lag |
| Crash loses acknowledged data | Durability configuration or storage fault | Verify flush policy and failure model |

A shared transaction database has different guarantees from a globally distributed system. WAL can make one engine recoverable, but it does not itself establish consensus between replicas. Likewise, snapshot visibility and isolation are distinct: MVCC can implement multiple isolation levels without guaranteeing serializability automatically.

**Related chapters:** [Database consistency](/en/topics/database-consistency/) explains transaction isolation and MVCC snapshots. [SQL query planning](/en/topics/sql-query-planning/) explains when the optimizer selects an index scan, heap fetches or a sequential scan. [Consensus](/en/topics/raft-consensus/) covers a distinct cross-node ordering and failure problem.

## Exercises and verification

1. Recompute the idealized page capacity for header=24 B, item pointer=4 B and tuple=96 B in an 8,192 B page. Explain what the model excludes.
2. Describe why an index covering all selected fields still might need to consult heap visibility.
3. Construct a crash timeline where WAL is flushed before the heap page. Identify what recovery replays.
4. Explain how a page split can propagate to the root and why the tree height then increases.
5. For a tenant-indexed table with millions of rows, compare a tenant equality lookup, an unfiltered full scan and a range scan using a composite key. State index and selectivity assumptions.
