---
id: system-design-architecture-review
title: "System Design Architecture Review: Checkout Invariants and Recovery"
description: "Review a proposed checkout architecture for overselling, dual-write loss, payment ambiguity, queue overload and tenant isolation."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [system-design-order-service, system-design-process, asynchronous-messaging]
sources:
  - {title: "AWS Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
  - {title: "AWS Builders Library — Avoiding Insurmountable Queue Backlogs", url: "https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/", kind: "original engineering guidance"}
---
A System Design proposal should survive a **hostile but constructive architecture review**: what is the authority for each decision, what happens when a dependency times out, how does backlog grow, and which assumptions must change as scale or regulatory constraints shift? A diagram that includes a queue, database and cache is not sufficient evidence. This workshop reviews a fictional marketplace checkout architecture and records **blocking defects, conditional approvals and measurable follow-up work** rather than simply declaring a design “scalable” [1][2].

## Proposal to review: checkout across services

A candidate proposes an API receiving an order request, checking product availability from a Redis cache, writing an order record, publishing `OrderCreated` to RabbitMQ, and charging the customer in a separate worker. A dashboard shows order status from an eventually consistent search index. The application has a CDN and a global load balancer. At first glance the services seem decoupled and asynchronous; the important question is which of their **guarantees** are actually supported.

The functional requirements are simple: an authorized account submits a cart, receives one logical order even when retrying, never receives a confirmed order for unavailable stock, and can see whether payment succeeded. The nonfunctional requirements include recoverable outages, tenant isolation, auditability of payment references and a defined maximum time until a pending order reaches a terminal state. None of these requirements is proved by boxes labeled “cache” or “queue.”

## Blocking defect 1: cache decides whether stock can be sold

The proposal authorizes a purchase using a cached number of available units. Two checkout workers may both read stock=1 and issue successful orders before the cache updates. This violates the invariant **committed reservations cannot exceed authoritative available stock**. A cache may show an estimate to the UI, but the reservation decision must be made through a transactional authority, such as a guarded database update under the stock owner [1].

A reviewed design therefore separates *display* from *commit*. Catalog pages can tolerate seconds of stale data; the order state transition cannot. The reviewer should ask for an explicit test in which two independent requests race for the final unit. The expected outcome is one accepted reservation and one insufficient-stock response. A mock cache test alone does not demonstrate this property.

## Blocking defect 2: event publication and order commit can diverge

If the API commits its order row and then publishes a broker event, a crash between the two operations leaves an order with no processing intent. If it publishes first and then crashes before committing, the consumer may see an event for a nonexistent order. The design needs a transactional outbox or another carefully defined atomic handoff; the broker's publisher confirm is **not** a transaction commit spanning the application database [2].

A relay can publish an outbox event and crash before marking it done, producing a duplicate. Consequently the consumer also needs idempotency and a stable operation/event identity. “We use RabbitMQ” does not specify whether messages are durable, whether consumers ACK after committing their effects, how DLQs are inspected, or how replay avoids charging the same customer twice.

![Architecture review identifies consistency, durability and capacity defects before approving a checkout design.](/diagrams/system-design-review-gates.svg)

## Blocking defect 3: payment timeout interpreted as failure

The external payment provider might charge successfully and return no response. Starting a second charge with a new operation identity risks charging twice. A safe design stores an operation reference, uses the provider's documented idempotency contract where available, and **reconciles unknown outcomes** before taking another irreversible action. Compensation is a new action and may itself fail; it is not a magical distributed rollback [1].

Order states should distinguish `pending_payment`, `payment_unknown`, `paid`, `cancel_pending` and `cancelled` as required by the business flow. A timeout should not automatically set `payment_failed`. A reviewer should demand a sequence diagram or explicit state transitions for success, network ambiguity, duplicate notification and refund failure.

## Recompute volume after a peak change

Assume **150,000 orders/day**, each producing **two asynchronous processing tasks**, and a **30× peak-to-average workload multiplier**. This yields 300,000 tasks/day / 86,400 ≈ 3.47 tasks/s average, and approximately 104.17 tasks/s at peak, excluding retries and duplicates. If healthy workers process only 80 tasks/s, the peak deficit is approximately 24.17 tasks/s; after one hypothetical hour of constant peak load, backlog is **87,000 tasks**.

~~~python
from math import ceil
from fractions import Fraction

def peak_task_rate(orders_per_day, tasks_per_order, peak_factor):
    if orders_per_day < 0 or tasks_per_order < 0 or peak_factor < 0:
        raise ValueError("negative workload")
    return Fraction(orders_per_day * tasks_per_order * peak_factor, 86400)

def backlog_after_peak(arrival_rate, worker_capacity, seconds):
    if min(arrival_rate, worker_capacity, seconds) < 0:
        raise ValueError("negative argument")
    return ceil(max(0, arrival_rate - worker_capacity) * seconds)

peak = peak_task_rate(150_000, 2, 30)
assert round(float(peak), 2) == 104.17
assert backlog_after_peak(peak, 80, 3600) == 87000
~~~

This is a **fluid-rate teaching calculation**. Real arrival bursts, slow destinations, retries, quotas and task-size distributions change latency and queue dynamics. It does not establish that 80 workers suffice, because the number of workers is different from the **measured service capacity in tasks per second**. Reviewers should demand workload-specific throughput and tail latency tests.

## Outage exercise: draining the queue

Assume a downstream provider is unreachable for **20 minutes** while new tasks arrive at a constant **120 tasks/s**. With zero successful processing during outage, backlog reaches 144,000 tasks. When connectivity returns, processing resumes at 150 tasks/s while arrivals remain at 120/s; **only 30 tasks/s** can drain the backlog, requiring 4,800 seconds (80 minutes), even without retries.

~~~python
def drain_time(backlog, incoming, processing):
    if backlog < 0 or incoming < 0 or processing <= incoming:
        raise ValueError("positive spare capacity required")
    return ceil(backlog / (processing - incoming))

assert 120 * 20 * 60 == 144000
assert drain_time(144000, 120, 150) == 4800
assert drain_time(0, 120, 150) == 0
~~~

A review should reject any “five-minute recovery” target if measured capacity and backlog arithmetic contradict it. Options include admission control, reserved recovery workers, tenant fairness, bounded retries and differentiated priorities. Those changes can shift cost and fairness, so they require product decisions, not just tuning a queue size.

## Tenant isolation and authorization checks

The architecture allows multiple sellers and buyers. IDs from an API route or message are not themselves permission to read another tenant's order or payment status. Every read and state transition must be scoped to an **authenticated principal and authoritative tenant context**, including background workers and exports. A stale search index must not bypass the order database's authorization decision.

If a tenant generates 80% of events, one FIFO can dominate worker capacity. A reviewer should ask whether the system needs per-tenant quotas, isolation of large tenants or fair scheduling, and how those policies interact with paid service tiers. Partitioning by tenant may help routing but introduces skew and potential hot partitions.

## Approve conditionally, with executable evidence

| Finding | Severity | Evidence required |
| --- | --- | --- |
| Cached stock authorizes checkout | Blocking | Concurrent last-unit reservation test |
| No order/outbox atomic commit | Blocking | Crash before/after commit and relay replay |
| Payment timeout treated as rejection | Blocking | Unknown-outcome reconciliation drill |
| No backlog/recovery calculation | Blocking for defined SLO | Capacity test with arrival/retry budgets |
| Order status from stale search alone | Conditional | Read model lag and authorization guard |
| No release and rollback owner | Operational risk | Migration, rollout and on-call runbook |

Reviewers should separate **approval for a constrained first release** from claims of universal production readiness. An architectural finding is not fixed by assigning it a ticket; the team must close it with specific tests, runbooks and monitored thresholds. This is a review of one hypothetical design, not a proof that a single reference architecture fits every organization.

## Exercises and verification

1. Give a two-request interleaving showing overselling when cache stock is used as authority.
2. Show both crash windows in database-then-broker and broker-then-database dual writes.
3. Specify a payment state machine with a durable `unknown` state and explicit reconciliation.
4. Recompute peak backlog if worker capacity rises from 80 to 110 tasks/s.
5. Write an architecture approval note with **three blocking findings**, each with an objective verification test.

**Related chapters:** [Order service design](/en/topics/system-design-order-service/), [RabbitMQ integration](/en/topics/rabbitmq-durable-consumer-integration/), [PostgreSQL concurrency](/en/topics/postgresql-concurrency-integration/) and [adaptive design](/en/topics/adaptive-system-design-assessment/) support a rigorous review [1][2].
