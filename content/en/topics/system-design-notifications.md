---
id: system-design-notifications
title: "System Design Case Study: Durable Multi-Channel Notifications"
description: "Design a complete notification platform with SLOs, APIs, transactional outbox, queue capacity, provider failures and recovery tests."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [system-design-process, asynchronous-messaging, api-contracts-pagination, capacity-estimation]
sources:
  - {title: "AWS Builders Library — Avoiding Insurmountable Queue Backlogs", url: "https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/", kind: "original engineering guidance"}
  - {title: "AWS Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
  - {title: "Google SRE Workbook — Implementing SLOs", url: "https://sre.google/workbook/implementing-slos/", kind: "engineering workbook"}
---
A notification platform makes an effective **end-to-end system design exercise** because it combines user preferences, durable event identity, asynchronous work, external providers, retries, quotas and observable completion. The hardest question is not which queue to choose: it is what counts as a successful notification and what must remain true when a consumer crashes after an external provider has accepted the message. This study models an intentionally hypothetical multi-channel service rather than claiming to describe any particular company's implementation [1][2].

## Product requirements and explicit exclusions

Assume applications submit an event for a user through an authenticated API. The service may send email and push notifications according to user preferences. Clients can query status by an event identifier. Required properties: no cross-tenant access, no loss of an acknowledged durable event under the specified storage failure model, bounded retries, and the ability to stop attempting an opted-out channel. Editing templates or full marketing analytics are out of scope.

Define success in stages: **accepted** means request and event are persisted; **queued** means a channel task exists durably; **provider accepted** means the external provider acknowledged a request; and **delivered to person** may be unobservable. Avoid labeling provider acceptance as proof that an email was read or a push appeared on a device. Per-channel outcomes are separate from aggregate event status.

## SLOs and workload assumptions

Assume **one million submitted events/day**, two channels per event on average, and a 20× burst relative to the daily mean. These are hypothetical exercise inputs, not production measurements. That yields about 11.57 events/s on average and 231.48 events/s at peak, with approximately 23.15 delivery tasks/s on average and 462.96 tasks/s at peak before retries. If a worker sustains a **measured safe** 40 attempts/s for this exact provider mix, at least twelve workers are required to cover that peak under ideal distribution; a thirteenth gives N+1 application-worker capacity, not provider availability.

An illustrative objective is: among eligible, accepted notifications whose provider is available within its contractual limits, 99% receive provider acknowledgment within five minutes. This excludes messages lacking a reachable destination and must specify how outages are counted; **do not hide a provider outage by silently excluding it**. A complete service-level objective must be agreed with product owners and monitored from accepted event to provider acknowledgment [3].

## Architecture and authority boundaries

The path is: client → authenticated request API → **transactional event + outbox store** → outbox relay → durable message broker → delivery workers → email/push providers. Read-only status requests go to the event database or a derived read model. A preferences store determines eligible channels; template rendering operates under explicit data-classification and secret-handling rules.

![Notification acceptance, durable outbox and delivery workers with retry outcomes.](/diagrams/notification-system-design.svg)

The event database is the **authority** for accepted event identity and initial delivery intent. A broker acknowledgment is not a substitute for database commit. When event and outbox are written in one local transaction, either both persist or neither does; the relay can later publish the outbox record. If the relay publishes then crashes before marking progress, it may publish twice: consumers must tolerate repeats [1][2].

## API contracts and durable keys

A sample POST /v1/notifications accepts user reference, event type, template variables and client operation ID. Authenticate tenant and verify the user belongs to its scope; limit payload size and reject unsupported channels. Use a durable uniqueness constraint on (tenant_id, client_operation_id) and a fingerprint to distinguish retries from different new intents. Return 202 with event ID and a GET /v1/notifications/{id} status URL after durable acceptance **if processing is asynchronous**.

Define each delivery attempt's logical key as (event_id, channel). A provider-specific request ID or idempotency token should be passed when the provider contract supports it. If a client repeats the same request after timeout, the API must retrieve the already persisted event instead of scheduling another logical notification. The same key with a different payload receives a documented conflict.

## Data model and state transitions

One practical relational model uses Event(id,tenant_id,user_id,type,status,created_at,client_key,fingerprint), Delivery(event_id,channel,state,attempts,next_attempt_at,provider_ref,lease_token), and Outbox(id,event_id,payload,published_at). A unique index covers Event(tenant_id,client_key) and another covers Delivery(event_id,channel). Avoid placing secrets or personally identifying template data in uncontrolled broker logs.

A delivery moves **pending → leased → provider_accepted**, or **leased → retry_wait → leased**, and ends in **permanent_failure** when retry policy exhausts or a nonretryable result is received. A lease must expire and have a fencing token or equivalent protection; otherwise a stalled worker can later commit obsolete state. Cancellation and opt-out semantics need an explicit priority: an opted-out channel must not continue sending merely because old work is already queued.

## Worker idempotency: an executable local model

The following model illustrates **logical deduplication**, not durable exactly-once external sending. It stores a set of accepted (event, channel) outcomes within one process. A real worker must persist this state transactionally and manage lease races and provider ambiguities.

~~~python
class LocalDeliveryModel:
    def __init__(self):
        self.accepted = set()
        self.provider_calls = []

    def deliver(self, event_id, channel, allowed=True):
        if channel not in {"email", "push"}:
            raise ValueError("unknown channel")
        key = (event_id, channel)
        if key in self.accepted:
            return "already_accepted"
        if not allowed:
            return "suppressed"
        self.provider_calls.append(key)  # Simulated provider acceptance.
        self.accepted.add(key)
        return "accepted"

model = LocalDeliveryModel()
assert model.deliver("e1", "email") == "accepted"
assert model.deliver("e1", "email") == "already_accepted"
assert model.deliver("e1", "push") == "accepted"
assert model.deliver("e2", "push", allowed=False) == "suppressed"
assert model.provider_calls == [("e1","email"),("e1","push")]
~~~

The two operations `provider_calls.append` and `accepted.add` are **not atomically coupled**. A crash after the provider accepts but before the durable success record creates an unknown outcome. Retrying may send twice unless the provider supports an idempotency key or a safe reconciliation mechanism. A unique local delivery row prevents duplicate local intent, not necessarily duplicate external delivery [2].

## Backlog calculation and recovery proof

If the downstream provider cannot accept work for 20 minutes while new tasks arrive at **463 tasks/s**, backlog grows by about 555,600 tasks, ignoring retries. When the provider recovers and aggregate workers safely process **600 tasks/s**, the available drain margin is only 600−463=137 tasks/s if incoming traffic stays at that peak. Clearing the backlog then takes about 4,055 seconds, **67.6 minutes**, assuming constant rates and no additional failures. Queueing can therefore turn a short outage into over an hour of delayed user notifications [1].

~~~python
from math import ceil

def backlog_recovery(arrival_rps, outage_seconds, processing_rps):
    if arrival_rps < 0 or outage_seconds < 0 or processing_rps <= arrival_rps:
        raise ValueError("need positive recovery margin")
    backlog = arrival_rps * outage_seconds
    return backlog, ceil(backlog / (processing_rps - arrival_rps))

pending, seconds = backlog_recovery(463, 20 * 60, 600)
assert pending == 555600
assert seconds == 4056
try:
    backlog_recovery(463, 1200, 400)
    assert False
except ValueError:
    pass
~~~

This is a fluid-rate **scenario**, not a queueing tail-latency distribution. Real provider quotas, retry jitter, tenant fairness and nonconstant arrivals affect recovery. Mitigations include admission limits, reserved capacity for urgent notifications, queue isolation per priority or tenant, deduplication before enqueue, and drop/expiry policies that are explicitly accepted by product owners.

## Failure analysis and observable invariants

| Fault | Safe response | Verification |
| --- | --- | --- |
| API crashes before commit | No accepted event; retry may create | Repeated client key |
| API crashes after commit | Reuse durable event on retry | Unique key and fingerprint |
| Relay publishes twice | Consumer deduplicates logical delivery | Duplicate broker message injection |
| Provider accepts then response lost | Outcome ambiguous; reconcile or provider idempotency | Simulate timeout after provider effect |
| One tenant floods queue | Partition/admission and fair scheduling | Per-tenant lag and latency |
| User opts out before delivery | Check effective preference policy before send | Opt-out race regression test |
| Worker dies holding lease | Lease recovery and fencing | Crash/failover test |

A single global queue can allow noisy tenants to delay everyone. However, queue per tenant can be expensive at high cardinality; grouping or shuffle-sharding policies must be evaluated against isolation goals. **At-least-once delivery attempts plus idempotent effects** are usually easier to reason about than an unsupported claim of end-to-end exactly once.

## Sizing, cost and observability

Estimate broker storage as queued message size × retained messages, separately from event and status row storage. Count retries in **attempts**, not only distinct notifications: provider egress and cost grow with attempts. Track accepted event rate, lag from event commit to task creation, oldest queued age, attempts per task, provider timeout/error categories, end-to-end p95/p99 to provider acceptance, suppressed notifications and permanent failures.

A successful HTTP acceptance can coexist with a nonfunctional worker fleet. Therefore a service SLO should measure **business outcome** and not only API 202 rate. A design review must identify operational owners for queue recovery, provider quota changes, templates, secrets and privacy incidents.

## Exercises and verification

1. Recalculate task peak and worker requirement if average channels per event drops from two to one.
2. Explain why outbox transaction solves the database-to-broker gap but cannot make provider email delivery exactly once.
3. Trace two crash points: before outbox commit and after provider acceptance before success persistence.
4. Derive the 67.6-minute recovery result; state the assumption that makes it invalid when provider quota is only 500 tasks/s.
5. Propose tenant-isolation and opt-out tests for duplicate events, queue backlog and late delivery.

**Related chapters:** [System design process](/en/topics/system-design-process/), [asynchronous messaging](/en/topics/asynchronous-messaging/), [API contracts](/en/topics/api-contracts-pagination/) and [capacity estimation](/en/topics/capacity-estimation/) provide the underlying methods.
