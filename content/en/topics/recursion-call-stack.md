---
id: recursion-call-stack
title: "Recursion, Call Stacks and Divide-and-Conquer"
description: "Understand recursive contracts, base cases, stack frames, termination proofs and divide-and-conquer recurrences with executable tests."
category: foundations
difficulty: beginner
updated: 2026-10-09
prerequisites: [complexity-analysis, arrays-and-strings, stacks-queues]
sources:
  - {title: "MIT OpenCourseWare — Introduction to Algorithms", url: "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/", kind: "university course"}
  - {title: "Python Documentation — sys.getrecursionlimit", url: "https://docs.python.org/3/library/sys.html#sys.getrecursionlimit", kind: "official language documentation"}
---
**Recursion** solves a problem by invoking the same computation on smaller instances. A recursive program is not correct because it calls itself: it is correct only when a precise contract holds, each reduction moves toward a stopping condition, and the results of subproblems are combined appropriately. Its resource costs depend on both the number of calls and how many are simultaneously active. Those distinctions matter in coding exercises, tree algorithms and production programs [1].

## From a contract to a base case

Consider computing a factorial for an integer n≥0. The mathematical contract is 0!=1 and n!=n×(n−1)! for n>0. The **base case** handles n=0 without another call. The **recursive case** invokes factorial(n−1) on a smaller input and multiplies by n. A valid program must also reject n<0, because repeatedly subtracting one from a negative integer never reaches zero.

Termination and correctness are separate proof obligations. The variant n is a nonnegative integer that strictly decreases on each recursive call, so there cannot be infinitely many calls before n=0. For correctness, use induction on n: the base case returns the stipulated value; assuming the recursive call returns (n−1)!, multiplying by n gives n!, completing the argument.

~~~python
def factorial(n):
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError("factorial expects a nonnegative integer")
    if n == 0:
        return 1
    return n * factorial(n - 1)

assert factorial(0) == 1
assert factorial(5) == 120
assert factorial(1) == 1
try:
    factorial(-1)
    assert False
except ValueError:
    pass
~~~

This implementation is pedagogical, **not** safe for arbitrarily large n in Python. Python limits recursive call depth to protect the interpreter's call stack, and the exact limit depends on its environment [2]. An iterative loop avoids a call frame for every input value and is better for large n.

## Trace the call stack rather than only the return values

A function invocation creates a conceptual **stack frame** holding local variables, return location and execution state. With factorial(3), calls enter factorial(3) → factorial(2) → factorial(1) → factorial(0). The deepest call returns 1; then factorial(1) returns 1, factorial(2) returns 2 and factorial(3) returns 6. The calls form a chain with four simultaneously active frames, even though the function's source code contains just one recursive call.

![Recursive calls descend toward the base case and results unwind through stack frames.](/diagrams/recursion-call-stack.svg)

The call stack is LIFO: the most recently called function finishes first. A deep recursive algorithm can exhaust memory or hit an interpreter limit even if its time complexity is otherwise good. Tail recursion does not generally receive a guaranteed constant-stack optimization in Python. Where stack depth might grow with untrusted input, choose an iterative implementation or explicit heap-allocated work stack.

## Count calls and distinguish time from stack space

For factorial on n≥0, there are n+1 invocations. Ignoring big-integer multiplication costs, the **word-RAM** time complexity is Θ(n), while extra call-stack memory is Θ(n). The returned integer itself may grow to many bits, and arithmetic on large integers is not constant time. State the chosen computational model before presenting Θ(n) as an unconditional machine-time bound.

For a recurrence T(n)=T(n−1)+Θ(1), expansion produces T(n)=Θ(n). A naive recursive Fibonacci computation instead has overlapping subproblems: fib(n) calls fib(n−1) and fib(n−2), recomputing many of the same values. Its call tree grows exponentially, even though maximum recursion depth remains O(n). Thus **time complexity and maximum stack depth are different quantities**.

~~~python
def fib_memoized(n):
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be nonnegative")
    memo = {0: 0, 1: 1}
    def solve(k):
        if k not in memo:
            memo[k] = solve(k - 1) + solve(k - 2)
        return memo[k]
    return solve(n)

assert fib_memoized(0) == 0
assert fib_memoized(1) == 1
assert fib_memoized(10) == 55
assert fib_memoized(20) == 6765
~~~

Memoization stores each distinct subproblem once. Under constant-cost arithmetic and hash operations, this example performs O(n) work and stores O(n) values; its recursion depth is still O(n). In production, an iterative Fibonacci or a logarithmic-time fast-doubling method may be preferable for large n.

## Divide-and-conquer versus overlapping subproblems

Divide-and-conquer splits an input, solves smaller instances and combines their results. Mergesort divides a sequence in half, sorts each half and merges two ordered halves; the combine step costs Θ(n). On balanced inputs, its recurrence is T(n)=2T(n/2)+Θ(n). Every level of the recursion tree performs Θ(n) work, and there are Θ(log n) levels, yielding Θ(n log n) time [1].

This differs from naive Fibonacci. Mergesort's left and right halves represent disjoint positions, while naive Fibonacci's recursive branches repeatedly ask for the same fib(k). **Memoization** is valuable for overlapping subproblems, but it does not replace the merge step needed in sorting. The dividing rule, number of subproblems and cost of combining them determine the recurrence.

## Prove termination using a decreasing measure

For a divide-and-conquer algorithm on n items, verify that every recursive subproblem has strictly smaller size for n>base. If a function splits [lo,hi) and accidentally recurses on the original [lo,hi) range again, a superficially plausible midpoint expression can cause nontermination. A **well-founded measure**, often interval length hi−lo, makes the proof explicit: every call decreases the nonnegative measure until a base case.

A more complex recursive routine may require a lexicographic measure such as (remaining vertices, remaining alternatives), or a set of visited graph nodes to prevent cycling. Recursion on a cyclic graph without a visited discipline may recurse forever even though the graph has finitely many vertices.

## Common implementation traps

| Mistake | Consequence | Repair |
| --- | --- | --- |
| Missing base case | Calls never stop | Define terminal state first |
| Input does not decrease | No termination guarantee | Show decreasing variant |
| Shared mutable default accumulator | State leaks between calls | Initialize state per invocation |
| Exponential overlapping subproblems | Repeated work | Memoize or use DP |
| Recursive graph traversal without visited set | Cycles cause repeated visits | Track visited vertices |
| Assuming tail-call optimization | Stack exhaustion in Python | Iterate or use explicit stack |

Python's list slicing is another hidden cost. Implementing mergesort with slices allocates new sublists, so its space behavior differs from a version merging into reusable buffers. Express complexity in terms of the real operations used rather than the pseudocode alone.

## Exercises and verification

1. Trace factorial(4) with five stack frames, showing each intermediate return. Explain why the largest simultaneous depth is five.
2. Prove factorial terminates for n≥0 and identify exactly why the proof fails if negative n is accepted.
3. Draw naive fib(5)'s call tree, mark duplicate fib(2) computations, and compare to memoization.
4. Use a recursion tree to derive Θ(n log n) from T(n)=2T(n/2)+Θ(n) for powers of two.
5. Replace factorial recursion with a loop and explain why its stack usage changes to O(1) auxiliary space under the same integer arithmetic assumptions.

**Related reading:** [Stacks and queues](/en/topics/stacks-queues/) introduce LIFO behavior; [complexity analysis](/en/topics/complexity-analysis/) provides recurrence models; [sorting](/en/topics/sorting-algorithms/) implements divide-and-conquer concretely.
