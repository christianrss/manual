---
id: programming-control-flow-functions
title: "Programming fundamentals: control flow, functions and loop invariants"
description: "Learn branches, loops, functions, scope and invariants by tracing a complete linear-time array algorithm with boundary tests."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: []
sources:
  - {title: "Python tutorial — Control flow tools", url: "https://docs.python.org/3/tutorial/controlflow.html", kind: "official programming tutorial"}
  - {title: "Python language reference — Compound statements", url: "https://docs.python.org/3/reference/compound_stmts.html", kind: "official language reference"}
  - {title: "Python language reference — Execution model", url: "https://docs.python.org/3/reference/executionmodel.html", kind: "official language reference"}
---
A program executes **statements in a defined order**, evaluates expressions, and changes which statement comes next with branches, loops and function calls. These ideas precede classes, patterns, databases and distributed systems. Without them, even a simple algorithm can look plausible while mishandling empty input or repeating a calculation unnecessarily. Python provides an explicit control-flow model in its tutorial and language reference [1][2]. This chapter develops the mechanics rather than introducing a framework.

## Expressions, conditions and branches

An *expression* produces a value. A *statement* controls execution or changes bindings and state. For example, `quantity > 0` evaluates to a Boolean; `if quantity > 0:` uses that result to select a block. An `else` block runs when the condition is false. Python uses indentation to delimit a block; indentation is part of the syntax, not a stylistic brace replacement [1].

Distinguish a predicate from its side effects. `if items:` asks whether a container is truthy, whereas `if items is None:` asks whether it is the distinct missing-value object. They are not interchangeable: an empty list may be a valid request, but None may be invalid. A condition should express the intended domain question. Use explicit comparisons when falsy-but-valid values like zero, empty strings or empty collections must be distinguished from absent input.

## Loops, progress and termination

A `for` loop consumes elements from an iterable; `range(1, n)` generates integers from 1 through n−1. A `while` loop evaluates its condition before each iteration. Either can fail to terminate if the state controlling progress never changes. A termination argument identifies a **variant** such as the number of unprocessed elements, which decreases until it reaches zero. The language's semantics also govern `break`, `continue` and loop `else` clauses [2].

An invariant is a statement that remains true at a chosen point in every iteration. To reason about a loop, prove initialization (true before the first iteration), maintenance (one iteration preserves it) and termination (the final invariant implies the desired result). This method is the programming-level counterpart of mathematical induction. It is especially useful when code maintains indices or two pointers.

## Functions, parameters, return and scope

A function gives a computation a name and an input/output contract. A parameter is a local name bound to an argument object at call time; Python does not copy mutable arguments automatically [3]. Therefore `append` on a list parameter can affect a caller's list, while rebinding the local name does not alter the caller's binding. A clear function contract states accepted types, boundary cases, return value, exceptions and mutation guarantees.

Prefer returning a meaningful result to printing an intermediate value: returning permits composition and independent tests. A return statement exits a function; falling through its end returns None. Variables created inside the function are local under Python's binding rules, unless explicit `global` or `nonlocal` semantics apply [3]. Small cohesive functions are easier to test, but splitting one straightforward loop into ten tiny wrappers can make reasoning harder.

## Worked algorithm: the longest non-decreasing run

Given a sequence of comparable values, find the **earliest longest contiguous** segment in which each next value is at least the previous one. A contiguous segment differs from a subsequence: a segment cannot skip items. Input `[4, 4, 2, 3, 3, 0]` contains runs `[4,4]`, `[2,3,3]` and `[0]`; the answer is start=2, length=3. If several runs tie, return the first. Empty input returns (0,0), an explicit sentinel that cannot be interpreted as a nonempty segment.

The loop processes each adjacent comparison once. `start` and `length` describe the current run, while `best_start` and `best_length` describe the best run completely or partially observed. Updating the best only when `length > best_length` preserves the earliest winner on ties.

~~~python
def longest_non_decreasing_run(values):
    """Return (start, length) for the earliest longest contiguous run."""
    if not isinstance(values, (list, tuple)):
        raise TypeError("expected a sequence")
    if not values:
        return (0, 0)
    start = best_start = 0
    length = best_length = 1
    for index in range(1, len(values)):
        if values[index] >= values[index - 1]:
            length += 1
        else:
            start, length = index, 1
        if length > best_length:
            best_start, best_length = start, length
    return (best_start, best_length)

assert longest_non_decreasing_run([]) == (0, 0)
assert longest_non_decreasing_run([5]) == (0, 1)
assert longest_non_decreasing_run([4, 4, 2, 3, 3, 0]) == (2, 3)
assert longest_non_decreasing_run([1, 2, 0, 1]) == (0, 2)
assert longest_non_decreasing_run([-2, -1, -1, -3]) == (0, 3)
try:
    longest_non_decreasing_run(None)
except TypeError:
    pass
else:
    raise AssertionError("invalid input accepted")
~~~

## Derive correctness, not just example output

Before iteration `index`, the first `index` elements have been processed; the current run ends at `index−1`, and the best pair is the earliest maximal run among those prefixes. If the next item is at least the previous one, extend the current run. Otherwise the previous run ended and a new run begins at the current index. In either case, comparing the current length to the best preserves the invariant. After the last element, the recorded pair is therefore the required earliest longest segment.

Termination follows because the loop visits the finite indices 1 through n−1 exactly once. For n input values the number of comparisons is max(n−1,0), giving O(n) time. The algorithm stores a constant number of indices and lengths, so **auxiliary** space is O(1); it does not copy the input. If comparing elements itself costs more than constant time, the total cost must include those comparison costs. The exception check rejects non-sequences, but deliberately leaves cross-type comparability to Python's comparison semantics.

## Counterexamples and debugging technique

Replacing `>` with `>=` in the best update chooses a later run on ties and changes the public contract. Using `values[index] > values[index−1]` instead of `>=` breaks runs with equal neighbors. Starting `best_length` at zero for nonempty inputs and forgetting its initialization can mishandle single-element sequences. These are algorithmic errors, not matters of style.

Trace a small input on paper using columns for index, current start/length and best start/length. Start with empty and one-element inputs, then ties, repeated values and decreasing sequences. Only after manually explaining the trace should you trust random tests. Exceptions should have precise meanings: invalid container types are different from empty valid input.

## Exercises and verification

1. Trace every variable for `[3,3,1,2,2,0]` and check the result. Predict what changes when the strict comparison is used.
2. Explain why `[1,4,2,5]` cannot return the noncontiguous subsequence `[1,2,5]`.
3. Modify the function to return the actual run without changing the O(n) search bound; explain the additional memory used for the slice.
4. Write a quadratic reference algorithm that enumerates every starting index and validates extensions; compare its results with the linear version on all sequences of length at most five over values {0,1,2}.
5. Show a function that mutates a list parameter and another that rebinds it; explain the difference without saying Python copies arguments [3].

Next: [arrays and strings](/en/topics/arrays-and-strings/), [complexity analysis](/en/topics/complexity-analysis/) and [loop proof techniques](/en/topics/logic-proofs-invariants/).