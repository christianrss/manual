---
id: raft-consensus
title: "Distributed Consensus: Raft, Quorums and Replicated Logs"
description: "Derive quorum intersection and Raft terms, elections, log matching, commit rules, safety and limits during network partitions."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [database-consistency, asynchronous-messaging, concurrency-synchronization]
sources:
  - {title: "Ongaro and Ousterhout — In Search of an Understandable Consensus Algorithm", url: "https://raft.github.io/raft.pdf", kind: "peer-reviewed systems paper"}
  - {title: "MIT 6.5840 — Distributed Systems", url: "https://pdos.csail.mit.edu/6.5840/", kind: "university course"}
---
A replicated database or metadata service may need multiple machines to agree on one sequence of commands despite crashes and delayed messages. **Distributed consensus** provides a way to coordinate that decision while preserving a stated safety model. It does not make network partitions disappear, and it cannot ensure progress when too few nodes can communicate. Raft is a leader-based algorithm that decomposes this problem into leader election, log replication and safety restrictions [1].

## Specify the fault model and the state machine

Assume n nodes exchange messages across a network that may delay, duplicate or drop communication and may partition. Nodes can crash and later restart using durable state. Ordinary Raft is designed for **crash faults**, not arbitrary Byzantine behavior where a node lies or signs inconsistent information. A deterministic state machine applies commands in log order: equal initial state plus equal ordered commands yields equal results. External side effects require additional idempotency and transaction design.

A log entry contains a command and the **term** in which a leader created it. Terms act as monotonically increasing logical epochs, not synchronized wall-clock time. Nodes have follower, candidate or leader roles. A voter with a newer term can invalidate leadership assertions from an older term. Persisting current term, vote and log safely is necessary so restart does not undo promises that other nodes relied upon [1].

## Why majority quorums intersect

For n=2f+1 voting nodes, a majority quorum contains f+1 nodes. Any two quorums of that size intersect: (f+1)+(f+1) = 2f+2 > 2f+1=n. Thus they share at least one voter. For n=5, the majority is 3. If two groups each claim to have 3 distinct voters, they would need 6 voters, impossible. However, **intersection alone is not sufficient** to prove full Raft log safety: voting restrictions and log matching also matter.

![Five-voter Raft cluster with majority three.](/diagrams/raft-majority.svg)

~~~python
from itertools import combinations

def majority(n):
    if n < 1:
        raise ValueError("positive voter count required")
    return n // 2 + 1

def majority_quorums(n):
    return [set(c) for c in combinations(range(n), majority(n))]

groups = majority_quorums(5)
assert majority(5) == 3
assert len(groups) == 10
assert all(a & b for a in groups for b in groups)
assert majority(3) == 2
~~~

This code enumerates **quorum sets** only and costs combinatorial time/memory; it is a teaching proof check, not a Raft implementation. Real membership changes require carefully chosen reconfiguration protocols rather than naïvely switching n or assuming a majority of the new set is automatically compatible with the old set.

## Election rules and leader completeness

When a follower does not hear timely leader communication, it may become a candidate, increase its term and request votes. Each node grants at most one vote per term, and a candidate must show a log at least as up-to-date as the voter's according to Raft's last-log term/index rule. This prevents electing an arbitrary stale node that lacks required committed entries. Randomized election timeouts reduce simultaneous candidacies but are not a guarantee of instantaneous election [1].

If two candidates compete, no one may gain a majority until timeout or partition conditions change. Election safety means at most one leader can be elected **for a given term**, under correct persistence and voting rules. In a split network, a node from an old term might still believe it is leader; it cannot commit new entries without a quorum under Raft's rules. A stale leader's own belief is not proof of authority.

## Log matching and replication

The leader appends commands to its log and sends AppendEntries to followers with the previous index and term. A follower accepts the extension only when its log matches at that preceding position; conflicting uncommitted suffix entries are resolved as the leader repairs that follower's history. This forms the **log matching property**: if two logs contain entries with the same index and term, their preceding entries agree according to Raft's safety guarantees [1].

A client can submit the same command repeatedly after a network timeout. Raft gives log-level ordering and replication, **not automatically exactly-once business effects** for retries. The replicated state machine should remember client/operation identifiers and previous results, or use another correct deduplication protocol, so a retransmitted payment request does not repeat a charge.

## The subtle commit rule

For an entry created in the leader's **current term**, once replicated on a majority, the leader can consider it committed under Raft's commit procedure. Entries from **previous terms cannot be committed merely by counting replicas**; they become committed indirectly when a current-term entry is committed according to the protocol. This distinction prevents a leader from incorrectly asserting safety when logs from older terms have complex divergence [1].

Consider a five-node cluster where a leader has an entry replicated to three nodes, then network partitions remove two nodes. The connected trio can still form a majority and make progress provided elections, logs and term rules allow it. A fragment of only two voting nodes cannot commit new entries, even if both remain healthy. **Availability** depends on reachable voting quorums, not just total CPU uptime.

## Read consistency and linearizability

A leader serving a read from its local state could be **stale** if it was partitioned and replaced by a new leader. Linearizable reads need extra checks ensuring the leader is current and that the state machine has applied committed entries sufficiently; implementations may use a quorum-based ReadIndex protocol or carefully justified lease strategy. Raft's replicated log **by itself** does not certify every arbitrary leader-local read as linearizable.

Client-visible completion also depends on durable persistence, command application and how the service associates the reply with a unique request identity. A replicated log protects ordering of entries under assumptions; it does not define business-side transaction boundaries, API authentication, network encryption or disaster recovery policy.

## Failures, metrics and operational choices

| Failure | Safety requirement | Availability consequence |
| --- | --- | --- |
| Follower crashes | Preserve leader/committed history | Majority may still progress |
| Leader crashes | Elect sufficiently up-to-date replacement | Brief election interruption |
| Minority partition | No new commits without quorum | Minority cannot perform linearizable writes |
| Delayed old leader messages | Reject stale terms/conflicts | Temporary retries/confusion |
| Storage loses persisted vote/log | Raft assumptions violated | Safety may fail |

Monitor leader changes, term churn, failed append attempts, commit-index lag, applied-index lag, disk fsync latency and network delay. Timeouts that are too short relative to normal RPC and disk delays cause churn; too long delay failure detection. Use careful membership change procedures and disaster-recovery testing before assuming a replicated service is automatically safe.

The broader course on distributed systems at MIT develops replicated state machines, failures and testing as connected topics [2]. **Related chapters:** [Database consistency](/en/topics/database-consistency/) distinguishes serializability from linearizability; [asynchronous messaging](/en/topics/asynchronous-messaging/) studies duplicates and durable acknowledgment.

## Exercises and verification

1. For five voters, list two majorities and show their intersection. For six voters, why is the majority four, not three?
2. A leader has a majority-replicated entry from an older term. Explain why Raft requires special commit handling instead of just counting copies.
3. Trace a five-voter partition into groups of 2 and 3. Which group can elect and commit, assuming correct logs and voting?
4. Why can a former leader return a stale value even while its local log is internally consistent?
5. Define a deduplication state entry for client C, request R and response X. Explain how applying the same command twice must preserve one business effect.
