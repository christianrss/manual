---
id: sliding-window
title: "Two Pointers and Sliding Windows"
description: "Derive linear-time window algorithms using monotonic conditions, loop invariants and exact edge-case reasoning instead of memorized templates."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis, hash-tables]
sources:
  - {title: 'USACO Guide — Two Pointers', url: 'https://usaco.guide/silver/two-pointers?lang=cpp', kind: algorithms tutorial}
  - {title: 'MIT 6.006 — Introduction to Algorithms', url: 'https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/', kind: university course}
---
A sliding window avoids recomputing statistics for overlapping contiguous subarrays or substrings. It works especially well when a **monotone condition** lets one boundary advance without ever needing to move backwards. This property, not the presence of two indexes, explains the time bound [1].

## Fixed-size versus variable-size windows
With fixed length `k`, compute an initial window aggregate, then remove the outgoing element and add the incoming element. Assuming constant-time updates, `n-k+1` windows cost `O(n)` total rather than `O(nk)`.

A variable-size window maintains indices `left ≤ right` and some valid-state predicate, for example "contains at most `k` distinct values". On each new `right`, update counts; while invalid, advance `left` and remove departing contributions. Because each index only increases from 0 to at most `n`, the combined number of movements is `O(n)` even when the inner `while` appears nested [2].

## Example: longest substring without repetition
For an input string, return the maximum number of **characters** in a contiguous substring with all distinct characters. This implementation treats Python Unicode code points as characters; grapheme clusters, such as combined accents, require a different tokenizer if that is the application contract.

```python
def longest_unique(text: str) -> int:
    last_seen = {}
    left = 0
    best = 0
    for right, character in enumerate(text):
        if character in last_seen and last_seen[character] >= left:
            left = last_seen[character] + 1
        last_seen[character] = right
        best = max(best, right - left + 1)
    return best

assert longest_unique('abba') == 2
assert longest_unique('') == 0
assert longest_unique('aaaa') == 1
assert longest_unique('abcabcbb') == 3
```

**Invariant:** after processing position `right`, the substring `text[left:right+1]` contains no repeated character. If the current character last appeared inside that window, moving `left` past that occurrence restores the invariant. If it appeared before `left`, the window was already valid and the boundary must not move backwards. This is exactly why the condition `last_seen[character] >= left` matters.

The algorithm takes `O(n)` expected time for `n` code points, assuming expected constant-time dictionary accesses. Auxiliary space is `O(min(n, Σ))`, where `Σ` is the number of distinct possible characters observed. It is not `O(1)` for an unbounded alphabet.

## When the pattern fails
Suppose the task is the shortest subarray with sum at least `S`. If **all numbers are nonnegative**, shrinking a valid window preserves an ordered relationship between sum and window size. With arbitrary negative values, the sum may decrease when you extend the window and increase when you remove an element. The usual positive-number sliding-window proof collapses; prefix sums with an appropriate monotone deque may be needed.

Two-pointer methods for pair sums in a sorted array have a related monotonicity assumption: if the current sum is too small, increasing the left value moves toward the target. On an unsorted array, that implication does not hold.

## A derivation from monotonic movement

A two-pointer algorithm is linear only if each pointer moves at most `O(n)` times *and* its work per move has bounded cost. For a variable window `[left,right]`, consider all sequences of moves: `right` advances at most `n` times, and `left` advances at most `n` times, so there are at most `2n` boundary moves. This is an **amortized** argument; a particular iteration of the outer loop may shrink the window many times. It is not enough to count that there are two pointers [1].

When the state is a frequency dictionary, adding a character increments its count, and removing decrements it; delete zero counts if the number of distinct keys is used as a condition. The state invariant should say exactly what is represented by the counts. An off-by-one error in deciding whether the window is `[left,right)` or `[left,right]` changes length computations and invalidation rules.

## Fixed-window worked example

For numbers `[3,1,4,1,5]` and fixed width `k=3`, the first sum is `3+1+4=8`. Slide right: subtract the departing 3, add 1, obtaining 6; slide again: subtract 1, add 5, obtaining 10. The maximum is 10, obtained without re-summing all three elements each time. The maintained invariant is 'current_sum equals the sum of elements inside the current window'. If `k>n`, decide whether to reject, return a sentinel, or search no windows; there is no universal default.

```python
def max_fixed_sum(values, width):
    if width <= 0 or width > len(values):
        raise ValueError("require 1 <= width <= input length")
    current = sum(values[:width])
    best = current
    for right in range(width, len(values)):
        current += values[right] - values[right-width]
        best = max(best, current)
    return best

assert max_fixed_sum([3,1,4,1,5],3) == 10
assert max_fixed_sum([-5,-2,-9],2) == -7
```

## Counterexample: negative values invalidate sum monotonicity

Suppose you want the shortest subarray whose sum is at least 3. With numbers `[2,-3,5]`, extending the interval from `[2]` to `[2,-3]` **decreases** its sum from 2 to -1; extending to `[2,-3,5]` increases it to 4. The usual 'grow until valid, shrink while valid' reasoning for nonnegative values is not automatically sound. An alternative for signed values uses prefix sums `p[j]-p[i]` and a monotone deque, requiring a different invariant [2].

## Validate against a slow oracle

For short random strings, compare `longest_unique` with a brute-force implementation that enumerates all substrings and checks `len(set(substring))==len(substring)`. Keep test cases with repeated characters, empty input, Unicode combining marks and long runs of the same symbol. The test oracle costs more time but is small and independent of the optimized reasoning. Finally, distinguish 'subsequence' (not necessarily contiguous) from 'substring' or 'subarray' (contiguous); sliding windows apply to the latter.

## Exercises and verification
1. For `'abba'`, after processing the second `'b'`, `left=2`. When the next `'a'` is inspected, the previous `'a'` lies before the boundary; `left` must remain 2.
2. Adapt the function to return the substring itself by retaining the best `(start, length)` pair; verify ties explicitly.
3. With an array `[2,-3,5]`, show why enlarging a window cannot be assumed to increase its sum.

If you cannot state the monotone property or window invariant, do not claim that a two-pointer algorithm is correct merely because it appears linear.
