---
id: dynamic-programming
title: "Dynamic Programming: States and Recurrences"
description: "Learn to define states, derive recurrence relations, prove transition correctness and select memoization or tabulation with exact cost bounds."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis]
sources:
  - {title: 'CP-Algorithms — Introduction to Dynamic Programming', url: 'https://cp-algorithms.com/dynamic_programming/intro-to-dp.html', kind: technical reference}
  - {title: 'MIT 6.006 — Introduction to Algorithms', url: 'https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/', kind: university course}
---
Dynamic programming (DP) solves a problem by identifying overlapping subproblems and reusing their results. It is not a magic speed-up for recursion. A solution requires a state representation that contains exactly the information needed for future decisions, a recurrence derived from valid choices, and a base case [1].

## Four questions to answer first
1. **State:** what does `dp[i]` (or `dp[i,j]`) represent, in one precise sentence?
2. **Transition:** which mutually complete choices can produce that state?
3. **Base case:** what is known without further recursion?
4. **Evaluation order:** which dependencies must be solved before this state?

If a state omits relevant history, two supposedly equal states may demand different answers. If the transition fails to cover one valid choice, the optimum may be missed. These are logical errors that memoization cannot repair [2].

## Derivation: minimum coins
Given positive integer denominations `coins` and nonnegative target `amount`, find the fewest coins needed when each denomination may be reused any number of times. Assume denominations are positive; a zero-valued coin would create an unproductive self-dependency. Define `dp[x]` as the minimum number of coins to make **exactly** amount `x`, or infinity if impossible.

The empty combination makes amount zero, so `dp[0]=0`. For each `x>0`, the final coin of any valid solution has some denomination `c≤x`, and what comes before it must optimally solve `x-c`. Therefore:

`dp[x] = 1 + min(dp[x-c] for c in coins if c<=x)`.

An unattainable predecessor contributes infinity. The recurrence considers every possible last coin, and every valid solution has one: it is exhaustive. Replacing a nonoptimal predecessor with an optimal one would improve the solution, so optimal substructure holds.

```python
def min_coins(coins, amount):
    if amount < 0 or any(c <= 0 for c in coins):
        raise ValueError('positive denominations and nonnegative amount required')
    unreachable = amount + 1
    dp = [unreachable] * (amount + 1)
    dp[0] = 0
    for value in range(1, amount + 1):
        for coin in coins:
            if coin <= value:
                dp[value] = min(dp[value], 1 + dp[value - coin])
    return -1 if dp[amount] == unreachable else dp[amount]

assert min_coins([1, 3, 4], 6) == 2  # 3 + 3
assert min_coins([2], 3) == -1
assert min_coins([], 0) == 0
assert min_coins([1], 0) == 0
```

The nested loops visit at most `amount × len(coins)` transitions: `O(A·C)` time and `O(A)` auxiliary memory, where `A=amount` and `C=len(coins)`. This is **pseudo-polynomial** in numeric `A`, not polynomial in the bit length `log A` of its representation.

## Memoization, tabulation and memory reduction
**Top-down memoization** evaluates only reachable states, but recursion depth and lookup overhead matter. **Bottom-up tabulation** fills a dependency-respecting order and may make memory usage predictable. Both are DP if the recurrence is sound. Space reduction is valid only if discarded states are no longer needed by any subsequent transition.

For Fibonacci numbers, a state depends only on the previous two values, so keeping the entire array is unnecessary. For longest common subsequence, careless one-dimensional compression can overwrite a value needed later; traversal direction and saved temporary values become part of the proof.

## Failure modes and counterexamples
A greedy solution to the coin example chooses the largest coin first. For denominations `[1,3,4]` and amount 6, it chooses `4+1+1` (3 coins) while DP finds `3+3` (2 coins). Greedy is not generally valid without a proof about the denomination system. Likewise, DP is not appropriate merely because a problem mentions maximizing or minimizing something: check for reusable subproblem states.

## Formal state correctness: induction over dependency order

A DP state must summarize everything future decisions depend on. For minimum-coin change with positive denominations, `dp[x]` stores the optimum for exactly `x`; the recurrence considers every possible **last coin**. Correctness can be established by strong induction on `x`: the base case `dp[0]=0` is optimal; for `x>0`, each candidate uses one coin `c` plus an optimal solution to the smaller amount `x-c`, optimal by the induction hypothesis. Taking the minimum covers every valid solution. This proof fails if zero or negative denominations allow nondecreasing dependencies [1].

## A second DP model: longest common subsequence

For strings `A` and `B`, define `dp[i][j]` as the LCS length of prefixes `A[:i]` and `B[:j]`. The base cases are `dp[0][j]=dp[i][0]=0`. If the last characters match, an optimal subsequence can include them: `dp[i][j]=dp[i-1][j-1]+1`. Otherwise at least one of the two last characters is excluded, giving `dp[i][j]=max(dp[i-1][j],dp[i][j-1])`. With lengths `m,n`, the table uses `O(mn)` time and space; retaining only neighboring rows reduces the **length computation** to `O(min(m,n))` space, but not an entire reconstructed sequence without additional decisions [2].

```python
def lcs_length(a,b):
    previous = [0]*(len(b)+1)
    for x in a:
        current = [0]*(len(b)+1)
        for j,y in enumerate(b,1):
            current[j] = previous[j-1]+1 if x == y else max(previous[j],current[j-1])
        previous = current
    return previous[-1]

assert lcs_length("ABCBDAB","BDCABA") == 4
assert lcs_length("","x") == 0
assert lcs_length("abc","def") == 0
```

## Memoization versus tabulation: actual engineering choice

Top-down memoization caches only visited states but requires safe recursion depth and unambiguous cache keys. Bottom-up tabulation requires an order respecting all dependencies, making memory layout and complexity easier to predict. In either form, the number of distinct states multiplied by work per state provides a starting cost model; it excludes potential costs of hashing a large state key or copying sequences into memo entries. Space optimization is legal only after proving a state will never be needed again.

## Pseudopolynomial time and invalid greedy shortcuts

The coin algorithm uses `O(A·C)` time for numeric amount `A` and number of denominations `C`. Because representing `A` in binary requires only `Θ(log A)` bits, this is **pseudopolynomial**, not polynomial in encoded input length. A 'greedy picks the largest coin' argument is wrong for denominations `1,3,4` and target 6, where `4+1+1` loses to `3+3`. Greedy methods demand a separate exchange argument or proof of a special coin system.

**Checkpoints:** show why `dp[x]` cannot use an unbounded negative denomination without modifying its state model; derive the LCS recurrence for `"ab"` and `"ba"` (answer 1); explain why a DP with `2^n` states is not automatically efficient even if each transition is constant-time.

## Exercises and verification
1. Write the state and recurrence for climbing stairs using steps 1 or 2. Base `ways(0)=1`; for `n>=1`, sum valid predecessor counts.
2. In the coin example, explain why `unreachable=A+1` is a safe sentinel: any attainable amount uses at most `A` positive integer coins if denomination 1 is available; more generally a solution can use at most `A` positive-valued coins.
3. Test `min_coins([4,6],8)==2` and `min_coins([4,6],7)==-1`.

The interview skill is to **derive the state and prove the transition**, not to memorize a two-dimensional array template.
