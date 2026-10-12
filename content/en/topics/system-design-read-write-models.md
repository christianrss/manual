---
id: system-design-read-write-models
title: "System design: authoritative writes, projections and consistency"
description: "Design write paths and read projections with replay-safe event processing, consistency targets, lag budgets and recovery verification."
category: system-design
difficulty: intermediate
updated: 2026-10-12
prerequisites: [system-design-process, database-consistency, asynchronous-messaging]
sources:
  - {title: "Martin Fowler — CQRS", url: "https://martinfowler.com/bliki/CQRS.html", kind: "original architecture article"}
  - {title: "Chris Richardson — Transactional Outbox", url: "https://microservices.io/patterns/data/transactional-outbox.html", kind: "original pattern description"}
  - {title: "PostgreSQL — Transaction Isolation", url: "https://www.postgresql.org/docs/current/transaction-iso.html", kind: "official database documentation"}
---
System design often treats “the database” as one box. In practice, **accepting a write** and **serving a read** have different correctness, latency and failure requirements. One architecture can serve both from a transactional database; another can maintain a derived read model. The second choice becomes useful only if its staleness, replay and recovery contracts are understood. Command Query Responsibility Segregation (CQRS) describes separating models for updates and queries, but it is not a requirement to use distinct databases, event sourcing or microservices [1].

## Specify an observable contract

Consider a hypothetical order service. After an order is confirmed, its authoritative record must survive failures within the stated durability model. A customer reads an order-by-ID page that must provide **read-your-writes** after confirmation. A separate dashboard aggregates completed orders by store and accepts up to five seconds of lag during normal operation. This lag target is a *hypothetical product requirement*, not a universal distributed-system guarantee.

The write path accepts a command, validates the actor and business preconditions, applies a transaction and returns a stable order identifier. The read-by-ID path can use the primary data source to satisfy read-your-writes. The dashboard can consume a projection that is rebuilt from a durable event history. Keeping these promises separate prevents an accidental claim that a fast cache can substitute for authoritative state.

## Derive the simplest design first

A single transactional relational database can provide both writes and indexed reads. Begin there if measured traffic is moderate. Use an order table keyed by order_id, a tenant identifier for access control, immutable customer price snapshots where required, and an index matching the dashboard's actual query. Benchmark the query before building a second persistence subsystem.

A separate projection adds machinery: an event publisher, transport or log, consumer, checkpoint, ordering policy, error handling and a repair path. It may permit cheap specialized aggregations and independent read scaling, but does not improve correctness automatically. CQRS can use different in-process models on the same database; physical separation is another optional decision [1].

## Keep the write authoritative

Suppose the order transaction updates orders and records an outbox event containing order_id, aggregate_version and the new confirmed total. Both records must commit atomically. A background relay publishes from outbox; if it crashes after publishing but before marking delivered, the event may be published twice. Transactional outbox addresses the database/event dual-write gap, but does not provide one-time delivery to arbitrary consumers [2].

Define a stable aggregate version, monotonically increasing for each order. Use a unique event ID to deduplicate individual events and treat sequence gaps deliberately. Do not claim that a global timestamp alone establishes order when producers run concurrently; multiple aggregates can be processed independently, while one aggregate's transitions must respect its authorized sequence.

## Model the projection and replay semantics

The following projector accepts full replacement totals for one order per version. Its small dictionary represents derived state, not the authoritative order database. A duplicate with identical version and payload has no new effect; a duplicate version with different payload is rejected as an integrity conflict. An out-of-order future version is rejected for later retry rather than silently applying it. The projection stores each order once, so updating its amount replaces the previous contribution instead of double-counting it.

~~~python
from decimal import Decimal

class Projector:
    def __init__(self):
        self.orders = {}
    def apply(self, order_id, version, total):
        if not order_id or type(version) is not int or version < 1:
            raise ValueError("invalid event identity")
        if not isinstance(total, Decimal) or not total.is_finite() or total < 0:
            raise ValueError("invalid amount")
        previous = self.orders.get(order_id)
        if previous is None:
            if version != 1:
                raise ValueError("missing initial version")
        else:
            old_version, old_total = previous
            if version == old_version:
                if total != old_total:
                    raise ValueError("conflicting replay")
                return False
            if version != old_version + 1:
                raise ValueError("out-of-order event")
        self.orders[order_id] = (version, total)
        return True
    def total(self):
        return sum((amount for _, amount in self.orders.values()), Decimal("0"))

projection = Projector()
assert projection.apply("A", 1, Decimal("10.00"))
assert not projection.apply("A", 1, Decimal("10.00"))
assert projection.apply("B", 1, Decimal("4.50"))
assert projection.apply("A", 2, Decimal("8.00"))
assert projection.total() == Decimal("12.50")
before = dict(projection.orders)
for event in (("A", 2, Decimal("100")), ("A", 4, Decimal("9")),
              ("C", 2, Decimal("5"))):
    try:
        projection.apply(*event)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid replay accepted")
assert projection.orders == before
~~~

For n currently projected orders, apply has expected O(1) time per event under conventional dictionary-hashing assumptions, and O(n) stored state; computing total by scanning is O(n) time. Maintaining a running aggregate could make total queries O(1), but then it must be updated atomically with per-order state and tested against conflicting replays. This sample does **not** persist checkpoints, authenticate events, serialize concurrent writers or solve memory growth.

## Quantify staleness and backpressure

Suppose the source creates 600 events/s while the consumer sustainably processes 500 events/s for 120 seconds, with constant rates and no duplicates. The backlog grows by (600−500)×120 = 12,000 events. If arrivals then fall to 300/s and processing remains 500/s, clearing this backlog takes 12,000/(500−300) = 60 seconds, even before considering retries or queue overhead.

~~~python
def backlog(arrivals_per_s, capacity_per_s, seconds, initial=0):
    if min(arrivals_per_s, capacity_per_s, seconds, initial) < 0:
        raise ValueError("negative input")
    return max(0, initial + (arrivals_per_s-capacity_per_s)*seconds)

assert backlog(600, 500, 120) == 12000
assert backlog(300, 500, 60, 12000) == 0
assert backlog(500, 500, 60, 12000) == 12000
~~~

This is a fluid approximation, not a bound on individual event lag. A five-second lag SLO needs instrumentation for event creation-to-visibility delay, queue age, processing failures and p95/p99 under representative burst distributions. A dashboard can explicitly display “last updated at” and degrade rather than silently present stale totals as authoritative.

## Recovery, ordering and consistency

Persist projector state and last acknowledged offset in a consistent checkpoint boundary, or rebuild from a replayable authoritative log. A checkpoint ahead of the projected state can lose updates; a checkpoint behind may replay them. Durable deduplication makes the second case safe only when the projection update and checkpoint are committed consistently. With multiple workers, partition or serialize processing per aggregate; an in-memory version check alone does not prevent two processes from racing.

Read-your-writes on the customer order page may require primary reads, session routing to a caught-up replica, or a wait on a committed version. A separate dashboard projection can serve eventual data only because its user-visible contract permits lag. Isolation levels, concurrent updates and anomalies depend on actual database semantics and should be tested against the chosen database [3].

## Counterexamples and architecture review

Do not introduce a broker solely because the word CQRS appears in a system-design prompt. A single indexed SQL query may be cheaper, simpler and more accurate. A cached count may be acceptable for analytics yet prohibited for charging a customer. Events representing incremental deltas require different replay logic from the replacement-total example: naively applying a duplicate +10 delta twice corrupts the sum. If an event stream has gaps that never recover, “eventual consistency” does not promise convergence.

Review security boundaries as well: read projections can leak tenant data if their keys omit tenant identity or their query layer trusts caller-provided IDs. Events may contain personal information that must obey retention and deletion policy. Data correctness includes authorization, not merely arrival order.

## Exercises and verification

1. Rewrite the projector for delta events. Prove which event identity and deduplication state prevent double addition; test replay after process restart.
2. Compute the backlog if input stays 600/s while processing drops to 400/s for three minutes, then recovers to 700/s while input becomes 300/s.
3. Design a dashboard lag SLO and alert. Distinguish queue depth from event age and explain how to measure both.
4. Show a crash boundary between an order commit and outbox relay. Explain why the message can repeat and why it must never describe a rolled-back order.
5. Decide whether a user immediately retrieving an order may read the asynchronous dashboard replica. State the consistency requirement that determines the answer.

Related: [data consistency](/en/topics/database-consistency/), [asynchronous messaging](/en/topics/asynchronous-messaging/), [API reliability](/en/topics/api-reliability/), [architecture review](/en/topics/system-design-architecture-review/).