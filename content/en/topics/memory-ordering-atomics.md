---
id: memory-ordering-atomics
title: "Memory Models: Atomics, Happens-Before and Visibility"
description: "Explain C++ data races, per-object modification order, release/acquire, relaxed operations, sequential consistency and publication safety."
category: foundations
difficulty: advanced
updated: 2026-10-09
prerequisites: [concurrency-synchronization, processes-virtual-memory]
sources:
  - {title: "C++ working draft — Data races and happens-before", url: "https://eel.is/c++draft/intro.races", kind: "draft language standard"}
  - {title: "std::memory_order — cppreference", url: "https://en.cppreference.com/w/cpp/atomic/memory_order", kind: "technical language reference"}
---
Two threads can execute instructions on separate cores without agreeing about the order in which every memory change becomes visible. Compilers also reorder or remove operations when the language's semantics permit. A **memory model** specifies which executions are allowed, which synchronization makes data safe to share and which patterns have undefined behavior. The rules of C++ are the subject here; Python threads, Java and hardware assembly have related but **not identical** guarantees [1].

## The critical distinction: atomicity is not ordering

Atomicity means an operation on an atomic object participates in its specified indivisible modification behavior; it does not necessarily order other memory locations. A pair of ordinary assignments, even to naturally aligned machine words, is **not** a two-field atomic transaction. An algorithm should define the exact invariant it requires: does it merely need a counter without lost updates, or does it need a consumer to observe a whole initialized object?

In C++, conflicting accesses to the same memory location from different threads, where at least one modifies it, and without the required happens-before relation or atomic protection, can constitute a **data race**. A data race has undefined behavior, not merely 'sometimes reads an old value'. Undefined behavior permits compiler optimizations that defeat attempts to reason purely from one observed CPU interleaving [1].

## Sequenced-before, synchronizes-with and happens-before

Within one thread, evaluations relate by the language's **sequenced-before** rules. Across threads, some synchronized operations create a **synchronizes-with** edge. The transitive closure with sequenced-before contributes to the **happens-before** relation: if A happens-before B, guarantees follow about ordering and visible side effects under the language rules [1]. These names describe a *formal relation*, not elapsed wall-clock order or a universally shared cache timeline.

An atomic object also has its own **modification order**, a total order of modifications to that one object. Different atomic objects need not have a common global modification order when using weak memory orderings. Thus observing a recent change to flag X does not by itself establish ordering for a separate payload Y.

![Release and acquire connect producer initialization to consumer reads.](/diagrams/memory-release-acquire.svg)

## Relaxed atomics are still useful

A `memory_order_relaxed` atomic read/modify/write provides atomicity and modification order for its object but does not, by itself, synchronize ordinary accesses to other objects [2]. This suits a statistics counter whose exact increment count matters but which does not publish another data structure. It is unsafe to treat a relaxed 'ready' flag as proof that an unprotected consumer may read an initialized non-atomic payload.

For example, multiple threads increment a relaxed atomic count and another thread reads it. The count behaves according to atomic ordering, but there is no guarantee that reading a particular count reveals everything each worker modified elsewhere. If the design requires an invariant connecting counters and a multi-field state snapshot, use appropriate synchronization rather than assuming one atomic load creates a consistent transaction.

## Release/acquire as a publication protocol

A producer initializes an object, then performs a **release** store to an atomic flag. A consumer repeatedly reads that *same flag* with **acquire** semantics and, after it observes the producer's released value (or a value from the relevant release sequence), reads the initialized data. The successful acquire synchronizes with the release, establishing visibility of preceding writes. Acquire alone on an unrelated flag, or an acquire that never reads the release sequence, does not establish this relationship [1][2].

~~~cpp
#include <atomic>
#include <thread>
#include <cassert>

struct Payload { int left = 0, right = 0; };
Payload payload;
std::atomic<bool> ready{false};

void producer() {
    payload.left = 7;
    payload.right = 11;
    ready.store(true, std::memory_order_release);
}
void consumer() {
    while (!ready.load(std::memory_order_acquire)) {}
    assert(payload.left == 7 && payload.right == 11);
}
// Run producer and consumer exactly once, then join both threads.
// Do not mutate payload concurrently after the ready publication.
~~~

This code is an **illustrative fragment**, not a whole executable C++ program. It requires one producer and no later conflicting non-atomic mutations to payload. A real implementation needs a lifecycle for ownership, repeated publications and shutdown; merely changing ready back to false without another synchronization protocol would not suffice.

## Sequential consistency and its limits

`memory_order_seq_cst` imposes an additional single total order over the relevant sequentially consistent atomic operations, consistent with their formal constraints [2]. This is easier to reason about than many weaker orderings, but it is not a blanket guarantee of atomicity for an entire group of ordinary fields. Two sequentially consistent counters can each be atomic while a caller still observes values from different moments; an invariant spanning both requires further design.

A mutex provides exclusion for code honoring the same mutex, and its acquire/release protocol establishes appropriate ordering for protected data. Often this is safer than crafting a lock-free algorithm. Optimizing with weaker atomics should follow a proven protocol and realistic profiling, not a belief that lower-order instructions are always faster on every architecture.

## Interleaving exercise: the lost-update baseline

A small program can enumerate the steps of a **non-atomic** increment to illustrate why atomic read-modify-write or a lock matters. It is a sequential state-space model, **not** a simulator of the C++ memory model: the real C++ racy version has undefined behavior.

~~~python
from itertools import combinations

def interleavings():
    steps = ("Aread", "Awrite", "Bread", "Bwrite")
    for a_slots in combinations(range(4), 2):
        b_slots = [k for k in range(4) if k not in a_slots]
        seq = [None] * 4
        seq[a_slots[0]], seq[a_slots[1]] = steps[:2]
        seq[b_slots[0]], seq[b_slots[1]] = steps[2:]
        yield seq

def run_trace(steps):
    memory = 0
    registers = {}
    for step in steps:
        thread, action = step[0], step[1:]
        if action == "read":
            registers[thread] = memory
        else:
            memory = registers[thread] + 1
    return memory

outcomes = {run_trace(s) for s in interleavings()}
assert outcomes == {1, 2}
~~~

Here each thread reads, then writes one increment in program order. The six interleavings include schedules where both read zero and later write one, losing an increment. The exercise isolates the *algorithmic hazard*; the C++ specification does not constrain an unsynchronized data race to the outcomes shown.

## Counterexamples and boundary checks

| Pattern | What it ensures | What it does not ensure |
| --- | --- | --- |
| Relaxed atomic counter | Atomic modifications of counter | Visibility of unrelated payload |
| Release store + matching acquire load | Publication happens-before edge | Mutual exclusion of later writers |
| Seq-cst atomic operations | Strong common order for those operations | Multi-object transaction by default |
| Mutex around shared invariant | Exclusion and ordering for participants | Protection from code ignoring lock |
| Volatile ordinary flag | Certain compiler-facing semantics | General inter-thread synchronization in C++ |

A plain volatile variable is **not** a general substitute for `std::atomic`. Thread-safe publication of a pointer also requires ensuring the pointed-to object's lifetime extends through every reader. Memory reclamation in lock-free structures (hazard pointers, epoch schemes) is an additional challenge even after atomic pointer updates are correct.

## Exercises and verification

1. Explain why a relaxed `ready` flag is insufficient to publish non-atomic initialized fields.
2. State exactly which acquire must observe which release to establish inter-thread happens-before in the example.
3. Give an example of two atomic variables that still do not preserve a joint balance invariant.
4. Show why a mutex-protected update can be correct only when **every** conflicting access follows the same policy.
5. Run the Python interleaving model, list a sequence resulting in one, and explain why its result is not a proof about undefined C++ executions.

**Related chapters:** [Concurrency and synchronization](/en/topics/concurrency-synchronization/) introduces races and locks; [processes and virtual memory](/en/topics/processes-virtual-memory/) distinguishes virtual mappings from the memory-order guarantees within one address space.
