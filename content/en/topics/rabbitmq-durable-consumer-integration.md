---
id: rabbitmq-durable-consumer-integration
title: "RabbitMQ Integration Lab: Redelivery and Transactional Inbox"
description: "Test a real RabbitMQ consumer disconnect, redelivered messages and PostgreSQL inbox deduplication with manual acknowledgments."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [failure-recovery-workshop, postgresql-concurrency-integration, asynchronous-messaging]
sources:
  - {title: "RabbitMQ — Consumer Acknowledgements and Publisher Confirms", url: "https://www.rabbitmq.com/docs/confirms", kind: "official broker documentation"}
  - {title: "RabbitMQ — Work Queues", url: "https://www.rabbitmq.com/tutorials/tutorial-two-python", kind: "official broker tutorial"}
  - {title: "PostgreSQL — INSERT ON CONFLICT", url: "https://www.postgresql.org/docs/current/sql-insert.html", kind: "official database documentation"}
---
An event can arrive **more than once** even when the publisher and broker are behaving correctly. A consumer can commit its business effect, lose the network connection, and disappear before acknowledging delivery. RabbitMQ then may requeue the still-unacknowledged message and deliver it to another consumer. The correct question is not “How do I make the queue exactly once?” but “Where can I make the business effect idempotent?” This workshop tests a **real RabbitMQ broker and PostgreSQL inbox** in GitHub Actions [1][2].

## Define acceptance, delivery and processing

A producer's request, a broker's acceptance, a consumer's receipt, a consumer's database commit and a broker acknowledgment are five separate events. RabbitMQ distinguishes **publisher confirms** (broker-side acceptance of publication) from **consumer acknowledgments** (consumer says a delivery can be removed). One does not substitute for the other [1].

For this exercise, a message has a stable event ID and one logical effect: increment the count of processed events by inserting one record in a database. We require **at most one committed inbox effect per event ID** under the one-database authority. We allow the RabbitMQ message to be delivered repeatedly if a consumer fails before acknowledgment. We do not claim business processing at an unrelated external payment provider is exactly once.

## What the integration test actually runs

The workflow launches a RabbitMQ 4 management container and a PostgreSQL 17 container on the Linux runner. The Python test connects with `pika` to AMQP on port 5672, declares a uniquely named durable queue, turns on publisher confirms, and publishes one persistent message with a stable `message_id`. It obtains the delivery with `basic_get(auto_ack=False)`, writes the event ID to a real PostgreSQL table, and closes the consumer connection **without acknowledging**.

![RabbitMQ requeues an unacknowledged message; a PostgreSQL inbox rejects duplicate effects.](/diagrams/rabbitmq-redelivery-inbox.svg)

A second connection reads the requeued message, asserts that its body and identity match, and observes RabbitMQ's redelivery flag. It attempts the same PostgreSQL effect, which is prevented by a primary key on the event ID. The second consumer then acknowledges the delivery, and the test checks that the database contains **one effect, not two**.

The executable source is [tests/test_rabbitmq_postgres_integration.py](https://github.com/christianrss/manual/blob/main/tests/test_rabbitmq_postgres_integration.py), run by the normal test discovery. This is genuine networked broker behavior and a genuine database constraint, not a stub returning a convenient value.

## The atomic inbox pattern

The receiver maintains `inbox(event_id PRIMARY KEY, effects)`. A transaction attempts `INSERT ... ON CONFLICT(event_id) DO NOTHING RETURNING event_id`. When a row is returned, the event was not previously recorded and the transaction can commit its local effect. If the unique key already exists, the consumer knows it already committed that event locally; it must **not repeat the effect** [3].

~~~sql
INSERT INTO inbox(event_id, effects)
VALUES ($1, 1)
ON CONFLICT(event_id) DO NOTHING
RETURNING event_id;
~~~

In this narrowly defined example, inserting the row **is** the business effect. In a real balance update, both the inbox insert and balance mutation must commit in **the same PostgreSQL transaction**. Recording a deduplication marker first and transferring money later leaves a crash window where the marker says “done” but money never moved. Reversing those independent writes creates a double-effect window.

## A finite model of delivery and effect

A pure Python model can demonstrate the distinction between **attempts** and **committed effects** without pretending to simulate the RabbitMQ protocol. Its accepted-delivery counter increments whenever a message is observed; the durable-effect set records logical event IDs.

~~~python
def process_deliveries(deliveries):
    seen = set()
    attempts = 0
    effects = 0
    for event_id in deliveries:
        attempts += 1
        if event_id not in seen:
            seen.add(event_id)
            effects += 1
    return attempts, effects

assert process_deliveries(["e1", "e1", "e2"]) == (3, 2)
assert process_deliveries(["e9"] * 5) == (5, 1)
assert process_deliveries([]) == (0, 0)
~~~

Unlike PostgreSQL, the local Python set is neither durable nor concurrency-safe across processes. The actual integration test supplies the persistent authority, while this model explains the expected identity logic in a form readers can execute without containers.

## Acknowledge only after the durable effect

Consumer acknowledgment should come **after** the transaction protecting the local effect commits. If it comes before the commit and the worker crashes, the broker may delete the delivery while the effect is missing. If the database commit succeeds but the broker ACK is lost, redelivery occurs; the durable inbox detects the duplicate. This prioritizes avoiding lost work over avoiding repeated attempts [1].

There is a subtle performance cost: keeping messages unacknowledged while a database transaction runs consumes prefetch capacity and holds broker delivery state. Bound the number of unacknowledged messages per consumer, apply backpressure, and monitor latency and unacked counts. Do not assume more consumers produce linear throughput if all update one hot database row.

## What a publisher confirm does not prove

The publisher turns on RabbitMQ confirmations and sends with a mandatory routing key to a declared queue. A successful confirmation means the broker accepted responsibility under the relevant queue/durability contract; it is **not evidence that the consumer applied the business effect**. Likewise, a message set as persistent and placed in a durable queue is not a substitute for testing broker restart, disk failure or clustered replication.

A publishing relay may crash after the broker accepts the event but before marking its own outbox row as published. It will publish the same identity again; the inbox pattern must tolerate **both duplicated publication and redelivery**. Database-to-broker atomicity still requires outbox reasoning [2].

## Failure matrix and test scope

| Failure boundary | Result | Protection |
| --- | --- | --- |
| Publisher fails before confirmation | Acceptance unknown | Retry with stable message ID |
| Broker accepted, relay crashes | May publish duplicate | Durable inbox key |
| Consumer closes without ACK | Broker redelivers | Manual acknowledgment |
| Consumer committed inbox, ACK lost | Repeat delivery, no second local effect | Unique transactional inbox |
| Consumer ACKs before effect | Can lose business action | Commit then ACK |
| External PSP effect completed, connection lost | Financial outcome unknown | PSP idempotency and reconciliation |

The current CI test explicitly checks the **consumer-close** case, publisher-confirm path and duplicate inbox effect. It does not stop the RabbitMQ server mid-write, test a quorum cluster, validate TLS or model multi-region network partitions. These are separate test plans, not implicit consequences of one green job.

## Exercises and verification

1. Draw the event ordering when a consumer commits its PostgreSQL inbox row and crashes before ACK; explain the next delivery.
2. Why is a unique inbox row insufficient if a bank balance update commits in a separate transaction?
3. Distinguish RabbitMQ publisher confirms from consumer ACKs and HTTP 202 returned by an upstream API.
4. Design a test that publishes the same logical event **twice** and still obtains one local effect.
5. State what a RabbitMQ node crash test or quorum-queue test would prove beyond the single-broker requeue scenario.

**Related chapters:** [Messaging fundamentals](/en/topics/asynchronous-messaging/), [fault injection](/en/topics/failure-recovery-workshop/), [PostgreSQL concurrency](/en/topics/postgresql-concurrency-integration/) and [webhook system design](/en/topics/system-design-interview-workshop/) explain the other boundaries.
