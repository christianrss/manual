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

## Exercises and verification
1. For `'abba'`, after processing the second `'b'`, `left=2`. When the next `'a'` is inspected, the previous `'a'` lies before the boundary; `left` must remain 2.
2. Adapt the function to return the substring itself by retaining the best `(start, length)` pair; verify ties explicitly.
3. With an array `[2,-3,5]`, show why enlarging a window cannot be assumed to increase its sum.

If you cannot state the monotone property or window invariant, do not claim that a two-pointer algorithm is correct merely because it appears linear.
