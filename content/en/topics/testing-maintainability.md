---
id: testing-maintainability
title: "Testing, Contracts and Maintainable Changes"
description: "Build correct, reviewable changes using invariants, test boundaries, integration contracts, regression cases and explicit operational risk analysis."
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis]
sources:
  - {title: 'Google Engineering Practices — Code Review', url: 'https://google.github.io/eng-practices/review/', kind: engineering guidance}
  - {title: 'Martin Fowler — The Practical Test Pyramid', url: 'https://martinfowler.com/articles/practical-test-pyramid.html', kind: engineering article}
---
Maintainability is not equivalent to maximizing abstraction or maximizing test count. It is the ability to change behavior safely, understand what can break and obtain trustworthy feedback. The central question for a code change is: **which invariants must remain true before and after the change?** [1].

## Contracts before tests
A function contract consists of allowed inputs, outputs, errors, side effects and externally observable constraints. For an API, it also covers authorization, version compatibility, response codes, idempotency and timeouts. Without a contract, "tests pass" may only mean a mistaken implementation agrees with mistaken tests.

Take a reservation command. Invariants might include: a seat is assigned to at most one confirmed reservation; retrying the same idempotency key cannot create a second charge; and any emitted confirmation must refer to durable committed state. These invariants map to different test boundaries.

## Choose the narrowest reliable test
| Boundary | What it demonstrates | What it cannot prove alone |
| --- | --- | --- |
| Unit test | Function behavior under controlled inputs | Real DB constraints, network failures |
| Integration test | Compatibility with DB, queue or service | End-to-end product requirements |
| Contract test | Producer/consumer interface compatibility | Business correctness of every consumer |
| End-to-end test | A meaningful customer workflow | All rare race conditions or internal branches |
| Load/fault test | Behavior under measured pressure/failure | Logical correctness for all inputs |

A healthy suite combines these; no single layer substitutes for all others. The test pyramid is a heuristic favoring many fast focused checks and fewer slow end-to-end checks, not a universal numerical prescription [2].

## Example: integer interval merging
Given closed intervals `[start,end]`, including touching endpoints, merge any intervals that overlap. The input contract requires `start ≤ end`. A key invariant is that after each iteration, all processed intervals are represented by sorted, mutually disjoint merged intervals.

```python
def merge_closed_intervals(intervals):
    if any(start > end for start, end in intervals):
        raise ValueError('reversed interval')
    result = []
    for start, end in sorted(intervals):
        if not result or start > result[-1][1]:
            result.append([start, end])
        else:
            result[-1][1] = max(result[-1][1], end)
    return result

assert merge_closed_intervals([(1,3),(3,4),(8,9)]) == [[1,4],[8,9]]
assert merge_closed_intervals([]) == []
assert merge_closed_intervals([(4,4)]) == [[4,4]]
```

Sorting ensures that an incoming interval cannot begin before previously considered starts. If `start > previous_end`, it is disjoint; otherwise it overlaps the last merged interval, and extending that interval preserves the invariant. Complexity is `O(n log n)` time for sorting and `O(n)` output space. The amount of additional temporary sorting memory depends on the runtime implementation.

## Review and operational safety
A useful review asks whether the behavior is correct, whether the abstraction actually simplifies change, whether tests exercise boundaries, and whether monitoring can detect regressions [1]. Before a risky deployment: define the rollback method, migration compatibility, feature gating, metrics and acceptance threshold.

Avoid tests that assert only the current internal implementation structure. Prefer observable outcomes and invariants so that refactoring does not require rewriting every test. Mocking every dependency can remove the exact integration behavior that matters most.

## Partition the input space before implementing

A reliable suite comes from the contract, not from arbitrary happy-path samples. Divide inputs into equivalence classes (valid, invalid, boundary and malformed), then identify transitions between them. For interval merging, distinguish empty input, one interval, disjoint intervals, overlaps, touching closed endpoints, reversed endpoints, duplicates and deeply nested intervals. Each case tests a separate premise. Test implementation independence: checking that a mocked helper was called does not prove that the final interval representation is correct.

## Property-based reasoning for interval merging

For a returned list `out`, establish at least four properties: (1) each output interval has start ≤ end; (2) outputs are ordered by start; (3) adjacent outputs are strictly separated under the closed-interval rule; and (4) the union of covered points equals that of the original intervals. Properties (1)-(3) can hold while (4) fails if an interval is accidentally dropped. In a small bounded domain, compare membership of each integer point to a simple oracle as an independent regression check.

```python
def covered(intervals, point):
    return any(start <= point <= end for start,end in intervals)

for sample in ([], [(1,3)], [(1,3),(3,5)], [(1,10),(2,4)], [(8,9),(1,2)]):
    output = merge_closed_intervals(sample)
    assert all(a <= b for a,b in output)
    assert all(output[i][1] < output[i+1][0] for i in range(len(output)-1))
    assert all(covered(sample,p) == covered(output,p) for p in range(-1,12))
```

## Contract tests and compatibility

An API contract includes more than a JSON shape: status codes, pagination stability, timeouts, auth semantics and idempotency guarantees may be observable behavior. Consumer-driven contract tests can detect incompatible schema changes, but a green schema test does not establish that a booking is never charged twice. Persisted invariants belong in database integration tests with concurrency; resilience belongs in failure-injection tests. Use deterministically controlled clocks for expiry tests and compare exact semantic behavior, not timing flukes [2].

## From pull request to rollback

A robust change description should state why it is needed, affected interfaces, backward-compatibility plan, migration ordering, observability signals and rollback trigger. For schema migration, use expand/migrate/contract when old and new application versions coexist: add a compatible field, backfill or dual-read as justified, switch readers and only then remove obsolete fields. Rollback becomes unsafe if new writes cannot be interpreted by the old version. Design and rehearse a recovery path *before* deploying.

## What automated checks cannot prove

Unit tests can demonstrate specified examples and properties, but finite tests do not establish universal correctness. High line coverage may coexist with weak assertions, missed races or untested operational behavior. Security review, load tests, static analysis and production observability add different evidence. Likewise, more abstraction is not a virtue in itself; an interface should express a genuinely varying contract, not merely mirror a concrete class [1].

## Exercises and verification
1. Change the contract from closed intervals to half-open intervals `[start,end)`. Does `[1,3)` overlap `[3,5)`? No; the merge condition must change accordingly.
2. Test duplicate events in a reservation consumer; a unit test with a mock queue is insufficient to prove the real DB's uniqueness enforcement.
3. In a code review, ask: what changes for clients, which failure can occur, what metric would reveal it, and which test demonstrates the invariant?

Code quality is ultimately demonstrated by understandable behavior under change, not by the number of layers or design patterns used.
