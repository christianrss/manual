---
id: concurrency-interview-workshop
title: "Concurrency Interview Workshop: Races, CAS and Interleavings"
description: "Derive a two-worker lost-update counterexample, fix it with versioned CAS, enumerate schedules and test thread synchronization."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [concurrency-synchronization, testing-strategies]
sources:
  - {title: "Python threading — Lock, Barrier and synchronization", url: "https://docs.python.org/3/library/threading.html", kind: "official Python documentation"}
  - {title: "PostgreSQL — Transaction Isolation", url: "https://www.postgresql.org/docs/current/transaction-iso.html", kind: "official database documentation"}
---
**Concurrency interview problems** are tests of invariants under different execution orders, not contests to remember the names of lock primitives. A correct implementation should state which operation is atomic, what other workers can observe, and which failure model it tolerates. This workshop studies a **one-seat reservation**, first with a deliberately broken read-then-write protocol, then with optimistic version checking and thread-safe local operations. Threads on common CPython builds do not remove the need to synchronize compound state changes [1].

## Contract and competing operations

The domain has exactly one seat, initially `free`, and two customers, A and B. A successful reserve(customer) returns success and makes that customer the owner. Once reserved, the seat cannot be reserved by someone else. The invariant is **at most one winner**. Define unsuccessful attempts explicitly: an already-owned seat returns false, while repeating a request by the same customer needs a separate idempotency contract if that behavior is desired. This exercise instead returns false for all attempts after the first successful reservation.

Distinguish *safety* (never two accepted owners), *liveness* (a waiting request may eventually finish under scheduling assumptions), and *durability* (the winning decision survives specified crashes). A Python mutex can protect safety inside one running process, but cannot guarantee durability or coordinate unrelated replicas. An external database authority needs an atomic conditional update [2].

## Construct a reproducible lost-update schedule

A broken routine does `read owner`, checks free, then `write customer`. Individually correct reads and writes do not make the combined transaction atomic. If A reads `free`, B reads `free`, A commits A and reports success, then B commits B and reports success, both callers were told they won. Final state B does not reveal that A already received a success response.

![Two workers read free before either writes; a conditional commit permits one winner.](/diagrams/concurrency-interview-schedule.svg)

Model this schedule explicitly rather than relying on thread timing. A deterministic schedule is evidence of a race, not a probabilistic stress test.

~~~python
def broken_schedule(steps):
    owner = None
    observed = {}
    wins = []
    for worker, phase in steps:
        if phase == "read":
            observed[worker] = owner
        elif phase == "commit":
            if observed[worker] is None:
                owner = worker
                wins.append(worker)
        else:
            raise ValueError("unknown phase")
    return owner, wins

race = [("A", "read"), ("B", "read"), ("A", "commit"), ("B", "commit")]
final_owner, successes = broken_schedule(race)
assert final_owner == "B" and successes == ["A", "B"]
~~~

The model deliberately gives each worker its own captured read and does not pretend an actual database would allow this overwrite under every isolation level. Its purpose is to expose the missing atomic **check-and-write** operation.

## Fix it with an optimistic version check

A conditional update compares the old version and changes the owner **in one atomic action**. Under an authoritative store implementing compare-and-swap (CAS), exactly one competing writer can successfully change version zero to version one. The unsuccessful caller must not claim success. A local Python demonstration can serialize this action through a lock; that lock protects only threads sharing the same object.

~~~python
from threading import Lock

class Seat:
    def __init__(self):
        self._owner = None
        self._version = 0
        self._lock = Lock()

    def read(self):
        with self._lock:
            return self._owner, self._version

    def reserve_if_version(self, customer, expected):
        if not customer:
            raise ValueError("customer required")
        with self._lock:
            if self._version != expected or self._owner is not None:
                return False
            self._owner = customer
            self._version += 1
            return True

seat = Seat()
assert seat.read() == (None, 0)
assert seat.reserve_if_version("A", 0)
assert not seat.reserve_if_version("B", 0)
assert not seat.reserve_if_version("A", 1)
assert seat.read() == ("A", 1)
~~~

The linearization point is the guarded transition in `reserve_if_version`. While the lock is held, the version and owner change as one locally synchronized operation. The check `owner is None` is necessary because a later version could correspond to a release in a richer model, and allowing unconditional retries would not uphold the one-time booking rule. In a database, the equivalent is a conditional UPDATE or a uniqueness constraint protected by its transaction semantics.

## Enumerate all legal interleavings

For two workers with a `read` followed by a `commit`, only schedules preserving **each worker's local program order** are legal. There are six distinct order-preserving interleavings of two length-two sequences. A correct model should verify safety across all six, not only the schedule that once failed. Here the conditional commit is represented as one atomic step.

~~~python
from itertools import combinations

def all_schedules():
    for a_positions in combinations(range(4), 2):
        a = iter(("read", "commit"))
        b = iter(("read", "commit"))
        yield [(("A", next(a)) if i in a_positions
                else ("B", next(b))) for i in range(4)]

def guarded_model(schedule):
    owner = None
    version = 0
    observations = {}
    successes = []
    for worker, operation in schedule:
        if operation == "read":
            observations[worker] = version
        elif operation == "commit":
            if owner is None and observations[worker] == version:
                owner = worker
                version += 1
                successes.append(worker)
    return owner, successes

schedules = list(all_schedules())
assert len(schedules) == 6
assert all(len(guarded_model(s)[1]) == 1 for s in schedules)
assert any(len(broken_schedule(s)[1]) == 2 for s in schedules)
~~~

This is a **finite-state test** under a narrow two-worker, two-operation model. It does not establish liveness or thread safety for all production code. In a larger system, add retries, releases, crashes and network partitions to the state space, then explore the new interleavings. Exponential growth of schedules is why model checking needs carefully chosen abstraction and bounded domains.

## Test real threads without assuming a scheduling race

A stress test can be useful, but a passing stress test does not prove absence of a race. Use a barrier to start several workers together, invoke the synchronized method, and check the result. The barrier makes starting more comparable but **does not force every possible instruction interleaving**; the explicit state exploration above is the deterministic counterexample check [1].

~~~python
from threading import Barrier, Thread

shared = Seat()
barrier = Barrier(4)
outcomes = []

def attempt(name):
    _, version = shared.read()
    barrier.wait()
    result = shared.reserve_if_version(name, version)
    outcomes.append(result)

threads = [Thread(target=attempt, args=(name,))
           for name in ("A", "B", "C", "D")]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join(timeout=5)
assert not any(thread.is_alive() for thread in threads)
assert outcomes.count(True) == 1
assert shared.read()[0] in ("A", "B", "C", "D")
~~~

The local list `outcomes` collects only the results after each call; the crucial guarantee is enforced by the Seat object's guarded mutation. For an actual payment or inventory service, the test must use distinct connections/processes and a real authority. Python threads and a single Lock cannot reproduce a distributed conflict or validate database transaction isolation.

## Deadlocks, progress and fairness

Mutual exclusion solves the lost-update safety issue but can introduce deadlocks if resources are acquired in inconsistent orders. Worker A holding account lock while waiting for inventory, and B holding inventory while waiting for account, can form a cycle. Break the cycle by a common lock acquisition order, by reducing critical-section size, or by bounded acquisition and recovery. Lock timeouts are not themselves a complete recovery protocol if some side effects already happened.

A lock also does not promise **fairness**. Python's documentation states that which blocked thread acquires a released primitive lock is not defined [1]. High contention may starve a worker even when safety is preserved; distinguish starvation from deadlock and measure wait time separately from service time.

## When a local lock is the wrong tool

| Setting | Correctness boundary | Missing from a mutex alone |
| --- | --- | --- |
| Threads in one process | Shared in-memory Seat object | Crash durability |
| Several API processes | Transactional datastore | Cross-process coordination |
| Multiple regions | Leader/quorum or clear authority | Partition and failover policy |
| External payment provider | Provider idempotency and reconciliation | Atomic cross-provider commit |
| Queue consumers | Durable claim/lease and deduplication | Replay, crash recovery |

Exactly one locally accepted reservation is achievable inside one authority, but exactly-once **external effects** require stronger end-to-end assumptions. Idempotency identities and durable state are essential to distinguish retries after ambiguous results.

## Exercises and verification

1. Draw the six legal two-worker interleavings and identify which broken schedules yield two successes.
2. Explain which instruction in the corrected Seat implementation acts as the linearization point.
3. Extend the model with a `release` operation and identify why an old version must not succeed after a release and re-reservation (the ABA issue).
4. Compare a single-process Lock with a database conditional UPDATE for three stateless API replicas.
5. Design a deadlock scenario with two locks and describe a lock-order policy that eliminates its cycle.

**Related chapters:** [Concurrency fundamentals](/en/topics/concurrency-synchronization/), [memory ordering](/en/topics/memory-ordering-atomics/), [formal model checking](/en/topics/formal-model-checking/) and [transaction isolation](/en/topics/transactional-indexing-isolation/) deepen the guarantees [1][2].
