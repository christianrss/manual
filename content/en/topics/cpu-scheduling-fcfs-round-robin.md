---
id: cpu-scheduling-fcfs-round-robin
title: "CPU Scheduling: FCFS, Round Robin, Response and Fairness"
description: "Derive FCFS and Round Robin scheduling, preemption, arrival ties, turnaround and waiting with executable models and independent tick oracles."
category: operating-systems
difficulty: intermediate
updated: 2026-10-10
prerequisites: [processes-virtual-memory]
sources:
  - {title: "Operating Systems: Three Easy Pieces — Scheduling", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/", kind: "university textbook"}
  - {title: "MIT xv6 book — Scheduling", url: "https://mit-pdos.github.io/xv6-riscv-book/sched.html", kind: "university teaching OS reference"}
  - {title: "Python collections.deque", url: "https://docs.python.org/3/library/collections.html#collections.deque", kind: "official library reference"}
---
The CPU executes instructions, while the operating system determines **which runnable thread or process gets CPU time**. A scheduling policy allocates that time in competition with goals of responsiveness, throughput and fairness. This is distinct from CPU pipelining, which overlaps parts of *machine instructions*. The [processes and virtual memory](/en/topics/processes-virtual-memory/) chapter introduces process state and privilege; this chapter derives a narrow model of execution order [1][2].

The examples are **single-CPU, deterministic teaching models**, not xv6 kernel code or real scheduling benchmarks. In particular, they exclude I/O, locks, interrupts, context-switch costs, multicore execution and priorities. Stating these omissions matters: a model with no blocking cannot establish behavior when a production task waits on disk or a network response.

## Runnable, running, blocked and dispatch

A task may be *runnable* (eligible), *running* (currently on the CPU), or *blocked* (waiting for an event). A scheduler selects from the runnable set. A dispatcher/context switch implements the decision by saving and restoring CPU execution state. The scheduler cannot merely choose a blocked task and make its requested I/O finish; the readiness condition must change first.

**Preemption** removes CPU access before the current CPU burst completes. A timer can trigger a quantum expiration, but timing alone does not implement safe switching. The real xv6 example requires careful coordination of process locks, execution context and the scheduler stack [2]. Fairly choosing a task does not make unsynchronized operations on shared memory safe.

## A precise time and queue model

We accept a finite sequence of \`Job(name, arrival, burst)\` records. Arrival is a nonnegative integer; CPU burst is a strictly positive integer. Names are unique, nonempty and free of surrounding whitespace. A Python \`bool\` is not accepted as an integer scheduling parameter. There is exactly **one processor** and no blocking or additional bursts.

A deterministic tie policy completes the specification: simultaneous arrivals enter in original input order. **FCFS** runs the earliest arrival to completion, never preempting. **Round Robin** runs the front of the ready queue for \`min(quantum, remaining)\`, then appends unfinished work to the back. When a new job arrives **exactly** at a quantum boundary, the new arrival is appended **before** the old unfinished task returns. Other reasonable tie conventions produce different traces; those differences must be documented, not dismissed as nondeterministic bugs [1].

The model does not count an idle gap as execution. It also assumes **zero switch overhead**, even when adjacent quanta belong to the same task. Thus all reported times use abstract units of CPU service, not milliseconds measured on a real host.

## Implement FCFS and Round Robin with state invariants

FCFS sorts arrivals by \`(time, input_index)\`, advances the clock across idle intervals and executes each job once. Round Robin maintains \`remaining\`, a \`deque\` of runnable identifiers, and a cursor over sorted arrivals. \`deque\` supports efficiently appending at the end and popping from the front [3].

~~~python
from collections import deque
from dataclasses import dataclass

@dataclass(frozen=True)
class Job:
    name: str
    arrival: int
    burst: int

@dataclass(frozen=True)
class Slice:
    name: str
    start: int
    end: int

def validate_jobs(jobs):
    items = tuple(jobs)
    seen = set()
    for j in items:
        if not isinstance(j, Job):
            raise ValueError("expected Job")
        if not isinstance(j.name, str) or not j.name.strip() or j.name != j.name.strip() or j.name in seen:
            raise ValueError("duplicate or invalid name")
        if type(j.arrival) is not int or j.arrival < 0 or type(j.burst) is not int or j.burst <= 0:
            raise ValueError("arrival >= 0 and burst > 0 must be integers")
        seen.add(j.name)
    return items

def fcfs(jobs):
    items = validate_jobs(jobs)
    order = sorted(enumerate(items), key=lambda pair: (pair[1].arrival, pair[0]))
    time = 0
    trace = []
    for _, job in order:
        time = max(time, job.arrival)
        trace.append(Slice(job.name, time, time + job.burst))
        time += job.burst
    return tuple(trace)

def round_robin(jobs, quantum):
    items = validate_jobs(jobs)
    if type(quantum) is not int or quantum <= 0:
        raise ValueError("positive integer quantum required")
    order = sorted(enumerate(items), key=lambda pair: (pair[1].arrival, pair[0]))
    remaining = {j.name: j.burst for j in items}
    ready = deque()
    result = []
    time = cursor = finished = 0
    while finished < len(items):
        if not ready:
            time = max(time, order[cursor][1].arrival)
            while cursor < len(order) and order[cursor][1].arrival <= time:
                ready.append(order[cursor][1].name)
                cursor += 1
        name = ready.popleft()
        duration = min(quantum, remaining[name])
        result.append(Slice(name, time, time + duration))
        time += duration
        remaining[name] -= duration
        # Arrivals at a quantum boundary precede requeue of the old task.
        while cursor < len(order) and order[cursor][1].arrival <= time:
            ready.append(order[cursor][1].name)
            cursor += 1
        if remaining[name]:
            ready.append(name)
        else:
            finished += 1
    return tuple(result)

jobs = (Job("A", 0, 5), Job("B", 1, 2), Job("C", 3, 1))
assert fcfs(jobs) == (Slice("A", 0, 5), Slice("B", 5, 7), Slice("C", 7, 8))
assert round_robin(jobs, 2) == (
    Slice("A", 0, 2), Slice("B", 2, 4), Slice("A", 4, 6),
    Slice("C", 6, 7), Slice("A", 7, 8))
assert fcfs(()) == round_robin((), 1) == ()
assert round_robin((Job("late", 5, 2),), 1) == (
    Slice("late", 5, 6), Slice("late", 6, 7))
~~~

**Round Robin invariant:** before removing the next task, the ready queue contains arrived, unfinished tasks not currently running, each once, in admission order. For every task, \`remaining + sum(executed_slice_durations) = original_burst\`. A positive execution slice reduces total remaining work, so a finite collection of finite positive bursts terminates. The arrival cursor is monotone and never revisits the same record.

The example produces FCFS slices A(0–5), B(5–7), C(7–8). With quantum 2, Round Robin produces A(0–2), B(2–4), A(4–6), C(6–7), A(7–8). C is waiting at time 4, yet A precedes it because A was already enqueued; C receives CPU before A's final quantum at time 6. A one-job trace may contain consecutive slices for the same job without implying actual context switching.

For \`n\` jobs, sorting costs \`O(n log n)\`; each arrival is processed once. If \`s=sum(ceil(burst_i/quantum))\` denotes the maximum number of slices, the event-driven Round Robin computation costs \`O(n log n + s)\` time and \`O(n+s)\` space including the returned trace, under bounded identifier lengths and average constant-time dictionary operations. This is the simulator's cost; **total simulated CPU service** is \`sum(burst_i)\`, a different quantity.

## Response, waiting and turnaround are different metrics

For job \`i\`, let \`a_i\` be arrival, \`f_i\` first dispatch, \`c_i\` completion and \`b_i\` total CPU burst. Define:

- **Response** \`= f_i - a_i\`: delay until the first CPU service.
- **Turnaround** \`= c_i - a_i\`: elapsed time from arrival to completion.
- **Waiting** \`= turnaround - b_i\`: time not running **under this no-I/O model**.

When a real job blocks on I/O, \`turnaround - CPU\` also contains blocked time, and cannot directly be called ready-queue waiting. Likewise first CPU dispatch is not the same as first byte of a web response. A metric must say which phenomenon it measures [1].

~~~python
def scheduling_metrics(jobs, trace):
    items = validate_jobs(jobs)
    first, finish = {}, {}
    used = {job.name: 0 for job in items}
    for segment in trace:
        if segment.name not in used or segment.end <= segment.start:
            raise ValueError("invalid slice")
        first.setdefault(segment.name, segment.start)
        finish[segment.name] = segment.end
        used[segment.name] += segment.end - segment.start
    if any(used[j.name] != j.burst for j in items):
        raise ValueError("trace lacks requested CPU service")
    return {
        j.name: (first[j.name] - j.arrival,
                 finish[j.name] - j.arrival - j.burst,
                 finish[j.name] - j.arrival)
        for j in items
    }

assert scheduling_metrics(jobs, fcfs(jobs)) == {
    "A": (0, 0, 5), "B": (4, 4, 6), "C": (4, 4, 5)}
assert scheduling_metrics(jobs, round_robin(jobs, 2)) == {
    "A": (0, 3, 8), "B": (1, 1, 3), "C": (3, 3, 4)}
~~~

These examples show why a shorter first response does not guarantee shorter turnaround. Under RR, B first runs just one time unit after arrival, but A finishes later than under FCFS. The helper above validates total executed service, but alone does **not** independently prove that a trace obeys arrivals or prevents CPU overlap. Dedicated tests compare it with a separate tick-by-tick reference.

## Convoy effect and the shortest-job alternatives

Consider three simultaneously ready tasks with CPU bursts A=6, B=1, C=1. FCFS in A–B–C order completes at 6, 7, 8, for average turnaround \`(6+7+8)/3 = 7\`; responses are 0, 6, 7. RR with quantum 1 gives B and C an earlier first dispatch, illustrating a **convoy** under FCFS. The long job A, conversely, will complete later in that rotation [1].

**Shortest Job First** (SJF) chooses the shortest known runnable burst; **Shortest Remaining Time First** (SRTF) is a preemptive variant. They can improve average turnaround on selected workloads, but require knowledge or estimates of bursts. A continuing stream of short tasks can starve a longer task when selection always prefers the shorter one. No scheduling policy should be praised by a single mean without stating workload and fairness conditions.

## Starvation, time quantum and switching costs

A finite set of ready, CPU-bound tasks with finite bursts, finite positive quantum and fair rotation eventually receives service under this RR model. That fact does **not** guarantee a universal upper bound under unbounded arrivals, blocked tasks, other priority classes or broken scheduler invariants. Starvation must be analyzed under explicit workload and admission assumptions.

Very small quanta improve first-response opportunities but can cause frequent expensive context switches. Very large quanta approach FCFS behavior when each burst fits a single slice, reducing switching but potentially worsening interactivity. Cache/TLB effects, scheduler overhead and priorities are not charged in this simulator. There is **no universally optimal quantum** independent of workload and hardware [1][2].

## What the simulator does not implement

No interrupt controller, kernel timer, context saving, virtual-memory switch, scheduler lock, per-CPU run queue, priority inheritance, deadline guarantee or multicore migration is present. Code that passes these tests has not implemented an operating-system scheduler. Nor does it establish starvation freedom for arbitrary future arrivals or responsiveness under blocking.

Testing quality depends on **independent expectations**. The accompanying unit test advances a separate reference model **one time unit at a time**, rather than reusing the chapter's event-driven queue algorithm. It checks idle periods, simultaneous arrivals, quantum-boundary tie semantics, resource conservation and exact job metrics. These are finite exhaustive test domains, not formal proofs or independent hardware measurements.

## Exercises and verification

1. Derive the five RR slices and response, waiting and turnaround of A(0,5), B(1,2), C(3,1) by hand before running Python.
2. Change the quantum to 1 and 10. Which arrivals enter the queue first? Under what conditions does RR match FCFS?
3. Insert jobs arriving exactly when a quantum ends. Reverse the tie convention and enumerate the differences.
4. Derive the first-response times for the convoy example A=6, B=1, C=1 under FCFS and quantum-1 RR.
5. Insert idle time before the first arrival, then explain why the CPU is neither waiting on a ready task nor doing useful work.
6. Add blocking states and derive why the previous waiting-time formula no longer measures only runnable-queue waiting.
7. Model a nonzero context-switch cost. Decide whether adjacent quanta of the same job incur the same cost as switching between jobs.
8. Construct an adversarial arrival stream for SJF and specify an aging or minimum-service invariant that would rule out starvation.

**Continue:** [MLFQ and priority inheritance](/en/topics/mlfq-priority-inheritance/) builds on this chapter and concurrency; [concurrency and synchronization](/en/topics/concurrency-synchronization/) explores what scheduling interleavings do to shared invariants; [processes and virtual memory](/en/topics/processes-virtual-memory/) explains protection and kernel boundaries. Real-time guarantees, I/O scheduling, MLFQ and multicore load balancing require distinct treatment [1][2][3].
