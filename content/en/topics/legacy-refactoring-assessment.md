---
id: legacy-refactoring-assessment
title: "Legacy-Code Assessment: Characterization, Tenant Scoping and Safe Pagination"
description: "Investigate an intentionally flawed ticket search, characterize its behavior, then implement a corrected, independently graded contract without exposing private fields."
category: interview-practice
difficulty: intermediate
updated: 2026-10-11
prerequisites: [refactoring-design-patterns, testing-strategies, api-security, api-contracts-pagination]
sources:
  - {title: "Martin Fowler — Refactoring Boundary", url: "https://martinfowler.com/bliki/RefactoringBoundary.html", kind: "primary engineering essay"}
  - {title: "Martin Fowler — Self-Testing Code", url: "https://martinfowler.com/bliki/SelfTestingCode.html", kind: "primary engineering essay"}
  - {title: "OWASP API Security Top 10 — Broken Object Level Authorization", url: "https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/", kind: "security reference"}
  - {title: "OWASP API Security Top 10 — Broken Object Property Level Authorization", url: "https://api-security.owasp.org/editions/2023/en/0xa3-broken-object-property-level-authorization/", kind: "security reference"}
  - {title: "Python Documentation — Sorting HOWTO", url: "https://docs.python.org/3/howto/sorting.html", kind: "official language documentation"}
---
This assessment uses a deliberately defective, synthetic ticket-query module. Its purpose is not to make another architectural diagram; it is to inspect executable code, reproduce failures, protect intended contracts and justify a focused correction. The [refactoring chapter](/en/topics/refactoring-design-patterns/) explains how internal restructuring differs from externally observable behavior changes. That distinction is essential here: **fixing wrong pagination, removing private fields and rejecting invalid input changes the old behavior**. First characterize the existing program; then implement a new, explicitly corrected contract. Do not claim that the entire exercise is behavior-preserving refactoring [1].

The repo contains a [legacy implementation](https://github.com/christianrss/manual/blob/main/examples/python/legacy_ticket_search.py), an [unsolved replacement](https://github.com/christianrss/manual/blob/main/examples/python/refactor_ticket_search.py) and a [public contract grader](https://github.com/christianrss/manual/blob/main/examples/python/ticket_search_grader.py). These are teaching artifacts using fictional data, not a deployable access-control system. The replacement deliberately raises `NotImplementedError`; no completed solution is published.

## Inspect the legacy behavior before proposing abstractions

The old function `legacy_search_tickets(tickets, tenant_id, status=None, offset=0, limit=10)` sorts the input list **in place** by descending `created_at`, slices it using `offset` and `limit`, filters the resulting window by tenant and status, and returns all fields of each surviving record. It defines `total` as the number of records in that window. It performs no input validation. These actions are observable even when the final list looks plausible.

Set up a reproducible baseline with four records: `a1` (tenant a, open, timestamp 10), `b1` (tenant b, open, timestamp 30), `a3` (tenant a, open, timestamp 20) and `a2` (tenant a, closed, timestamp 20). Ask tenant a for `offset=0, limit=1`. The legacy implementation sorts all four records, takes the highest timestamp belonging to tenant b, **then** removes it: `{"items":[],"total":0}`. A correct tenant-scoped query should find three matching records and return `a2` first under the new tie-breaker. The earlier response is a bug, not a valid empty dataset.

A characterization test captures precisely the **current** flawed output so that a reviewer can identify what is changing. A specification test captures the **required new** result. Do not rewrite legacy assertions to expect secure behavior while they still call the buggy module. Fowler's work emphasizes defining the refactoring boundary and using automated tests to detect unintended effects [1][2].

## State the target contract independently of the code

Implement `search_tickets(tickets, tenant_id, status=None, offset=0, limit=10)` in the separate unsolved module. It must return a dictionary with exactly two keys: `items`, a list of fresh public records, and `total`, an integer count **before pagination**.

`tickets` is a list or tuple of dictionaries. Each dictionary has required fields `id`, `tenant_id` and `status` (all nonempty, case-sensitive strings), plus `created_at` (nonnegative integer timestamp, excluding Python booleans). Additional input fields may exist but must never reach public output. A ticket ID may be repeated in a different tenant, but it must be unique **within one tenant across the entire input**. Any violation, including a malformed row in another tenant, must raise `ValueError`.

The caller-supplied tenant must be a nonempty string obtained from a **trusted, authenticated server-side context**. `status=None` means no status filter; otherwise status must be a nonempty string. `offset` must be an integer at least zero; `limit` an integer between 1 and 100 inclusive. Booleans are invalid in numeric parameters. Reject invalid values with `ValueError` before exposing results or modifying any input.

## Filter before pagination and define deterministic order

First select records belonging to the trusted tenant and matching the optional status. Then sort matches by `created_at` **descending** and, for equal timestamps, by `id` **ascending**. Finally slice that ordered list with the requested offset and limit. Count all matches before slicing. Each output item must contain **exactly** `id`, `status` and `created_at`; no `tenant_id`, `owner_email`, `internal_note` or other unlisted fields may be returned.

For the four-ticket example, the complete result for tenant a is `[a2,a3,a1]`, with total 3. A first page with limit 1 is `[a2]`; an offset of 1 returns `[a3]` but retains total 3. Filtering to status `open` yields `[a3,a1]`, total 2. If offset exceeds the available match count, items is empty while total still describes the matching dataset. Sorting by timestamp alone is insufficient when records tie: Python preserves relative input order in stable sorts, but that input order is **not the specified second sort key** [5].

A data query must not treat pagination as an authorization boundary. OWASP identifies object-level access control failures and inappropriate property exposure as distinct API security risks [3][4]. This exercise requires an explicit allowlist of output properties, rather than returning copies of the entire internal record and hoping the caller hides sensitive fields.

## Mutation, validation and authority boundaries

The input list, individual ticket dictionaries and nested caller-owned structures must remain unchanged after **every** call, including calls that raise. Sorting the original input in place violates this condition even if the output is otherwise correct. Returning the very same dictionary objects also violates the contract: callers may modify a response row and unexpectedly alter their repository's source data. The public grader checks caller-side mutation and output aliasing on representative cases.

A local Python function comparing `row["tenant_id"]` against a string does **not** authenticate a tenant or prove access rights. In a production service the authenticated principal, allowed tenant scope, fine-grained authorization and storage query must be controlled by trusted boundaries. A user-editable URL parameter cannot simply be treated as an authoritative tenant identity. For actual persistent systems, tenant filtering should be enforced at the authoritative storage/query boundary, and authorization should be checked for each object and exposed property [3][4].

Validation of records across the full input is required even if a queried tenant has no tickets. This guarantees deterministic rejection of malformed datasets and duplicate IDs rather than allowing malformed rows to remain invisible until another query. It also makes the contract intentionally stricter than typical best-effort search APIs, which may instead reject errors during ingestion; that architectural choice must be acknowledged.

## Complexity and alternatives without pattern inflation

Let `n` be the number of input rows and `m<=n` the number matching the tenant and status. A straightforward validation pass plus sorting selected rows requires `O(n+m log m)` comparison-model time and `O(n)` additional storage, which satisfies the target `O(n log n)` time and `O(n)` space. Python's arbitrary-precision integer and string-comparison costs add bit or character costs absent from the unit-cost model. State your assumptions rather than calling all operations constant-time.

For a high-volume production endpoint, offset pagination can become expensive or unstable as records change between requests. A cursor tied to a total ordering may be preferable, but implementing it would be **a different API contract**; do not silently replace `offset` with a cursor in this exercise. Likewise, adding a Repository, Strategy, Factory or dependency-injection framework solely to wrap one deterministic function is not inherently better than a cohesive function with clear preconditions and separated concerns. Discuss extraction only where it enables reuse, isolation, or demonstrably simpler testing [1].

## Run the characterization and contract checks separately

From the repository root, execute:

~~~bash
python -m unittest tests/test_legacy_refactoring_assessment.py -v
python examples/python/ticket_search_grader.py
~~~

The first command runs characterization and grader-quality tests; it is intended to pass **while the replacement remains unsolved**. The second command intentionally raises `NotImplementedError` until you implement the candidate. After implementing the candidate, rerun the public grader; it checks valid and invalid inputs, match counts, ordering, projection, immutability and edge conditions. These visible fixtures are not hidden or independently proctored tests.

Write additional cases before changing the candidate: a different-tenant record newer than all visible records; duplicate IDs in a tenant that is **not** requested; zero timestamps; same-timestamp IDs in reversed input order; invalid status; `offset` beyond the last page; a tuple input; a limit of exactly 100; and privacy fields that must be omitted. Include a test that mutates a returned row and verifies source rows stay unchanged. A test suite is a sampling mechanism, not a proof that every possible input is safe.

## Exercises and verification

1. **Trace the old defect:** explain why the first page can be empty even when tenant a has three tickets. Which invariant did pagination violate? **Check:** filtering must precede taking a tenant's page, and total counts pre-page matches.
2. **Write characterization evidence:** give the legacy result for the sample with limit 1 and the new required result, labeling each distinctly. **Check:** legacy items empty, total 0; required item a2, total 3.
3. **Explain a privacy boundary:** why is returning the entire internal ticket dictionary unacceptable even after the correct tenant filter? **Check:** authorization to an object does not entail permission to every property [4].
4. **Design an unseen test:** insert two equal-timestamp tickets in reverse ID order. Which tie-breaker is required? **Check:** identifier ascending, irrespective of caller list order.
5. **Assess an attempted fix:** replacing `tickets.sort(...)` with `sorted(tickets,...)` removes mutation but leaves the selection-before-filter bug and private-field exposure. State which tests would still fail.
6. **Production review:** identify the trustworthy source of tenant identity, where row-level authorization must execute, and why an in-memory demonstration cannot prove database-backed isolation.

The deliverable is the candidate function, independent tests, a concise defect-to-contract comparison and a change explanation. Do not modify or ship the intentionally defective legacy file as a production implementation. The exercise measures disciplined bug correction and code review, not stylistic pattern-counting.
