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

**Newly published:** `software-project-lifecycle` traces a privacy-sensitive export from requirements through review, release, telemetry and postmortem; `algorithm-interview-workshop` derives rooms-by-heap and shortest signed-subarray-by-deque with bounded exhaustive oracles; `system-design-interview-workshop` develops a multi-tenant webhook service with controlled requirement changes and queue recovery. New follow-ups published: `concurrency-interview-workshop`, `failure-recovery-workshop`, and `maintainable-implementation-workshop` expand interleaving exploration, crash injection and testable state ownership. Now also published: `cpp17-concurrency-implementation` compiles and runs a native threaded bucket; `sqlite-multiprocess-recovery` launches independent Python workers with a durable database file and a postcommit hard-exit test; `independent-coding-assessment` supplies two unsolved original graph challenges and a public grading harness. Production-grade cross-service testing, unseen private cases, and expert review remain needed. Publication is not proof of interview readiness.

## P1 — Problem-solving and coding competency

Already published: `recursion-call-stack`, `sorting-algorithms`, `two-pointers-prefix-sums`, `greedy-intervals`, `monotonic-stacks`, `tree-algorithms`, `algorithm-interview-workshop`, `independent-coding-assessment` (unsolved starter and public grader), `binary-search`, `sliding-window`, `dynamic-programming`, `backtracking-search`, `graph-traversal`, `shortest-paths`, `strongly-connected-components`, `maximum-flow-matching`.

Still required: repeated unfamiliar problems, timed review of greedy, monotonic-stack and tree algorithms; boundaries, duplicates, overflow, adversarial complexity, language-specific collections and mutation semantics. Published workshops increase coverage but independent reasoning remains essential.

**Chapter contract:** describe input/output, invariant, an algorithm, proof or correctness argument, worst-case and memory, counterexample and executable tests in EN/PT.

## P1 — Software engineering and object-oriented design

**Now published:** `object-oriented-design` (identity, encapsulation and composition); `solid-dependency-inversion` (all five principles, behavioral substitution and ports); `testing-strategies` (unit, property, integration, contract and E2E scopes); `testing-maintainability`, `low-level-design`, `concurrency-synchronization` and `production-incident-response`.

**Additional published EN/PT chapters:**
- `debugging-profiling` — minimize failures, prove a binary-search invariant, measure CPU/memory and use operational tracing.
- `ci-cd-release-engineering` — immutable artifacts, automated gates, cautious canary evaluation, schema expand/migrate/contract and rollback.
- `refactoring-design-patterns` — behavior-preserving changes, Strategy, Adapter and comparison with Decorator.

**Additional published chapters:** `software-project-lifecycle` (discovery through operational learning); `concurrency-interview-workshop` (deterministic schedules, CAS and locks); `failure-recovery-workshop` (transactional-outbox fault injection); `maintainable-implementation-workshop` (Python token bucket and testable clock); `cpp17-concurrency-implementation` (g++-compiled C++17 token bucket, native threads and mutex); `sqlite-multiprocess-recovery` (independent processes, SQLite file, post-commit hard exit, durable replay). Cross-process tests are real for local SQLite but not a validation of networked PostgreSQL or external brokers.

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

**Additional published EN/PT:** `service-boundaries` — modular monoliths versus microservices, synchronous failure, consistency, events and gradual extraction.

**Additional published chapter:** `system-design-interview-workshop` — original webhook delivery design, changing tenant skew and ordering requirements, quantitative retry/backlog analysis, security, and recovery questions.

**Practice still required:** justify storage choices under changed workloads; design order cancellation races; scale feeds under skew and privacy requirements. Beyond tested SQLite process termination, verify real networked database/broker failure modes and private unseen coding cases. Independently solving fresh design prompts remains essential.

Advanced chapters such as `raft-consensus`, `memory-ordering-atomics` and `formal-model-checking` are **optional enrichment** until the core path is complete.

## Review and completion definition

- Every required topic must have a **published, bilingual independent chapter**, not a mere mention in a long table.
- Articles should include original examples, verified source attribution, complexity/assumptions and anti-patterns.
- Every system design case should present *requirements → capacity estimates → API and data model → architecture → consistency and failures → alternatives → validation*.
- For code, CI runs Python fences in both languages; diagrams and other languages need additional relevant validation before claiming execution.
- Tracks should list only published article IDs; `planned_topics` remains honest about gaps.
- Passing CI establishes syntactic/build checks, not theoretical correctness or suitability for a real interview.


## Verification added in this edition

- The published `examples/cpp/token_bucket.cpp` is compiled using `g++ -std=c++17 -Wall -Wextra -Werror -pthread` and executed by `tests/test_cpp_token_bucket.py` on the Linux runner. The C++ source asserts deterministic refill behavior and a twelve-thread shared-bucket quota. This is **compiled native code**, not merely a Markdown snippet.
- `examples/python/sqlite_process_race.py` and `tests/test_sqlite_multiprocess.py` create an actual file-backed SQLite authority. Two separate OS processes compete for a conditional reservation. Another process exits with code 23 after commit, and a new process confirms durable idempotent replay.
- `examples/python/unsolved_drills.py` intentionally retains `NotImplementedError`; `examples/python/drill_grader.py` contains twelve public baseline cases. CI confirms the grader catches wrong answers, **not** that either unsolved problem has already been implemented.
- CI success does not prove business correctness for all interleavings, crash modes or compiler/OS combinations. `EDITORIAL.md` still requires human technical review and honest limitations.


## New integration edition: actual PostgreSQL and RabbitMQ services

- `postgresql-concurrency-integration` (EN/PT): PostgreSQL 17 on GitHub Actions, independent checkout processes, conditional stock update, transaction with outbox, replay after postcommit process exit and conflicting operation keys. Executable CLI: `examples/python/postgres_checkout.py`, tests: `tests/test_postgres_integration.py`.
- `rabbitmq-durable-consumer-integration` (EN/PT): RabbitMQ 4 service and PostgreSQL inbox in the same CI build. Test: `tests/test_rabbitmq_postgres_integration.py`; creates a durable queue, publishes with confirms, commits an inbox effect, disconnects before ACK, observes redelivery, and verifies no duplicate effect.
- `adaptive-system-design-assessment` (EN/PT): hypothetical multi-tenant document-processing design with changing load, noisy neighbors, outages, geographic residency, deletion races and measurable recovery objectives. Its numbers are **examples**, not performance claims.
- Required packages: `psycopg[binary]` and `pika`; service containers defined in `.github/workflows/pages.yml`.
- Verified boundary: two real services on one Linux CI runner and a single broker node. **Not tested:** PostgreSQL leader failover or durability under power loss; RabbitMQ clustered quorum and broker disk crash; production tenant credentials and TLS; distributed end-to-end exactly-once effects.
- Interview drills are original; publishing and validating tests do not establish readiness for unfamiliar interviews.


## Edition: adversarial property tests, PostgreSQL SSI and broker restart

- `property-based-algorithm-testing`: Hypothesis-generated lists and targets exercise EN/PT binary-search bounds and signed-subarray deque implementations against independent `bisect` and quadratic oracles. The test is `tests/test_property_based_sde_algorithms.py`. This is **sampled testing**, not formal proof and not a hidden private OA grader.
- `postgresql-serializable-retry-lab`: two independent PostgreSQL connections synchronize reads with `threading.Barrier`; READ COMMITTED permits both doctors to leave (write skew), while SERIALIZABLE aborts one with 40001. The failed operation re-runs the **entire transaction** and is then denied. Source `examples/python/postgres_serializable_lab.py`; test `tests/test_postgres_serializable.py`.
- `rabbitmq-broker-restart-lab`: the separate CI step `scripts/verify_rabbitmq_restart.py` publishes a persistent message to a durable classic queue with publisher confirmation, restarts **the same** RabbitMQ Docker container, then reconnects and retrieves the original message by ID. This tests single-node process/container restart with preserved storage, **not** quorum replication or data-center failure.
- `system-design-architecture-review`: systematic order-system critique with overselling, non-atomic dual writes, PSP ambiguous outcomes, quota isolation, capacity and queue recovery arithmetic.
- Pending reference-grade work: independent human review, unknown assessments without solutions, multi-node PostgreSQL replication/failover, RabbitMQ majority-election under node loss, network partitions and full production security validation. CI pass confirms the described exercises only.


## New physical replication and distributed quorum laboratories

- `rabbitmq-quorum-leader-failover` (EN/PT): `scripts/verify_rabbitmq_quorum.py` provisions three independent broker containers on one ephemeral GitHub runner, joins the nodes, declares an explicitly three-member quorum queue, confirms a persistent publication, stops its first broker, recovers the exact message via a survivor and publishes again through the surviving majority. **No** two-node loss, network partition, independent-host failure or data-center recovery is asserted.
- `postgresql-streaming-promotion` (EN/PT): `scripts/verify_postgres_promotion.py` creates distinct primary/standby PostgreSQL 17 data volumes, runs real `pg_basebackup -R`, waits until a marker row is visible after WAL replay, stops the old primary, runs `pg_promote`, and verifies a second committed insert. This demonstrates **manual** promotion after a stopped primary and **observed** replay for the marker, not automatic leader fencing or zero-loss asynchronous failover.
- `independent-coding-assessment-ii` (EN/PT): second original unsolved assessment in `examples/python/unsolved_drills_2.py` with minimax contiguous batch capacity and incremental four-neighbor island counting. `examples/python/drill_grader_2.py` contains 18 public fixtures. CI checks the starter/grader setup, **not** solutions to the tasks.
- These experimental tests are resource-intensive and intentionally destructive **only to their disposable Docker containers**. Never run them on shared production services. The publication status is determined by GitHub Actions, not by the presence of files in `main`.
- Further required review: human algorithm/proof review, application client failover, geo-independent fault domains, RPO/RTO measurement, multi-node majority loss, PostgreSQL fencing and rejoin, and adversarial unseen implementation checks.


## Edition: quorum majority-loss, fail-closed fencing and partition models

- `rabbitmq-quorum-majority-loss` (EN/PT): the existing three-node RabbitMQ CI test additionally stops a second voting node, establishes that the last node still accepts AMQP connections, and launches a bounded publisher-confirm probe which **must not positively confirm** a fresh write while a quorum is unavailable. Restarting a second node must restore a fresh confirmed publication. This is a **node-stop** experiment, not an injected network partition. An unconfirmed attempt is **unknown**, not proven lost.
- `postgresql-failover-fencing-gates` (EN/PT): `examples/python/failover_gate.py` and `tests/test_failover_gate.py` check a fail-closed decision model with epoch and receipt validation. `scripts/verify_postgres_promotion.py` also rejects a promotion when `docker inspect` observes the old primary still running, then verifies it stopped before proceeding. The controller's fake receipt is **not** a trusted production fence, and Docker-state inspection cannot prevent an independent restart.
- `network-partition-quorum-models` (EN/PT): `examples/python/network_partition_quorum.py` and `tests/test_partition_quorum_models.py` exhaustively enumerate all **8 undirected link graphs with three members** and **1,024 with five members**, verifying that at most one connected component can have a strict majority. These static, symmetric graphs do **not** simulate Raft election timeouts, asymmetric packet loss or real network isolation.
- Verified evidence is linked to relevant GitHub Actions CI jobs; deployment success is required before calling the chapter updates live.
- **Open requirements:** enforce independent fencing and leadership across control-plane failures; real network partition experiments against RabbitMQ and PostgreSQL; client-routing convergence; PostgreSQL RPO/RTO under unexpected crash; independent host-failure domains; human review and new private coding cases.


## Edition: living-node network isolation and measured PostgreSQL switchover

- `rabbitmq-live-network-partition-lab` (EN/PT): an extension of `scripts/verify_rabbitmq_quorum.py` uses Docker `network disconnect` and `network connect --alias mq3` against a **still-running** RabbitMQ member. The other quorum member remains AMQP-accessible, but its one-member minority must not yield a positive publisher confirmation. After reconnection, a fresh confirmed publication must succeed. Checks on `State.Running`, `RestartCount` and bridge membership distinguish network isolation from a stopped node. This is a Docker bridge partition on one host, not arbitrary packet loss or cross-host resilience.
- `postgresql-failover-rpo-rto-measurements` (EN/PT): `scripts/verify_postgres_promotion.py` now cuts the original primary's Docker bridge connectivity **without stopping its process** and demonstrates a local transactional write using Docker exec; it must still reject promotion until a controlled stop. `scripts/failover_metrics.py` and `tests/test_failover_metrics.py` track monotonic stop, promote and first-write intervals and expose a machine-readable log with known marker replay wait. This measures a **CI-controlled write-restoration interval**, not application RTO or zero-loss RPO.
- Source articles distinguish the source of authority, client uncertainty, failure scope, stable event identity, and replication lag from universal availability claims.
- Open: independent fencing and automatic controller/leader lifecycle, multiple host failure domains, asymmetric firewall/network partitions, performance percentiles, real application-level RTO, quantified loss under unexpected primary crash, and independent human review.
