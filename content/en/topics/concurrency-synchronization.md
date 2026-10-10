---
id: concurrency-synchronization
title: "Concurrency: Races, Locks, Conditions and Deadlocks"
description: "Derive synchronization invariants, critical sections, race conditions, condition-variable protocols, deadlocks and bounded queues."
category: foundations
difficulty: advanced
updated: 2026-10-10
prerequisites: [processes-virtual-memory, cpu-scheduling-fcfs-round-robin, testing-maintainability]
sources:
  - {title: "Python documentation — threading", url: "https://docs.python.org/3/library/threading.html", kind: "official documentation"}
  - {title: "Operating Systems: Three Easy Pieces — Concurrency", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/", kind: "university textbook"}
---
**Concurrency** means multiple activities can progress with overlapping lifetimes; **parallelism** means executing work at the same instant on different computational resources. A program may be concurrent on one CPU through interleaving, or parallel across cores. Correctness requires defining which shared states must remain consistent regardless of scheduling order. Merely using threads or asynchronous syntax does not establish safety [1][2].

The [CPU scheduling chapter](/en/topics/cpu-scheduling-fcfs-round-robin/) explains how a runnable task receives CPU time. This chapter analyzes whether shared-state invariants survive different valid interleavings; fair scheduling does not make unsynchronized increments correct [1][2].

## Interleavings and the lost-update race

Suppose two threads increment a counter represented by shared memory. Each increment conceptually reads the old value, adds one and writes the result. From initial x=0, schedule T1 reads 0, T2 reads 0, T1 writes 1, T2 writes 1: final x=1 although two increments occurred. This is a **lost update**. The possibility depends on operations, memory model and interleavings; the result cannot be fixed by inserting arbitrary sleeps.

A **critical section** is a region accessing shared state that needs a specified atomicity or mutual-exclusion guarantee. A mutex allows only one owner into such a region at a time. Locks protect **invariants**, not merely individual variables: checking account balance and decrementing it separately without common synchronization still permits overdrawing even if each read and write is individually atomic.

## Data races and memory ordering

A data race in languages such as C/C++ can have especially serious semantics because unsynchronized conflicting accesses may produce undefined behavior under the language memory model. Python threading has implementation-specific behaviors, and the global interpreter lock in common CPython builds does not make arbitrary read-modify-write transactions semantically atomic. Free-threaded Python variants are another reason to use explicit synchronization. Code should rely on documented primitives, not observed scheduling quirks [1].

**Happens-before** describes ordering guarantees established by program order and synchronization in a particular memory model. Without an ordering relation, different threads may observe writes at unexpected times. A mutex acquisition/release protocol is a conventional way to establish both exclusion and necessary visibility. Using an ordinary boolean as an unsynchronized stop flag may be wrong in languages with weak or formally constrained memory models.

## Safe shared counter and verification

~~~python
from threading import Thread, Lock

class Counter:
    def __init__(self):
        self.value = 0
        self.lock = Lock()

    def add(self, n):
        for _ in range(n):
            with self.lock:
                self.value += 1

counter = Counter()
threads = [Thread(target=counter.add, args=(1000,)) for _ in range(4)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert counter.value == 4000
~~~

The linearization point for this small counter update lies inside the protected critical section; every thread shares the same lock. This particular test demonstrates one execution, not proof across all schedulers. Formal reasoning depends on all access paths respecting the lock; a single unprotected writer breaks the invariant. Lock contention reduces scalability: the protected section must be as small as correctness permits, without moving checks outside their required atomic boundary.

## Condition variables and bounded producer-consumer

A condition variable allows a thread to sleep while waiting for a predicate over shared state. A producer holds the associated mutex while modifying the queue and **notifies** waiters after making a useful condition true. A consumer calls wait while the predicate is false. Crucially, wait releases the lock while sleeping and reacquires it before returning, so producers can progress [1].

![Bounded queue transitions between empty, partially full and full states.](/diagrams/bounded-queue.svg)

~~~python
from threading import Condition, Thread

class BoundedBuffer:
    def __init__(self, capacity):
        if capacity <= 0: raise ValueError("positive capacity required")
        self.capacity = capacity
        self.items = []
        self.cv = Condition()

    def put(self, item):
        with self.cv:
            while len(self.items) == self.capacity:
                self.cv.wait()
            self.items.append(item)
            self.cv.notify_all()

    def take(self):
        with self.cv:
            while not self.items:
                self.cv.wait()
            item = self.items.pop(0)
            self.cv.notify_all()
            return item

buffer = BoundedBuffer(2)
received = []
worker = Thread(target=lambda: received.append(buffer.take()))
worker.start()
buffer.put(7)
worker.join(timeout=3)
assert not worker.is_alive() and received == [7]
~~~

Use **while**, not if, around the waiting predicate: notifications are hints to recheck state, not promises that another awakened consumer has not taken the item. Notification does not itself release the lock; the waiter continues only after reacquiring it. A real bounded queue should offer cancellation, timeouts, shutdown behavior and possibly separate conditions for not-empty and not-full. The example is for one small demonstration, not an optimized queue.

## Deadlock, livelock and starvation

**Deadlock** occurs when tasks wait in a cycle for resources or conditions that can never be satisfied by the waiting tasks. For instance, T1 holds lock A and waits for B, while T2 holds B and waits for A. A global **lock-order** rule (always acquire A before B) prevents this particular circular wait. Avoiding hold-and-wait or adding abortable timeouts may be appropriate, but timeouts alone do not repair the underlying protocol.

**Livelock** means tasks keep changing state or retrying without useful progress; **starvation** means some task waits indefinitely while others advance. A system can avoid deadlock and still be unfair. Priority inversion occurs when a high-priority task waits behind a lower-priority holder; some kernels use priority inheritance to mitigate it. Correctness and progress properties are separate: mutual exclusion alone does not ensure that everyone eventually completes [2].

## Concurrency versus distributed systems

A process lock protects threads in that process, not independent processes on different machines. For a globally unique payment or reservation, enforce invariants at the authoritative data store, such as a database unique constraint plus appropriate transaction isolation. Distributed locks require leases, expiration, fencing tokens and fault-model analysis; a Redis lock is not magically equivalent to a durable database transaction. Also distinguish asynchronous I/O (many operations waiting) from multi-core CPU parallelism.

## Exercises and verification

1. Write an explicit two-thread schedule producing a lost update from 0 to 1 instead of 2.
2. Show why replacing while with if in the bounded buffer is unsafe when two consumers wake and race for one item.
3. Draw a wait-for graph of locks A and B; enforce global acquisition order and argue why circular wait disappears.
4. Why can a shared lock serialize all requests and harm throughput? Identify which data can be sharded under separate locks without violating invariants.
5. Extend the buffer with a close() operation and define what take() must return when closed and empty; test that all waiting threads eventually wake.
