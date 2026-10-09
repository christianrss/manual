---
id: system-design-process
title: "System Design Method: Requirements, Sizing, Interfaces and Failures"
description: "Learn a complete system design method through requirements, workload estimation, APIs, data ownership, failure handling and verifiable SLOs."
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites: [capacity-estimation, api-reliability, database-consistency]
sources:
  - {title: "Google SRE Workbook — Implementing SLOs", url: "https://sre.google/workbook/implementing-slos/", kind: "official engineering workbook"}
  - {title: "Amazon Builders Library — Timeouts, retries and backoff with jitter", url: "https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/", kind: "original engineering guidance"}
---
System design is the discipline of turning a product requirement into a system whose **observable behavior, resource costs, and failure response** can be explained and tested. A credible design is not a diagram of fashionable cloud services. It begins with an explicit workload and a small set of critical invariants, then moves through contracts, storage, components, trade-offs, recovery, and proof by measurement. Service level objectives (SLOs) make reliability a measurable design choice rather than a vague aspiration [1].

## Step 1: ask what the system must do

Clarify **functional requirements** first: who can create an object, who can read it, how it is updated, whether deletion is allowed, and whether clients need a synchronous answer. For a hypothetical note-sharing service, assume authenticated users can create private notes, retrieve their own notes by identifier, and list them in reverse creation order. Editing, collaboration, search, and public sharing are deliberately out of scope for the first version.

Also establish **negative requirements** and invariants. A user must never read another user's private note; a successful create must be durable before the API claims completion; an idempotent create retry must not create two notes with the same operation key. These statements are different from implementation decisions such as picking PostgreSQL or Redis. Put them in writing before optimizing.

## Step 2: quantify nonfunctional constraints

Define a user-facing availability SLI as successful eligible requests divided by eligible requests during a specified window. Suppose the target is **99.9% monthly success**, p95 server-side latency under 250 ms for reads, and recovery from a single application-node failure. These are **hypothetical requirements**, not guarantees of an actual service. The 0.1% monthly error budget is an allowed fraction of eligible requests, not permission to lose user data [1].

Security includes authentication, authorization, data classification and retention. Durability is about committed records surviving specified failures, and is not synonymous with API availability. A successful read in 80 ms can still be wrong if it crosses tenant boundaries. Agree on consistency expectations—for example, read-your-writes for an owner immediately after successful note creation—before selecting asynchronous replication.

## Step 3: estimate workload with units

Assume 8.64 million requests/day, 90% reads, a peak-to-average ratio of 10, and average response payload 2 KiB. These are **scenario assumptions** used to demonstrate the method. Mean throughput is 100 requests/s; the hypothetical peak is 1,000 requests/s; reads at peak are 900/s. Raw outbound payload at peak is about 1.95 MiB/s, excluding protocol overhead. If 10% of daily requests create records averaging 1 KiB of raw payload, annual raw growth is about 301 GiB, excluding replication, indexes, logs, backups and metadata.

![System design from requirements through validation.](/diagrams/system-design-method.svg)

~~~python
from math import ceil

def estimate(daily_requests, peak_multiplier, safe_rps_per_node):
    if daily_requests < 0 or peak_multiplier <= 0 or safe_rps_per_node <= 0:
        raise ValueError("positive capacity parameters required")
    mean_rps = daily_requests / 86400
    peak_rps = mean_rps * peak_multiplier
    required = ceil(peak_rps / safe_rps_per_node)
    # An N+1 assumption for a single failed identical application node.
    provisioned = required + 1
    return mean_rps, peak_rps, required, provisioned

mean, peak, required, provisioned = estimate(8_640_000, 10, 300)
assert (mean, peak, required, provisioned) == (100, 1000, 4, 5)
assert (provisioned - 1) * 300 >= peak
assert 0.001 * 8_640_000 == 8640
~~~

The 300 RPS/node threshold must be obtained by benchmarking the actual request mix at an **acceptable latency and utilization**, not guessed from processor count. The N+1 calculation addresses one application instance failure only; it does not guarantee survival of a shared database, network or whole-zone outage. A high read cache hit rate can reduce storage traffic, but adds staleness and invalidation costs.

## Step 4: contracts before components

Define request identity and payload contracts. One proposed interface uses POST /v1/notes with an idempotency key and body containing text. A successful committed create returns 201 with a stable note ID. GET /v1/notes/{id} returns 200 only if the authenticated principal owns the note; a security policy may deliberately return 404 instead of revealing another user's identifier. GET /v1/notes?limit=...&cursor=... returns a bounded page and a continuation token.

An API definition must specify maximum body size, validation, authorization, timeouts, error codes, rate limits, request retries and versioning. It must also define what **201 means**: creation is durably committed in the chosen authority. Returning 201 for a merely enqueued operation is misleading; a true asynchronous acceptance path may instead use 202 with a status resource under its stated contract [2].

## Step 5: draw the smallest valid architecture

Start with clients → HTTPS ingress/load balancer → stateless note API → transactional primary datastore. Introduce cache only after identifying a read bottleneck and a feasible invalidation policy. Add an outbox and message consumer only when there is an actual asynchronous requirement, such as indexing or sending notifications. Splitting one small note service into six microservices introduces new network and consistency boundaries without solving a proven problem.

For the create path, authorize the actor, validate size and content, write the note and its idempotency record in a transaction, commit, then return 201. The **database** enforces unique owner+operation-key pairs so concurrent retries cannot duplicate creation. The application should read back the previous outcome for a repeated key; the same key with a different payload requires a defined conflict response. A process-local map is inadequate after restart or when traffic reaches another instance.

## Step 6: choose storage through access patterns

The workload needs direct ID lookup, owner-scoped listing ordered by timestamp, and transactionally consistent creation. A relational store with a composite index on (owner_id, created_at, note_id) is a plausible first choice. The order of index fields supports an owner filter followed by stable chronological order; check actual query plans and retention policies. Storing only a timestamp as a pagination boundary risks collisions when two notes share the same time, so use (created_at, note_id) as a composite cursor key.

A document or key-value store is not inherently wrong. Selection depends on transactional requirements, query diversity, consistency and operational skill. A read replica may reduce primary load but may not satisfy read-your-writes after replication delay. Separately estimate row, index, WAL, backup and replica growth rather than treating raw payload as allocated disk.

## Step 7: analyze failures and scaling decisions

A client timeout after a committed write is an **ambiguous outcome**: the client did not receive the response, not proof that the write failed. Idempotency must handle that ambiguity. If the datastore is unavailable, the API should fail within its deadline or expose an explicit degraded behavior; filling unbounded queues can shift a brief outage into a prolonged backlog. Retrying at several layers can magnify overload [2].

| Failure or growth | Initial handling | Trade-off |
| --- | --- | --- |
| Single API node lost | Health checks and spare capacity | Shared dependencies remain |
| Primary database unavailable | Fail closed for writes; documented recovery | Availability decreases |
| Duplicate POST after timeout | Durable idempotency key and outcome | Additional transaction/index work |
| Hot owner listing | Indexed query, bounded page, measured caching | Cache staleness/extra cost |
| Read replica lag | Read primary for required read-your-writes | Higher primary load |
| Notification consumer down | Durable outbox and replay | Eventual delivery, duplicate handling |

Do not promise 'exactly once' end-to-end merely because an event bus acknowledges a message. State which durable effect is exactly-once under which key and which downstream work is at-least-once with idempotent consumers.

## Step 8: validate, then iterate

Verify authorization with cross-tenant negative tests; data consistency with concurrent creates and repeated keys; throughput with realistic reads/writes at 1,000 requests/s; latency at p50, p95 and p99; and recovery with node termination. Instrument request outcomes, saturated queues, database latency and replication lag. Compare observed SLIs with the stated SLO and adjust the design on evidence [1].

For an interview explanation, an effective order is: **scope → measurable requirements → order-of-magnitude estimates → API/data model → minimal architecture → key bottlenecks → failures and validation**. Each assumption must be challengeable and each extra component justified.

## Exercises and verification

1. Recompute peak RPS if the daily request count doubles and peak multiplier becomes eight; state which inputs are assumptions.
2. Explain why 99.9% API success does not imply any acceptable loss of committed note records.
3. Sketch one transaction preventing duplicate note creation under concurrent retries.
4. Explain why a replica might violate read-your-writes and choose a mitigation.
5. Name the first measurement that would justify introducing a cache, and the correctness risk the cache creates.

**Related chapters:** [Capacity estimation](/en/topics/capacity-estimation/), [reliable APIs](/en/topics/api-reliability/), [caching](/en/topics/caching/), and [database consistency](/en/topics/database-consistency/) provide deeper treatment of individual decisions.
