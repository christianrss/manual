---
id: algorithm-interview-workshop
title: "Algorithm Interview Workshop: Interval Rooms and Negative-Sum Windows"
description: "Practice two original coding problems using a heap and a monotonic deque, with proofs, counterexamples and independent exhaustive tests."
category: algorithms
difficulty: intermediate
updated: 2026-10-10
prerequisites: [heaps-priority-queues, two-pointers-prefix-sums, monotonic-stacks]
sources:
  - {title: "Amazon SDE II Interview Preparation", url: "https://amazon.jobs/content/en/how-we-hire/sde-ii-interview-prep", kind: "official preparation overview"}
  - {title: "Python — heapq", url: "https://docs.python.org/3/library/heapq.html", kind: "official language documentation"}
  - {title: "Python — collections.deque", url: "https://docs.python.org/3/library/collections.html#collections.deque", kind: "official language documentation"}
---
Coding practice is valuable when the candidate can **specify a contract, derive an invariant, justify complexity and disprove tempting alternatives** without relying on an IDE. This chapter contains two original workshop exercises: determining the minimum number of concurrent rooms for time intervals, and finding the shortest subarray whose sum reaches a target even when numbers can be negative. They test distinct ideas—an ordered priority queue and a monotonic deque—and should not be presented as leaked or guaranteed interview questions. The broader interview-preparation approach favors correctness, maintainability and tested code over memorizing recipes [1].

## Workshop protocol: define the problem before typing

For each exercise, say aloud what the function receives, what it returns, how boundaries are interpreted, and which invalid inputs are rejected. Start with small examples and an explicit lower-bound argument. Then write code with meaningful variable names, execute edge cases and inspect worst-case complexity. A deliberate counterexample to a weaker solution is more convincing than a large suite of happy-path assertions.

In an assessment without an IDE, keep a small checklist: empty collection, single element, duplicates, touching boundaries, large input, negative values where applicable, and whether mutation of input is permitted. Complexity must specify which quantity is n; calling something O(n) without accounting for sorting or a heap operation does not explain actual work.

## Exercise A: minimum rooms for overlapping intervals

**Contract:** Given n half-open intervals [start,finish), each with start strictly less than finish, find the minimum number of identical rooms required to run all jobs without changing their times. Two intervals that touch—[1,3) and [3,5)—can use the same room. The output is an integer. The caller owns the original input and the function must not mutate it.

The answer is the **maximum number of simultaneously active jobs** at any instant, because those jobs require distinct rooms, and a room can be reused as soon as its preceding job finishes. Sort intervals by start time and keep a min-heap of the finish times of currently active jobs. Before starting each job, remove all finishes at or before its start, then insert its finish. Track the largest active-heap size [2].

![Interval sweepline uses a heap of active end times; monotonic prefix deque solves negative-sum subarrays.](/diagrams/algorithm-interview-workshop.svg)

~~~python
from heapq import heappush, heappop

def min_rooms(intervals):
    for start, end in intervals:
        if start >= end:
            raise ValueError("interval must have positive duration")
    active_ends = []
    maximum = 0
    for start, end in sorted(intervals):
        while active_ends and active_ends[0] <= start:
            heappop(active_ends)
        heappush(active_ends, end)
        maximum = max(maximum, len(active_ends))
    return maximum

assert min_rooms([]) == 0
assert min_rooms([(1,3), (3,5)]) == 1
assert min_rooms([(0,5), (1,4), (2,3)]) == 3
assert min_rooms([(0,4), (2,6), (4,8)]) == 2
try:
    min_rooms([(2,2)])
    assert False
except ValueError:
    pass
~~~

At the moment a job starts, removing ended jobs leaves exactly those overlapping the new job from earlier starts. Thus heap size after insertion is the number of concurrently active requests at that instant. Every time maximal overlap occurs, it occurs immediately after some start; the maximum recorded is therefore the lower bound on necessary rooms. Reusing freed rooms gives a schedule meeting that bound, proving optimality.

Sorting takes O(n log n), and each interval end enters/leaves the heap at most once, for O(n log n) additional work and O(n) auxiliary heap storage. The output is not a list of room assignments. To return actual assignments, maintain a free-room pool and an active heap of (end, room_id) pairs; the counting algorithm alone does not preserve room identity.

## Wrong answer A: count overlaps against the first job

A common but incorrect approach counts how many intervals overlap the first input interval and uses that value as the answer. Peak overlap may occur much later. For [(0,1), (2,6), (3,5), (4,7)], the first job overlaps none, while three later jobs overlap each other. Another error is using a strict `end < start` retirement condition: it falsely counts [1,3) and [3,4) as requiring two rooms under half-open semantics.

A brute-force oracle for small n can evaluate concurrency at every interval start. For each start time t, count jobs with start ≤ t < finish; the maximum is the answer. This O(n²) oracle is intentionally slower but easy to audit independently of the heap logic.

~~~python
def rooms_oracle(intervals):
    return max((sum(a <= t < b for a, b in intervals)
                for t, _ in intervals), default=0)

from itertools import combinations
interval_pool = [(a,b) for a in range(4) for b in range(a+1,5)]
for size in range(5):
    for test in combinations(interval_pool, size):
        assert min_rooms(test) == rooms_oracle(test)
~~~

The exhaustive check covers a finite integer-time domain, not arbitrary real timestamps. The interval invariant justifies the general case; the oracle protects against implementation mistakes in that model.

## Exercise B: shortest nonempty subarray with sum at least K

**Contract:** Given an array of n integers (possibly negative) and a **positive** integer K, return the shortest length of a **contiguous, nonempty** subarray whose sum is at least K. Return -1 when none exists. Reject nonpositive K. Unlike a positive-only window exercise, increasing the right endpoint can **decrease** the sum and removing the leftmost element can increase it when numbers are negative.

Example [2,-1,2] with K=3 has answer 3; [2,-1,2] with K=2 has answer 1. A conventional sliding window that shrinks only after reaching K can miss an optimal solution when negative elements distort monotonic growth. The correct linear-time technique uses **prefix sums and a monotonic deque** [3].

## Derive the prefix-sum deque invariant

Define P[0]=0 and P[j]=sum of the first j elements. The sum of subarray [i,j) is P[j]-P[i]. For each right endpoint j, seek an earlier i with P[j]-P[i] ≥ K while minimizing j-i. Maintain candidate prefix indices in a deque whose prefix values are **strictly increasing** and whose indices are increasing.

When the current prefix P[j] reaches the threshold against the deque's front, that front yields a feasible subarray; record its length and remove it. It will never be better for any later right endpoint because the current j is already the earliest feasible endpoint for that candidate. Before adding j, remove candidates at the back with prefix value ≥ P[j]: the newer index j is later (hence gives a shorter or equal span) and has a no-larger prefix (hence makes future sums at least as large). This domination argument is the correctness invariant.

~~~python
from collections import deque

def shortest_at_least(values, target):
    if target <= 0:
        raise ValueError("target must be positive")
    prefix = [0]
    for value in values:
        prefix.append(prefix[-1] + value)
    candidates = deque()
    best = len(values) + 1
    for right, current in enumerate(prefix):
        while candidates and current - prefix[candidates[0]] >= target:
            best = min(best, right - candidates.popleft())
        while candidates and prefix[candidates[-1]] >= current:
            candidates.pop()
        candidates.append(right)
    return best if best <= len(values) else -1

assert shortest_at_least([2,-1,2],3) == 3
assert shortest_at_least([2,-1,2],2) == 1
assert shortest_at_least([-5,2,3],5) == 2
assert shortest_at_least([],1) == -1
assert shortest_at_least([1,-1,5],5) == 1
try:
    shortest_at_least([1,2],0)
    assert False
except ValueError:
    pass
~~~

Each prefix index is appended once and removed from one side at most once, giving O(n) deque operations. Constructing P takes O(n) time and space. In Python, integers grow to represent exact sums; in a fixed-width language, use a suitably wide integer type and discuss overflow on large values.

## Independent oracle and limits of the technique

Check every contiguous [i,j) using a running sum for each i. That costs O(n²) in n array elements and uses O(1) extra storage. Its simplicity makes it a good regression oracle against a complex amortized algorithm. Exhaustively test small arrays over {-2,-1,0,1,2} and positive targets; this checks duplicate prefix sums and negative cases.

~~~python
from itertools import product

def shortest_oracle(values, target):
    answer = len(values) + 1
    for i in range(len(values)):
        total = 0
        for j in range(i, len(values)):
            total += values[j]
            if total >= target:
                answer = min(answer, j - i + 1)
    return answer if answer <= len(values) else -1

for n in range(6):
    for arr in product((-2,-1,0,1,2), repeat=n):
        for goal in (1,2,3,4):
            assert shortest_at_least(arr, goal) == shortest_oracle(arr, goal)
~~~

The monotonic deque is designed for this **static one-dimensional prefix-sum problem**. It is not a general data structure for arbitrary online range updates or a substitute for interval scheduling. If updates arrive between queries, more complex structures and different guarantees may be required.

## Review rubric and extension tasks

**Assess skill separately from reading solved code.** The two implemented problems above teach invariants, but their answers are visible on this page: reproducing them is not an unseen assessment. A defensible mock session uses two original, independently chosen tasks under the official SDE II coding section's **90-minute/two-question** constraint; this allocation is a *practice model*, not a prediction of exact Amazon questions [1]. Record the statement, assumptions and tests before consulting an editorial solution.

Suggested self-assessment budget: 5 minutes to inspect both tasks, 35 minutes per task, and 15 minutes to test and review both solutions. Track input validation, algorithmic correctness, boundary cases, runtime and auxiliary memory. The grader in the repository exposes public fixtures; passing them is evidence only for those fixtures, not unseen inputs. Use [independent assessment I](/en/topics/independent-coding-assessment/) and [independent assessment II](/en/topics/independent-coding-assessment-ii/) as **unsolved starting points**, but rotate truly unfamiliar tasks from independently curated sources for a realistic blind assessment.



| Criterion | Room allocation | Shortest subarray |
| --- | --- | --- |
| Input contract | Positive-duration half-open intervals | Integers, positive K, nonempty answer |
| Core invariant | Heap equals active end times | Candidate prefixes increase |
| Optimality | Maximum overlap lower bound | Dominated earlier prefixes can be discarded |
| Complexity | O(n log n) and O(n) space | O(n) time and O(n) space |
| Counterexample | Touching endpoints / late overlap | Negative numbers break positive-only window |
| Oracle | Count activity at starts | Enumerate all subarrays |

As a timed self-review, explain each proof without looking at the code and rewrite both functions with tests. Then change one constraint—closed intervals for A, or an array containing only positive values for B—and explain exactly which comparison or algorithm can be simplified.

## Exercises and verification

1. For [(0,1),(2,6),(3,5),(4,7)], trace the active heap and determine the peak room count.
2. Explain why using `<` instead of `<=` when retiring a room is wrong under half-open endpoints.
3. Prove that an older prefix at least as large as a newer prefix can be removed from the deque.
4. Give a negative-valued array where a positive-only sliding-window argument is invalid.
5. Repeat the independent oracles with a different tiny domain and record any counterexample before altering the optimized solution.

**Related chapters:** [Heaps](/en/topics/heaps-priority-queues/), [interval scheduling](/en/topics/greedy-intervals/), [prefix sums](/en/topics/two-pointers-prefix-sums/), and [monotonic stacks](/en/topics/monotonic-stacks/) supply the primitives.
