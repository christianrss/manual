---
id: service-boundaries
title: "Service Boundaries: Modular Monoliths, Microservices and Events"
description: "Choose software service boundaries by ownership, consistency, synchronous failure and measured scaling trade-offs."
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites: [system-design-process, asynchronous-messaging]
sources:
  - {title: "Martin Fowler — Microservices Guide", url: "https://www.martinfowler.com/microservices/", kind: "engineering articles"}
  - {title: "AWS Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "engineering guidance"}
---
A service boundary specifies **which component owns a business decision, its durable state and its failure contract**. It is not synonymous with a network address. A modular monolith can separate order, inventory and payment policies behind narrow interfaces in one process; independently deployed services add network latency, partial failure, authorization, telemetry and distributed consistency. Choose the smallest deployment boundary that solves a measurable team or scaling problem, not an arbitrary number of microservices [1].

## Begin with capabilities and invariants

Consider an order system with catalog browsing, checkout, stock reservations and payment authorization. Product descriptions may be stale for a short period, but **available stock must not become negative after a committed reservation**. That invariant identifies an inventory authority. An order service can request inventory reservations, but if the two run in separate databases a single local ACID transaction no longer spans both. The boundary decision therefore changes the correctness argument.

Map business capabilities first: catalog manages descriptions; inventory owns available and reserved units; checkout owns customer-facing order identity and lifecycle; payment integration owns references to provider operations. Define who may change each piece of data and whether other components read an API, consume an event, or query a derived view. Shared direct writes to another domain's tables destroy ownership even if each team deploys a separate service.

## Modular monolith as a baseline

In a modular monolith, packages enforce domain interfaces while one deployable artifact owns the process. A single database can support local transactions across order and stock tables when justified, and a function call avoids network timeout ambiguity. Modules remain separately testable if they do not import each other's private tables, internal classes or mutable globals. An internal API is useful even before extraction [1].

A monolith is not inherently one unstructured file. Conversely, splitting a tightly coupled application into containers can create a **distributed monolith**: teams must coordinate every deployment and failures propagate synchronously through all services. Decomposition is justified by independent scaling patterns, ownership, regulatory isolation, deployment cadence or fault containment **when the added network and consistency cost is acceptable**.

![A domain boundary is a decision about ownership, not merely separate deployment boxes.](/diagrams/service-boundaries.svg)

## Synchronous calls and partial failure

A synchronous checkout call to inventory is easy to read: reserve(sku,qty) returns success or failure. After a network timeout, however, checkout cannot tell whether inventory committed the reservation and the response was lost. Simply retrying without an **operation identity** risks reserving twice. Give the command a stable scoped idempotency key and persist its outcome under the inventory authority.

An RPC chain also increases the ways a request can fail. If four independent dependencies must all be available and each independently succeeds with probability 0.999 in the same request window, their joint success probability is 0.999⁴ ≈ 99.60%. This is a *deliberately simplified independence model*, not an observed availability forecast. Correlated failures, caching, fallback, retries, demand and dependency placement change the result. Similarly, adding the p95 latency of every hop does **not** give the end-to-end p95.

~~~python
def independent_chain_success(probabilities):
    if any(not 0 <= p <= 1 for p in probabilities):
        raise ValueError("probability out of range")
    result = 1.0
    for p in probabilities:
        result *= p
    return result

assert round(independent_chain_success([0.999] * 4) * 100, 2) == 99.60
assert independent_chain_success([]) == 1.0
assert independent_chain_success([1, 0.5]) == 0.5
try:
    independent_chain_success([1.2])
    assert False
except ValueError:
    pass
~~~

A product of independent probabilities is only valid under the stated independence model. It must not become an automatic sizing formula for real microservice architectures. Measure actual user journeys and dependencies before setting SLOs.

## Asynchronous collaboration and the outbox

An asynchronous flow can persist order state plus an **outbox event** in one database transaction. A relay later publishes the event to a broker, and inventory or payment workers consume it. This reduces synchronous waiting but makes completion **eventual**: a client may see pending state while background work runs. The broker may redeliver messages, so consumers deduplicate by stable event or command identity [2].

Event delivery does not grant atomicity across services. If order and inventory own separate databases, use a saga-like protocol with explicit states, deadlines and compensation. A stock release after failed payment is a new operation, not a rollback of an external charge. A payment provider timeout leaves an uncertain outcome; reconcile before making assumptions about money movement.

## Decide ownership at the consistency boundary

A good boundary minimizes invariants that span authorities. For example, keep stock units and reservation ledger under one owner, even if other domains consume `InventoryReserved` events. Catalog search may materialize availability estimates, but those cannot authorize a sale. A global uniqueness rule—such as one username across customers—requires a known authoritative registry rather than unrelated per-service uniqueness indexes.

When callers require immediate consistency across several entities, splitting the entities prematurely often adds a distributed transaction or redesign burden. In contrast, a read model that tolerates lag can be replicated asynchronously and scaled separately. Record consistency requirements per API: strong committed read, read-your-writes, eventually consistent, or bounded staleness.

## Evolution: extracting without an all-at-once rewrite

A staged migration can keep the old application authoritative while routing one capability through a defined adapter. First isolate interfaces inside the process; then measure cross-module calls, define data ownership and remove direct table access. Build a new service behind the adapter, backfill state, stream changes and verify parity. Cut traffic in a controlled phase, observe error and latency, and retain a rollback plan [1].

Dual writes to old and new databases are not automatically safe: a crash after one commit can leave conflicting states. Choose a source of truth during transfer, replay changes with stable version markers and block stale writes at cutover. Beware schema changes that make rollback of application code incompatible with persisted records.

## Latency, failures and operating cost

| Choice | Useful when | Hidden cost |
| --- | --- | --- |
| Module in monolith | Same transactional scope, small team | Shared process/deploy failure domain |
| Synchronous API | Caller needs immediate result | Partial failure, timeout ambiguity |
| Outbox plus events | Work can complete later | Lag, duplicates, replay operations |
| Separate service | Independent scaling, teams or isolation | Ops, ownership, API versioning |
| Shared database writes | Rare legacy transition only | Couples contracts and data authority |

Beyond CPU and storage, count service-to-service authentication, secrets, tracing, incident ownership, deployment pipelines and on-call. Four services needing synchronized updates may be more expensive to change than one well-designed module. Extraction is not automatically an improvement in maintainability.

## Exercises and verification

1. Define the stock invariant and explain why an asynchronously updated catalog cache cannot enforce it.
2. Trace timeout after inventory commits and show how a durable idempotency key resolves replay.
3. Recompute the simplified independent success probability for three dependencies at 99% each; list two reasons it cannot predict a real service SLO.
4. Propose an incremental catalog extraction that retains a single authoritative source through migration.
5. Compare a synchronous inventory call and an outbox event on latency, correctness, retry behavior and operational recovery.

**Related chapters:** [System Design process](/en/topics/system-design-process/), [order service](/en/topics/system-design-order-service/), [asynchronous messaging](/en/topics/asynchronous-messaging/) and [API reliability](/en/topics/api-reliability/) expand the techniques [1][2].
