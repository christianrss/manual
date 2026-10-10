---
id: system-design-interview-workshop
title: "System Design Interview Workshop: Multi-Tenant Webhook Delivery"
description: "Solve a complete webhook-delivery design with workload estimates, durable outbox, idempotency, retries, queue recovery and changed constraints."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [system-design-process, asynchronous-messaging, api-reliability]
sources:
  - {title: "Amazon SDE II Interview Preparation", url: "https://amazon.jobs/content/en/how-we-hire/sde-ii-interview-prep", kind: "official preparation overview"}
  - {title: "AWS Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
  - {title: "AWS Builders Library — Timeouts, retries, backoff with jitter", url: "https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/", kind: "original engineering guidance"}
---
A system-design exercise is not solved by sketching a queue and a database. A useful answer starts from **business semantics, a workload, an ownership model and a failure definition**, then changes the design when interview constraints change. This original workshop designs a multi-tenant outbound webhook dispatcher: SaaS customers register endpoints, the product emits events, and delivery workers send signed HTTP requests. It is a worked engineering exercise, not an official or recalled interview question. Public system-design guidance emphasizes asking clarifying questions and evaluating practicality, reliability and scalability rather than memorized diagrams [1].

## Prompt, requirements and clarification questions

The initial prompt is: “Design a webhook service that sends each committed account event to subscribed customer URLs.” Before drawing boxes, ask what `delivered` means. In this exercise it means the remote endpoint returned an eligible **2xx acknowledgment** before the client's deadline. It does **not** mean the customer successfully processed the webhook or persisted its own business effect. Assume at-least-once attempts, a maximum retention/retry window of 24 hours, per-tenant access control, observable event status, and customer-managed secret rotation.

Clarify subscription count per event, maximum payload size, acceptable delay, order requirements, custom retry policy and whether users can replay historical events. Assume **ordering is not guaranteed across different event IDs**. Per-object ordering can be added later with partitioning and serial dispatch, but it reduces throughput and adds head-of-line blocking. Define what happens to an event if a subscription is disabled after it was queued: the service must check current delivery policy before dispatch.

## Capacity model with explicit assumptions

Assume **200,000 source events/day**, an average of three active subscriptions per event, and a **50× peak-to-average task rate**. The mean outbound work is 600,000 delivery tasks/day ÷ 86,400 seconds ≈ 6.94 tasks/s, and the hypothetical peak is approximately 347.2 tasks/s **before retries**. If one worker has been measured to handle 60 HTTP attempts/s at its target timeout distribution, six workers cover the ideal peak, and a seventh provides one-worker spare capacity under ideal balancing. Provider quotas, uneven tenant traffic and retries may invalidate that simple count.

Payload bytes and attempt counts are separate dimensions. If each outbound attempt sends a 2 KiB body, a 350 attempts/s peak represents around 700 KiB/s outbound payload before HTTP/TLS overhead. An average event with three subscriptions creates three **delivery identities**, not necessarily three successes. Storage capacity must include durable outbox entries, attempt history, indexes and tenant retention; no single multiplication by payload size captures all of them.

## Authority, data model and accepted-event contract

The event-producing service is authoritative for whether an event **committed**. It writes the business change and an outbox entry in a single local transaction. The webhook relay publishes a stable event ID and its routing context to a broker. The dispatcher resolves the relevant subscriptions and creates deliveries uniquely identified by (event_id, subscription_id). A subscription registry owns endpoint URL, tenant, active flag, secret version and rate policy.

![An outbox feeds unique delivery tasks, workers and tenant-scoped retry queues.](/diagrams/webhook-design-drill.svg)

One possible data model is `Event(id, tenant_id, type, created_at)`, `Subscription(id, tenant_id, url, active, secret_version)`, `Delivery(event_id, subscription_id, state, next_attempt_at, attempts, lease_version)` and `Attempt(delivery_id, attempt_no, response_class, duration)`. The unique pair on Delivery makes event fanout **logically idempotent**, while leases plus compare-and-swap avoid two healthy workers claiming the same row simultaneously. These constraints belong in the durable authority, not a Python process-local dictionary.

An internal API may expose `GET /v1/webhook-deliveries/{id}` scoped to the authenticated tenant, plus replay requests with stable operation IDs. Do not expose arbitrary tenant or subscription identifiers without authorization; otherwise guessing a delivery ID can reveal endpoints or event payloads. External callbacks should authenticate the sender using a signed payload, timestamp and replay protection agreed with clients.

## Why queues do not create exactly-once effects

The relay can publish successfully and crash before marking its outbox row complete, so the broker may receive a duplicate event. A worker may send a webhook that the customer processes, then lose the acknowledgment. A retry can trigger another business action at the receiver. An HTTP signature proves sender authenticity under key management assumptions; it does **not** make receiver processing exactly once. Send a stable delivery/event identifier so the receiver can store a deduplication key atomically with its own effect when possible [2].

For provider and tenant fairness, do not place unlimited work from a single noisy subscription into one global FIFO that blocks every other customer. Introduce bounded queues, tenant admission limits and fair scheduling, preserving metrics by account. Separate dead-letter/quarantine handling for persistent 4xx errors and malformed endpoints from retriable timeouts and 5xx conditions, under the service's documented policy.

## Retry schedule: bounded exponential growth

A simple exercise models capped exponential backoff. For attempt n numbered from one, delay = min(cap, base × 2^(n−1)). The **production schedule should add jitter**, a deadline budget, per-tenant rate limits and response-specific policy; deterministic retries from thousands of failed workers can synchronize load spikes [3].

~~~python
def retry_delay_seconds(attempt, base=2, cap=300):
    if not isinstance(attempt, int) or attempt < 1:
        raise ValueError("attempt begins at one")
    if base <= 0 or cap <= 0:
        raise ValueError("positive time parameters required")
    # Bound the exponent before constructing enormous integers.
    exponent = min(attempt - 1, cap.bit_length() + 2)
    return min(cap, base * (2 ** exponent))

assert [retry_delay_seconds(n) for n in range(1,7)] == [2,4,8,16,32,64]
assert retry_delay_seconds(30) == 300
try:
    retry_delay_seconds(0)
    assert False
except ValueError:
    pass
~~~

The function assumes integer-second cap/base; it is a local **backoff policy illustration**, not a scheduler or a time guarantee. A negative or non-integer attempt is invalid. This bound uses bit_length on the integer cap to avoid oversized exponents. Real workers additionally must persist `next_attempt_at`, check whether the subscription remains enabled, and avoid retries beyond retention expiry.

## Backlog scenario and recovery arithmetic

Suppose a major network route fails for **15 minutes** while tasks continue arriving at an approximated constant 350 tasks/s. The queue grows by 350 × 900 = **315,000 tasks**, ignoring retries and timeouts already consuming worker slots. After recovery, if healthy dispatch capacity is 500 tasks/s but incoming work remains 350/s, the drain margin is only **150 tasks/s**. Clearing the pre-existing backlog requires 315,000 ÷ 150 = **2,100 seconds, or 35 minutes**, even after connectivity is restored [3].

~~~python
from math import ceil

def drain_seconds(incoming, outage_seconds, processing):
    if incoming < 0 or outage_seconds < 0 or processing <= incoming:
        raise ValueError("no positive drain margin")
    pending = incoming * outage_seconds
    return pending, ceil(pending / (processing - incoming))

assert drain_seconds(350, 900, 500) == (315000, 2100)
assert drain_seconds(0, 600, 500) == (0, 0)
try:
    drain_seconds(350, 900, 340)
    assert False
except ValueError:
    pass
~~~

These figures are **fluid approximations**, not tail latency guarantees. If retries consume 200 extra attempts/s after recovery, the capacity remaining for new tasks and backlog may collapse. The correct analysis includes retry budgets, quota constraints, prioritization, queue age percentiles, and separate failure domains for destination URLs.

## Change the requirements mid-design

A strong design survives follow-up changes rather than defending its first diagram. Suppose a **single enterprise tenant generates 70% of events**. The global FIFO creates head-of-line blocking: use per-tenant or weighted-fair dispatch and monitor quotas, accepting additional scheduling complexity. Suppose some clients require **ordering per customer object**. Partition delivery tasks by (tenant_id, object_id) and use a serial logical consumer/sequence ledger, noting that a dead message can stall later events unless policy allows skipping.

Now suppose regulators require deleting payloads after 24 hours while retaining aggregate delivery metrics. Keep the event payload and attempt metadata under separate retention policies, redact logs, and document whether replays remain possible after expiry. Suppose a receiver is down for two days: a 24-hour retention rule means the dispatcher cannot promise delivery after the expiry. Expose a terminal state and clear replay semantics instead of leaving an infinite backlog.

## Evaluation rubric, experiments and failure cases

| Decision | Evidence required | Common unsupported claim |
| --- | --- | --- |
| Durable acceptance | Business change and outbox share a commit | Broker acknowledgment is equivalent |
| Delivery identity | Unique event/subscription mapping | Queue transport gives exactly once |
| Backoff | Capped retries, jitter and deadlines | Retrying faster increases reliability |
| Tenant isolation | Fair scheduling and measured quotas | One FIFO serves everyone fairly |
| Ordering | Explicit partition/sequence contract | Timestamps guarantee global order |
| Recovery | Drain margin, replay and reconciliation | Queue clears immediately after outage |

Verify with tests for duplicate relay publications, concurrent worker claims, lost 2xx response after customer effect, cross-tenant status access, secret rotation, long-lived disabled endpoints, and queue recovery under skew. Track time from event commit to acknowledged endpoint (p50/p95/p99), attempt counts, oldest queued age, tenant fairness, dropped/expired deliveries and failed signatures.

## Exercises and verification

1. Derive the 347.2 tasks/s peak and explain why a retry storm could exceed it.
2. Show a two-step crash sequence proving why even a perfect outbox cannot guarantee exactly-once processing at a remote customer.
3. Modify the retry rule to add a deterministic seeded **test-only** jitter source and state its limitations.
4. Recompute backlog time if effective processing falls from 500 to 400 tasks/s while arrival stays 350 tasks/s.
5. Sketch an authorization test preventing tenant A from requesting the status or replay of tenant B's delivery.

**Related chapters:** [System Design process](/en/topics/system-design-process/), [API idempotency](/en/topics/api-reliability/), [queues and messaging](/en/topics/asynchronous-messaging/), [notifications case](/en/topics/system-design-notifications/) and [service boundaries](/en/topics/service-boundaries/) explain the building blocks.
