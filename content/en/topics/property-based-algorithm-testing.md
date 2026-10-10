---
id: property-based-algorithm-testing
title: "Property-Based Algorithm Testing: Oracles, Shrinking and Metamorphic Checks"
description: "Generate adversarial cases with Hypothesis; compare binary search and signed-subarray algorithms against independent oracles."
category: algorithms
difficulty: advanced
updated: 2026-10-09
prerequisites: [binary-search, algorithm-interview-workshop, testing-strategies]
sources:
  - {title: "Hypothesis — Introduction", url: "https://hypothesis.readthedocs.io/en/latest/tutorial/introduction.html", kind: "official library documentation"}
  - {title: "Hypothesis — Replaying failed tests", url: "https://hypothesis.readthedocs.io/en/latest/tutorial/replaying-failures.html", kind: "official library documentation"}
---
A few selected examples cannot establish algorithm correctness across all permitted inputs. **Property-based testing** describes general relationships—such as an optimized result agreeing with an independently written oracle—and generates many cases, including combinations the developer did not anticipate. Hypothesis for Python also attempts to **shrink** a failure into a smaller counterexample, which is often more useful for debugging than a large random input [1][2]. This is a tool for discovering flaws, not a proof that no untested input exists.

## Start from a precise contract, not a random generator

For a lower-bound search, assume a sorted nondecreasing integer list and a target integer. Return the first index where value ≥ target, or list length if no such element exists. A generator creating arbitrary unsorted arrays violates that contract; a generator that sorts an arbitrary list produces valid inputs. Crucially, the independent oracle should not reimplement the same binary-search branching: a linear scan is easier to audit.

For a shortest-subarray problem, negative integers are explicitly permitted. The target is positive and the output is the smallest length of a nonempty contiguous window with sum ≥ target, or −1 if no window exists. A quadratic oracle that enumerates subarrays is acceptable on generated arrays of length up to twelve; using it on millions of elements would make the test suite impractical.

## A generated lower-bound oracle

Hypothesis separates a **strategy** describing valid input data from a **property** that must hold. Compare the optimized search with a direct scan, and additionally verify that all indices before the answer have values below the target while all indices from the answer onward have values at least the target.

~~~python
from hypothesis import given, settings, strategies as st

def lower_bound(values, target):
    lo, hi = 0, len(values)
    while lo < hi:
        middle = lo + (hi - lo) // 2
        if values[middle] < target:
            lo = middle + 1
        else:
            hi = middle
    return lo

@settings(max_examples=60, deadline=None)
@given(st.lists(st.integers(-20, 20), max_size=20),
       st.integers(-25, 25))
def check_lower_bound(raw, target):
    values = sorted(raw)
    expected = next((i for i, v in enumerate(values) if v >= target),
                    len(values))
    actual = lower_bound(values, target)
    assert actual == expected
    assert all(v < target for v in values[:actual])
    assert all(v >= target for v in values[actual:])

check_lower_bound()
~~~

Sorted inputs with duplicate values are common here; an off-by-one condition that skips equal values will fail. The oracle's linear O(n) cost is acceptable because input sizes are deliberately bounded for testing. The optimized algorithm remains O(log(n+1)) comparisons under random access.

![A generated input is compared with an independent oracle and a failing example shrinks.](/diagrams/property-based-testing-loop.svg)

## Metamorphic properties when a complete oracle is difficult

An **oracle** answers what the output ought to be. Sometimes a full oracle is expensive or unavailable. A **metamorphic property** relates answers under controlled changes to the input. For example, duplicating the list contents might not preserve a binary-search insertion index, but adding the same constant k to every array value and the target preserves the lower-bound index. This property is useful but **not complete**: an incorrect implementation that always returns zero would also satisfy it.

~~~python
@settings(max_examples=50, deadline=None)
@given(st.lists(st.integers(-10, 10), max_size=20),
       st.integers(-12, 12), st.integers(-100, 100))
def check_shift_invariance(raw, target, shift):
    values = sorted(raw)
    assert lower_bound(values, target) == lower_bound(
        [x + shift for x in values], target + shift)

check_shift_invariance()
~~~

Always identify weak properties that false implementations can satisfy. Combine oracle agreement, boundary invariants, transformations and explicitly selected regressions instead of assuming that generating hundreds of inputs automatically gives strong tests.

## Signed subarray and a quadratic independent oracle

For the shortest signed subarray, the optimized approach uses prefix sums and a monotonic deque: candidate prefix indices increase while dominated prefixes are removed. A simpler oracle can enumerate all possible contiguous windows, with no deque. Negative numbers and duplicate prefix values must be included or the generator misses exactly the edge cases where a positive-only sliding window fails.

~~~python
from collections import deque

def shortest_signed(values, target):
    prefix = [0]
    for v in values:
        prefix.append(prefix[-1] + v)
    pending = deque()
    answer = len(values) + 1
    for j, total in enumerate(prefix):
        while pending and total - prefix[pending[0]] >= target:
            answer = min(answer, j - pending.popleft())
        while pending and prefix[pending[-1]] >= total:
            pending.pop()
        pending.append(j)
    return answer if answer <= len(values) else -1

def exhaustive_window(values, target):
    best = len(values) + 1
    for start in range(len(values)):
        for end in range(start + 1, len(values) + 1):
            if sum(values[start:end]) >= target:
                best = min(best, end - start)
    return best if best <= len(values) else -1

@settings(max_examples=80, deadline=None)
@given(st.lists(st.integers(-5, 5), max_size=12),
       st.integers(1, 15))
def check_signed_subarrays(values, target):
    assert shortest_signed(values, target) == exhaustive_window(values, target)

check_signed_subarrays()
~~~

The oracle shown is intentionally simpler, not efficient: repeated slicing and summing make its worst-case cost cubic in the maximum input length, while the deque algorithm is O(n). Restrict generator size for meaningful feedback and never extrapolate its speed to production workloads.

## Shrinking, regression seeds and reproducibility

Hypothesis shrinks a failing test case to expose a smaller witness when possible [1]. For example, a routine that returns sorted unique values rather than a sorted multiset fails for duplicated inputs, often with the simplest case of two equal elements. A **stored regression** with exactly that minimal input should be added to ordinary tests even if future random test runs do not regenerate the original failure.

CI should choose an intentional randomness policy. Hypothesis can make its CI behavior deterministic; when exploring new cases over time, opt in to a varying generator stream and retain the minimal failing example in version control. A reported seed or reproduction blob is useful for investigation, but a stable explicit test fixture is easier to maintain across library versions [2].

## Independent checks and failure modes

| Failure | Weak test | Stronger evidence |
| --- | --- | --- |
| Equality branch wrong | All array elements distinct | Duplicate-rich generator plus oracle |
| Sliding window assumes positives | Only positive arrays | Signed generator including zeros |
| Oracle duplicates implementation logic | Compare same algorithm twice | Brute-force independent method |
| Failing case disappears next run | Random-only execution | Store minimized regression fixture |
| Generator covers invalid inputs | Unsorted data for lower bound | Generate within stated contract |
| Test time explodes | Brute-force on huge values | Explicit length bounds and budgets |

A property test can find implementation counterexamples; it does not replace an **invariant proof**, a performance evaluation or a concurrency test against real shared state. Conversely, a proof about an algorithm cannot ensure a buggy translation of the algorithm into a programming language is correct. The techniques complement one another.

## Put the generated checks into the build

This edition also adds `tests/test_property_based_sde_algorithms.py`, which loads both published EN/PT algorithm implementations and compares each with its own **independently written oracle**. CI installs Hypothesis and runs these property-based tests as part of normal unittest discovery. The tests preserve the distinction between the **published unsolved exercises** and the solved examples: they do not publish answers to the independent coding assessment.

Each generated failure must be investigated, turned into a minimal regression fixture, and addressed in the implementation rather than weakening the input strategy. A green test result is evidence for that run's generated cases and chosen properties; it is not formal verification of every possible input.

## Exercises and verification

1. Change lower-bound comparison from `<` to `<=` and identify a minimal duplicate-valued counterexample.
2. Produce an incorrect function that still satisfies the shift-invariance test and explain why the property is insufficient.
3. Add a generator for histogram rectangles with nonnegative heights and compare against the cubic brute-force formula.
4. Determine how the signed-subarray oracle's runtime grows when increasing maximum input length from 12 to 25.
5. Explain when an explicit regression test is more valuable than a reproducible random seed.

**Related chapters:** [Binary search](/en/topics/binary-search/), [signed-subarray workshop](/en/topics/algorithm-interview-workshop/), [testing strategies](/en/topics/testing-strategies/) and [formal model checking](/en/topics/formal-model-checking/) provide the underlying reasoning [1][2].
