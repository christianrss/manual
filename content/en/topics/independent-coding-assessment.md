---
id: independent-coding-assessment
title: "Independent Coding Assessment: Coupon Routes and Parallel Task Rounds"
description: "Solve two original, unspoiled graph challenges with precise contracts, public fixtures, a grader and a transparent evaluation rubric."
category: algorithms
difficulty: advanced
updated: 2026-10-09
prerequisites: [graph-traversal, shortest-paths]
sources:
  - {title: "Amazon SDE II Online Assessment Preparation", url: "https://amazon.jobs/content/en/how-we-hire/sde-ii-oa-prep", kind: "official employer guidance"}
  - {title: "Python unittest documentation", url: "https://docs.python.org/3/library/unittest.html", kind: "official language documentation"}
---
A coding interview is not a reading-comprehension exercise: **knowing an algorithm after seeing its solution does not establish that you can derive it under an unfamiliar constraint**. This assessment contains two independent, original challenges whose reference implementations are intentionally not included. You receive a precise specification, baseline input/output cases, a working grader and review criteria. You must provide the algorithm, reasoning, complexity and robust edge handling yourself. These are not official or leaked Amazon questions. Amazon's public SDE II guidance emphasizes syntactically correct, scalable, maintainable, well-tested code over pseudocode [1].

## How to use this assessment

Clone the [Engineering Manual repository](https://github.com/christianrss/manual) and open [unsolved_drills.py](https://github.com/christianrss/manual/blob/main/examples/python/unsolved_drills.py). The file declares two functions and raises `NotImplementedError`. Implement each function without modifying the provided contracts. Run the [public grader](https://github.com/christianrss/manual/blob/main/examples/python/drill_grader.py) and then devise additional tests that the grader does **not** provide.

For a simulated assessment, reserve 90 minutes for both problems, including discussion, implementation and tests. That is a **practice target**, not a claim about an exact task allocation or guarantee of any employer's assessment. Record what you decided before looking at other references. Afterward, explain one invariant, a failure case and a time/space bound for each answer.

## Challenge A: a directed route with one discount

You are given a **directed graph** with nodes labeled 0 through n−1 and weighted edges (u,v,w), where w is a nonnegative integer. Start at node 0 and reach node n−1. You may apply a **single coupon at most once**, reducing the cost of exactly one traversed edge from w to floor(w/2). Alternatively, do not apply any coupon. Return the minimum total integer cost, or −1 if no directed route exists.

The graph may contain duplicate edges, self-loops, zero-weight edges and cycles. A path may repeat nodes, but with nonnegative edge weights there is no reason to benefit from a positive-cost cycle. The output for n=1 is zero without requiring a coupon. All inputs in the assessed contract have n≥1 and valid node IDs, so you need not invent error semantics outside those bounds. State how you prevent overflow in a fixed-width implementation.

**Example:** n=3, edges (0,1,9), (1,2,5), (0,2,30). The best result is **9**: take 0→1 at discounted cost floor(9/2)=4, then 1→2 at cost 5. Another option, discounting the direct edge, costs 15. The optimal cost is not necessarily obtained by discounting the globally largest edge because that edge may not belong to a useful route.

## Challenge B: minimal parallel deployment rounds

There are n build/deployment tasks numbered 0 through n−1 and directed prerequisite relations (u,v): task u must **finish in an earlier round** than task v. Within one round, any number of available tasks may run concurrently. Determine the minimum number of sequential rounds needed to finish all tasks. Return −1 if constraints form a directed cycle and completion is impossible.

Duplicate edges represent the same prerequisite and must not artificially increase a dependency count. Independent tasks can share round one; an empty task set requires zero rounds. The graph can have disconnected components, diamonds and a long dependency chain. This is not a CPU scheduling problem with limited machines: assume **unbounded workers and equal one-round task duration**. Changing those assumptions changes the problem.

**Example:** n=4 with prerequisites (0,2), (1,2), (2,3) requires **three rounds**: {0,1}, then {2}, then {3}. A cycle (0,1),(1,2),(2,0) produces −1. Explain why a cycle cannot be scheduled without violating an earlier-round prerequisite.

## Baseline cases you can run immediately

The grader supplies six published input/output cases for each problem, including disconnection, zero weights, singleton graphs, duplicate prerequisites and directed cycles. You can inspect or edit the fixtures, but changing expected results is **not** solving the task.

~~~python
from pathlib import Path
files = [
    Path("examples/python/unsolved_drills.py"),
    Path("examples/python/drill_grader.py"),
]
assert all(item.is_file() for item in files)
from itertools import chain
assert len(list(chain(range(6),range(6)))) == 12
~~~

After implementing both functions, run the following from the repository root. Until implementation, `NotImplementedError` is **intentional** and the grader will not pass; the website CI instead checks the grader's fixtures and its ability to reject incorrect behavior without providing a solution.

~~~text
python examples/python/drill_grader.py
~~~

The grader's public samples are necessary but insufficient. A hardcoded lookup table can pass them without meeting the algorithmic contract. Your own tests must cover changed graphs, adversarial layouts and asymptotically larger inputs [2].

## Required proof and complexity discussion

For Challenge A, identify what information about the **discount already used or still available** a search must retain. Explain how you avoid confusing two otherwise identical node positions that have different coupon availability. State why your computation terminates on cycles, which properties of edge weights you rely on, and your worst-case complexity in n nodes and m edges.

For Challenge B, identify the condition under which a task becomes eligible, how a task's earliest round follows from the rounds of its predecessors, and what constitutes an impossibility witness. Explain why duplicate edges do not distort the result. State how often you inspect each task and dependency.

Do not submit only a diagram or pseudocode: the actual assessment deliverable is a **function that executes**, plus reasoning precise enough for another engineer to review. Python's `unittest` can run new test cases and compare expected outputs; independent randomized checks need an oracle chosen independently of your optimized approach [2].

## Common traps to challenge yourself

| Mistake | Why it can fail | What your tests should expose |
| --- | --- | --- |
| Treat directed edges as bidirectional | Creates paths not present in the input | One-way disconnected graph |
| Always discount largest graph edge | Edge may not be on chosen path | Two alternative routes |
| Mutate input edges unexpectedly | Caller sees altered graph | Reuse same input for another test |
| Assume all tasks form one connected component | Omits independent work | Disconnected prerequisites |
| Count duplicate prerequisites twice | Task never becomes ready correctly | Repeated identical edge |
| Fail to detect cycles | Infinite loop or false rounds | Self-cycle and multi-node cycle |

## Evaluation rubric

Use a 100-point self-review: 20 for a precise contract and edge cases; 30 for correct implementation on unfamiliar tests; 20 for invariant/proof and termination; 15 for complexity and resource bounds; and 15 for code clarity and meaningful tests. This is **an independent learning rubric**, not an Amazon scoring scheme. An implementation that only passes the visible fixtures cannot earn a robust correctness claim.

## Exercises and verification

1. Implement both functions without changing their signatures or using precomputed answers from the fixture table.
2. Add a case with two parallel edges of different weights in Challenge A and justify the correct route.
3. Add a graph in which the direct route is expensive but discounting a longer multi-edge route wins.
4. Add a self-loop to Challenge B and verify that the implementation returns −1.
5. After passing the public grader, generate your own large input and explain measured runtime versus expected complexity.

**Related chapters:** [Shortest paths](/en/topics/shortest-paths/), [graph traversal](/en/topics/graph-traversal/), [algorithm workshop](/en/topics/algorithm-interview-workshop/) and [testing strategies](/en/topics/testing-strategies/) contain background techniques; they are not implementations of these challenge contracts.
