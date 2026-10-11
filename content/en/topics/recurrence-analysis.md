---
id: recurrence-analysis
title: "Solving Algorithmic Recurrences: Trees, Substitution and Master Theorem"
description: "Derive and independently verify divide-and-conquer recurrences, exact operation counts, Master cases, counterexamples and stack costs."
category: foundations
difficulty: intermediate
updated: 2026-10-11
prerequisites: [complexity-analysis, recursion-call-stack]
sources:
  - {title: "MIT 6.006 — Introduction to Algorithms, Lecture Notes", url: "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/resources/lecture-notes/", kind: "university course notes"}
  - {title: "MIT 6.046J — Recitation Notes, Divide and Conquer", url: "https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/pages/recitation-notes/", kind: "university recitation notes"}
  - {title: "MIT 6.046J — Introduction to Algorithms, Lecture 2", url: "https://ocw.mit.edu/courses/6-046j-introduction-to-algorithms-sma-5503-fall-2005/resources/lecture-videos/", kind: "university lecture"}
---
A recurrence describes the resource cost of a computation in terms of the costs of smaller computations. It does not describe the recursive program's *output*; an algorithm may calculate a numerical answer in linear time or calculate the same answer in exponential time. The introductory [complexity analysis](/en/topics/complexity-analysis/) chapter explains asymptotic notation, while [recursion and call stacks](/en/topics/recursion-call-stack/) covers termination and stack frames. This chapter solves cost recurrences rather than repeating those introductions. The methods are standard topics in MIT's introductory and advanced algorithms courses [1][2][3].

The worked models count **abstract unit-cost operations**, not elapsed nanoseconds. Unless stated otherwise, `n` is a positive power of two, `T(1)=1` abstract operation, and recursion calls are evaluated sequentially. These restrictions allow exact identities; rounding and realistic instruction costs require separate treatment.

## Write the cost recurrence from the program

Consider a function which divides an input of size `n` into two equal halves, recursively processes both, then performs exactly `n` units of combining work for `n>1`. It has the cost contract

`T(1)=1`, and `T(n)=2T(n/2)+n` for `n=2,4,8,...`.

The coefficient 2 means **two recursive calls**. The term `n` measures work *outside* those calls. Confusing these quantities causes a typical error: declaring a recurrence logarithmic because each argument is halved, while ignoring that both halves are processed. Conversely, binary search ordinarily retains just one half, so a corresponding idealized recurrence is `T(n)=T(n/2)+1` [1].

A recurrence is meaningful only after specifying the input-size domain, stopping condition, branch count and nonrecursive work. If code allocates slices, their copying work may change the combine cost. If recursive arguments overlap, counting each call remains correct, but memoization can change the number of actual calls and therefore the cost relation.

## Recursion trees: derive each level before summing

Expand `T(n)=2T(n/2)+n`. At level zero there is one problem of size `n`, costing `n` outside recursive calls. At level one there are two problems of size `n/2`, each costing `n/2`: together they cost `n`. At level `i`, there are `2^i` problems, each of size `n/2^i`, still totaling `n`.

Let `k=log₂n`, an integer under the power-of-two assumption. Internal levels `i=0,...,k-1` contribute `kn`. The final level has `2^k=n` leaves, each of base cost 1. Thus

`T(n)=n log₂n+n=n(1+log₂n)=Θ(n log n)`.

This is an **exact equation for the specified model**, not an exact comparison count for all merge-sort implementations. Their merge loops and base cases can have different costs. If the per-node combine work is `cn` and the base cost is `d`, the same argument gives `cn log₂n+dn` [1][3].

## Substitution: verify a proposed closed form

The recursion-tree calculation suggests `T(n)=n(1+log₂n)`. To prove it by induction on `k=log₂n`, first check `n=1`: the formula gives 1. Suppose it holds at `n/2`; then

`T(n)=2(n/2)(1+log₂(n/2))+n`

`=n(1+log₂n-1)+n=n(1+log₂n)`.

The argument establishes both the base case and the induction step for every permitted `n`. Substitution must prove the claim; matching a few observed outputs would not suffice. For upper bounds with additive lower-order terms, one sometimes needs a **stronger induction hypothesis** (for example, a negative linear correction) to make constants close correctly [2][3].

A second example shows why guessing from one data point is dangerous: let `T(n)=2T(n/2)+n²`, with the same base case. Substitute the proposed `2n²-n`:

`2[2(n/2)²-(n/2)]+n² = 2n²-n`.

The base case is also 1. Hence this exact model has quadratic rather than `n log n` growth, even though its call tree has the **same shape**. Work per node matters as much as branching.

## The Master theorem and its hypotheses

For `T(n)=aT(n/b)+f(n)`, where constants `a>=1`, `b>1`, `f(n)` is asymptotically nonnegative and rounding is absent or controlled, let `p=log_b(a)`. There are approximately `n^p` leaves. Compare the nonrecursive work `f(n)` with `n^p` [2][3].

| Case | Sufficient condition | Tight bound |
| --- | --- | --- |
| Leaf-dominated | `f(n)=O(n^(p-epsilon))` for some `epsilon>0` | `Θ(n^p)` |
| Balanced work | `f(n)=Θ(n^p log^q n)`, fixed `q>=0` | `Θ(n^p log^(q+1) n)` |
| Root-dominated | `f(n)=Ω(n^(p+epsilon))` and `a f(n/b)<=c f(n)` for some `c<1` eventually | `Θ(f(n))` |

The **regularity condition** in the third row is not optional. The middle row includes a common logarithmic extension of the elementary three-case form, for nonnegative fixed `q`. Do not extrapolate these cases to arbitrary oscillating or negative `f`, variable branching factors, or uneven splits without a separate argument.

For `T(n)=2T(n/2)+1`, `p=1` and the constant work is polynomially smaller than `n`: `Θ(n)`. For `T(n)=2T(n/2)+n`, work is balanced: `Θ(n log n)`. For `T(n)=2T(n/2)+n²`, work dominates and regularity holds since `2(n/2)²=n²/2`: `Θ(n²)`. These three have identical branching and different growth rates.

## When the theorem does not settle the answer

`T(n)=T(n-1)+n` is not a constant-factor shrink, so the Master theorem does not apply. Expansion gives `T(n)=1+2+...+n=n(n+1)/2=Θ(n²)`. The recursion depth is `n`, not `log n`, even though there is only one recursive branch.

The basic cases above also do not directly classify `T(n)=2T(n/2)+n/log₂n` for powers of two `n>=2` and `T(1)=1`. With `k=log₂n`, the nonrecursive work summed across level `i` equals `n/(k-i)`. Therefore the total is `n+n(1+1/2+...+1/k)=n(1+H_k)`, where `H_k=Θ(log k)` is a harmonic number. The result is `Θ(n log log n)` for growing `n`. It lies between linear and `n log n`. A memorized three-row table misses this case; level-by-level summation does not [2].

Also, a routine that splits into sizes `floor(n/2)` and `ceil(n/2)` is not literally the same recurrence as two equal halves. Its asymptotic result may agree, but exact closed forms must handle rounding and base cases separately.

## Independently reproducible cost models

The iterative model below counts all tree levels for six **different** recurrence families. Its output is a total abstract work count and is not a benchmark. It rejects zero, negative, nonintegral and non-power-of-two input sizes, including Python booleans; the `kind` must name one declared recurrence.

~~~python
def recurrence_work(n, kind):
    if type(n) is not int or n <= 0 or (n & (n - 1)) != 0:
        raise ValueError("n must be a positive power of two")
    branching = {
        "split-unit": 2,
        "split-linear": 2,
        "split-quadratic": 2,
        "split-log": 2,
        "halve-unit": 1,
        "halve-linear": 1,
    }
    if type(kind) is not str or kind not in branching:
        raise ValueError("unknown recurrence family")
    branches = branching[kind]
    nodes, size, total = 1, n, 0
    while size > 1:
        if kind.endswith("unit"):
            local = 1
        elif kind.endswith("quadratic"):
            local = size * size
        elif kind == "split-log":
            local = size * (size.bit_length() - 1)
        else:
            local = size
        total += nodes * local
        nodes *= branches
        size //= 2
    return total + nodes  # each leaf has T(1) = 1

def descending_work(n):
    if type(n) is not int or n < 1:
        raise ValueError("n must be a positive integer")
    total = 1
    for size in range(2, n + 1):
        total += size
    return total

for k in range(9):
    n = 1 << k
    assert recurrence_work(n, "split-unit") == 2 * n - 1
    assert recurrence_work(n, "split-linear") == n * (k + 1)
    assert recurrence_work(n, "split-quadratic") == 2 * n * n - n
    assert recurrence_work(n, "split-log") == n * (1 + k * (k + 1) // 2)
    assert recurrence_work(n, "halve-unit") == k + 1
    assert recurrence_work(n, "halve-linear") == 2 * n - 1
assert descending_work(5) == 15
~~~

For binary subdivision, the model processes `Θ(log n)` *tree levels*, performs constant-time control per level under the unit-cost arithmetic model, and holds a fixed number of integer variables. The returned number can grow as `n²`, so the bit cost of operating on large Python integers is not constant. This instrumentation is **not** an implementation of the underlying recursive sorting algorithm; it calculates its stylized work count.

## Stack space is not total tree work

Recursion-tree *width* counts simultaneous branches in the mathematical expansion, not active stack frames of a sequential program. Balanced recursion with two calls can have `Θ(n)` total leaves while retaining only `Θ(log n)` active frames along one path. Memory allocated for merge buffers is additional and can be `Θ(n)`, depending on implementation. A single `n-1` recursive call produces `Θ(n)` depth. Thus `T(n)` by itself does **not** determine auxiliary memory use [1].

Replacing recursion with the iterative cost counter above reduces the depth *of the counter*, not of any other algorithm whose cost it describes. In real Python, available stack depth is limited; a mathematically finite recursion may still fail with a runtime exception. For any complexity claim, count separately: operations executed, maximum call depth, temporary arrays and output storage.

## Exercises and verification

1. Derive `T(n)=T(n/2)+n`, with `T(1)=1`. **Check:** the per-level costs are `n,n/2,...,2`, followed by base 1. Therefore `T(n)=2n-1=Θ(n)`.
2. Derive `T(n)=2T(n/2)+n log₂n` on powers of two. **Check:** level costs are `nk,n(k-1),...,n` with `k=log₂n`, plus `n` leaves. So `T(n)=n[1+k(k+1)/2]=Θ(n log²n)`.
3. Explain why `T(n)=2T(n/2)+n²` has `Θ(n²)` work. **Check:** level costs are `n²,n²/2,n²/4,...`; the geometric sum is at most `2n²` and the exact model is `2n²-n`.
4. **Unseen exercise:** design an `O(log n)`-space, nonrecursive cost evaluator for `T(n)=3T(n/3)+n` on powers of three. Prove its exact work formula without reusing the code above; then compare predictions to your implementation.
5. Explain why the measured ratio `T(2n)/T(n)` alone cannot certify an asymptotic bound. **Check:** finite measurements cannot establish a universal bound, and hardware behavior can violate the unit-cost model.

The included assertions check representative inputs. Separate test oracles should calculate recursive costs by a *different* mechanism and verify invalid inputs. Neither passing tests nor inspecting a growth curve substitutes for the inductive proof.
