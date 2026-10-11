---
id: usage-metering-system-design-assessment
title: "Independent System Design Assessment: Usage Metering, Late Events and Billing Reconciliation"
description: "Design a tenant-isolated usage ledger with quantitative capacity estimates, deterministic replay, late-event corrections, failure tests and an auditable design review."
category: interview-practice
difficulty: advanced
updated: 2026-10-11
prerequisites: [capacity-estimation, system-design-process, asynchronous-messaging, database-consistency, data-partitioning-sharding]
sources:
  - {title: "Apache Beam — Programming Guide: Watermarks and Late Data", url: "https://beam.apache.org/documentation/programming-guide/", kind: "official distributed processing documentation"}
  - {title: "AWS Builders' Library — Making Retries Safe with Idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
  - {title: "Google SRE Book — Monitoring Distributed Systems", url: "https://sre.google/sre-book/monitoring-distributed-systems/", kind: "original engineering reference"}
---
An architecture interview is not a contest to list managed services. A useful assessment asks the candidate to **derive contracts from incomplete requirements**, quantify assumptions, define an authority for financial decisions, then explain what changes when the workload or failure model changes. The previous [adaptive document-processing assessment](/en/topics/adaptive-system-design-assessment/) examined queue fairness and regional storage; the [checkout architecture review](/en/topics/system-design-architecture-review/) examined stock and payment commits. This is a different problem: **usage metering used to create auditable invoices from delayed, replayed, tenant-scoped events**.

The case is fictional and independently authored. It is not a leaked or official employer question. The mathematical inputs and review rubric are public; there is no private judge, live database or supervised interview infrastructure. The reader supplies the design and the supporting evidence, not a memorized final diagram.

## Initial prompt: an intentionally incomplete product request

A SaaS provider bills customers for units consumed by an API. Several producers emit usage records, and a customer dashboard shows a daily total before a monthly invoice is finalized. Build an ingest interface, aggregation pipeline, billing handoff, query API and operational monitoring. The initial product owner says only: “the total must be correct, customers should see it soon, and retries must not charge twice.”

This is **not** a complete engineering contract. Before choosing SQL, streaming, queues or caching, ask whose clock defines the billing period, how a billable unit is represented, whether corrections are permitted after invoice creation, what constitutes a successful ingest acknowledgment, what lateness is acceptable, and who decides a tenant's identity. Also clarify the consequences of losing a nonbillable diagnostic event versus a billable event: the durability requirement may differ, and those types must not silently share one ambiguous policy.

Define separate terms: **event time** is when the usage purportedly occurred; **processing time** is when the server handles the record; **invoice finalization** is a business state transition. An incoming record with event time from three days ago is not a new charge for today merely because it arrived today. Watermarks in streaming engines describe progress estimates for event-time windows; they are not an unconditional proof that no old record will ever arrive [1].

## Submit a contract, not only a service diagram

Begin by proposing a versioned envelope such as `(tenant_id, source_id, event_id, event_time, unit_type, quantity, schema_version)`. Do not copy that list mechanically: decide how the server obtains trusted tenant and source identity, the permitted quantity range, the time-skew policy, and whether a signed correction is a new auditable event or an overwrite. Specify which fields participate in the deduplication identity and what happens if the **same identity carries a different payload**.

A request that times out may have committed. Blindly retrying with a **new** event ID can double the intended usage, while treating every repeated payload as a duplicate may incorrectly collapse two genuinely different consumption events. The caller's stable intent identifier needs a defined scope and conflict policy. AWS's Builders' Library explains why retries and late-arriving requests must preserve an explicitly stated meaning of idempotency [2].

Describe what HTTP `202 Accepted` means under your proposal. If the service returns success before a durable write, a crash may silently lose billable usage. If it waits for an external streaming service that is unavailable, ingress availability may become tightly coupled to the streaming dependency. Both approaches require a stated failure policy and an observable method to reconcile client-visible acknowledgments against the system of record.

## Baseline workload: derive values with units

Use the hypothetical baseline in the committed [scenario file](https://github.com/christianrss/manual/blob/main/examples/system-design/usage_metering_scenario.json): **2,400,000 new source events per day**, **2,048 logical bytes per event**, a **40× peak-to-mean multiplier**, **28 days** of raw retention, workers measured at **250 events/second**, a planning utilization ceiling of **60%**, and tolerance of **one unavailable worker replica**. These are scenario assumptions, not measurements from a deployed service.

Mean ingest rate is `2,400,000 / 86,400 ≈ 27.78 events/s`. The hypothetical peak ceiling is `ceil(27.78 × 40) = 1,112 events/s`. Logical retained input bytes are `2,400,000 × 2,048 × 28 = 137,625,600,000 bytes`, approximately `128.17 GiB` using `1 GiB = 1,073,741,824 bytes`. This excludes replicated copies, indexes, WAL, backups, compression, dead letters and duplicate attempts; it is not a disk or cloud bill.

At 60% of the **assumed measured** 250 events/s worker throughput, each worker is planned for 150 events/s. `ceil(1112/150)=8` healthy workers cover this idealized peak; adding one idle/failure-equivalent replica produces **9** workers for the stipulated one-worker loss assumption. This is not an autoscaling prescription: a shared database ceiling, burst shape, hot partitions or long-tail event processing can invalidate linear scaling.

The following example invokes a reproducible, intentionally **arithmetic-only** model; it performs no network ingestion or invoicing:

~~~python
from examples.python.usage_metering_design_math import (
    peak_ingest_rate, raw_retained_bytes, outage_backlog,
    drain_seconds, ideal_worker_replicas, BYTES_PER_GIB,
)
assert peak_ingest_rate(2_400_000, 40) == 1112
assert raw_retained_bytes(2_400_000, 2048, 28) == 137625600000
assert ideal_worker_replicas(1112, 250, 60, 1) == 9
assert outage_backlog(1200, 600) == 720000
assert drain_seconds(720000, 1200, 1800) == 1200
assert 128 < raw_retained_bytes(2_400_000, 2048, 28) / BYTES_PER_GIB < 129
~~~

The code uses **integer ceiling division**, so large event counts are not rounded through floating-point intermediates. Verify numerical predictions against independent arithmetic, but do not mistake verified multiplications for verified throughput.

## Outage injection: distinguish peak from recovery traffic

A separate exercise assumption states that **1,200 events/s arrive continuously while consumers stop for 600 seconds**. That rate is a specific outage scenario, **not derived from** the earlier 1,112 events/s planning peak; it deliberately stresses the original sizing assumption. With no starting backlog, the outage accumulates `1,200 × 600 = 720,000` pending records.

After restoration, suppose the full processing path sustains **1,800 events/s** while new work continues at 1,200 events/s. Only 600 events/s can retire the old backlog. Its idealized drain time is `720,000/600 = 1,200 seconds = 20 minutes`, provided arrivals and processing stay constant and there are no retries or poison messages. At only **1,000 events/s** of service, arrivals exceed processing; the backlog grows, so claiming a finite drain time is mathematically false.

A positive drain margin is not itself a latency guarantee. Include queue age, end-to-end acceptance-to-aggregation delay, consumer lag, dead-letter growth and the health of the authoritative write path in the measurement plan. Google SRE emphasizes monitoring signals that reveal user-visible service conditions rather than only host utilization [3].

## Changed requirements: delayed events and invoice corrections

The interviewer now introduces four changes: **5% of records may arrive 72 hours late**; sources sometimes retry an event identifier with a conflicting payload; one tenant produces **70% of ingest** for half an hour; and a verified correction can apply after the billing period has been invoiced. Each change attacks a prior assumption about completeness, identity, fairness or finality.

Decide when a daily preview may be *provisional* and when an invoice may become *final*. Explain the difference between a configurable streaming lateness window and a business rule for correcting already finalized charges. If invoices can change silently after a customer sees them, auditability is lost. If late events are simply dropped after a watermark advances, valid usage may go unbilled. One defensible design might record an immutable original event and a separate adjustment linked to an invoice version, but the assessment requires comparing viable alternatives and defining the authority that permits corrections.

A single shared partition keyed poorly can become a hot shard when one tenant dominates traffic. Conversely, splitting events for one tenant across arbitrarily many workers may make deterministic ordering or exactly-once materialization harder. State which invariants need transactionality and which derived aggregates may be eventually consistent. The challenge is not solved by writing “use Kafka and Redis” on a diagram.

## Storage choices, security boundaries and trade-offs

Produce a data model identifying an **authoritative ledger of accepted usage**, a deduplication record or equivalent replay control, provisional aggregates, and an immutable or versioned invoice decision. If a queue acknowledgment is issued before the durable record exists, describe the failure interval and a recovery proof. If writes are distributed across two independent resources, explain why a successful call to one does not imply an atomic commit to both. A transactional outbox, a single authoritative log or another explicitly argued mechanism may be chosen, but each option has constraints and costs [2].

Show where tenant identity is authenticated, where authorization is enforced on ingest and read paths, and how a data-export request is scoped. A dashboard cache must not become financial authority. If the same event ID may be used by two legitimate tenants or sources, deduplication keyed solely by event ID may incorrectly merge independent billable events. Retention must be long enough for the chosen replay guarantee, or reconciliation must explicitly handle records older than the retained deduplication window.

Compare two realistic architectures using operational complexity, recovery semantics, replay ability, storage growth, query freshness and invoice correctness. Name uncertainties that would require experiments: histogram of per-event processing CPU, largest tenant burst, actual payload distribution, downstream SQL throughput, event lateness distribution and correction frequency. No vendor choice can be proved optimal from hypothetical traffic alone.

## Independent review rubric, failure gates and evidence

Use the [submission template](https://github.com/christianrss/manual/blob/main/examples/system-design/usage_metering_submission_template.md). Its **100-point educational rubric** assigns 10 to clarifications, 15 to contracts and authority, 20 to consistency and invariants, 15 to quantitative capacity, 20 to failure injection, 10 to architectural alternatives and 10 to test evidence. It also contains blocking conditions: cross-tenant access, cache-only invoice authority, silent finalized-invoice overwrites, confusing event and processing time, or promising queue drain without spare processing capacity.

Scoring requires a human reviewer; the repo does not contain a system-design grader. A candidate should supply a small decision record with chosen architecture, rejected alternatives, assumptions, failure behavior, monitoring thresholds and rollback conditions. Include **at least two tests involving races** (concurrent same-ID ingest and correction versus invoice close) and a measurable success criterion for each. A diagram and a guessed hardware count are insufficient.

## Exercises and verification

1. **Recompute sizing:** if throughput per worker decreases to 180 events/s at the same 60% target, how many interchangeable replicas are needed to preserve peak plus one-worker failure? *Check:* planned rate is 108 events/s per worker; `ceil(1112/108)+1=12`.
2. **Diagnose an outage:** with arrivals 1,200 events/s and recovered capacity 1,000 events/s, explain why no finite drain bound exists. *Check:* backlog grows by 200 events each second during those assumptions.
3. **Test identity:** submit identical event IDs from two tenants, then repeat an ID for the same tenant/source with changed quantity. Define the outcome and where the authoritative dedup record is committed.
4. **Handle delayed records:** describe a verified usage record that arrives after invoice finalization. Which financial artifact changes, which cannot be overwritten, and how can an auditor reconstruct the decision?
5. **Design a fault experiment:** have the broker redeliver an event after the ledger commits but before the consumer acknowledges. State the observable invariant and what database or log evidence demonstrates it.
6. **Challenge the architecture:** require a whole-day data replay after the deduplication record has expired. Identify why the original exactly-once claim becomes unsound and propose a bounded recovery contract.

The public arithmetic model checks dimensioned quantities only. Correctness of a billing system depends on authenticated authority, concurrency boundaries, durable state transitions, documented invoice policies and empirical tests that are **not supplied by these fixtures**.
