---
id: rabbitmq-quorum-majority-loss
title: "RabbitMQ Quorum Majority Loss: Fail Closed and Recover Writes"
description: "Test loss of a three-member queue majority, bounded publisher confirms, and successful writes after restoration on real RabbitMQ nodes."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [rabbitmq-quorum-leader-failover]
sources:
  - {title: "RabbitMQ 4.1 — Quorum Queues", url: "https://www.rabbitmq.com/docs/4.1/quorum-queues", kind: "official broker documentation"}
  - {title: "RabbitMQ — Consumer Acknowledgements and Publisher Confirms", url: "https://www.rabbitmq.com/docs/confirms", kind: "official broker documentation"}
  - {title: "RabbitMQ — Network Partitions", url: "https://www.rabbitmq.com/docs/partitions", kind: "official broker documentation"}
---
A replicated queue can remain available after one node fails yet become unavailable when **a majority of its voting members disappears**. The difference is not a generic network timeout: it is part of the **consistency contract** of a quorum queue. This workshop extends the existing three-node RabbitMQ laboratory to exercise both sides of the boundary: confirmed writes with two surviving queue members, no positive confirmation from a one-member minority, and resumed confirmed writes after restoring a second member. It uses actual Docker containers and RabbitMQ's AMQP protocol, not simulated queues [1][2].

## The invariant: one node does not constitute a quorum

For a queue with three members, the majority threshold is two. After stopping the first node, the two remaining members can elect or retain a leader and accept new confirmed publications. Stop a second node, and only one of the original three members remains. A majority is now impossible. The surviving broker may **still accept a TCP connection**; that does not mean the quorum queue can safely commit a new message.

![Three-member quorum proceeds with two survivors, stalls with one, and resumes when a member returns.](/diagrams/rabbitmq-majority-loss.svg)

The critical safety statement is narrow: **a publisher should not receive a successful quorum-queue confirmation for a newly committed write while only one voting member is available**. The exact client exception or timeout can vary across broker versions and election states. Application code must distinguish the absence of a positive acknowledgment from a definitive rejection: once a connection fails, a message's outcome may be **unknown** to the publisher.

## Set up the actual failure schedule

The source [verify_rabbitmq_quorum.py](https://github.com/christianrss/manual/blob/main/scripts/verify_rabbitmq_quorum.py) creates an isolated three-node RabbitMQ cluster with a quorum queue explicitly initialized with three members. It first publishes a persistent event with publisher confirms enabled, stops the initial broker, verifies the event is recoverable through a survivor, and successfully publishes another message through the remaining two-member majority.

The new portion stops a **second** broker while leaving one broker running. It successfully opens a separate AMQP connection to the surviving broker, which prevents a trivial interpretation of a connection failure as a quorum-specific finding. Then it attempts a fresh publisher-confirmed message in an isolated child process with a hard deadline.

## A bounded negative test avoids hanging CI

In the minority state, the test launches a new Python publisher process rather than letting an indefinite blocking publish stall the entire workflow. The child uses \`confirm_delivery()\`, a persistent message, and the same quorum queue. The parent treats a **positive exit with a completed confirmation as a test failure**. A bounded timeout or connection/channel error is evidence that the attempted write **was not positively confirmed during the observation window**, not proof that the broker permanently dropped it [2].

A positive *publisher confirm* is the key signal. Merely returning from socket send or receiving a TCP ACK cannot establish the queue's replicated commit. The exact application policy on ambiguous publication should preserve a stable event ID and retry safely, because a previously uncertain publication might become visible after recovery.

## Restore the majority and demonstrate liveness

After the minority experiment, the script restarts the second stopped broker, waits for it to accept AMQP logins, and then repeatedly tries to publish a **new identifiable message** through the surviving broker until a publisher confirmation succeeds or a strict deadline expires.

The resumed positive acknowledgment is important: without it, a negative test could be satisfied by a permanently broken cluster. The experiment thus checks the **transition back to progress** as well as the protection against positively confirmed writes with insufficient voting members.

The demonstration remains limited to stopping and starting Docker processes. It does not deliberately partition networks or manipulate packet loss. A real partition experiment would require isolating node connections without stopping the brokers and verifying majority/minority behavior while clients remain connected to different network segments [3].

## Derive the failure tolerance before building

A quorum threshold for n voting members is floor(n/2)+1. Thus a three-member queue can continue with two available members, and a five-member queue with three. This rule concerns majority intersection and leadership, not throughput or guarantees about every form of storage failure.

~~~python
def majority_size(voters):
    if not isinstance(voters, int) or voters < 1:
        raise ValueError("positive member count")
    return voters // 2 + 1

def has_majority(total, available):
    if available < 0 or available > total:
        raise ValueError("invalid availability count")
    return available >= majority_size(total)

assert has_majority(3, 2)
assert not has_majority(3, 1)
assert has_majority(5, 3)
assert not has_majority(5, 2)
~~~

The arithmetic is a **model of membership**, not a broker driver. When members lag, fail to communicate, or have incompatible membership views, simply counting powered-on containers is insufficient; the actual queue and consensus state must determine whether progress is safe.

## The ambiguous publication problem

Imagine that the publisher sends event E and then loses its connection before receiving a confirmation. E may have committed before the failure or might not have committed. Retrying E with a **different** event ID can produce two logical operations. Use a stable identity across attempts and make the consumer's effect idempotent at its authoritative storage boundary [2].

This is why quorum replication and transactional inbox deduplication are complementary, not substitutes. Quorum replication protects the queue's replicated data safety and availability; inbox uniqueness prevents a business action from being applied twice even when a confirmed message is republished or redelivered.

## Capacity and recovery do not follow from quorum alone

Suppose a consumer fleet drains 200 jobs/s and new accepted work arrives at 180 jobs/s. After 20 minutes without processing, 216,000 jobs accumulate. At the same throughput and arrival rate, spare capacity is only 20 jobs/s, yielding three hours to drain the backlog. These are **illustrative constant-rate assumptions**, not measured RabbitMQ performance.

~~~python
def drain_seconds(arrivals_per_s, processing_per_s, outage_seconds):
    if arrivals_per_s < 0 or outage_seconds < 0 or processing_per_s <= arrivals_per_s:
        raise ValueError("positive recovery margin required")
    return (arrivals_per_s * outage_seconds) / (processing_per_s - arrivals_per_s)

assert drain_seconds(180, 200, 1200) == 10800
~~~

A restored quorum does not automatically meet an application latency SLO. Track backlog age, confirm latency, redelivery attempts, consumer throughput and time to recover the write path separately.

## Observed, inferred and untested evidence

| Situation | What the executable lab checks | What it does not establish |
| --- | --- | --- |
| One node stopped | Confirmed message recovered; new publish confirmed | Automatic client failover for every application |
| Two nodes stopped | No positive minority publish confirm before deadline | Permanent loss of the attempted message |
| Two nodes available again | Fresh publish eventually confirmed | All old replicas fully caught up |
| Entire CI host unavailable | Nothing; all brokers share one host | Datacenter fault tolerance |
| Nodes separated by network partition | Not injected | Jepsen-style partition correctness |
| Business consumer retries | Separate inbox test applies | Exactly-once external provider effects |

The negative test is designed to **fail closed**, with a bounded waiting period. Keep the published claims tied to the actual failure schedule rather than describing the exercise as a universal distributed-system certification.

## Exercises and verification

1. Explain why a successful AMQP login to a one-member minority does not prove a quorum queue can confirm a write.
2. Why must a missing publisher confirmation be treated as an ambiguous outcome rather than evidence that an event was definitely rejected?
3. Modify the Docker experiment to isolate one node with network rules while keeping its process running. Predict which partition can progress.
4. Extend the test so a returning node catches up and document which RabbitMQ management metrics demonstrate that recovery.
5. Recalculate backlog drain when accepted arrivals rise to 190 jobs/s but processing remains 200 jobs/s.

**Related chapters:** [Three-node quorum failover](/en/topics/rabbitmq-quorum-leader-failover/), [broker restart](/en/topics/rabbitmq-broker-restart-lab/), [transactional inbox](/en/topics/rabbitmq-durable-consumer-integration/) and [Raft consensus](/en/topics/raft-consensus/) give the surrounding foundations [1][2][3].
