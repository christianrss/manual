---
id: greedy-intervals
title: "Greedy Interval Scheduling: Exchange Proofs and Counterexamples"
description: "Prove earliest-finish interval scheduling, test boundary cases and distinguish greedy cardinality from weighted optimization."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [sorting-algorithms, complexity-analysis]
sources:
  - {title: "MIT 6.046J — Interval Scheduling", url: "https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/resources/lecture-1-course-overview-interval-scheduling/", kind: "university lecture"}
---
A greedy algorithm makes a choice and commits to it without exploring every possible future. A locally promising step is **not sufficient** to establish optimality. The crucial proof obligation is: can at least one optimal solution be rearranged to contain the greedy decision? Interval scheduling is a particularly clear example because its earliest-finish strategy has an exchange proof, while several attractive alternatives fail [1].

## Problem, constraints and endpoint semantics

We are given n jobs, represented by **half-open** time intervals [start,finish), where start is strictly less than finish. Choose the largest possible number of non-overlapping jobs for one machine. A job can follow another exactly when its start is greater than or equal to the previous finish. We assume identical value per job, no setup time, and no interruption once selected.

Thus [1,3) and [3,5) are compatible: the point 3 belongs to the second interval but not the first. With closed intervals, touching could count as conflict instead. Agreeing on endpoint behavior is part of the input contract, not an implementation detail. Maximizing the number of jobs is also different from maximizing total occupied time or revenue.

## The earliest-finish algorithm

Sort by **increasing finish time**. Select the first job, then choose the next job whose start is at or after the last selected finish; continue until the list is exhausted. The intuition is that finishing early leaves the greatest possible remaining time, but intuition must be backed by the formal argument below [1].

For jobs A=[0,5), B=[1,2), C=[2,3), D=[3,4), E=[4,5), choosing earliest start yields only A. Earliest finish selects B,C,D,E: four jobs. Choosing the **shortest duration** instead is not generally optimal either; a tiny job late in the day can block a sequence of many earlier jobs.

![Interval scheduling favors compatible jobs that finish soon.](/diagrams/greedy-interval-scheduling.svg)

## Implementation, edge cases and complexity

~~~python
def schedule(jobs):
    for start, finish in jobs:
        if start >= finish:
            raise ValueError("require start < finish")
    ordered = sorted(jobs, key=lambda p: (p[1], p[0]))
    chosen = []
    last_finish = None
    for start, finish in ordered:
        if last_finish is None or start >= last_finish:
            chosen.append((start, finish))
            last_finish = finish
    return chosen

jobs = [(0,5),(1,2),(2,3),(3,4),(4,5)]
assert schedule(jobs) == [(1,2),(2,3),(3,4),(4,5)]
assert schedule([]) == []
assert schedule([(1,3),(3,6)]) == [(1,3),(3,6)]
assert len(schedule([(0,4),(1,3),(2,5)])) == 1
try:
    schedule([(2,2)])
    assert False
except ValueError:
    pass
~~~

The sort takes O(n log n) comparisons and the forward scan O(n), giving total O(n log n) time. The sorted copy and output take O(n) auxiliary space. If jobs arrive already ordered by finish, the selection pass alone needs O(n) time. The program rejects zero-length intervals so ties cannot silently change the model's meaning.

## Proof using an exchange argument

Let g be a compatible job with the earliest finish among remaining jobs. Take any optimal schedule whose first job is o. By the greedy rule, finish(g) ≤ finish(o). Replace o with g: every later job in the optimal schedule starts no earlier than finish(o), therefore also no earlier than finish(g). The replacement maintains feasibility and leaves the number of chosen jobs unchanged. Hence **there exists an optimal schedule beginning with g**.

Now remove all jobs that start before finish(g). The remaining problem has the same constraints, only a smaller feasible set. Repeating the exchange argument proves by induction that every greedy step can be extended to a maximum-cardinality schedule. It does **not** prove g belongs to every optimum, nor that the chosen jobs have the highest profit [1].

The structural rule is called the *greedy-choice property*: some optimal solution contains the locally selected element. If an objective or constraint invalidates the replacement argument, this greedy algorithm no longer has a correctness proof.

## Weighted scheduling: a counterexample

Suppose X=[0,2) pays 1, Y=[0,3) pays 100 and Z=[2,4) pays 1. The earliest-finish algorithm picks X then Z for two jobs, profit 2. The optimal weighted schedule picks only Y, profit 100. Replacing Y with X retains the number of jobs but destroys profit, exactly where the exchange argument stops working.

Weighted interval scheduling is usually modeled with dynamic programming. Sort jobs by finish, define p(i) as the latest earlier job finishing before i starts, and compute OPT(i)=max(OPT(i−1), weight(i)+OPT(p(i))). The first alternative skips i and the second includes it. Binary search for predecessors yields O(n log n) time under ordinary comparison assumptions. This is not the same objective as the unweighted problem [1].

## Union of intervals is another operation

A frequent sequence question asks for the **union** of overlapping time intervals rather than a compatible subset. Sort by start. Merge a new interval into the last output interval if it begins **strictly before** the output's end; extend the end to their maximum. Two touching half-open intervals can remain separate if the contract combines only overlapping ranges.

~~~python
def merge_overlap(intervals):
    for start, finish in intervals:
        if start >= finish:
            raise ValueError("require start < finish")
    out = []
    for start, finish in sorted(intervals):
        if out and start < out[-1][1]:
            out[-1] = (out[-1][0], max(finish, out[-1][1]))
        else:
            out.append((start, finish))
    return out

assert merge_overlap([(1,4),(2,6),(8,9)]) == [(1,6),(8,9)]
assert merge_overlap([(1,3),(3,5)]) == [(1,3),(3,5)]
assert merge_overlap([]) == []
~~~

The invariant is that the output describes precisely the union of processed intervals and consecutive output segments do not overlap. Merge can create a segment that was not an original job, so it cannot substitute for maximum-cardinality scheduling.

## Recognizing a false greedy rule

| Task | Suitable strategy | Critical assumption |
| --- | --- | --- |
| Most compatible jobs | Earliest finish | Equal unit value |
| Most weighted profit | Dynamic programming | Different objective |
| Union of time coverage | Sort and merge | Results can be new intervals |
| Minimum number of rooms | Heap or overlap sweep | Must accept every job |

Beware algorithms that sort by earliest start, minimum duration, highest profit, or smallest overlap without an exchange proof. A counterexample with only three jobs is often enough to refute a proposed universal rule. Passing a few tests does not establish correctness; an exchange proof does.

## Exercises and verification

1. Trace A through E and explain why the greedy schedule accepts four jobs.
2. Show explicitly why finish(g) ≤ finish(o) guarantees feasibility after exchanging the first optimal choice.
3. Compare profits 2 and 100 in the weighted counterexample and identify the broken assumption.
4. Explain precisely why [1,3) and [3,5) can share one machine.
5. Implement a brute-force oracle for at most eight jobs, checking each subset's compatibility, and compare its optimum with schedule(jobs).

**Related chapters:** [Sorting](/en/topics/sorting-algorithms/) establishes prerequisite ordering; [dynamic programming](/en/topics/dynamic-programming/) handles weighted variants.
