---
id: rabbitmq-live-network-partition-lab
title: "RabbitMQ Live Network Partition: Running Brokers Without a Quorum"
description: "Disconnect a running broker from its Docker network, observe minority confirmation behavior and restore the real quorum."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [rabbitmq-quorum-majority-loss, network-partition-quorum-models]
sources:
  - {title: "Docker — network disconnect", url: "https://docs.docker.com/reference/cli/docker/network/disconnect/", kind: "official container documentation"}
  - {title: "RabbitMQ — Network Partitions", url: "https://www.rabbitmq.com/docs/partitions", kind: "official broker documentation"}
  - {title: "RabbitMQ — Publisher Confirms and Consumer Acknowledgments", url: "https://www.rabbitmq.com/docs/confirms", kind: "official broker documentation"}
---
A stopped broker and an isolated broker are different failure cases. When a node is stopped, its process cannot accept any work. During a network partition, the process can remain **running** while being unable to communicate with other quorum members. A minority broker may answer an AMQP login while its quorum queue cannot make progress. This laboratory extends the three-member RabbitMQ test to **disconnect and reconnect an actual Docker bridge network** without stopping the isolated RabbitMQ process [1][2].

## Contract: demonstrate loss of communication, not loss of a process

Begin with a three-member quorum queue and an actual confirmed event. The test already demonstrates that two members can recover the event after the initial leader is stopped, and that a one-member minority cannot give a positive publisher confirmation. The added phase deliberately keeps the second and third brokers running, with the first still stopped. It then removes the third broker's connection to the shared bridge. Now the second broker cannot reach the third: neither can form a majority of the original three queue members.

The assertion is specific: **no positive publisher confirmation during a bounded observation window**. An exception or timeout does not establish that the message was rejected or lost. The client may need to retry a stable event identity after recovery; this ambiguity is documented in RabbitMQ's publisher-confirm semantics [2].

![One live RabbitMQ node is disconnected from the Docker bridge while another remains accessible to an AMQP publisher.](/diagrams/rabbitmq-live-network-partition.svg)

## Check process identity before the split

The test obtains the isolated container's Docker \`RestartCount\` and running state before changing network membership. It then disconnects that container from the user-defined bridge and checks that **the same process container is still running** and its restart count has not changed. This matters: silently substituting \`docker stop\` would test node failure, not communication failure.

The authoritative command sequence for the controlled lab is:

~~~text
docker inspect --format '{{.State.Running}}' <isolated-node>
docker inspect --format '{{.RestartCount}}' <isolated-node>
docker network disconnect <test-bridge> <isolated-node>
docker inspect --format '{{json .NetworkSettings.Networks}}' <isolated-node>
~~~

These are illustrative commands with placeholders. The reproducible implementation runs them with the actual generated network and container names; see [verify_rabbitmq_quorum.py](https://github.com/christianrss/manual/blob/main/scripts/verify_rabbitmq_quorum.py). The script uses only its own ephemeral CI cluster, never a production broker.

## Observe the majority requirement while processes remain alive

The test opens a fresh AMQP connection to the accessible node. A successful login establishes **endpoint accessibility**, not availability of the replicated queue. It then launches a subprocess to execute a mandatory, publisher-confirmed publish through that node. The process is bounded because an unavailable quorum can cause the request to wait. Returning successfully with a positive confirm in this minority state would fail the test.

The distinction between a negative answer and an unknown outcome is essential. The publish attempt may have reached the local broker before a timeout; its eventual fate is not established solely by an exception. A system should use a stable event ID, an idempotent recipient and reconciliation or retry policy rather than treating every timeout as evidence that nothing happened [2].

## Restore the network without replacing the server

The repair operation uses Docker's \`network connect\` to attach the **same running container** back to the original bridge. It supplies the node's DNS alias so other brokers can resolve the Erlang node name again, and compares the running state and restart count with values taken before the split [1].

The test then repeatedly publishes a fresh uniquely identified event until RabbitMQ positively confirms it or a finite deadline expires. This positive **post-healing** check is as important as the negative check: a broken cluster that never recovers would otherwise appear to satisfy the safety-only assertion.

## Model majority and distinguish process presence

In a three-member queue, the minimum voting majority is two. If the isolated group has only one member it cannot form a strict majority, even when that member's process is alive. A useful pure model shows the distinction:

~~~python
def can_form_majority(members, mutually_reachable):
    if members < 1 or not (0 <= mutually_reachable <= members):
        raise ValueError("invalid membership")
    return mutually_reachable >= members // 2 + 1

assert can_form_majority(3, 3)
assert can_form_majority(3, 2)
assert not can_form_majority(3, 1)
assert not can_form_majority(3, 0)
~~~

This function does not implement Raft. It assumes a fixed voter set and sufficient mutual communication. It cannot establish that the leader's term is current, that replicas hold the required entries, or that confirmations were delivered. Those are the reasons a *real* broker test accompanies the static model [3].

## What a genuine network partition adds

The earlier node-stop test established resilience when an entire broker container was stopped. The network test covers a different failure boundary: a process that continues running while its peer connections disappear. This is relevant to a split-brain risk and to monitoring systems that would otherwise use process uptime or listening ports as a proxy for write availability.

Docker bridge disconnection is still a coarse disruption. It interrupts **all** traffic on that interface, not a surgically selected Erlang distribution port or an asymmetric packet-loss profile. The script does not introduce arbitrary latency, reorder packets, reproduce a cloud routing flap or isolate independent hosts. Its hosts and Docker daemon still share one CI machine.

## Write safety is not an application delivery guarantee

A returned publisher confirm says the broker accepted the message under the queue contract. It does **not** mean an external consumer applied an inventory change, charged a card or completed a webhook. An at-least-once delivery pipeline still needs stable logical event IDs and transactional inbox deduplication at the business authority. A network partition can also interrupt publisher responses after a message was committed; retries may produce duplicates.

A production client must also maintain a reconnection strategy that handles stale DNS, changed endpoints, lost channels and duplicate delivery. The test's fresh AMQP connections are explicit; a deployed application's connection pool may behave differently.

## Observations and limitations

| Assertion | Evidence in the lab | Not established |
| --- | --- | --- |
| Network link removed | Docker bridge membership inspected | All conceivable network faults |
| Isolated broker still running | Docker running state and restart count | Broker internal progress |
| Peer AMQP endpoint available | Fresh client login | Quorum commit availability |
| Minority has no positive confirm | Bounded child publisher attempt | Definitive loss of an uncertain event |
| Network restores | Same container reattached | Automatic application routing |
| Majority publishes again | Confirmed event after repair | Global exactly-once business effect |

Treat a passing test as evidence for **this fault schedule** and environment only. A negative test is especially vulnerable to weak assertions: it must verify that the target is reachable and that the client attempted the actual quorum-queue publication, not merely that some unrelated TCP port was down.

## Exercises and verification

1. Explain why a healthy AMQP socket on a broker in a one-member partition does not make its quorum queue writable.
2. Add a metric for the interval between bridge reconnection and first positive publisher confirm. Which parts of that measurement are client-side?
3. Repeat the experiment with all three brokers running, isolating exactly one node so the other two retain majority. Specify which side should progress.
4. Compare bridge disconnection with packet drop on Erlang distribution ports and asymmetric packet loss.
5. Explain why retrying an ambiguous publication with a new event ID can violate an application's idempotency contract.

**Related chapters:** [Quorum majority loss](/en/topics/rabbitmq-quorum-majority-loss/), [static partition models](/en/topics/network-partition-quorum-models/), [transactional inbox](/en/topics/rabbitmq-durable-consumer-integration/) and [Raft consensus](/en/topics/raft-consensus/) explain adjacent guarantees [1][2][3].
