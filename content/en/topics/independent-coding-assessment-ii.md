---
id: independent-coding-assessment-ii
title: "Independent Coding Assessment II: Minimax Batches and Dynamic Islands"
description: "Solve two original unsolved challenges on monotone capacity search and incremental grid connectivity, with 18 public fixtures."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [binary-search, disjoint-set-union]
sources:
  - {title: "CP-Algorithms — Binary Search", url: "https://cp-algorithms.com/num_methods/binary_search.html", kind: "technical algorithm reference"}
  - {title: "CP-Algorithms — Disjoint Set Union", url: "https://cp-algorithms.com/data_structures/disjoint_set_union.html", kind: "technical algorithm reference"}
---
Unfamiliar coding tasks should be solved from the **input contract and invariants**, not by recalling a previously seen answer. This second independent workshop introduces two original challenges that exercise complementary SDE II fundamentals: a **minimax partition** problem involving a monotone feasibility decision, and a **dynamic grid connectivity** problem with repeated updates. Unlike the surrounding solved articles, the exercise source intentionally raises `NotImplementedError`; there is no published implementation to copy. These challenges are independently authored, not official or leaked employer assessments.

## Assessment instructions and constraints

The source [unsolved_drills_2.py](https://github.com/christianrss/manual/blob/main/examples/python/unsolved_drills_2.py) contains two function signatures and precise docstrings. Implement them without renaming functions or altering inputs. Run the [public grader](https://github.com/christianrss/manual/blob/main/examples/python/drill_grader_2.py), which checks **18 examples** across both tasks. The published examples are visible, so passing them alone cannot prove an algorithm handles new graphs, sequences or edge cases.

A suggested 90-minute practice session allocates time to clarify data boundaries, derive a candidate solution, write code, then review a counterexample and complexity. That is a learning convention, **not** an official hiring time limit. Keep notes of attempted approaches, failed tests, and how your implementation responds to constraints changing. A code review will assess whether your solution remains explainable under maintenance.

## Challenge A: minimum possible peak batch load

A pipeline receives tasks with **nonnegative integer loads** in a fixed order. It must divide them into **at most k nonempty contiguous batches**, preserving task order. The capacity needed for a partition is the maximum sum of loads in any batch. Return the **smallest capacity** across valid partitions. For an empty input, return zero. Assume k≥1 and arbitrary-size nonnegative integers, without floating-point rounding.

Example: loads [7,2,5,10,8], k=2. One valid partition [7,2,5] | [10,8] has sums 14 and 18, so capacity 18. A capacity of 17 cannot place the last two tasks together, nor can it fit the first three and their remaining tasks into one other batch. Thus the expected minimum is **18**.

A high-level hint: identify which capacity values are *feasible* and prove whether feasibility can change from true back to false as allowed capacity increases. A correct answer needs a proof that the chosen feasibility test never underestimates the batches required. You must derive and implement the details yourself [1].

## Changed constraints and tempting mistakes

If k exceeds the number of tasks, do not invent empty batches as mandatory work. The contract permits **at most** k, not exactly k, so the optimum may use fewer batches. If loads contain zeros, a zero capacity may be feasible; code assuming positive sums can fail. If tasks are [10] and k=10, capacity ten remains required.

Do not sort loads: doing so changes contiguous order and the problem being solved. Do not use floating-point accumulation for large integers when exact totals are part of the contract. When reporting complexity, separate the number of loads n, the batch limit k, and the numerical range of candidate capacities. A binary search over a numerical answer domain is only justified **after** proving monotonicity.

## Challenge B: islands after incremental activation

You have a rows × columns grid, initially with every cell inactive. Each action supplies a valid coordinate (r,c) and activates that cell permanently. After **every action**, return the number of connected components of active cells under **four-direction adjacency**: up, down, left, right. Diagonally adjacent cells are **not connected**. Repeated activation is a no-op: it must not create another component or decrement a count incorrectly.

Example: 3×3 grid, actions [(0,0),(0,1),(1,2),(1,1),(0,0)]. The component counts are **[1,1,2,1,1]**. Activating (1,1) connects the component containing (0,0),(0,1) to the separate cell (1,2), reducing two components to one. The final action repeats (0,0), so the count stays one.

A straightforward solution can recompute connected components from scratch after every action, but assess its performance when the grid and action count become large. A more efficient strategy maintains component identities under activation and merges active neighbors; derive the invariants and account for duplicate actions before committing to a data structure [2].

## Counterexamples that a shallow implementation misses

Diagonal cells at (0,0) and (1,1) remain separate until a valid orthogonal bridge appears. A newly activated cell can connect **more than two existing components**, but each *distinct* neighbor component should be merged only once. Multiple active neighbors may already belong to the same component: decrementing once per neighbor rather than once per successful component merge produces negative or incorrect counts.

Do not allocate rows×columns memory blindly if the full grid is enormous but only a few cells are activated. State the input bounds you assume and compare dense versus sparse representations. An empty action list returns an empty list even if grid dimensions are nonzero. For a grid with a zero dimension, the contract allows no valid activation coordinates.

## Verification discipline without published solutions

The grader includes cases for empty input, duplicate actions, diagonal-only adjacency, a bridge across several components, zero loads, one large item, more batches than tasks, and a sequence where the last activation joins **four components**. The reference implementation remains deliberately absent; the CI only confirms that the starter functions are unsolved and the public grader detects trivial wrong implementations.

~~~python
from pathlib import Path
examples = Path("examples/python")
assert (examples / "unsolved_drills_2.py").is_file()
assert (examples / "drill_grader_2.py").is_file()
assert len([1, 1, 2, 1, 1]) == 5
~~~

Add your own independent tests after passing public examples. For small n, a brute-force enumeration of partitions can serve as an oracle for the first challenge. For tiny grids, recomputing connected components after each activation provides an oracle independent from any optimized incremental connectivity structure. Restrict oracle sizes to prevent exponential or repeated-search costs from dominating the suite.

## Evaluation and communication rubric

| Dimension | Required evidence | Points |
| --- | --- | ---: |
| Contract and edge cases | Explicit assumptions and adversarial inputs | 20 |
| Correct executable implementation | Pass public and newly created tests | 30 |
| Correctness reasoning | Invariants and termination arguments | 20 |
| Resource analysis | Time/space with clear input parameters | 15 |
| Maintainability | Clear names, no surprising mutation, useful tests | 15 |

This 100-point rubric is editorial, not an employer grading model. Published fixture cases may be memorized, so an evaluator should supply **additional unseen inputs** when scoring a candidate. Having a working harness does not mean either function has been solved.

## Exercises and verification

1. Implement both functions without changing their signatures or modifying the expected fixture answers.
2. Construct a capacity example where sorting loads appears to help but changes which partitions are legal.
3. Demonstrate why a batch feasibility test must count required contiguous groups rather than average total load alone.
4. Build an island sequence that joins four distinct neighbor components in one activation.
5. Explain how memory requirements differ between a dense Boolean grid and a sparse map keyed by activated coordinates.

**Related chapters:** [Binary search on answers](/en/topics/binary-search/), [Disjoint-set union](/en/topics/disjoint-set-union/), [Graph traversal](/en/topics/graph-traversal/), and [Independent assessment I](/en/topics/independent-coding-assessment/) provide foundational material without implementing these tasks.
