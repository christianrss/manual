---
id: complexity-analysis
title: "Asymptotic Analysis and Algorithmic Cost"
description: "Derive time and space complexity from loops, recurrences and invariants, while distinguishing worst-case, amortized and expected costs."
category: foundations
difficulty: foundational
updated: 2026-10-10
prerequisites: []
sources:
  - {title: 'MIT 6.006 — Introduction to Algorithms', url: 'https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/', kind: university course}
  - {title: 'MIT 6.046J — Design and Analysis of Algorithms', url: 'https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/', kind: university course}
---
An algorithm is not efficient merely because it runs quickly on one input. Analysis asks how resources grow with the input, under an explicitly stated model of computation. In the standard RAM model, elementary arithmetic, comparisons and indexed access are commonly treated as constant-cost operations; this approximation is not appropriate for arbitrarily large integers, external memory or networking [1].

## Definitions and assumptions
Let `T(n)` be the maximum number of elementary operations for inputs of size `n`. **Big O** gives an asymptotic upper bound: `T(n) ∈ O(g(n))` if some constants `C > 0` and `n0` satisfy `T(n) ≤ C·g(n)` for all `n ≥ n0`. **Big Omega** gives a lower bound and **Big Theta** gives both. These are properties of functions, not a synonym for worst case. You can discuss expected-case `O(n)` or worst-case `Θ(n²)` without contradiction [2].

| Symbol | Meaning | Example |
| --- | --- | --- |
| `O(g(n))` | asymptotic upper bound | insertion sort is `O(n²)` worst case |
| `Ω(g(n))` | asymptotic lower bound | reading an unsorted array to find its maximum is `Ω(n)` |
| `Θ(g(n))` | asymptotically tight bound | complete linear scan is `Θ(n)` |
| `o(g(n))` | grows strictly slower | `n ∈ o(n log n)` |

State **what n measures**: elements, vertices, edges, bytes or bits. State whether you count auxiliary memory, retained output or total memory. Recursion uses stack space even without an explicit array.

## Deriving rather than guessing
For sequential phases, add costs; for nested loops, count iterations rather than just the number of `for` statements. Consider:

```python
def pairs_under_limit(values, limit):
    total = 0
    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            if values[i] + values[j] < limit:
                total += 1
    return total
```

For `n` elements, the inner body runs `(n−1)+(n−2)+...+1 = n(n−1)/2` times. Therefore time is `Θ(n²)`, with `Θ(1)` auxiliary memory. If the output were an explicit list of all qualifying pairs, output space could be `Θ(n²)` as well.

In contrast, repeatedly halving an interval of length `n` yields at most `⌊log₂ n⌋+1` iterations; however, **binary search requires a monotone predicate or sorted ordering**. Halving alone does not prove correctness.

## Recurrences, amortization and expectation
A divide-and-conquer algorithm often obeys a recurrence. Merge sort, in an idealized even split, has `T(n)=2T(n/2)+Θ(n)`, resulting in `Θ(n log n)` [1]. Derive it as `log₂ n` levels each costing `Θ(n)`, rather than memorizing the answer.

**Amortized** cost bounds the total work over a sequence, without assuming random inputs. A dynamically resized array may occasionally copy `n` elements, but geometric capacity growth makes total copying across `n` appends `O(n)`, hence amortized `O(1)` per append. **Expected** cost instead takes an average under a probability model (for instance randomized hashing); neither guarantees that every individual operation is fast.

## Common failure modes
- Treating hash-table lookup as **unconditional** `O(1)`; collisions and attacks affect worst-case behavior.
- Ignoring hidden linear work such as slicing, serialization or copying.
- Confusing `O(n+m)` graph traversal with `O(n)` where `m` is the number of edges.
- Claiming `O(1)` memory for a recursive algorithm that can recurse `n` levels.
- Assuming asymptotic superiority automatically means lower real latency on small inputs.

## Counting operations under an explicit cost model

The earlier example already proves the triangular sum and quadratic bound. Consider a different algorithm: two nested loops, but the inner loop doubles its counter. The existence of two loops does not imply `n²` work; count actual iterations [1].

```python
def power_visits(n):
    if n < 0:
        raise ValueError("negative n")
    total = 0
    for _ in range(n):
        step = 1
        while step <= n:
            total += 1
            step *= 2
    return total

assert power_visits(0) == 0
assert power_visits(8) == 32
for n in range(1, 65):
    assert power_visits(n) == n * n.bit_length()
```

For `n >= 1`, the inner loop executes `floor(log₂ n)+1` times per outer iteration. Thus `T(n)=n(floor(log₂ n)+1)=Theta(n log(n+1))` under a unit-cost RAM model, with `Theta(1)` auxiliary space. Actual Python integers have arbitrary precision; enormous values require bit-complexity analysis. Indexing a linked list, executing a SQL query and reading RAM use different cost models. Declare primitive-operation costs and whether recursive stack frames count as auxiliary memory before assigning an asymptotic bound.
## Recurrences: expansion, substitution and hypotheses

For a balanced divide-and-conquer recurrence `T(n)=2T(n/2)+cn` on powers of two with `T(1)=d`, a recursion tree has `log₂n` internal levels, each costing `cn`, plus `n` leaves costing `d`. Consequently `T(n)=cn log₂n + dn = Θ(n log n)`. This is a proof using a particular recurrence, not a rule for every divide-and-conquer algorithm [2].

The Master theorem applies to recurrences of the form `T(n)=aT(n/b)+f(n)`, with `a≥1, b>1` and technical regularity conditions. Compare `f(n)` with `n^(log_b a)`; do not blindly use the theorem for unequal subproblem sizes or functions that violate its conditions. Substitution provides an alternative: hypothesize `T(n)≤C n log n`, insert the hypothesis into the recurrence and choose constants making the induction work. Account for base cases and rounding.

## Amortized proofs, with a concrete potential

For a dynamic array that doubles capacity whenever full, consider appending `n` items from empty. Reallocations copy `1+2+4+...+2^k < 2n` elements, while the appends themselves write `n` items; total work is `O(n)`. Thus the **amortized** cost per append is `O(1)`, even though a resize costs `Θ(n)`. This bound is deterministic across a sequence, not an expectation. With the potential method, choose a nonnegative potential representing prepaid work; amortized cost is actual cost plus change in potential, and the sum telescopes. An invalid potential that becomes negative without accounting for the initial value cannot justify the claimed bound [2].

## Verification beyond a timing plot

Before implementing, state: input domain; whether integers are machine words or arbitrarily large; what `n` means; cost of comparisons and indexing; and whether auxiliary memory includes recursion frames. Instrument comparison counts in tests and examine `T(2n)/T(n)`: ratios near two suggest linear growth, near four suggest quadratic growth, but cache behavior and constants can mislead. Mathematical derivation establishes the asymptotic bound; measurements check whether the model predicts real performance.

**Checkpoint:** Why can binary search on a linked list fail to be `O(log n)`? Because locating each midpoint may require walking `Θ(n)` links; random access was a hidden assumption. Why is a hash lookup not unconditionally `O(1)`? Because the bound depends on collision resolution and a distributional or implementation assumption.

## Exercises and verification
1. A loop doubles `i` from 1 while `i < n`. It performs `⌈log₂ n⌉` iterations for positive powers of two, so its time is `Θ(log n)`.
2. Two independent scans of `n` items cost `Θ(2n)=Θ(n)`, not `Θ(n²)`.
3. In a complete graph with `V` vertices, `E=V(V−1)/2`. A traversal taking `Θ(V+E)` is therefore `Θ(V²)` on that family of inputs.

To verify your analysis, count operations for several input sizes, normalize by the predicted growth rate, and inspect whether the ratio stabilizes. Measurements can falsify a model; they do not replace a proof.
