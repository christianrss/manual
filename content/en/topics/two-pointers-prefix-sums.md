---
id: two-pointers-prefix-sums
title: "Two Pointers and Prefix Sums: Invariants and Subarray Queries"
description: "Derive opposite-end pointers and prefix sums, prove their invariants, and solve range and negative-value subarray problems with tests."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [arrays-and-strings, sorting-algorithms, hash-tables]
sources:
  - {title: "USACO Guide — Two Pointers", url: "https://usaco.guide/silver/two-pointers", kind: "algorithm teaching guide"}
  - {title: "USACO Guide — Prefix Sums", url: "https://usaco.guide/silver/prefix-sums", kind: "algorithm teaching guide"}
  - {title: "Python Documentation — itertools.accumulate", url: "https://docs.python.org/3/library/itertools.html#itertools.accumulate", kind: "official language documentation"}
---
A large class of sequence problems becomes easier after identifying **information that can be maintained incrementally**. Two pointers preserve an interval or a candidate pair while avoiding repeated scanning. Prefix sums precompute cumulative totals so that a range sum becomes a subtraction. These techniques are not interchangeable: each has specific assumptions, invariants and update behavior. Recognizing those assumptions is more important than memorizing a particular interview template [1][2].

## Two pointers from opposite ends

Suppose a sequence of n numbers is sorted in nondecreasing order and we need two **distinct positions** whose values sum to target T. Set left=0 and right=n−1. If a[left]+a[right] is less than T, increasing right cannot help because right is already the largest remaining value; all pairs using this left index are too small, so advance left. If the sum exceeds T, every pair using the current right with any remaining left value is too large, so decrease right. On equality, return the pair [1].

This is an **elimination proof**: each step removes at least one index from consideration without discarding any possible solution. Therefore at most n−1 pointer movements occur and the search takes O(n) time and O(1) extra space on sorted random-access input. If input is unsorted, sorting first can cost O(n log n). If the result must preserve original indices, sort (value,index) pairs rather than discarding index identity.

![Sorted values and pointer decisions by comparison with target sum.](/diagrams/two-pointers-prefix.svg)

~~~python
def pair_sum_sorted(values, target):
    left, right = 0, len(values) - 1
    while left < right:
        total = values[left] + values[right]
        if total == target:
            return (left, right)
        if total < target:
            left += 1
        else:
            right -= 1
    return None

assert pair_sum_sorted([-4, -1, 2, 5, 9], 4) == (1, 3)
assert pair_sum_sorted([3, 3], 6) == (0, 1)
assert pair_sum_sorted([7], 14) is None
assert pair_sum_sorted([], 1) is None
assert pair_sum_sorted([1, 3, 5], 20) is None
~~~

The function requires sorted input and constant-cost numeric comparisons/additions. It never pairs an element with itself because left must be strictly less than right. Duplicates are allowed. For unsorted input where one pass and arbitrary values matter more than constant space, a hash-based two-sum approach may provide expected O(n) time with O(n) extra storage instead.

## Two pointers moving in the same direction

A **sliding window** maintains an interval [left,right) whose right endpoint extends as new elements arrive; left advances when a constraint is violated. For nonnegative values and a nonnegative bound B, a window sum grows or stays constant as right advances, and decreases or stays constant when left advances. This monotonicity supports finding a maximum-length window whose sum is at most B in O(n) pointer movements [1].

When negative values are present, discarding a prefix may prevent the best answer: extending right can later *decrease* the sum. The simple rule 'shrink while sum>B' no longer proves correctness. Example [4,-3,2] with bound 3: after seeing the first 4, a naïve algorithm shrinks immediately and loses the length-three segment whose total is 3. Prefer a prefix-sum-based method or a different monotonic data structure depending on the exact task.

## Prefix-sum definition and telescoping argument

For array a of length n, define P[0]=0 and P[i+1]=P[i]+a[i] for 0≤i<n. Thus P[k] is the sum of the **first k elements**. The sum of the half-open subarray a[l:r] equals P[r]−P[l], because the first l elements appear in both prefix totals and cancel. This is a telescoping identity, not an estimate. It holds for negative numbers and zeros as well as positive values [2].

For a=[3,−2,5,1], prefixes are P=[0,3,1,6,7]. Query [1,3) gives P[3]−P[1]=6−3=3, matching −2+5. Query [0,4) gives 7. Building all prefixes costs O(n) time and O(n) storage; each **static** range sum then takes O(1) arithmetic operations. If input values change, recomputing prefixes can cost O(n); for frequent updates consider Fenwick or segment trees rather than claiming O(1) for dynamic ranges.

~~~python
def prefixes(values):
    result = [0]
    for value in values:
        result.append(result[-1] + value)
    return result

def range_sum(prefix, left, right):
    n = len(prefix) - 1
    if not 0 <= left <= right <= n:
        raise ValueError("invalid half-open range")
    return prefix[right] - prefix[left]

p = prefixes([3, -2, 5, 1])
assert p == [0, 3, 1, 6, 7]
assert range_sum(p, 1, 3) == 3
assert range_sum(p, 0, 4) == 7
assert range_sum(prefixes([]), 0, 0) == 0
try:
    range_sum(p, 2, 5)
    assert False
except ValueError:
    pass
~~~

The standard library's itertools.accumulate can compute running totals [3], but you must still prepend P[0]=0 if the algorithm relies on prefix indices matching half-open boundaries. Mixing one-based and zero-based conventions is among the most frequent off-by-one sources of failure.

## Count target-sum subarrays, including negatives

The equation sum(a[l:r])=T becomes P[r]−P[l]=T, equivalently P[l]=P[r]−T. Process r from left to right and maintain a frequency map of **previous** prefix values. Before inserting the new prefix P[r], count how often P[r]−T already appeared. That number is precisely the count of starting indices l<r that produce target T. Initialize the map with P[0]=0 occurring once, so intervals starting at zero are counted.

~~~python
def count_target_subarrays(values, target):
    seen = {0: 1}
    prefix = 0
    total = 0
    for value in values:
        prefix += value
        total += seen.get(prefix - target, 0)
        seen[prefix] = seen.get(prefix, 0) + 1
    return total

assert count_target_subarrays([1, -1, 1], 1) == 3
assert count_target_subarrays([0, 0], 0) == 3
assert count_target_subarrays([], 0) == 0
assert count_target_subarrays([2, -2, 3], 3) == 2
~~~

The last assertion can be checked manually: [2,−2,3] and [3] each sum to three. The dictionary may store O(n) distinct prefixes. Under the usual expected O(1) hash operations and constant-cost arithmetic, total time is expected O(n), with O(n) extra memory; unconditional worst-case O(n) should not be claimed for a hash implementation without assumptions.

## Prefix sums, difference arrays and range updates

Static prefix sums accelerate **queries**, but they do not inherently accelerate arbitrary point updates. A **difference array** solves a different problem: representing many range-add updates efficiently when values need not be read between updates. Define D[0]=a[0] and D[i]=a[i]−a[i−1]. Adding delta to each index in [l,r) modifies only D[l]+=delta and, if r<n, D[r]−=delta. Reconstruct the final array through cumulative addition in O(n).

This works because every reconstructed position from l through r−1 incorporates the added delta, and the negative delta at r cancels it for later positions. Difference arrays are useful when **updates are batched** and the final array is needed afterward. For mixed online range queries and updates, a Fenwick or segment tree might be appropriate, with different supported operations and logarithmic costs.

## Recognize the problem before choosing the tool

| Problem | Suitable method | Hidden assumption |
| --- | --- | --- |
| Pair sum in sorted array | Opposite-end pointers | Sorted input |
| Window sum constraint by extension | Sliding window | Often needs nonnegative values |
| Many range sums, no updates | Prefix sums | Static snapshot |
| Number of subarrays with target sum | Prefix + frequency map | Expected hash operations |
| Many batched range additions | Difference array | Reconstruct later |
| Dynamic range sums | Fenwick/segment tree | Additional update/query complexity |

Two pointers is not a guarantee of O(n) if a nested loop resets one pointer repeatedly; prove that each pointer only moves monotonically and at most n times. Prefix preprocessing is wasteful when one range sum is queried once. Hash frequencies count **subarrays**, not merely distinct prefix values, so storing a set instead of counts undercounts repeated zeros.

## Exercises and verification

1. Trace left/right movements for sorted [-4,−1,2,5,9] and target 4; justify each discarded index.
2. Explain why opposite-end pair sum fails on unsorted data such as [8,1,7,2] unless ordering is first established.
3. For [3,−2,5,1], compute P and derive sums of [0,2), [1,3) and the empty range [2,2).
4. Show with [4,−3,2] why the naïve nonnegative-only sliding-window rule loses the optimal interval.
5. Enumerate all nonempty subarrays of [0,0] to verify count_target_subarrays equals three for target zero.

**Related reading:** [Arrays and strings](/en/topics/arrays-and-strings/) introduce half-open intervals; [sorting](/en/topics/sorting-algorithms/) prepares ordered input; [sliding window](/en/topics/sliding-window/) expands same-direction pointers into a full method.
