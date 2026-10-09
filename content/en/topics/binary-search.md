---
id: binary-search
title: "Binary Search: Bounds, Invariants and Monotone Predicates"
description: "Derive binary search with a partition invariant, implement exact bounds, analyze complexity and explain when the method is invalid."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis]
sources:
  - {title: "CP-Algorithms — Binary Search", url: "https://cp-algorithms.com/num_methods/binary_search.html", kind: "technical reference"}
  - {title: "Python Documentation — bisect", url: "https://docs.python.org/3/library/bisect.html", kind: "official language documentation"}
---
Binary search finds a **transition in a monotone decision** by discarding half of the remaining range at each step. Searching a sorted array is only one example. Its correctness depends on a proved monotonicity property rather than on the fact that a midpoint is calculated [1].

## Define the contract

Let a be an array of n comparable elements in nondecreasing order. The **lower bound** of x is the first position i such that a[i] is at least x, or n if none exists. The **upper bound** is the first position whose value is strictly greater than x. They are insertion points, not necessarily matches. In [1, 2, 2, 2, 5], lower bound of 2 is 1 and upper bound is 4; the number of occurrences equals 4 minus 1 [2].

Define predicate P(i) to be true exactly when a[i] is at least x. Sorting produces a sequence of zero or more false values followed by zero or more true values. Maintain an interval [lo, hi] of **possible answers**, initially [0,n], where n is the sentinel for no match. At each iteration, examine mid in [lo,hi). If a[mid] is less than x, every earlier element is too small, so set lo=mid+1. Otherwise the answer is no later than mid, so set hi=mid. Thus the answer remains inside [lo,hi] after every iteration [1].

## Implementation and verification

~~~python
def lower_bound(a, x):
    lo, hi = 0, len(a)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if a[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return lo

def upper_bound(a, x):
    lo, hi = 0, len(a)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if a[mid] <= x:
            lo = mid + 1
        else:
            hi = mid
    return lo

a = [1, 2, 2, 2, 5]
assert (lower_bound(a, 2), upper_bound(a, 2)) == (1, 4)
assert lower_bound(a, 3) == 4
assert lower_bound([], 7) == 0
assert lower_bound(a, 9) == len(a)
~~~

**Proof:** Initially the answer belongs to [0,n]. A decision at mid discards only candidates that are impossible by the sortedness assumption. Whenever lo < hi, the interval length decreases strictly, so termination follows. At termination lo=hi is the smallest position satisfying the predicate, or n. This gives a correctness proof for all valid input arrays, not merely the examples.

## Complexity and alternatives

After k iterations at most approximately n/2^k candidate positions remain. Therefore time is O(log(n+1)) and additional space is O(1), assuming random-access indexing and constant-time comparisons. On linked lists, reaching the midpoint itself can be expensive. Using lo+(hi-lo)//2 avoids adding two potentially overflowing positive indices in fixed-width integer languages; Python integers do not overflow that way [1].

| Array | Lower bound of 2 | Upper bound of 2 |
| --- | ---: | ---: |
| Empty | 0 | 0 |
| [2] | 0 | 1 |
| [1,2,2,5] | 1 | 3 |
| [3,4] | 0 | 0 |

For a minimum-feasible-capacity question, define P(capacity) as whether a solution exists. If feasibility changes exactly once from false to true over a finite integer range, binary search also works. With R possible integer answers and a feasibility test costing C, the complexity is O(C log R). If feasibility oscillates, the approach is incorrect even when each individual test is reliable. Searching for a position is logarithmic, but inserting into a Python list still shifts elements in O(n) time [2].

## Failure modes and applicability

Unsorted data, nonmonotone predicates, concurrently modified sequences, inconsistent comparators, and unspecified duplicate handling invalidate the reasoning. A hash table can be preferable for many independent key lookups; for a tiny unsorted list, linear scan can be cheaper than sorting. The Python bisect documentation also warns against concurrent mutations during bisection [2].

## Exercises and verification

1. Trace lower bound of 4 in [1,2,2,5]: examine index 2 (value 2), then index 3 (value 5); the answer is 3.
2. Explain why P(i) = (a[i] equals x) is not monotone even for sorted data: it may be false, true, and false again.
3. Verify the implementation against Python bisect_left and bisect_right on empty, repeated, and out-of-range cases.
4. Invent a capacity predicate, prove its monotonicity, and count the maximum number of evaluations for R=1,024.
