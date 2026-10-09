---
id: asynchronous-messaging
title: "Queues, Delivery Semantics and Idempotency"
description: "Design asynchronous processing with at-least-once delivery, acknowledgments, dead-letter queues, retries, idempotent consumers and backpressure."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [capacity-estimation, database-consistency]
sources:
  - {title: 'RabbitMQ — Reliability Guide', url: 'https://www.rabbitmq.com/docs/reliability', kind: official messaging documentation}
  - {title: 'AWS Builders Library — Avoiding Insurmountable Queue Backlogs', url: 'https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/', kind: engineering article}
---
Queues decouple a producer's acceptance of work from its eventual execution. They can smooth bursts and isolate failures, but they move correctness questions from a synchronous call stack into durable messages, acknowledgments and consumer retries. A queue is not, by itself, a guarantee that each business action occurs exactly once [1].

## Delivery models and acknowledgment
Under **at-most-once** delivery, a message may be lost but is not intentionally redelivered. Under **at-least-once**, the consumer may receive a duplicate after a crash or an acknowledgment failure. **Exactly-once business effect** generally requires more than a broker setting: the consumer must coordinate deduplication and durable state changes within its own correctness boundary.

A classic ambiguity: a worker charges a payment successfully, crashes before acknowledging the message, and the broker redelivers it. If the consumer repeats the charge without an idempotency check, the user can be charged twice. This is why stable message identifiers and idempotent processing are critical for externally visible effects.

## Example: idempotent state transition
The conceptual transaction is:

```text
BEGIN database transaction
  INSERT INTO processed_messages(message_id) VALUES (id)
    -- unique constraint; if already present, do not apply the effect again
  UPDATE inventory SET reserved = reserved + quantity WHERE ...
COMMIT
ACK message only after successful commit
```

The uniqueness constraint and state update must share an atomic transaction in the same database. A process crash **after commit but before ACK** then causes a duplicate delivery, which the unique key rejects. However, if an external API is called inside this workflow, database atomicity does not extend to that API. Use external idempotency keys, reconciliation or a carefully designed saga.

## Retry discipline and dead-letter queues
Not all failures are transient. Network timeouts may warrant bounded retries with exponential backoff and jitter, while a structurally invalid payload may need immediate rejection. An unbounded immediate retry loop can become a self-inflicted denial of service. A **dead-letter queue (DLQ)** is an operational place for messages that could not be processed under defined policy; sending to a DLQ does not solve the underlying error [1].

Messages should carry a schema/version, stable identity, timestamp and tracing correlation information. Consumers must be designed for out-of-order arrivals if global ordering is not guaranteed. A single partition or queue may preserve a narrower order than a multi-partition distributed system.

## Backpressure and queue stability
Let `λ` be average arrival rate in jobs/sec and `μ` be sustained processing capacity under the same workload. If `λ > μ` for a prolonged period, backlog grows approximately by `(λ−μ) × elapsed_seconds` before constraints change. For `λ=150`, `μ=100` and 10 minutes, backlog rises by about `30,000` jobs. Draining that backlog requires capacity above the **current** arrival rate, not merely above zero [2].

Do not measure queue health only through total count. Track **age of oldest message**, time from enqueue to completion, retry rate, poison-message rate and effective worker throughput. Bounded queue admission and explicit overload responses are often better than accepting work that cannot be completed in time.

| Failure | Observable symptom | Countermeasure |
| --- | --- | --- |
| Worker crashes before ACK | Duplicate processing | Idempotent consumer and durable commit |
| Poison message | Repeated failures | Retry cap, quarantine / DLQ |
| Arrival rate exceeds service rate | Backlog and latency rise | Admission control, scale workers or reduce work |
| Schema evolves incompatibly | Consumer parse errors | Versioned contracts and compatibility tests |
| Downstream rate limits | Retries amplify load | Backoff, concurrency limits, circuit breaker |

## Exercises and verification
1. A worker commits a reservation then loses the ACK. Explain which unique database constraint makes redelivery safe.
2. A queue with 12,000 pending jobs accepts 80/s and completes 100/s. Ignoring other failures, approximate drain time: `12,000 / (100−80) = 600 seconds`.
3. Write three separate SLOs for enqueue availability, end-to-end completion latency and duplicate business effects. They measure different properties.

Asynchronous architecture is successful only when delays, duplicates and lost connectivity are part of the design, not afterthoughts.
