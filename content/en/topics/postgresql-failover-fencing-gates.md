---
id: postgresql-failover-fencing-gates
title: "PostgreSQL Failover Safety: Fencing Receipts and Promotion Gates"
description: "Implement and test fail-closed promotion decisions, reject stale fence evidence and examine real PostgreSQL standby promotion boundaries."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [postgresql-streaming-promotion]
sources:
  - {title: "PostgreSQL 17 — Failover", url: "https://www.postgresql.org/docs/17/warm-standby-failover.html", kind: "official database documentation"}
  - {title: "Patroni — Leader Lock and HA", url: "https://patroni.readthedocs.io/en/latest/modules/patroni.ha.html", kind: "official HA project documentation"}
  - {title: "Patroni — Distributed Coordination Store", url: "https://patroni.readthedocs.io/en/latest/modules/patroni.dcs.html", kind: "official HA project documentation"}
---
An unreachable PostgreSQL primary is not necessarily a **stopped** primary. A network partition can prevent the failover controller from contacting it while some application clients still write to it. Promoting a standby solely because a health probe timed out risks **two writable primaries** and divergent transaction histories. This chapter develops a fail-closed promotion contract, implements deterministic tests of its decision gate, and extends the physical replication Docker laboratory to refuse promotion when the former primary is still visibly running. It does **not** implement an independently trusted production fencing system or complete automatic failover [1][2].

## Separate suspicion, authority and evidence

A monitoring check can produce a *suspicion*: primary A did not respond within a deadline. Suspicion is not proof that A has stopped accepting writes. A separate **fencing authority** must ensure that A cannot continue acting as primary, or that any operation issued by A is rejected by an authority that validates an epoch/fencing token. Only then should promotion of B proceed.

In the existing [physical replication laboratory](/en/topics/postgresql-streaming-promotion/), A and B reside in isolated PostgreSQL Docker containers with separate data volumes. The test now calls a **stop-check gate while A is still running** and requires a refusal; then it issues \`docker stop\`, checks A's Docker runtime state again, and only afterward calls \`pg_promote\` on B.

![A failover decision must pass fencing and replay readiness gates before promotion.](/diagrams/postgresql-fencing-gates.svg)

Docker's running-state check is useful in this controlled environment but is **not a durable fence**. Another actor could restart A immediately after the check. In production, fencing might mean power isolation, hypervisor-level shutdown with an independently enforced state, a storage lease, or coordination through a properly designed consensus-based leader system. The trust, scope and failure behavior of that enforcement must be documented, not assumed.

## The fail-closed promotion contract

The repository includes [failover_gate.py](https://github.com/christianrss/manual/blob/main/examples/python/failover_gate.py). The model receives three externally provided operations: issue a fencing receipt, verify its authenticity/current applicability, and promote a candidate. It advances a logical **epoch**, rejects receipts for the wrong primary or an older epoch, and never calls the promotion callback unless the verifier accepts a matching receipt.

A useful separation is that the **same candidate** can be asked to promote repeatedly without performing promotion twice. This idempotency is modeled locally, not guaranteed across independently restarted failover coordinators; a production controller must persist epochs and leadership under a separate durable consensus authority.

~~~python
from dataclasses import dataclass

@dataclass(frozen=True)
class FenceReceipt:
    old_primary: str
    epoch: int
    verified: bool

def permitted(receipt, expected_old, current_epoch):
    return (isinstance(receipt, FenceReceipt)
            and receipt.old_primary == expected_old
            and receipt.epoch == current_epoch
            and receipt.verified)

assert permitted(FenceReceipt("A", 8, True), "A", 8)
assert not permitted(FenceReceipt("A", 7, True), "A", 8)
assert not permitted(FenceReceipt("B", 8, True), "A", 8)
assert not permitted(FenceReceipt("A", 8, False), "A", 8)
~~~

The \`verified\` field in this explanatory snippet is only **model input**, not an authenticated artifact; an attacker or faulty coordinator could set it to true. The real boundary must call a trusted verifier and use evidence that a candidate cannot forge. The repository's unit tests deliberately use injected fakes to check **decision ordering**, not physical shutdown assurance.

## The mandatory negative test: refuse a live primary

Tests should first verify the guard refuses an invalid operation. Otherwise a test that only checks “promotion succeeded after we stopped A” cannot tell whether the guard was actually used. The Docker lab now probes \`docker inspect\` while A remains running and asserts that promotion would be refused. After it stops A, it requires an explicit stopped-state observation before proceeding with promotion.

The [unit tests](https://github.com/christianrss/manual/blob/main/tests/test_failover_gate.py) also reject a missing receipt, a receipt targeting a different primary, a stale epoch and a receipt that fails verification. They confirm only an accepted current-epoch receipt reaches the injected promotion callback. No test fabricates a live production fence and claims it has isolated power or storage.

## Readiness of the replacement is another independent gate

Even with A fenced, B may be missing committed WAL because PostgreSQL physical streaming replication is often asynchronous. The promotion exercise waits until a **specific committed marker** is visible on B before the shutdown; therefore it proves replay of that marker, not that every transaction in the system has reached B. A production promotion policy may use received, flushed and replayed LSNs, durability objectives, synchronous acknowledgment conditions, and a maximum accepted loss budget [1].

If no eligible candidate meets the recovery point objective (RPO), the system may need to remain unavailable rather than silently accept unacceptable data loss. That is a product and operations decision: **availability** cannot be guaranteed independently of replication and consistency policies.

## Why a lease alone can be insufficient

A common mistake is to treat the expiry of a controller lease as proof that the former primary is dead. The controller may lose its lease while PostgreSQL continues running due to a long pause or network partition. A production design must ensure that old-write authority stops when leadership is lost, for example via watchdog-controlled shutdown or external fencing whose behavior survives controller failure [2][3].

Patroni illustrates the need for an **external distributed configuration store** to acquire a leader lock atomically and renew leadership. Its documentation also discusses the relationship between a leader-lock refresh and watchdog keepalives [2][3]. That does not mean adding the word “Patroni” to an architecture document automatically gives a correct cluster: topology, DCS availability, replication lag, timeline history and operating procedures still matter.

## Timeline, routing and old-primary rejoin

After B promotes, it accepts writes on a new history. A must not simply restart as an independent writable server carrying the previous timeline. A controlled rejoin may require rebuilding or rewinding the old node from the new authority, validating compatibility and preserving evidence about any transactions that diverged. Application clients need to discover or be routed to B, and old connection pools must not continue sending commands to A.

A successful \`pg_promote\` only confirms the database's local state change. It does **not** prove a load balancer updated, a DNS TTL expired, every application process reconnected, or old writers were fenced. Design a complete acceptance test around end-user operations before and after failover, not solely \`SELECT NOT pg_is_in_recovery()\`.

## Recovery objectives and operational trade-offs

Suppose failure detection takes 15 seconds, fencing confirmation 12 seconds, candidate promotion 8 seconds and client routing convergence 10 seconds. A simplistic serial model gives **45 seconds** of recovery time, before transaction retries or application warm-up. These numbers are hypothetical; parallel phases and long tails change real outcomes.

~~~python
def sequential_recovery_seconds(detection, fencing, promotion, routing):
    phases = (detection, fencing, promotion, routing)
    if any(x < 0 for x in phases):
        raise ValueError("durations must be nonnegative")
    return sum(phases)

assert sequential_recovery_seconds(15, 12, 8, 10) == 45
~~~

If fencing cannot be confirmed, the safe state is **blocked**, potentially exceeding the RTO. Relaxing that guard just to meet an availability target may sacrifice the single-writer property. Set priorities explicitly for orders, payments, inventory and other domains.

## Failure matrix and reviewer obligations

| Failure or observation | Safe decision | Evidence required |
| --- | --- | --- |
| Primary health check times out | Suspect, do not immediately promote | Independent fencing status |
| Fence receipt missing | Block promotion | Fail-closed controller tests |
| Old receipt from earlier epoch | Block promotion | Epoch-identity test |
| Old primary observed running | Block promotion | Live Docker negative test |
| Old primary stopped in disposable test | Candidate may be considered | Docker state check, replay policy |
| Primary network partitioned, still writing | Block until credible fencing | Real partition and fencing integration |
| Old primary returns after promotion | Never permit dual writes | Rejoin/fencing and routing tests |

The tests exercise a useful **ordering contract**, not a full automatic HA stack. The most important next experiment is to add an independent coordinator and a real fence whose loss of communication does not allow dual writers.

## Exercises and verification

1. Explain why failing to ping a primary is not sufficient evidence that its writes have stopped.
2. Describe how a stale epoch receipt could promote an unsafe candidate if the controller skipped its generation check.
3. Change the unit-test fake so the fencing verifier rejects the receipt; prove the promoter never runs.
4. Design a PostgreSQL client test that tries to write through the **old endpoint** after a new primary is promoted.
5. Specify how an independent watchdog or power controller provides fencing even if the failover controller crashes.

**Related chapters:** [Physical replication and promotion](/en/topics/postgresql-streaming-promotion/), [replication theory](/en/topics/database-replication-failover/), [write skew and SERIALIZABLE](/en/topics/postgresql-serializable-retry-lab/) and [incident recovery](/en/topics/production-incident-response/) explain other boundaries [1][2][3].
