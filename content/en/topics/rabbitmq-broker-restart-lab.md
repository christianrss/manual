---
id: rabbitmq-broker-restart-lab
title: "RabbitMQ Restart Lab: Durable Queues and Confirmed Messages"
description: "Restart a real single-node RabbitMQ container after a confirmed persistent publish and verify exact recovery, without claiming quorum failover."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [rabbitmq-durable-consumer-integration, asynchronous-messaging]
sources:
  - {title: "RabbitMQ — Queues and Durability", url: "https://www.rabbitmq.com/docs/queues", kind: "official broker documentation"}
  - {title: "RabbitMQ — Publisher Confirms and Consumer ACKs", url: "https://www.rabbitmq.com/docs/confirms", kind: "official broker documentation"}
  - {title: "RabbitMQ — Quorum Queues", url: "https://www.rabbitmq.com/docs/4.1/quorum-queues", kind: "official replicated queue documentation"}
---
A RabbitMQ consumer reconnecting after a **broker node restart** is not equivalent to a network-disconnected consumer reconnecting while the broker stays alive. A queue that exists only in memory can disappear when the node restarts. Even a durable queue does not make transient messages durable. This workshop executes a real **single-node broker restart** in GitHub Actions, preserving the service container and its storage, and verifies that a publisher-confirmed persistent message can still be consumed afterward [1][2].

## Three durability decisions, three different contracts

RabbitMQ distinguishes queue durability, message delivery mode and publisher confirmation. A **durable queue** persists queue metadata for recovery after restart. A **persistent message** asks the broker to retain the message across restarts under its storage guarantees. **Publisher confirms** tell the producer when the broker has accepted responsibility, according to the queue and message type. Using only one or two of these mechanisms does not establish the same expectation as combining them [1][2].

This test uses a **classic queue on one node** and a message with `delivery_mode=2`. The queue is declared `durable=True`, the channel uses `confirm_delivery()`, and the publisher closes the connection after the successful publish call. The exercise does not assert that one classic queue is replicated: RabbitMQ 4 classic queues are not multi-node replicated structures [3].

## Requirements and failure boundary

The system must retain **one unconsumed confirmed message** while the broker process is stopped and restarted in the **same container**. The test must use a fresh connection after restart, not an object that already held in-memory state. Once reconnected, it must find the queue and the expected message, acknowledge it and remove the temporary queue.

![A confirmed persistent message in a durable queue survives restart of the same RabbitMQ node.](/diagrams/rabbitmq-restart-sequence.svg)

The failure model is narrow: the Docker daemon restarts the **existing service container**, preserving its writable layer. The test does not destroy the container's data directory, move the queue to a different node, corrupt disks or break a clustered quorum. Therefore the result is evidence for **process/container restart recovery on this runner**, not disaster recovery or RabbitMQ leader failover.

## Executable integration test and reproducibility

The script [scripts/verify_rabbitmq_restart.py](https://github.com/christianrss/manual/blob/main/scripts/verify_rabbitmq_restart.py) performs the sequence below, using the broker container ID from the GitHub Actions job context. The build executes it as a separate step **after all other tests**, so restarting RabbitMQ does not interrupt the unrelated PostgreSQL or consumer-delivery tests.

~~~text
1. Connect to RabbitMQ and declare an isolated durable classic queue.
2. Enable publisher confirms and publish a persistent message.
3. Close the publisher connection; ask Docker to restart the same container.
4. Retry connecting until the broker is healthy again, within a hard timeout.
5. Verify the queue and exact message identity, then ACK and clean up.
~~~

A local machine can run the script when `RABBITMQ_CONTAINER_ID` points to its disposable broker container and `RABBITMQ_HOST` resolves the broker's AMQP endpoint. It requires Docker permissions. Never use a shared production container as a learning target: an intentional restart would disrupt clients.

## Why a publisher ACK is not a consumer ACK

A producer confirmation says that the broker accepted a publication under its documented conditions. The consumer's manual `basic_ack` says it no longer needs that delivery. Neither one says that another team's database transaction or external payment succeeded. If the consumer commits its effect but loses its ACK, the broker may deliver the same message again; the [transactional inbox lab](/en/topics/rabbitmq-durable-consumer-integration/) tests exactly that second scenario.

For a durable workflow, messages should include **stable event identities** and the consumer should deduplicate effects in the same authoritative transaction when possible. Broker persistence protects a message while it waits to be consumed; inbox idempotency protects the application when it receives the same logical message repeatedly. The two mechanisms solve distinct problems [2].

## A tiny policy model, not a broker implementation

For a teaching exercise, define when a publishing configuration is eligible for the **stated restart expectation**. This boolean does not prove data safety by itself; it only checks that the three necessary choices were made.

~~~python
def restart_test_configuration(queue_durable, message_persistent, confirmed):
    return bool(queue_durable and message_persistent and confirmed)

assert restart_test_configuration(True, True, True)
assert not restart_test_configuration(True, False, True)
assert not restart_test_configuration(False, True, True)
assert not restart_test_configuration(True, True, False)
~~~

An actual broker has filesystem, disk, resource and failure semantics missing from this function. That is why the repository also runs the real container restart and observes the actual delivery. A passing configuration checklist is not an integration test.

## A restart is not a quorum failover

Quorum queues in RabbitMQ use replicated state based on Raft. A typical three-member quorum queue can remain available after losing **one** member if a majority remains; it cannot continue normally when no majority is reachable. Confirmed writes are protected according to that replicated durability model [3]. A **single-node restart** cannot establish any of those majority-election properties, no matter how many times the test passes.

To test quorum behavior, provision a real multi-node cluster, create a quorum queue with appropriate replica membership, confirm publications, stop the current leader, observe election and verify messages after clients reconnect. Repeat while intentionally removing the majority and check the expected unavailability. Record replication placement and storage lifetime before claiming tolerance of a node loss.

## Recovery time, detection and retries

A restarted node needs time to boot before new TCP connections and AMQP channels can succeed. Clients should handle connection failure with bounded retry, deadlines and jitter. The script explicitly waits until reconnect succeeds or a deadline passes; a naive one-shot connection attempt might fail even when durable recovery succeeds seconds later.

Potential sources of slow recovery include large queue indexes, consumer redelivery, process startup, disk speed and network name resolution. A test that only waits until the port opens does not show that **queue contents** have been recovered; retrieving the **exact message body and ID** makes the assertion stronger.

## Failure matrix and operational consequences

| Fault | What may happen | Required evidence |
| --- | --- | --- |
| Consumer disconnects without ACK | Delivery is requeued | Manual ACK/redelivery test |
| Node restarts with durable/persistent confirmed data | Message should remain under stated conditions | Retrieve after same-container restart |
| Container destroyed and storage erased | Local data may be lost | External persistent volume and restore test |
| One quorum follower fails | Remaining majority can progress | Multi-node quorum experiment |
| Quorum loses majority | Queue becomes unavailable | Partition/minority experiment |
| External PSP commits then times out | Broker cannot prove remote effect | Provider idempotency/reconciliation |

A broker may be recovered while workers are still delayed by a backlog. Recovery time objective (RTO), maximum event age and replay count should be monitored separately. A broker restart that takes 15 seconds to recover does not imply every customer callback completes in 15 seconds.

## Exercises and verification

1. Identify which condition is missing when a durable queue receives transient messages without publisher confirms.
2. Explain the difference between a successfully reconnected AMQP client and actually retrieving the original message.
3. Change the exercise to destroy and recreate the broker container with a persistent volume; specify which volume configuration is required.
4. Outline a three-node quorum test that stops the current leader and observes a new leader and message retention.
5. Explain why consumer inbox deduplication is necessary even when all broker durability checks pass.

**Related chapters:** [RabbitMQ redelivery lab](/en/topics/rabbitmq-durable-consumer-integration/), [asynchronous messaging](/en/topics/asynchronous-messaging/), [fault injection](/en/topics/failure-recovery-workshop/) and [consensus](/en/topics/raft-consensus/) establish the surrounding guarantees [1][2][3].
