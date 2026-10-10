---
id: storage-selection
title: "Storage Selection: Relational, Document, Key-Value and Object Stores"
description: "Choose storage by access patterns, consistency invariants and cost; compare relational, document, key-value, blob and search models."
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites: [system-design-process, database-consistency]
sources:
  - {title: "DynamoDB Data Modeling", url: "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/data-modeling.html", kind: "official vendor documentation"}
  - {title: "PostgreSQL — Transaction Isolation", url: "https://www.postgresql.org/docs/current/transaction-iso.html", kind: "official database documentation"}
---
Storage selection is a **decision about access patterns, invariants, and operating costs**, not a vote for SQL or NoSQL. A datastore that returns individual documents quickly may be a poor authority for a business invariant spanning accounts and inventory. Conversely, a highly normalized relational schema may impose costly joins on a globally distributed, read-heavy lookup service. The correct first step is to write down the operations, their frequency, required atomicity, size and acceptable staleness [1][2].

## Define the workload before naming a product

Consider a hypothetical marketplace with 500,000 users. The initial use cases are: create an order containing multiple lines; decrement inventory without overselling; retrieve an order by ID; list a user's recent orders; read product descriptions; and store product photographs. These operations imply different access shapes. Order placement requires **cross-row atomicity within an authority**; photos are large immutable blobs; browsing product text may benefit from a specialized search index.

For each query, record: filter keys, sort keys, maximum page size, expected p95 latency, read/write ratio, peak rate and consistency. Avoid claiming that a database handles a workload efficiently merely because it can represent the data. Index configuration, cardinality, hot keys and measured request costs matter [1].

## Relational storage and transactional invariants

A relational database is often a defensible first **system of record** for orders. It provides declared keys and constraints, structured queries and transaction isolation. With a single database authority, a transaction can atomically insert the order, its lines, an inventory reservation and an outbox message, provided the schema and isolation strategy enforce the required invariants. That does **not** make an external payment API part of the same ACID transaction.

A possible design includes orders(id, owner_id, state, created_at), order_lines(order_id, sku, quantity, unit_price), stock(sku, available, reserved) and outbox(id, order_id, kind). Foreign keys protect relationships; a unique key on (owner_id, client_key) supports durable request deduplication. Index (owner_id, created_at DESC, id DESC) supports cursor-based listing. A transaction-safe inventory update must check availability inside the write rather than relying on a preliminary stale read [2].

SQL engines differ in default isolation and lock behavior. A query that works on a snapshot can still encounter lost updates or serialization failures under concurrency if implemented incorrectly. Test actual transactions in the chosen database; an in-memory dictionary or a unit test without concurrent connections cannot establish these properties.

## Document stores and aggregate boundaries

A document store can represent a product catalog item with variant attributes in one document and support efficient reads when the API usually returns the entire item. That convenience does not make every nested structure a good document. Embedding an ever-growing user's order history can create unbounded records and heavy rewrites; splitting into referenced documents may improve growth and pagination.

Some document databases offer multi-document transactions, while others prioritize partition-local operations. The brand label 'document store' is not itself a consistency model. Explicitly check atomic-operation scope, secondary-index maintenance, update preconditions, replication lag, and query-plan behavior in the chosen engine. The **aggregate boundary** should follow invariants and update patterns rather than arbitrary JSON shape.

## Key-value stores and access-pattern-first modeling

A key-value store excels when callers know keys or can form supported partition/sort-key queries. DynamoDB, for example, documents modeling tables around known access patterns, high-cardinality partition keys and optional sort keys to support item collections [1]. Modeling one user's newest orders might use a partition key derived from user and a descending sort key; listing orders of every user globally then requires another access path or a separate index.

A single very hot key can still overload a partition even when aggregate provisioned capacity is sufficient. Secondary indexes consume write capacity and must be included in sizing. A key-value cache such as Redis is **not automatically** an authoritative durable database, and a managed durable key-value database is not just a cache with larger memory.

## Blob storage, search and read models

Large images and attachments usually belong in **object/blob storage**, referenced by stable metadata in the authoritative database. Object storage semantics differ from relational row constraints: saving a file and committing a database row are not normally one transaction. Use an explicit two-stage process, garbage collection for abandoned objects, and authorized signed access rather than public URLs to private data.

Full-text search is another different workload. A search index may allow term analysis, relevance and facets, but is often an **eventually updated read model**, not the sole source of order payment state. Plan replay from the authoritative log/outbox and measure index freshness rather than promising that every successful write is instantly searchable.

![Access patterns lead to different storage authorities and derived read models.](/diagrams/storage-selection.svg)

## Quantify raw storage and write amplification

For a **hypothetical** 100,000 new orders per day, 2 KiB of logical order-and-line data each, one year's raw growth is approximately 69.6 GiB before indexes, WAL, replicas, retention backups and storage-engine metadata. If each write updates a base row and three secondary indexes, physical write work can materially exceed the payload calculation; the factor must be benchmarked for the actual engine. The exercise below counts **raw logical bytes only**, not a storage capacity commitment.

~~~python
def raw_growth_gib(records_per_day, bytes_per_record, days=365):
    if min(records_per_day, bytes_per_record, days) < 0:
        raise ValueError("negative inputs")
    return records_per_day * bytes_per_record * days / (1024 ** 3)

gib = raw_growth_gib(100_000, 2048)
assert 69 < gib < 70
assert raw_growth_gib(0, 2048) == 0
try:
    raw_growth_gib(-1, 2048)
    assert False
except ValueError:
    pass
~~~

Capacity planning also needs peak IOPS and burst size, read/write mix, index selectivity, retention, compression, recovery objectives and price of reserved throughput. The result changes if line-item averages grow or if each order includes many large attributes. Keep storage growth and request throughput as **separate calculations**.

## Decision matrix for the marketplace

| Requirement | Plausible first choice | Reason to reconsider |
| --- | --- | --- |
| Orders with inventory invariants | Transactional relational store | Measured scaling limit or geographic constraints |
| Flexible catalog product attributes | Relational JSON or document model | Complex cross-product joins or transactional updates |
| Lookup by exact key at very high scale | Managed key-value store | Additional unpredictable filters or hot keys |
| Product images | Object storage | Strong row/object atomicity is unavailable |
| Ranked product search | Search read model | Rebuild and freshness requirements |
| Popular product read acceleration | Cache | Invalidation and staleness risk |

These are **starting hypotheses**, not product prescriptions. One relational database with JSON support might satisfy both catalog and orders while the team is small, reducing operational overhead. Moving an invariant across storage systems creates an asynchronous consistency boundary that must be justified by a measured benefit.

## Migrations, failures and counterexamples

Moving from a relational primary to a new store is a data migration, not simply changing a repository adapter. Define a source of truth, backfill, ordered change capture, validation, cutover, rollback and deletion policy. Dual writes can diverge when one succeeds and the other times out. If replication is asynchronous, a read replica or search index might return a stale record after an acknowledged create.

Avoid blanket claims such as 'NoSQL scales automatically', 'SQL cannot shard', or 'eventual consistency is always acceptable'. Each is falsifiable by implementation and workload. The appropriate system is the smallest one whose guarantees cover the product's actual invariants at the measured scale.

## Exercises and verification

1. Create an access-pattern table for create order, update stock, list user orders and search products; include transaction scope and indexes.
2. Explain why photo upload and SQL order commit cannot be assumed atomic across two unrelated services.
3. Recalculate yearly raw growth for 250,000 records/day at 1.5 KiB each, distinguishing GiB from GB.
4. Give a counterexample where hashing every order ID helps individual lookups but harms user-scoped chronological listing.
5. Propose an observable measurement that would justify introducing a dedicated search engine instead of using SQL search.

**Related chapters:** [System Design methodology](/en/topics/system-design-process/), [transaction isolation](/en/topics/database-consistency/), [query planning](/en/topics/sql-query-planning/) and [sharding](/en/topics/data-partitioning-sharding/) examine these decisions in greater detail.
