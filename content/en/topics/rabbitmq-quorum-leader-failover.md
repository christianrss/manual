---
id: rabbitmq-quorum-leader-failover
title: "RabbitMQ Quorum Leader Failover: Three-Node Executable Lab"
description: "Test real RabbitMQ quorum replication: publish with confirms, stop the initial leader, recover data, and confirm writes on the surviving majority."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [rabbitmq-broker-restart-lab, raft-consensus]
sources:
  - {title: "RabbitMQ — Clustering Guide", url: "https://www.rabbitmq.com/docs/clustering", kind: "official broker documentation"}
  - {title: "RabbitMQ — Quorum Queues", url: "https://www.rabbitmq.com/docs/4.1/quorum-queues", kind: "official replication documentation"}
  - {title: "RabbitMQ — Consumer Acknowledgements and Publisher Confirms", url: "https://www.rabbitmq.com/docs/confirms", kind: "official broker documentation"}
---
A single RabbitMQ process can recover a durable message after restarting; that is not evidence that a **replicated quorum queue remains available when its leader node disappears**. This laboratory creates three actual RabbitMQ nodes in separate Docker containers, joins them to one cluster, publishes a persistent message to a three-member quorum queue with publisher confirmation, deliberately stops the initial node, and then retrieves the confirmed message through a surviving node. It also tests whether the surviving majority can confirm a new publication [1][2].

## Safety and liveness are different

A quorum queue uses a replicated log with Raft-style consensus. For three queue members, a majority means **at least two** online members capable of communicating. Losing one leader can require an election, but a new leader should be elected by the two remaining members and confirmed messages should remain recoverable under the broker's documented durability conditions [2]. If two members are lost, the remaining minority lacks a majority; clients must not interpret the resulting unavailability as permission to invent a successful write.

These claims depend on the event being confirmed by the publisher and on replicas being properly initialized. Merely creating three containers does not prove that a particular queue has three members. Our test declares the queue **after** the cluster has three online nodes, with `x-queue-type=quorum` and `x-quorum-initial-group-size=3`, as documented by RabbitMQ [2].

## Test topology and explicit authority

The laboratory creates an isolated Docker bridge network and starts nodes with hostnames `mq1`, `mq2` and `mq3`. Each container uses the same ephemeral Erlang cookie, which permits broker-to-broker authentication, and the same dedicated test-only AMQP user. The script joins the second and third nodes using `rabbitmqctl join_cluster rabbit@mq1`. The official clustering documentation describes the join operation and warns that manually joining an existing cluster is a development/testing technique, not recommended production orchestration [1].

![Three quorum members retain a confirmed message when the initial node stops and a majority survives.](/diagrams/rabbitmq-quorum-majority.svg)

Each test node has its own process and container filesystem. This is a real three-node RabbitMQ cluster **on one GitHub Actions host**. Consequently the test covers a broker process/container failure, but does not establish independent host failure domains, datacenter resilience, network partition handling, or multi-zone disaster recovery.

## Publisher contract and queue replication

The producer connects to the first broker on its mapped AMQP port, declares a **durable quorum queue** and turns on publisher confirmations. It sends a persistent message containing a stable `message_id`. After publication returns successfully under confirmation mode, it closes the publisher connection. That operation does not mean a consumer processed the event; it means the broker accepted it under the queue's confirmation contract [2][3].

RabbitMQ's quorum model uses members on separate nodes and an elected leader for queue operations. Members that are behind after a temporary outage can catch up from the surviving leader. The durability claim concerns **confirmed** messages: an application that fails to wait for confirmation cannot assume a message reached the quorum, even if it already sent bytes on a TCP socket.

## Stop the initial broker and recover on another

The test deliberately stops `mq1`, the client-local initial leader location in this controlled configuration. Afterward, it opens a fresh AMQP connection to `mq2` and repeatedly requests the queue's next message until either the expected body and ID arrive or a strict timeout expires. It **acknowledges after checking the message**, rather than consuming with auto-ack, so a failed assertion cannot silently mark a different message processed.

The script then publishes another message through `mq2` with publisher confirmations enabled. This second step matters: retrieving an old message proves post-failure readability, while a **new confirmed publication** demonstrates an available write path through the remaining two-member majority. The script does not claim which specific node is currently leader; queue leadership and client connection endpoints are not interchangeable concepts.

## Reproducible implementation and cleanup

The executable source is [scripts/verify_rabbitmq_quorum.py](https://github.com/christianrss/manual/blob/main/scripts/verify_rabbitmq_quorum.py). The GitHub Actions workflow runs it **after the existing single-node restart check**, as an additional step. The implementation provisions three ephemeral containers, asserts all three cluster node names are visible, publishes and recovers a real event, then removes the containers and Docker network in a `finally` block. All retries have finite deadlines.

Running this script requires Docker privileges and resources sufficient for three brokers. **Never run it on shared production Docker infrastructure:** intentionally stopping a node is disruptive. The CI runner's environment is disposable and separate from the service containers used by ordinary article tests.

## A quorum exercise is not a universal safety proof

A useful abstract invariant is that a quorum requires strictly more than half its members. For n members, the minimum majority is floor(n/2)+1; for a three-member queue the minimum is two. This arithmetic alone does not confirm that a particular broker is healthy or that its replicas contain the expected log entries.

~~~python
def majority(total_members):
    if not isinstance(total_members, int) or total_members <= 0:
        raise ValueError("positive membership count required")
    return total_members // 2 + 1

assert majority(3) == 2
assert majority(5) == 3
assert 3 - 1 >= majority(3)
assert 3 - 2 < majority(3)
~~~

A real distributed system also needs correct membership, fencing of old leaders, durable writes, state reconciliation and client reconnection policy. The mathematics explains quorum intersection, while the executable test exercises one concrete failure schedule. Neither substitutes for model checking or network-partition experiments.

## What remains untested

| Scenario | Test result or expectation | Evidence boundary |
| --- | --- | --- |
| Initial quorum leader stops | Confirmed message recoverable from a survivor | Actual three-node containers |
| New publish through surviving majority | Publication can be confirmed | Actual broker/AMQP confirmation |
| Two of three replicas become unavailable | No majority; normal queue writes unavailable | **Not injected here** |
| Entire Docker host fails | All three local containers may disappear together | **Not tested** |
| Network partitions isolate one member | Majority may progress; minority should not | **Not tested** |
| Old leader rejoins | Replica must catch up safely | **Not tested** |

The exercise does not change the application-level need for **idempotent consumers**. A publisher may retry an ambiguous attempt and send the same event twice; a consumer can commit its effect and crash before acknowledging, causing redelivery. Transactional inbox identity and broker quorum replication protect different boundaries.

## Exercises and verification

1. Explain why three broker processes on the **same host** cannot demonstrate tolerance of an entire host outage.
2. Derive the majority size for three, five and seven queue members and the tolerated number of node failures.
3. Add a test stopping a second member, but make its timeout bounded and do not claim a publish succeeded without confirmation.
4. Extend the laboratory to restart `mq1` and verify the returning replica catches up without duplicating logical business effects.
5. Compare client failover endpoints and the elected queue leader's identity; explain why the first does not reveal the second.

**Related chapters:** [Broker restart](/en/topics/rabbitmq-broker-restart-lab/), [redelivery and inbox](/en/topics/rabbitmq-durable-consumer-integration/), [Raft consensus](/en/topics/raft-consensus/) and [distributed observability](/en/topics/distributed-observability/) cover adjacent guarantees [1][2][3].
