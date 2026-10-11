---
id: logic-proofs-invariants
title: "Logic, Proof Techniques and Loop Invariants"
description: "Build precise program arguments with propositions, quantifiers, counterexamples, induction, loop invariants and termination proofs."
category: foundations
difficulty: foundational
updated: 2026-10-10
prerequisites: []
sources:
  - {title: "MIT 6.042J — Mathematics for Computer Science", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/", kind: "university course and open textbook"}
  - {title: "Python Language Reference — Expressions", url: "https://docs.python.org/3/reference/expressions.html", kind: "official language reference"}
---
An algorithmic argument must separate what is required, what a program actually does, and what has been proved. A sample run demonstrates behavior for one input; it does not establish correctness over an input domain. Discrete logic supplies the language for precise statements, while invariants and termination arguments connect those statements to executable loops. The same methods apply to data structures, concurrency protocols and system-design invariants. MIT's discrete mathematics course develops propositions, proofs, sets, functions and state machines as foundations for computer science [1].

## Propositions, domains and logical operators

A **proposition** is a statement with a truth value. Let P mean "the list is sorted" and Q mean "the binary-search result is correct." The implication P ⇒ Q is false only when P is true and Q is false; it does not claim that P is true. Therefore, proving an algorithm under a sorted-input precondition cannot justify calling it on an arbitrary unsorted list. Distinguish logical implication from causation and from code-level control flow.

Negation reverses truth; conjunction P ∧ Q requires both propositions; disjunction P ∨ Q requires at least one. A truth table for implication clarifies the often-misread false-premise cases:

| P | Q | P ⇒ Q |
| --- | --- | --- |
| False | False | True |
| False | True | True |
| True | False | False |
| True | True | True |

The **converse** Q ⇒ P is not equivalent to P ⇒ Q. The **contrapositive** ¬Q ⇒ ¬P is equivalent. For example, "if an integer is divisible by four, it is even" is correct; "if it is even, it is divisible by four" is false, as six shows. This one counterexample disproves the universal converse.

## Quantifiers and the order of claims

A statement ∀x∈D, P(x) asserts P for *every* x in the domain D. A statement ∃x∈D, P(x) needs only one witness. Negation exchanges the quantifiers: ¬(∀x P(x)) is equivalent to ∃x ¬P(x). An engineer claiming "all retries are safe" has a universal obligation; observing a successful retry is existential evidence, not proof.

Quantifier order matters. "For each request there exists a suitable worker" (∀r ∃w) does not imply "one worker handles all requests" (∃w ∀r). For the first statement, the worker may depend on the request; for the second, a single worker must work for every request. Many scalability mistakes arise from silently interchanging these obligations.

In code reviews, always name the domain: all integers, nonnegative integers, all byte strings, or all requests admitted by a validated API. Without a domain, a mathematical statement is often ambiguous. Python also has operational semantics: the operands of and/or are evaluated with short-circuit rules and can return an operand rather than a Boolean; do not confuse a mathematical connective with arbitrary object truthiness [2].

## Preconditions, postconditions and total correctness

A **precondition** describes admissible initial states. A **postcondition** describes required final states. Partial correctness means that if execution terminates from a state satisfying the precondition, its result satisfies the postcondition. **Total correctness** adds termination. Naming both obligations prevents the common shortcut "the answer is right whenever my loop finishes" when the loop might run forever.

Consider a function that returns the first index containing target in a sequence. Its precondition might allow any finite sequence supporting equality comparisons; its postcondition should state either a valid index whose element equals target and no earlier element matches, or -1 if no element matches. If the function promises only any matching index, its proof obligation is weaker. These are different interfaces.

Formal contracts are not identical to runtime validation. A Python assertion used to illustrate a mathematical property is not a safe substitute for unconditionally enforced input checks: Python can remove assert statements in optimized execution. A production boundary must validate untrusted inputs explicitly [2].

## Induction and structural reasoning

Mathematical induction establishes P(n) for all natural n: prove a base case, assume P(k), and prove P(k+1). For a loop, this is mirrored by initialization, maintenance and termination. For recursive structures, prove the empty or leaf case and then the constructor or recursive step. These methods are a way to audit every transition, not simply a formalism added after code is written [1].

As an example, the sum of the first n nonnegative integers is n(n−1)/2. At n=0 both sides are zero. Assuming the formula holds for n=k, adding the new term k gives k(k−1)/2 + k = k(k+1)/2, which is the formula for n=k+1. The proof covers all natural n. It does not assert that fixed-width machine arithmetic cannot overflow.

A counterexample is often faster than a proof attempt. To reject "greedy always finds the minimum number of coins," use denominations 1, 3, 4 and target 6: greedy selects 4+1+1 (three coins), while 3+3 uses two. An algorithm may be correct under a canonical coin system but fail for arbitrary denominations.

## Worked loop invariant: first occurrence

For a sequence of n elements, maintain index i and claim **all indices j below i fail to match target**. Initially i=0, so the range is empty and the statement is vacuously true. If the inspected element is not a match, incrementing i preserves the claim. If it matches, no earlier position matches and the return index is minimal. If the loop reaches n, every candidate has been excluded, so -1 is correct. A decreasing variant n−i is a nonnegative integer, and it decreases on every non-returning iteration, establishing termination.

~~~python
def first_index(items, target):
    i = 0
    while i < len(items):
        if items[i] == target:
            return i
        i += 1
    return -1

assert first_index([], 7) == -1
assert first_index([3, 7, 3, 7], 7) == 1
assert first_index([3, 3, 3], 3) == 0
assert first_index([1, 2, 3], 4) == -1
~~~

The runtime is O(n) in the worst case and O(1) auxiliary memory for a random-access sequence when equality costs O(1), where n is sequence length. If comparisons are expensive or have side effects, both the cost model and the proof need revision. The function does not modify the input; it assumes the sequence is not concurrently mutated during the scan.

## A stronger example: binary search and the candidate interval

For a finite **sorted, nondecreasing** sequence, seek the first position whose value is at least target. Maintain a half-open candidate interval [lo, hi), with the invariant that all indices below lo contain values strictly smaller than target, and all indices at or above hi contain values at least target. The latter is initially vacuous because hi=n. At midpoint m, if items[m] is smaller, every element through m is smaller and lo can become m+1. Otherwise, the answer is at m or earlier and hi can become m. The interval shrinks each iteration.

~~~python
def lower_bound(items, target):
    lo, hi = 0, len(items)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if items[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo

for xs in ([], [1], [1, 1, 3, 3, 9], [-5, -1, 0]):
    for value in range(-6, 11):
        expected = sum(x < value for x in xs)
        assert lower_bound(xs, value) == expected
~~~

At exit lo=hi, so the two exclusion claims identify the first valid index, or n when none exists. The variant hi−lo is nonnegative and strictly decreases. Runtime is O(log(n+1)) comparisons and O(1) auxiliary space under constant-time indexed access. On an unsorted list, the sorted-input precondition fails and neither the proof nor the result is reliable.

## Verification, falsification and proof boundaries

A proof is only as strong as its stated assumptions and the fidelity of the implementation to the proved model. Exhaustive enumeration over a finite domain can establish a property *within that domain*, while randomized tests may discover counterexamples but do not prove universal correctness. Testing and formal reasoning therefore complement rather than replace each other.

For the lower-bound example, enumerate short sorted arrays over the alphabet {-1, 0, 1}, compare the result to a linear oracle and inspect empty inputs, duplicate values, missing targets and extremes. An independent implementation of the specification is preferable to copying the same midpoint logic into the oracle. A model that assumes immutable inputs cannot establish correctness under concurrent mutation.

## Exercises

1. Negate the exact statement ∀x∈D, ∃y∈E, R(x,y). **Answer:** ∃x∈D, ∀y∈E, ¬R(x,y), including the chosen domains.
2. Find the first occurrence of an integer in a finite sequence and state initialization, maintenance, exit postcondition and a strictly decreasing termination variant. **Check:** the proof above applies to sequential equality comparisons.
3. Give a counterexample to "if a function terminates, it is correct." **Answer:** a function that returns 0 for every input terminates, but fails a contract requiring the input's square when input=2.
4. For the binary-search routine, explain why hi is initialized to n instead of n−1. **Answer:** the half-open interval must permit the valid insertion position n and maintain a well-defined empty interval for an empty list.

These exercises establish proof habits, not a claim of competence on unseen, independently assessed coding problems.