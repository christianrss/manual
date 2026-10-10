# SDE II — Coverage and Publication Order

**Review date:** 2026-10-09  
**Audience:** Engineers preparing for the **Software Development Engineer II** interview and assessments. This is an independently curated curriculum, not Amazon material or an endorsement.

Official primary references:
- [SDE II interview preparation](https://amazon.jobs/content/en/how-we-hire/sde-ii-interview-prep)
- [SDE II online assessment preparation](https://amazon.jobs/content/en/how-we-hire/sde-ii-oa-prep)
- [Software development interview topics](https://amazon.jobs/content/en/how-we-hire/interview-prep/software-development-topics)

The employer describes coding, data structures, algorithms, design, maintainable tested implementations, OOP, databases, distributed systems, operating systems and internet topics. **The detailed chapters below are our editorial interpretation**, not a list of exact interview questions or topics promised by Amazon.

## P0 — Essential foundations and data structures

**Now published:**
- `complexity-analysis` — asymptotic costs.
- `arrays-and-strings` — indexing, mutation, Unicode, dynamic growth.
- `recursion-call-stack` — termination proofs, frames and divide-and-conquer recurrences.
- `linked-lists` — pointer manipulation, cycle detection.
- `stacks-queues` — LIFO/FIFO, deques and BFS.
- `binary-trees-bst` — binary trees, traversal, BST invariants.
- `sorting-algorithms` — insertion/merge/quick/heap algorithms, stability and bounds.
- `two-pointers-prefix-sums` — pair search, cumulative sums and subarray counting.
- `hash-tables`, `heaps-priority-queues`, `tries-prefix-search`, `disjoint-set-union` — specialized ADTs.

**Additional core chapters now published:**
- `greedy-intervals` — earliest-finish schedule, exchange proof and weighted counterexample.
- `monotonic-stacks` — next greater, daily temperatures, histogram and amortized analysis.
- `tree-algorithms` — BFS levels, LCA, diameter and ancestor-bound BST validation.

**Next priority:** complete service-boundary decisions, debugging/profiling, safe CI/CD releases and refactoring, then reinforce these systems through targeted design exercises. Storage selection, orders/payment saga and a hybrid social feed have standalone bilingual studies. Published fundamentals require continued technical review.

## P1 — Problem-solving and coding competency

Already published: `recursion-call-stack`, `sorting-algorithms`, `two-pointers-prefix-sums`, `greedy-intervals`, `monotonic-stacks`, `tree-algorithms`, `binary-search`, `sliding-window`, `dynamic-programming`, `backtracking-search`, `graph-traversal`, `shortest-paths`, `strongly-connected-components`, `maximum-flow-matching`.

Still required: deliberate practice with greedy, monotonic-stack and tree algorithms; rigorous tests over empty input, duplicates, overflow, boundaries and adversarial complexity; language-specific collections, reference semantics and mutation; clear explanation of correctness without pseudocode-only solutions.

**Chapter contract:** describe input/output, invariant, an algorithm, proof or correctness argument, worst-case and memory, counterexample and executable tests in EN/PT.

## P1 — Software engineering and object-oriented design

**Now published:** `object-oriented-design` (identity, encapsulation and composition); `solid-dependency-inversion` (all five principles, behavioral substitution and ports); `testing-strategies` (unit, property, integration, contract and E2E scopes); `testing-maintainability`, `low-level-design`, `concurrency-synchronization` and `production-incident-response`.

**Next engineering chapters needed:**
1. `debugging-profiling` — reproducible defects, CPU/memory profiles, instrumentation and regression prevention.
2. `ci-cd-release-engineering` — versioning, code review, automated gates, progressive rollout/rollback and safe schema evolution.
3. `refactoring-design-patterns` — trade-offs with concrete before/after examples and design-pattern failures.

## P1 — System design methodology and worked solutions

Existing: `capacity-estimation`, `caching`, `asynchronous-messaging`, `load-balancing`, `rate-limiting`, `database-consistency`, `api-reliability`, `network-protocols`, `url-shortener` plus advanced internals.

**Newly published EN/PT:**
- `system-design-process` — functional and nonfunctional requirements, explicit estimates, APIs, storage authority, failure cases, measurable validation.
- `api-contracts-pagination` — HTTP method semantics, opaque signed cursors, ETags, idempotent commands, standardized errors and compatibility.
- `data-partitioning-sharding` — partition keys, hotspots, stable rendezvous mapping, migration protocol and global-uniqueness boundaries.
- `system-design-notifications` — full worked multi-channel design, durable transactional outbox, provider ambiguity, backlog math and recovery.

**Newly published end-to-end cases and decisions:**
- `storage-selection` — relational/document/key-value/object/search trade-offs, workload-derived sizing and authority boundaries.
- `system-design-order-service` — atomic stock reservation, checkout idempotency, payment saga, compensation and fulfillment failures.
- `system-design-feed` — read/write fanout, hybrid candidate materialization, privacy filters, cursor pagination and repair.

**Core chapter still needed:**
1. `service-boundaries` — when to split services, synchronous vs asynchronous collaboration, ownership and failure trade-offs.

**Practice still required:** justify storage choices under changed workloads; design order cancellation races; scale feeds under skew and privacy requirements. Publication does not substitute for independently solving new design prompts.

Advanced chapters such as `raft-consensus`, `memory-ordering-atomics` and `formal-model-checking` are **optional enrichment** until the core path is complete.

## Review and completion definition

- Every required topic must have a **published, bilingual independent chapter**, not a mere mention in a long table.
- Articles should include original examples, verified source attribution, complexity/assumptions and anti-patterns.
- Every system design case should present *requirements → capacity estimates → API and data model → architecture → consistency and failures → alternatives → validation*.
- For code, CI runs Python fences in both languages; diagrams and other languages need additional relevant validation before claiming execution.
- Tracks should list only published article IDs; `planned_topics` remains honest about gaps.
- Passing CI establishes syntactic/build checks, not theoretical correctness or suitability for a real interview.
