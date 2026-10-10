---
id: network-partition-quorum-models
title: "Network Partition Models: Exhaustive Quorum Connectivity Checks"
description: "Enumerate every undirected network graph for three and five voters, prove majority exclusivity, and identify untested partition behaviors."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [raft-consensus, rabbitmq-quorum-majority-loss]
sources:
  - {title: "RabbitMQ — Quorum Queues", url: "https://www.rabbitmq.com/docs/4.1/quorum-queues", kind: "official broker documentation"}
  - {title: "RabbitMQ — Network Partitions", url: "https://www.rabbitmq.com/docs/partitions", kind: "official broker documentation"}
  - {title: "Patroni — Distributed Coordination Store", url: "https://patroni.readthedocs.io/en/latest/modules/patroni.dcs.html", kind: "official HA project documentation"}
---
Stopping a node and partitioning a network are different failure experiments. A node can remain powered on, run PostgreSQL or RabbitMQ, and serve some clients while being **unable to communicate with other members**. That makes a simple “server running” test insufficient for consensus-based availability. This workshop builds a small executable model of **undirected connectivity**, enumerates every possible static link configuration for three and five nodes, and checks an important quorum invariant: **at most one disconnected component can contain a strict majority** [1][2].

## The failure model and what it deliberately ignores

Represent n voting members as vertices in an undirected graph. A link between nodes A and B means they can communicate **bidirectionally** in the modeled instant. A connected component groups nodes that can reach one another through a chain of working links. A component is *eligible for majority* when its size is strictly more than n/2.

![Three partition scenarios: one surviving majority, no majority, and repaired connectivity.](/diagrams/network-partition-quorum.svg)

This is a **static symmetric network abstraction**. It does not simulate packet reordering, asymmetric firewalls, delays, election timeouts, dynamic membership, node-specific WAL/log positions or split-brain bugs. A connected graph is only a **necessary structural condition** for participating in quorum; it is not proof that a Raft leader has been elected or that a particular message is committed [1].

## Enumerate every small topology

The executable [network_partition_quorum.py](https://github.com/christianrss/manual/blob/main/examples/python/network_partition_quorum.py) generates all potential node pairs using Python's \`itertools.combinations\`. For n nodes, the number of undirected pairs is n(n−1)/2, so there are **2^(n(n−1)/2)** possible present/absent link combinations.

For three nodes that yields eight graphs; for five nodes, **1,024 graphs**. In each graph, depth-first search finds connected components and the code checks how many have size at least floor(n/2)+1. The accompanying unit test runs these enumerations during CI. Exhaustive here means **every graph inside this small model**, not every network fault in a real cluster.

## Understand majority intersection

A strict majority has more than n/2 members. Two disjoint sets each containing a strict majority would together have more than n members, which is impossible. Therefore **two disconnected components cannot both be majorities of the same fixed membership**. This is a short mathematical proof; enumeration acts as a regression check on the model's implementation rather than a replacement for the proof.

~~~python
def majority_threshold(voters):
    if voters < 1:
        raise ValueError("positive membership required")
    return voters // 2 + 1

def disjoint_groups_can_both_be_majorities(voters):
    required=majority_threshold(voters)
    return 2 * required <= voters

assert majority_threshold(3)==2
assert majority_threshold(5)==3
assert not disjoint_groups_can_both_be_majorities(3)
assert not disjoint_groups_can_both_be_majorities(5)
~~~

This principle assumes **one agreed membership configuration**. Membership changes are not as simple as changing a number in a spreadsheet; consensus systems need safe transitions that preserve intersections across configurations.

## Study a three-node partition

Let the voters be A, B and C. If A is isolated while B and C can communicate, B+C forms a majority. The A side cannot safely confirm a new quorum-queue write merely because its local broker still answers TCP or AMQP connection requests. In the [majority-loss Docker laboratory](/en/topics/rabbitmq-quorum-majority-loss/), the one-member minority is tested separately using actual RabbitMQ publisher confirmations.

If all links are broken, three isolated singletons remain. None qualifies as a majority. Availability may be lost even while **all three processes are alive**. This is why liveness metrics such as node uptime and TCP connect success are insufficient for claims about write availability.

## Study a five-node split

With five voters, threshold is three. A split into groups of 2 and 3 yields exactly **one majority-eligible group**. A split into 2, 2 and 1 gives **none**. A split into 4 and 1 also yields one. The graph model exposes this difference explicitly in unit tests rather than assuming that losing the same number of links always has the same effect.

Even if a majority is reachable, it might need time to elect a leader, may reject certain operations during an election, or may have backpressure and slow storage. Connectivity is not a performance guarantee. A minority losing quorum is a deliberate **safety-versus-availability** consequence, not necessarily a failure in the implementation.

## Translate the model to RabbitMQ and PostgreSQL

RabbitMQ quorum queues have per-queue replicated membership and Raft-derived leader-election behavior [1]. A broker cluster may have three healthy nodes while a given queue has a different membership or an unavailable majority. Test the **queue's replica set**, not merely the count of running RabbitMQ containers.

PostgreSQL physical streaming replication is **not automatically a Raft quorum**. An asynchronous primary and standby can both be alive across a network partition; without external leadership and fencing, nothing in physical replication alone prevents both from becoming writers. A distributed configuration store and fencing/lease protocol may supply authority, but they have their own quorum and expiration rules [2][3].

## A matrix of fault injections to build next

| Injection | Question to answer | Evidence source |
| --- | --- | --- |
| Stop one broker | Can surviving majority publish? | Docker quorum lab |
| Stop two brokers | Does minority avoid positive confirms? | Docker majority-loss lab |
| Isolate a broker's network while keeping it running | Which side has a majority? | **Not yet integrated** |
| Break all links | Does write availability stop safely? | Small graph model only |
| Partition PostgreSQL primary from controller | Is old primary still writable? | Requires external fencing test |
| Heal connections | Can members catch up safely? | New recovery test needed |

A production chaos experiment should isolate **data-plane and control-plane traffic intentionally**, preserve unrelated administration access, use a disposable cluster, and collect leader/term, replication, acknowledgments, error and latency measurements. Merely applying firewall rules without observing the queue or writer authority does not establish meaningful safety.

## Complexity and limitations of exhaustive checks

Enumerating every link state has **exponential cost in the number of possible edges**: n=7 would already entail 2^21 graphs, more than two million. That is why CI restricts the exhaustive check to three and five voters. Larger clusters need property-based sampling, constrained model checking and targeted fault scenarios.

The test validates a graph invariant and the enumeration code. It cannot verify RabbitMQ's internal consensus algorithm, PostgreSQL's replication, a real packet-filter configuration, or an application's complete recovery procedure. Name those boundaries explicitly when reporting the result.

## Exercises and verification

1. List every possible membership split of five members into components and mark which contain a majority.
2. Explain why a broker can accept a TCP connection while the quorum queue cannot positively confirm a new write.
3. Change the model to directed/asymmetric links and state why plain undirected connectivity becomes insufficient.
4. Design a reproducible Docker network-partition test that leaves containers alive and checks real queue publisher confirms.
5. Explain why quorum intersection alone does not prevent split brain in a PostgreSQL primary/standby pair without fencing.

**Related chapters:** [Raft consensus](/en/topics/raft-consensus/), [RabbitMQ majority loss](/en/topics/rabbitmq-quorum-majority-loss/), [PostgreSQL fencing gates](/en/topics/postgresql-failover-fencing-gates/) and [distributed observability](/en/topics/distributed-observability/) provide complementary perspectives [1][2][3].
