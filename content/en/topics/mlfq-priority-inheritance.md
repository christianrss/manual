---
id: mlfq-priority-inheritance
title: "Priority Scheduling: MLFQ, Aging and Priority Inheritance"
description: "Derive MLFQ scheduling, periodic priority boosts, starvation and lock priority inheritance with independently verifiable models."
category: operating-systems
difficulty: intermediate
updated: 2026-10-10
prerequisites: [cpu-scheduling-fcfs-round-robin, concurrency-synchronization]
sources:
  - {title: "Operating Systems: Three Easy Pieces — Multi-Level Feedback Queue", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched-mlfq.pdf", kind: "primary university textbook chapter"}
  - {title: "Linux kernel — RT-mutex implementation design", url: "https://docs.kernel.org/locking/rt-mutex-design.html", kind: "official operating system design"}
  - {title: "Linux kernel — EEVDF Scheduler", url: "https://docs.kernel.org/scheduler/sched-eevdf.html", kind: "official current scheduler documentation"}
  - {title: "Python documentation — deque", url: "https://docs.python.org/3/library/collections.html#collections.deque", kind: "official standard library"}
---
A scheduler chooses a runnable task. The earlier [FCFS and Round Robin](/en/topics/cpu-scheduling-fcfs-round-robin/) chapter used arrival order and rotating time slices. Real workloads introduce another problem: short or interactive tasks need quick service even though the operating system does not know their next CPU-burst length. A **multi-level feedback queue (MLFQ)** uses observed CPU behavior to adjust scheduling priorities. **Priority inheritance**, by contrast, responds to a high-priority task blocking on a mutex owned by a lower-priority task. These address different problems and must not be conflated [1][2].

This chapter specifies and tests **two deliberately limited models**: a CPU-bound three-level MLFQ, and a finite wait-for graph that computes priority donation. Neither is a Linux scheduler implementation or a real-time correctness proof. The Linux kernel's ordinary fair scheduling has evolved to **EEVDF**, which must not be described as classical MLFQ [3].

## Priority classes and the feedback principle

A fixed-priority scheduler chooses from the highest nonempty runnable-priority class. When two runnable tasks have equal priority, a separate policy—such as Round Robin—must resolve their order. Fixed priorities alone do not classify an unknown job as interactive or CPU-bound.

MLFQ changes a task's level based on its own observed service: new tasks enter a high-priority queue; tasks that consume an assigned CPU budget descend; lower-priority tasks are eligible when no higher-priority work is runnable. The OSTEP treatment also introduces **periodic global boosting** to keep a low-priority job from being permanently stranded, and accumulated allotments to prevent repeatedly yielding just before a quantum expires from defeating demotion [1].

| Concern | Defined in this model | Not modeled |
| --- | --- | --- |
| CPU resources | One CPU, one active task per tick | Multicore migration and utilization |
| Work | Finite integer CPU demand, no I/O | Blocking, wake-ups, interactive heuristics |
| Priority | Three queues, level 0 highest | Linux scheduling classes or nice values |
| Quanta | Positive per-level CPU allotments | Physical timer precision |
| Boost | Optional periodic reset to level 0 | Kernel runtime fairness guarantees |
| Context switch | Zero cost | Cache/TLB effects, locks and interrupts |

**Terminology matters:** *priority* is a selection order, *quantum* bounds uninterrupted service, *allotment* counts CPU service before demotion, and *aging* increases the opportunity for long-waiting tasks to execute. Here, periodic **global boost** is one form of anti-starvation mechanism; it is **not** an individually tracked wait-time aging algorithm [1].

## Define event order before simulating MLFQ

We count discrete CPU ticks beginning at time 0. Tasks have unique nonblank names, nonnegative integer arrival times and strictly positive integer amounts of CPU work. Simultaneous arrivals use original input order. Queue 0 has the highest priority. By default the three per-level quanta are `(1, 2, 4)`; a task at the lowest level remains at that level after using a quantum. Unused quantum budget is **retained across preemption** by a newly ready higher-priority task.

Every tick follows this exact sequence:

1. If time is a positive multiple of `boost_interval`, move all unfinished **runnable** tasks to level 0. Existing ready queues are flattened from high to low in FIFO order; the formerly running task is placed last, and each promoted task's consumed allotment resets. A zero interval disables boosting.
2. Admit jobs whose arrival time has been reached, preserving input order.
3. If a higher-priority task is ready, preempt the current task and return it to the **front of its existing level**, retaining its partial allotment. Otherwise it continues.
4. Dispatch the front of the highest nonempty queue if the CPU is free; one task runs for exactly one tick.
5. Completion removes the task; exhausting a level's allotment demotes it by at most one level and queues it at the end, resetting its allotment.

A boost and an arrival at the same tick occur in **that order**. These tie-breaking decisions have observable consequences: swapping steps 1 and 2 or requeuing a preempted task at the back changes some traces. They are policy decisions in this teaching model, not universal kernel rules.

## Executable three-level MLFQ

The implementation deliberately returns **a tuple of CPU owners per tick**, using `None` for idle time. Unlike the previous chapter's event-driven Round Robin, this simple simulator inspects queues at each tick so it can express boost, preemption and demotion directly. A `deque` permits constant-time front and back operations under ordinary bounded-cost assumptions [4].

~~~python
from collections import deque
from dataclasses import dataclass

@dataclass(frozen=True)
class Task:
    name: str
    arrival: int
    work: int

def mlfq(tasks, quanta=(1, 2, 4), boost_interval=0):
    items = tuple(tasks)
    if (not isinstance(quanta, tuple) or len(quanta) != 3
            or any(type(q) is not int or q <= 0 for q in quanta)):
        raise ValueError("three positive integer quanta required")
    if type(boost_interval) is not int or boost_interval < 0:
        raise ValueError("invalid boost interval")
    seen = set()
    for item in items:
        if (not isinstance(item, Task) or not isinstance(item.name, str)
                or not item.name.strip() or item.name != item.name.strip()
                or item.name in seen or type(item.arrival) is not int
                or item.arrival < 0 or type(item.work) is not int
                or item.work <= 0):
            raise ValueError("invalid task")
        seen.add(item.name)

    arrivals = sorted(enumerate(items), key=lambda p: (p[1].arrival, p[0]))
    remaining = {task.name: task.work for task in items}
    levels = {task.name: 0 for task in items}
    used = {task.name: 0 for task in items}
    queues = [deque() for _ in range(3)]
    time = cursor = finished = 0
    current = None
    trace = []

    while finished < len(items):
        if boost_interval and time > 0 and time % boost_interval == 0:
            order = [name for queue in queues for name in queue]
            if current is not None:
                order.append(current)
            queues = [deque(order), deque(), deque()]
            for name in order:
                levels[name] = used[name] = 0
            current = None

        while cursor < len(arrivals) and arrivals[cursor][1].arrival <= time:
            queues[0].append(arrivals[cursor][1].name)
            cursor += 1

        if current is not None and any(
                queues[i] for i in range(levels[current])):
            queues[levels[current]].appendleft(current)
            current = None

        if current is None:
            for queue in queues:
                if queue:
                    current = queue.popleft()
                    break
        if current is None:
            trace.append(None)
            time += 1
            continue

        trace.append(current)
        remaining[current] -= 1
        used[current] += 1
        if remaining[current] == 0:
            finished += 1
            current = None
        elif used[current] == quanta[levels[current]]:
            levels[current] = min(levels[current] + 1, 2)
            used[current] = 0
            queues[levels[current]].append(current)
            current = None
        time += 1
    return tuple(trace)

assert mlfq((Task("A", 0, 6),)) == ("A",) * 6
assert mlfq((Task("A", 0, 7), Task("B", 2, 2))) == (
    "A", "A", "B", "A", "B", "A", "A", "A", "A"
)
assert mlfq((Task("A", 5, 2),)) == (
    None, None, None, None, None, "A", "A"
)
~~~

In the two-task example, A first consumes the top-level allotment at tick 0, then begins consuming its level-1 allotment. B arrives at tick 2 and takes the newly highest queue. A resumes according to its **remaining** budget when the higher-priority queue empties. B does not inherit A's remaining burst or modify it; only the scheduling order changes. Traces for a task arriving at time 5 contain five `None` entries, not an artificial execution slice before arrival.

**State invariant:** every admitted, unfinished task exists **exactly once**—either as `current` or in precisely one ready queue. Its remaining CPU demand plus its number of executed ticks equals its original demand. Each execution tick reduces that remaining demand by one. Queue level and spent allotment stay within their configured ranges. All boosts, arrivals and demotions maintain these properties, so finite positive workloads eventually complete under this simulator.

Let `n` be tasks, `T` total simulated elapsed ticks including idle gaps, and `B` the number of boost instants. Arrival sorting takes `O(n log n)`. A normal tick touches at most three queues, giving `O(T)` work; a boost may inspect up to `n` tasks, giving an overall upper bound `O(n log n + T + nB)` and `O(n+T)` storage including the trace. That bound is for **this Python simulator**, not for an actual kernel. Very large arrival timestamps make a per-tick simulation impractical compared with an event-driven implementation.

## Starvation, boosts and the limits of fairness claims

Without boosts, a low-priority CPU-bound task can be postponed while higher-priority work continually arrives. Increasing the priority of a task that has waited too long (*individual aging*) and periodically returning all runnable tasks to the top (*global priority boosting*) are related but different choices. OSTEP describes the boosting rule as a response to starvation and long-term changes in task behavior [1].

Within this model, a finite set of finite CPU workloads terminates even without boosting. That is **not** a proof of bounded waiting for an unbounded arrival stream. If arrivals can be admitted indefinitely or execution can block, both progress and fairness require additional assumptions. A boost helps by moving waiting work into a higher queue, but its effectiveness depends on its ordering, frequency and the arrival workload. Never infer a hard latency bound from a few favorable traces.

Another subtlety is **gaming**: if a policy resets a task's allotment whenever it voluntarily yields just before quantum expiration, a malicious task can remain near the top indefinitely. Our example has **no I/O or voluntary yielding**, so it cannot empirically demonstrate anti-gaming behavior. Its accounting retains partial budget across **priority preemption**; supporting true yields would require explicit blocked/wakeup events and an allotment policy that persists across them [1].

## Priority inversion: a separate problem involving locks

A low-priority task L holds a mutex. A high-priority task H needs the mutex and **blocks**. A medium-priority CPU-bound task M can then repeatedly preempt L, preventing L from releasing the resource H requires. H is indirectly delayed by M despite having greater nominal priority. This is **priority inversion**; simply moving H to the front of the runnable queue cannot help because H is **not runnable** while waiting for the lock [2].

**Priority inheritance** temporarily raises the effective priority of the lock owner to that of the strongest waiter. In the L/M/H example, base priorities L=1, M=2, H=3 (larger means more important **in this model**) produce effective priority L=3 while H waits for a mutex L holds. If L itself waits for a lock held by X, donation must **propagate transitively** to X. When blocking relationships disappear, priorities must be recomputed from base priorities, not left permanently elevated [2].

The Linux rt-mutex design uses dedicated waiter structures, locking rules and priority-chain handling; the following code does **none** of that. It only computes the expected priority values for a stable, finite, **acyclic** dependency graph.

## Executable transitive priority donation

`blocked_on` maps each waiting task to the owner it currently waits for. A task can wait for at most one owner in this simplified representation. We reject missing names and cycles rather than pretend that priority donation cures deadlock. Every priority is a nonnegative integer, and we explicitly reject `bool` masquerading as an integer.

~~~python
def effective_priorities(base, blocked_on):
    if (not isinstance(base, dict) or not base
            or any(not isinstance(name, str) or not name
                   or type(priority) is not int or priority < 0
                   for name, priority in base.items())):
        raise ValueError("invalid base priorities")
    if (not isinstance(blocked_on, dict)
            or any(waiter not in base or owner not in base or waiter == owner
                   for waiter, owner in blocked_on.items())):
        raise ValueError("invalid wait graph")

    for origin in base:
        seen = set()
        node = origin
        while node in blocked_on:
            if node in seen:
                raise ValueError("deadlock cycle is outside this model")
            seen.add(node)
            node = blocked_on[node]

    effective = dict(base)
    for _ in range(len(base)):
        changed = False
        for waiter, owner in blocked_on.items():
            if effective[owner] < effective[waiter]:
                effective[owner] = effective[waiter]
                changed = True
        if not changed:
            break
    return effective

base = {"L": 1, "M": 2, "H": 3, "X": 0}
assert effective_priorities(base, {"H": "L"}) == {
    "L": 3, "M": 2, "H": 3, "X": 0}
assert effective_priorities(base, {"H": "L", "L": "X"}) == {
    "L": 3, "M": 2, "H": 3, "X": 3}
assert effective_priorities(base, {}) == base
assert base["L"] == 1
try:
    effective_priorities(base, {"H": "L", "L": "H"})
except ValueError:
    pass
else:
    raise AssertionError("wait cycle must not be silently accepted")
~~~

**Invariant:** after each propagation pass, an owner's effective priority is no lower than the base priorities of all waiters whose donation has reached that owner; priorities only increase and never exceed the largest base priority. In an acyclic graph with `n` tasks, any dependency path has at most `n−1` edges, so at most `n` full relaxation passes suffice. This direct implementation costs up to `O(n²)` for cycle checks and `O(n×e)` for relaxation, where `e` is the number of waiting edges. Its compactness makes the semantics visible but would not justify using it inside a high-frequency kernel lock path.

The function recomputes donations from scratch. Removing H's dependency on L returns L to priority 1 unless another waiter still donates. It does **not** acquire, release or transfer locks; calculate deadlines; enforce mutex ownership; guarantee freedom from deadlock; or select the next CPU task. It is a small **priority-propagation contract**, not an rt-mutex.

## MLFQ, static priority inheritance and current Linux scheduling

MLFQ uses measured CPU consumption as a heuristic for **which runnable task** receives service. Priority inheritance addresses **who must run to release a resource for a blocked higher-priority task**. Replacing the second with the first confuses the cause of delay.

Modern Linux supports distinct scheduling classes and specialized real-time lock behavior. Its official EEVDF documentation discusses lag and virtual deadlines for fair scheduling; that should not be equated with these three literal FIFO priority queues [3]. Likewise, priority inheritance in real-time mutexes must coordinate actual scheduler classes, ownership and blocking, whereas our graph merely assigns integer ranks [2]. This distinction matters when explaining or implementing scheduler extensions.

## Exercises and verification

1. By hand, trace A(arrival 0, work 7), B(arrival 2, work 2) with quanta `(1,2,4)`, and explain every priority change and preemption.
2. Use `boost_interval=3` and show the queue order exactly when a boost coincides with a new arrival.
3. Replace the boost with **per-task waiting-time aging**. State its clock, threshold, tie rules and invariants before coding.
4. Add optional blocking events and prove how to preserve allotments across voluntary yields to avoid the classic gaming strategy.
5. Derive the `O(n log n+T+nB)` simulator bound and construct a case where a large idle gap dominates running time.
6. Calculate effective priorities for H→L→X and verify that removing H→L removes the donation to both L and X.
7. Explain why cycles in the wait graph indicate a distinct **deadlock** issue and why priority inheritance cannot resolve it.
8. Compare Linux EEVDF's virtual deadline selection with the teaching MLFQ. Identify which assumptions and data structures differ [3].

**Continue:** [Concurrency and synchronization](/en/topics/concurrency-synchronization/) develops lock correctness, and [FCFS/Round Robin](/en/topics/cpu-scheduling-fcfs-round-robin/) establishes baseline scheduling metrics. Kernel context-switch tracing, deadline schedulers and realistic blocked-I/O workloads remain separate work.
