---
id: independent-coding-engineering-assessment-iii
title: "Independent Assessment III: Dynamic Programming and Idempotent Event Processing"
description: "Solve two original unsolved exercises on contiguous partition costs and strict idempotent balance projection, with public graders and review criteria."
category: interview-practice
difficulty: intermediate
updated: 2026-10-11
prerequisites: [dynamic-programming, testing-strategies, programming-semantics-contracts, asynchronous-messaging]
sources:
  - {title: "MIT 6.006 — Dynamic Programming Lecture Notes", url: "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2008/pages/lecture-notes/", kind: "university teaching materials"}
  - {title: "Python Language Reference — Standard Type Hierarchy and Mappings", url: "https://docs.python.org/3/library/stdtypes.html", kind: "official language documentation"}
  - {title: "AWS Builders' Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering article"}
---
This workshop tests **independent implementation**, rather than introducing another collection of solved algorithms. The first task is a bounded contiguous partition problem that requires choosing a correct optimization state and proving it. The second is a small state-transition component where correctness includes input validation, event identity, mutation boundaries and deterministic failure. Both are original educational exercises and are **not** reproduced employer assessment questions.

Study the [dynamic programming](/en/topics/dynamic-programming/), [testing strategies](/en/topics/testing-strategies/) and [asynchronous messaging](/en/topics/asynchronous-messaging/) prerequisites before beginning. The same ideas occur in professional coding reviews: deriving a recurrence is useful only when the implementation respects all boundary conditions, while a clean API is insufficient if retries change its effects. MIT's algorithms materials establish the value of a precise state/transition derivation [1]; AWS describes why idempotent request identifiers are central to retried operations [3].

## Assessment setup and deliverables

The [starter file](https://github.com/christianrss/manual/blob/main/examples/python/unsolved_drills_3.py) contains exactly two unimplemented functions. The [public grader](https://github.com/christianrss/manual/blob/main/examples/python/drill_grader_3.py) checks representative valid and invalid cases. Download or clone the repository, implement the functions without changing their signatures, and run:

~~~bash
python examples/python/drill_grader_3.py
~~~

Work from the contract rather than matching fixtures. The grader has visible inputs and expected outputs, and therefore cannot prevent hard-coded responses. It is not a hidden assessment service, a certificate, or proof of interview performance. Suggested local practice: 45 minutes for task A, 30 minutes for task B, and 15 minutes for tests and explanation. This **90-minute exercise allocation is a self-study convention**, not a representation of any particular employer's assessment timing.

Submit code plus a short engineering note containing the input contract, state invariants, complexity bounds, at least one adversarial test created independently, and a meaningful design trade-off. A reviewer should reject a solution that accidentally mutates caller-owned data or misstates an expected-cost lookup as a universal worst-case bound.

## Task A — Minimum penalty for contiguous groups

Given an ordered sequence `loads` of `n` **nonnegative integer** values, partition it into nonempty contiguous groups. Each group contains at most `max_group_size = L` elements. If a group's load sum is `s`, its penalty is `s² + overhead`, where `overhead = h` is a nonnegative integer. Return the **minimum total penalty** across all valid partitions, without returning the groups.

For example, with `loads=[2,3,1]`, `L=2` and `h=2`, three singleton groups cost `(4+2)+(9+2)+(1+2)=20`. The grouping `[2]|[3,1]` costs `(4+2)+(16+2)=24`, while `[2,3]|[1]` costs `(25+2)+(1+2)=30`. The optimum is **20**. Increase overhead to 20, and `[2]|[3,1]` now costs 60, better than the three singletons costing 74. The optimum can change even when loads do not.

The public signature is `minimum_partition_penalty(loads, max_group_size, overhead)`. An empty input returns zero. `loads` must be a list or tuple of nonnegative integers; `L` must be a positive integer; `h` must be a nonnegative integer. Python `bool` is not accepted as an integer under this contract. Invalid inputs raise `ValueError`. Use exact integer arithmetic and do not reorder or mutate the input.

## Model, proof obligations and complexity

An executable solution must distinguish a *partition boundary* from a *group length*. A group ending at exclusive index `i` may start at `j` with `max(0,i-L) <= j < i`. It is tempting to pick the locally cheapest group, but the global optimum need not contain that local choice: a low overhead favors consolidation, whereas the square term penalizes large combined sums.

Define what `dp[i]` means, which earlier states contribute to it, and why every legal final group appears in the choices. A proof should cover the base state before any elements, optimal substructure (otherwise replacing an inferior prefix improves the proposed optimum), and termination because every candidate predecessor is smaller than `i`. This is a reasoning scaffold, **not executable solution code**. Use prefix sums only after explaining the arithmetic work saved.

Under a unit-cost integer model, the intended target is `O(n·min(n,L))` time and `O(n)` extra space. Saying `O(n²)` without incorporating the group bound loses a useful parameter; saying `O(n)` by assuming the best predecessor is always adjacent is generally false. Python's arbitrary-precision integers make the bit cost of huge numbers nonconstant. The published challenge tests outputs; independent benchmarking and source inspection are still required to evaluate performance.

## Task B — Idempotent balance projection

Implement `apply_idempotent_events(opening, events)`. `opening` maps nonempty, case-sensitive account identifiers to nonnegative integer balances in the smallest currency unit. The ordered event sequence contains triples `(event_id, account_id, delta)`, where both identifiers are nonempty strings and `delta` is a signed integer amount.

An event may affect only an account already present in `opening`. Its signed delta must not make that balance negative. The **first** occurrence of an event identifier applies its effect once. A later triple with the **same event ID and identical account and delta** is a retry, and is ignored. Reuse of the event ID with any differing payload is an error, even when the net change would happen to be zero. Event IDs are unique across accounts *within the call*.

Example: starting with `{"a":10}`, events `[("x","a",-3),("x","a",-3),("y","a",3)]` result in `{"a":10}`, not `{"a":7}` and not `{"a":13}`. By contrast, `[("x","a",-3),("x","a",-4)]` is invalid: a duplicated ID cannot silently change intent. Validity checks must reject unknown accounts, malformed event shapes, invalid types, blank identifiers and insufficient balances. Return a fresh dictionary; never mutate the inputs. These choices are part of the API contract, not optional clean-code advice.

## Identity, mutation and transaction boundaries

The processing order is meaningful: an initial zero balance followed by `+5,-5` is allowed, but `-5,+5` fails before it reaches the credit. A solution that sums deltas by account before validation loses the chronological insufficient-funds rule. A solution that compares only IDs and ignores their payload lets accidental ID reuse erase an intended operation. AWS's discussion of idempotent APIs similarly emphasizes stable request identifiers and detecting conflicting intent [3].

Returning a new dictionary gives a narrow **in-memory input immutability** guarantee: if the function raises an error, the caller-owned mapping is unchanged. It does not make the operation durable. There is no database transaction, external side effect, cross-call deduplication, multithreaded lock, or distributed exactly-once delivery here. An actual persistent service would need atomic coordination of the state mutation and the deduplication record, durable identity scope, replay retention policy, authorization and concurrent-writer controls [3].

For `A` accounts and `E` events, the target is `O(A+E)` **expected** operations and `O(A+E)` extra memory, using dictionary lookups under the standard hashing assumptions. Dict semantics and mutable container behavior are specified by Python's documentation [2]. A full guarantee against adversarial hashing or arbitrary-precision bit costs is outside this exercise.

## Review the design, not only the final output

For task A, distinguish objective value from partition reconstruction, expose the work bound in terms of `n` and `L`, and explain why greedy combination fails. For task B, identify the authoritative state, the ID namespace, when validation happens, why retries are skipped, and what the function cannot guarantee. Avoid conflating "idempotent within one function call" with "exactly once across service crashes."

A simple `seen_ids` set is insufficient for task B, because it cannot determine whether a repeated identifier carries a conflicting payload. Likewise, mutating `opening` directly and restoring it after error is unnecessarily fragile: interruption or a missed rollback path could leak partial state to the caller. Maintain a clear separation between input validation, domain state transitions and any infrastructure responsibilities.

## Independent evaluation and counterexamples

Develop additional tests **before** running the grader. For task A, brute-force every way to place cuts for short arrays and compare with the optimized implementation; also vary `L=1`, `L>=n`, empty arrays, all-zero loads, large integers, and high overhead. Enumerating partitions is exponential and should remain an oracle for *small* inputs, not the final algorithm.

For task B, generate unique IDs with randomly chosen signed deltas that preserve nonnegative balances, insert duplicate events at random positions **after** their originals, and verify replay leaves the result unchanged. Inject a conflicting payload with the same ID and require a `ValueError`. Verify that a late error never alters caller-owned data and that replay within one call differs from making a second independent call. Never suppress invalid events silently.

Document two counterexamples per task and derive what they disprove. A passed public grader demonstrates only behavior on its fixtures. The repo intentionally publishes neither completed function nor a private evaluation infrastructure.

## Exercises and verification

1. Enumerate all contiguous partitions of `[2,3,1]` for `L=2`, `h=20`. **Expected minimum:** 60. Explain why the previously best partition at `h=2` changes.
2. For `[0,0,0]`, `L=2`, `h=0`, explain why the result is zero regardless of how zero-cost groups are chosen. Prove an empty input returns zero without creating an empty group.
3. For `{"a":5}`, decide whether `[("x","a",-5),("x","a",-5),("y","a",2)]` is valid. **Expected result:** `{"a":2}`.
4. Determine the outcome of `{"a":1,"b":1}` with `[("x","a",0),("x","b",0)]`. **Expected:** `ValueError` because the second use of `x` conflicts even though both deltas are zero.
5. Propose the smallest change that would make task B safe across process restarts. **Check:** adding a database alone is insufficient; mutation and recorded idempotency outcome must be atomic, and concurrent processing must respect the same authority boundary [3].

The published program supplies a reproducible practice interface. Solving the two tasks independently, writing tests and explaining trade-offs are the evidence of learning—not the number of completed articles.
