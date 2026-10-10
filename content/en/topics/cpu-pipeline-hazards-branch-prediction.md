---
id: cpu-pipeline-hazards-branch-prediction
title: "CPU Pipelines: Data Hazards, Forwarding and Branch Prediction"
description: "Derive instruction latency, throughput, stalls, load-use dependencies and two-bit branch prediction with independently tested pipeline models."
category: computer-architecture
difficulty: intermediate
updated: 2026-10-10
prerequisites: [machine-representation-isa-cache]
sources:
  - {title: "MIT 6.004 — Pipelining the Beta (annotated slides)", url: "https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/pages/c15/c15s1/", kind: "university teaching material"}
  - {title: "MIT 6.5900 — Computer System Architecture lecture notes", url: "https://csg.csail.mit.edu/6.5900/lecnotes.html", kind: "university course materials"}
  - {title: "Intel — 64 and IA-32 Optimization Manual", url: "https://www.intel.com/content/www/us/en/developer/articles/technical/intel64-and-ia32-architectures-optimization.html", kind: "official vendor optimization manuals"}
---
Pipelining overlaps distinct phases of multiple instructions. Its primary goal is higher **throughput**, not necessarily lower **latency** for any single instruction. The CPU's instruction set architecture (ISA) states which architectural results must be observable; pipelining, data forwarding, stalling, branch prediction and speculative execution are implementation techniques that must preserve those results. A fast-looking schedule that reads the wrong register value is incorrect, irrespective of its cycles-per-instruction figure [1].

This chapter builds on [machine representation, ISA and cache mapping](/en/topics/machine-representation-isa-cache/). We derive a deliberately narrow five-stage, single-issue teaching model, compare its schedules with independently constructed timing constraints, then evaluate a two-bit branch predictor. It does **not** claim to model a contemporary Intel/AMD processor, an actual RISC-V implementation, memory stalls, cache coherence, precise interrupts or out-of-order issue. Those require additional contracts and experiments [1][2].

## Five stages: distinguish instruction latency from throughput

In the common instructional pipeline, **IF** fetches an instruction, **ID** decodes and reads registers, **EX** executes its arithmetic or computes an address, **MEM** performs the data-memory phase, and **WB** writes the architectural result. We use one cycle per stage, ordered IF→ID→EX→MEM→WB. Our instruction enters IF at issue cycle `s`, and occupies those stages at `s, s+1, s+2, s+3, s+4` respectively.

| Issue | Cycle 0 | Cycle 1 | Cycle 2 | Cycle 3 | Cycle 4 | Cycle 5 | Cycle 6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Instruction A | IF | ID | EX | MEM | WB | | |
| Instruction B | | IF | ID | EX | MEM | WB | |
| Instruction C | | | IF | ID | EX | MEM | WB |

A standalone instruction completes after **five modeled cycles**. Without hazards and with a single new instruction per cycle, `n` instructions complete in `n+4` cycles. Therefore `CPI=(n+4)/n`, tending toward **one instruction per cycle**, while each instruction still occupies five stages [1]. The `+4` term represents filling/draining this particular pipeline; it is not a fixed real-hardware penalty.

Reducing the amount of combinational work per stage can shorten the clock period and improve time-based throughput, but stage register overhead and imbalanced stages limit that gain. A nonpipelined design with a different clock period cannot be compared using CPI alone. Superscalar issue, nonunit stage durations and out-of-order execution change the model entirely [2][3].

## Hazards: structural, data and control conflicts

A **structural hazard** arises when two operations demand one nonduplicated resource in the same cycle, such as a single port serving instruction fetch and data access. Our model assumes independent instruction/data resources, so it has **no structural hazard**. This is an assumption, not proof that memory ports are unlimited.

A **data hazard** occurs when an instruction needs a value not yet produced by an earlier instruction. The key case in an in-order pipeline is **RAW (read after write)**. By contrast, WAR and WAW are ordering hazards that matter particularly when instructions can execute or finish out of order; this model commits in program order, so it does not separately schedule those conflicts. **Control hazards** come from branches or exceptions that redirect execution. Speculating on the wrong path requires squashing its architectural effects [1].

Stalling stops progress of dependent stages; forwarding (bypassing) supplies the result from a pipeline stage before the normal register-file writeback. Neither changes the program's required result, but both change cycle schedules and hardware complexity. A load-use dependency can still need a stall because data arrives **at the end of MEM**, too late for the next instruction's EX [1].

## Define cycle timing before claiming a stall count

Assume the consumer reads from the register file at the **start of ID** and consumes forwarded operands at the **start of EX**. ALU results appear at the **end of EX**; load data appears at the **end of MEM**; normal register-file writes take effect at the **end of WB**. Values produced during a cycle can only be read *at the start of a later cycle*.

Under these explicit conventions, if producer issue time is `p` and consumer issue is `c`:

| Producer and mode | Required consumer issue | For adjacent dependent instructions |
| --- | --- | --- |
| No forwarding, ALU or load | `c >= p+4` | 3 empty issue slots |
| ALU with forwarding | `c >= p+1` | No bubble |
| Load with forwarding | `c >= p+2` | 1 empty issue slot |

Derive the first row: producer WB completes at end of `p+4`. Consumer ID begins at `c+1`. To read the new value at the start of a later cycle, `c+1 > p+4`, hence `c >= p+4`. ALU forwarding similarly needs consumer EX at `c+2 > p+2`; load forwarding requires `c+2 > p+3`. Other teaching designs allow same-cycle WB/write and ID/read; that changes the first row's stall count. **Do not mix timing conventions** [1].

## Executable issue scheduler with RAW dependencies

Each artificial instruction is `(kind, destination, sources)`: `ALU` produces a register result after EX; `LOAD` produces one after MEM. For scheduling, these are metadata records, not executable opcodes or real instruction encodings. We deliberately assume every entry produces one named destination, and source tuples name previously or initially available registers. No memory aliasing, speculation, exceptions, stores or caches are modeled.

The scheduler records the **latest earlier writer** of each source register. Since issue and completion stay in order, that writer determines the relevant RAW dependency. It chooses the earliest single-issue cycle satisfying all input-readiness conditions. The function validates all records before scheduling and returns an immutable tuple without modifying external state.

```python
def issue_cycles(program, forwarding=True):
    if type(forwarding) is not bool:
        raise ValueError("forwarding must be boolean")
    validated = []
    for operation in program:
        if (not isinstance(operation, tuple) or len(operation) != 3):
            raise ValueError("expected (kind, destination, sources)")
        kind, destination, sources = operation
        if (kind not in ("ALU", "LOAD")
                or not isinstance(destination, str) or not destination
                or not isinstance(sources, tuple)
                or any(not isinstance(src, str) or not src for src in sources)):
            raise ValueError("invalid teaching instruction")
        validated.append((kind, destination, sources))

    writers = {}
    issued = []
    for kind, destination, sources in validated:
        earliest = (issued[-1] + 1) if issued else 0
        for source in sources:
            if source in writers:
                producer_issue, producer_kind = writers[source]
                separation = (4 if not forwarding
                              else 2 if producer_kind == "LOAD" else 1)
                earliest = max(earliest, producer_issue + separation)
        issued.append(earliest)
        writers[destination] = (earliest, kind)
    return tuple(issued)

dependent = [
    ("LOAD", "r1", ()),
    ("ALU", "r2", ("r1",)),
    ("ALU", "r3", ("r2",)),
]
assert issue_cycles(dependent, forwarding=True) == (0, 2, 3)
assert issue_cycles(dependent, forwarding=False) == (0, 4, 8)
assert issue_cycles([("ALU", "a", ()), ("ALU", "b", ())]) == (0, 1)

def modeled_cycles(issue_times):
    return 0 if not issue_times else issue_times[-1] + 5

assert modeled_cycles(issue_cycles(dependent, True)) == 8
assert modeled_cycles(issue_cycles(dependent, False)) == 13
```

For the three-instruction example, forwarding yields issue cycles `(0,2,3)`: the consumer of the load waits one issue slot, but the following ALU-to-ALU dependency forwards without another stall. Without forwarding, `(0,4,8)` contains six empty issue slots. The total modeled times are 8 and 13 cycles respectively, counting the final four pipeline stages after the last issue. These numbers are **properties of this model**, not benchmark results for a hardware processor.

A correctness invariant is: after scheduling the first `k` instructions, their issue times are strictly increasing and every scheduled source's most recent earlier writer has completed the stage that supplies the needed value before consumption. The next instruction chooses the smallest cycle that preserves all those inequalities. For a finite, validated program the loop terminates; time is proportional to the number of source operands plus instruction records, with dictionary expected-constant lookups and bounded register names. Space is proportional to instruction count and distinct destination registers.

## Branch prediction: a two-bit saturating counter

A conditional branch creates a control dependency: fetching from the correct next address may require knowing its outcome. A predictor guesses so that the front end can continue. If the guess is wrong, speculative wrong-path work must be discarded, with an implementation-dependent latency and throughput penalty. Prediction does not give permission to commit wrong-path results [1][3].

A classic **two-bit saturating counter** has four states: 0=strongly not taken, 1=weakly not taken, 2=weakly taken, 3=strongly taken. Predict *taken* for states 2 or 3, otherwise *not taken*. Each observed taken outcome increments the counter toward 3; each not-taken outcome decrements toward 0. This “hysteresis” avoids reversing a strong preference after a single contrary outcome. A single counter is **only a teaching predictor**, not an actual branch target buffer, history predictor or modern hardware algorithm [1].

```python
class TwoBitPredictor:
    def __init__(self, state=1):
        if type(state) is not int or state not in (0, 1, 2, 3):
            raise ValueError("state must be a two-bit integer")
        self.state = state

    def predict(self):
        return self.state >= 2

    def observe(self, taken):
        if type(taken) is not bool:
            raise ValueError("branch outcome must be boolean")
        predicted = self.predict()
        self.state = min(3, self.state + 1) if taken else max(0, self.state - 1)
        return predicted

counter = TwoBitPredictor(1)
outcomes = (True, True, False, False, False)
predictions = tuple(counter.observe(outcome) for outcome in outcomes)
assert predictions == (False, True, True, True, False)
assert sum(a != b for a, b in zip(predictions, outcomes)) == 3
assert counter.state == 0
```

The trace makes three mistakes, including two successive incorrect predictions while the state moves down from strongly taken. The transition invariant is `0 <= state <= 3`; state remains an integer after every valid observation. We validate `bool` outcomes rather than quietly accept integers `0` and `1`, to keep the event contract explicit. Prediction is computed from **pre-update** state; testing only the final state would miss an implementation that returns the prediction **after** learning the outcome.

## CPI, branch costs and the danger of multiplying guesses

For a simplified non-overlapping penalty model, we may write

`cycles ≈ instructions + 4 + data_stall_slots + mispredictions × penalty_cycles`.

This is an **additive analytical approximation**, not a simulator of speculative pipeline stages. It assumes one issue slot per cycle, full squashing costs of a fixed size, and no overlap among branch penalties, data stalls, cache misses or independent work. A trace with 3 misses and an *assumed* 2-cycle recovery penalty adds 6 modeled cycles, **not** evidence that a given processor loses two cycles per miss.

Practical performance counters and microbenchmarks are needed to evaluate an actual processor, and even measurements require controlling environment, data, compiler, instruction mix and warmup. Intel's optimization documentation discusses branch prediction and speculation as performance considerations, but no single miss cost should be copied across microarchitectures [3]. Likewise, cache conflict misses are **not** branch mispredictions; the [previous cache model](/en/topics/machine-representation-isa-cache/) describes a separate source of delay.

## Instruction-level parallelism, memory ordering and precise state

Independent instructions may overlap safely, but a data-dependent chain has a critical path. Compilers can sometimes reorder independent computations to hide load-use bubbles provided **observable behavior is preserved**. Hardware may forward values, speculate, reorder execution or rename registers to remove certain false dependencies. However, renaming does not remove genuine RAW dependence, and an instruction cannot architecturally observe a value before its producer has logically supplied it [2].

Correct handling of exceptions is more subtle than RAW scheduling: a processor must ensure that results exposed to software correspond to a well-defined architectural execution state. Modern out-of-order processors may execute instructions speculatively but retire in an order consistent with their ISA contract. Our scheduler has **no reorder buffer, exception handling, branch targets, memory dependence tracking or speculative architectural state**; presenting its schedule as a real CPU trace would be misleading [1][2].

## Exercises and verification

1. Draw a five-stage table for 3 independent instructions. Explain why each has latency of five stages while the steady-state throughput can be one instruction per cycle.
2. Re-derive the RAW timing inequalities for ALU and load producers. Change the WB/ID convention to “write first, read later in the same cycle” and calculate the difference in stall count.
3. Hand-schedule `LOAD r1; ALU r2←r1; ALU r3←r2` with and without forwarding; compare against the executable example.
4. Insert an independent ALU operation between load and use. Determine when it fully hides the load-use bubble; distinguish instruction *order* from instruction *reordering*.
5. Give a program where two sources of the same ALU operation depend on **different earlier writers**. Verify that the latest required issue cycle wins.
6. Enumerate all four two-bit predictor states and both possible outcomes; draw the transition table and verify the predicted direction is taken from the **old** state.
7. Identify which statements in this chapter concern **architectural correctness**, which concern **microarchitecture**, and which are only analytical assumptions.
8. Describe a wrong-path store after a mispredicted branch. Explain why a predictor that updates its state correctly is insufficient to guarantee architectural correctness.

**Next:** [Virtual memory and system calls](/en/topics/processes-virtual-memory/) covers a distinct translation/protection layer, and [concurrency](/en/topics/concurrency-synchronization/) introduces thread interleavings. Cache coherence, multi-core memory ordering, actual RISC-V execution timing and CPU performance-counter labs remain future independent topics [1][2][3].
