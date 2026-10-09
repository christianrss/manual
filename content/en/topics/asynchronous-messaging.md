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

## A precise message lifecycle

Separate the states **accepted by producer**, **durably stored by broker**, **delivered to consumer**, **business effect committed** and **acknowledged**. A successful producer HTTP response is not proof of durable eventual execution unless acceptance is coupled to durable storage. Likewise, delivery is not acknowledgment. A worker may crash in any interval between those states, creating different recovery obligations [1].

In an at-least-once system, the broker can redeliver when the consumer's acknowledgment is lost even though the effect committed. The consumer needs a durable deduplication key with a uniqueness constraint in the same transaction as local state changes. An in-memory 'seen IDs' set fails after restart; a read-then-write without a unique constraint races. If the effect is an external charge, the remote API's idempotency contract or reconciliation is required in addition to local database deduplication.

## Ordering and retries are scoped guarantees

Many brokers preserve ordering only within a queue or partition, not across independent consumers or partitions. If events `Created(v1)` and `Cancelled(v2)` arrive out of order, applying them naively may resurrect a cancelled entity. Include a per-entity version or monotonic sequence number, and specify how gaps are handled. Retry delays can reorder effects even when the normal path is ordered.

For retries, distinguish permanent validation failures from transient errors. Use bounded exponential backoff with jitter, maximum attempts or age, per-dependency concurrency limits and a dead-letter policy. A timeout means the remote operation's **outcome may be unknown**; retrying a non-idempotent command may duplicate effects [1].

## Derive recovery capacity, not just queue growth

If arrivals average `λ=80` jobs/s while workers can finish `μ=100` jobs/s, net drain is `μ−λ=20` jobs/s. An existing backlog of 12,000 jobs then needs at least `12,000/20=600` seconds to drain **provided those rates remain stable and failures cause no extra attempts**. When `λ≥μ`, backlog cannot drain at steady state. Retry traffic increases effective offered load and can create an unstable feedback loop [2].

Let `A` be age of oldest ready message. Two queues with 10,000 messages can have radically different customer impact depending on processing time and deadlines; backlog count alone is insufficient. Track end-to-end time, poison-message isolation, counts by attempt number, DLQ age and oldest-message age.

## Idempotent consumer pseudo-transaction

```text
on(message with id, entity_id, version):
    BEGIN
      INSERT INTO inbox(id) VALUES (message.id)
      IF unique-key conflict:
          ROLLBACK/COMMIT NO-OP; ACK; RETURN
      CHECK entity version and domain invariants
      APPLY business update
    COMMIT
    ACK broker message
```

This schematic assumes inbox and business entities share one transactional database. It cannot promise exactly-once effects for calls to systems outside that transaction. If the process crashes after commit and before ACK, the unique inbox record makes redelivery harmless for the local effect. If it crashes before commit, the broker retries after its visibility/acknowledgment policy. Think explicitly about transaction isolation and broker reconnects.

## Verification under faults

Test crash before effect, crash after commit but before ACK, duplicate messages with the same ID, two concurrent workers receiving one ID, reversed event versions, poison messages, disconnected broker and slow downstream API. Verify not just final state but number of externally visible effects. This exercise is a fault matrix: each possible interruption must have an explicit recovery outcome and observable signal.

## Exercises and verification
1. A worker commits a reservation then loses the ACK. Explain which unique database constraint makes redelivery safe.
2. A queue with 12,000 pending jobs accepts 80/s and completes 100/s. Ignoring other failures, approximate drain time: `12,000 / (100−80) = 600 seconds`.
3. Write three separate SLOs for enqueue availability, end-to-end completion latency and duplicate business effects. They measure different properties.

Asynchronous architecture is successful only when delays, duplicates and lost connectivity are part of the design, not afterthoughts.
