---
id: monotonic-stacks
title: "Monotonic Stacks: Next Greater, Temperatures and Histogram Areas"
description: "Prove linear-time monotonic-stack bounds, calculate next-greater positions and largest histogram rectangles with runnable tests."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [stacks-queues, arrays-and-strings]
sources:
  - {title: "Princeton Algorithms — Bags, Queues and Stacks", url: "https://algs4.cs.princeton.edu/13stacks/", kind: "university textbook"}
---
A **monotonic stack** [1] stores candidate indices in value order, allowing us to answer nearest-greater or nearest-smaller questions without restarting a scan for each element. The key insight is that when a new value dominates an earlier candidate, the earlier candidate can be resolved or permanently discarded. A nested while loop may look quadratic, but if each index enters once and leaves at most once, total stack operations are linear.

## What remains on the stack?

For a **next strictly greater value to the right** query, scan left to right, keeping indices whose values are nonincreasing from bottom to top. When the new value x is strictly greater than the value at the top index, that top index's next-greater position is the current index: any earlier positions were inspected without finding a greater value. Pop and continue until the stack condition holds, then push the new index.

Indices, rather than just values, preserve positions and distances. Equal values should **not** resolve strictly-greater queries. If a problem asks for greater-or-equal or smaller-or-equal neighbors, the comparison sign must change. Those few characters are part of the algorithm's mathematical contract, not a mere optimization.

## A complete next-greater implementation

~~~python
def next_greater_index(values):
    answer = [-1] * len(values)
    pending = []
    for i, value in enumerate(values):
        while pending and values[pending[-1]] < value:
            answer[pending.pop()] = i
        pending.append(i)
    return answer

assert next_greater_index([2,1,3,2,4]) == [2,2,4,4,-1]
assert next_greater_index([4,4,2]) == [-1,-1,-1]
assert next_greater_index([]) == []
assert next_greater_index([7]) == [-1]
~~~

For [2,1,3,2,4], position zero waits when 1 arrives; 3 resolves positions one and zero, both pointing to position two. The following 2 waits; 4 resolves that 2 and the earlier 3. The final 4 has no strictly greater value to its right and retains -1. The output records **indexes**, not values, making it reusable for distance questions.

## Why the nested loop costs O(n)

Each element index is pushed **exactly once**. An index can be popped no more than once: after popping it never reenters. Therefore across the entire scan there are at most n pushes and n pops, plus O(n) top comparisons. Time is O(n) and auxiliary space O(n) in the worst case, such as a decreasing input where many candidates remain unresolved.

This is an amortized, aggregate argument, not a claim that each outer-loop iteration does constant work. A single large incoming value can pop many candidates at once, but those same candidates cannot be popped again. Counting operations across the full algorithm avoids the common mistake of multiplying two loop bounds mechanically.

![A decreasing monotonic stack resolves pending positions when a greater value arrives.](/diagrams/monotonic-stack.svg)

## Daily temperatures as a distance transformation

If each number is a day's temperature, a common task asks how many days to wait for a **strictly warmer** day. When position j resolves earlier position i, the answer for i is j−i rather than j. Return zero when no warmer day exists. The same stack invariant applies; only the output contract changes.

~~~python
def days_until_warmer(temps):
    days = [0] * len(temps)
    stack = []
    for i, value in enumerate(temps):
        while stack and temps[stack[-1]] < value:
            earlier = stack.pop()
            days[earlier] = i - earlier
        stack.append(i)
    return days

assert days_until_warmer([73,74,75,71,69,72,76,73]) == [1,1,4,2,1,1,0,0]
assert days_until_warmer([5,5,5]) == [0,0,0]
~~~

The distinction between **nearest** and **largest** matters. The next warmer day is the earliest index after i with a higher temperature, not the day with the highest temperature in the remainder of the sequence.

## Largest rectangle in a histogram

A second pattern keeps bar indices in **nondecreasing height** order. For each bar of height h, the widest rectangle whose limiting height is h extends until a strictly shorter bar on both sides. When the current bar is shorter than the stack top, pop the top: the current position is the first strictly shorter position to its right (under strict comparisons), and the new stack top identifies a left boundary with height no greater than the popped bar. A sentinel at the end forces unresolved bars to be measured.

~~~python
def largest_histogram_rectangle(heights):
    if any(h < 0 for h in heights):
        raise ValueError("heights must be nonnegative")
    pending = []
    best = 0
    for i in range(len(heights) + 1):
        current = 0 if i == len(heights) else heights[i]
        while pending and heights[pending[-1]] > current:
            height = heights[pending.pop()]
            left = pending[-1] if pending else -1
            width = i - left - 1
            best = max(best, height * width)
        pending.append(i)
    return best

assert largest_histogram_rectangle([2,1,5,6,2,3]) == 10
assert largest_histogram_rectangle([]) == 0
assert largest_histogram_rectangle([2,2]) == 4
assert largest_histogram_rectangle([0,1,0]) == 1
~~~

A bar of height 5 with its neighbor of height 6 forms a rectangle of area 5×2=10 in the example. The algorithm runs in O(n) time and O(n) stack memory. Equal heights are retained until a strictly shorter height appears; then successive pops correctly consider the available widths. The virtual zero bar is only used to drain the stack, not part of the real histogram.

## Difference from a monotonic deque

A **monotonic deque** additionally removes indices at its *front* when they expire from a moving window. This supports sliding-window maximum, where the candidate set must obey a recency boundary. A monotonic stack only exposes one end and is suitable for nearest-neighbor and histogram boundary questions. Treating stack and deque as identical will produce wrong answers when old indices leave a window but no smaller/larger value arrives.

| Question | Invariant | Output |
| --- | --- | --- |
| Next strictly greater | Pending values nonincreasing | Index to right |
| Days until warmer | Pending temperatures nonincreasing | Distance in days |
| Largest histogram rectangle | Pending heights nondecreasing | Maximum area |
| Sliding-window maximum | Decreasing deque and expiration | Maximum per window |

## Counterexamples and failure modes

Comparing by `<=` instead of `<` changes what equal values mean. Returning the **value** instead of an **index** loses the distance. Ignoring the final stack drain misses rectangles extending to the end. A sentinel equal to zero is valid here because input bars are nonnegative and zero-height rectangles cannot improve best; negative heights are rejected.

A stack is also not a generic solution for arbitrary range maxima under point updates. Monotonic stack questions assume a particular one-pass relationship; repeated updates may require a segment tree or another data structure.

## Exercises and verification

1. Trace pending indices for [2,1,3,2,4] and justify every resolved next-greater position.
2. Prove O(n) total stack operations using a push/pop counting argument.
3. Explain why equal temperatures should not count as a warmer day.
4. Compute the maximal rectangle for [2,1,5,6,2,3] and identify the limiting bar and width.
5. Implement a quadratic nearest-greater oracle and compare it against next_greater_index for all arrays of length at most four over {0,1,2}.

**Related chapters:** [Stacks and queues](/en/topics/stacks-queues/) introduce the abstraction; [sliding windows](/en/topics/sliding-window/) develop recency constraints.
