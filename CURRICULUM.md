# Engineering Manual — Curriculum and Editorial Governance

Review date: 2026-10-10. This manual is an independent educational reference, not official Amazon material or a guarantee of hiring.

## Curriculum, in prerequisite order

1. **Mathematical and computational reasoning:** discrete logic, proofs, number representation, asymptotic complexity, recursion.
2. **Data structures and algorithms:** arrays, lists, stacks, queues, hashing, trees, graphs, sorting, search, dynamic programming, invariants, correctness, edge cases, memory costs.
3. **Engineering and maintainable code:** object orientation, composition, cohesion, coupling, SOLID, Clean Code as context-dependent practices, design patterns, refactoring, testing and debugging.
4. **Computer architecture and operating systems:** machine representation, ISA, CPU, pipelines and caches; processes, threads, scheduling, virtual memory, synchronization, file systems and I/O.
5. **Networks and security:** IP, TCP, UDP, DNS, HTTP, TLS; symmetric and asymmetric cryptography, authenticated encryption, hashes, signatures, key management, authentication, authorization and security threats.
6. **Databases and distributed systems:** SQL, indexes, isolation, persistence, replication, queues, consensus, availability, failure modes and peer-to-peer models.
7. **System design:** requirements, functional and nonfunctional constraints, capacity estimates, APIs, data model, architecture, security, consistency, failure response, cost and testing.
8. **Independent assessments:** unseen coding, refactoring and architecture exercises, timed explanation, behavior-based interviews with factual evidence.
9. **Optional electives:** blockchain, Byzantine models, advanced broker recovery, multi-node failover and niche technology experiments.

This is a dependency graph: reuse is expected across different learning tracks, but a chapter should have one primary subject and stable canonical URL.

## Actual coverage: evidence vs missing material

| Domain | Already published | Not yet adequately covered | Priority |
| --- | --- | --- | --- |
| Data structures and algorithms | Arrays, lists, maps, heaps, trees, graph problems, DP, sorting and search | Independent adversarial unseen exercises, additional proof methods | P0 |
| Software quality and design | Clean Code/cohesion/coupling worked primer, OOP, SOLID, patterns, refactoring, tests and LLD | Broader design-pattern families, independent review, assessed refactorings | P0 |
| System design | Capacity, service boundaries, caching, queues, complete cases | More entry-level-to-intermediate worked reviews and independent evaluations | P0 |
| Computer architecture | No standalone material | Bits, binary arithmetic, ISA, CPU, caches, DRAM and memory hierarchy | P1 |
| Operating systems and concurrency | Processes, virtual memory, locks, atomics | Scheduling, runtime threading, allocation, file systems and I/O | P1 |
| Computer networks | Network protocols survey | TCP/IP in depth, routing, DNS, HTTP and TLS details | P1 |
| Cryptography and security | API security and OAuth/PKCE | Cryptographic primitives, key exchange, AEAD, signatures, certificates | P1 |
| Theory of computation | Asymptotic analysis | Automata, computability, reductions, P, NP and NP-completeness | P2 |
| P2P and blockchain | Distributed quorum and consensus (different subject) | Peer discovery, overlays, Byzantine threat model, blockchain trade-offs | P3 |
| Specialized labs | PostgreSQL and RabbitMQ experiments | Elective only; never a substitute for fundamentals | P3 |

P0/P1/P2/P3 are **editorial priorities**, not official Amazon weightings. Count a chapter as published when it exists, but do not label it academically or professionally mastered without independent evaluation.

## New publication gates

1. **Placement:** one primary module; published prerequisites; stated learning outcome and target level. No disconnected fashionable chapters.
2. **Definition:** state assumptions, types, boundary conditions and meaning of symbols. Explain terms before relying on them.
3. **Derivation:** prove a nontrivial invariant, derive a model or present a falsifiable engineering argument; avoid definition-only pages.
4. **Implementation:** include tested executable code or a reproducible model, complexity and error handling. Tests must check more than one happy path.
5. **Counterexample:** show where the technique or abstraction is unsuitable and what failure or cost results.
6. **Assessment:** an independently solvable exercise, expected outcomes and at least one verifiable evaluation method; don't confuse seeing worked answers with solving new problems.
7. **Evidence:** use primary RFCs, original documentation, textbooks, standards and research; references must support the actual claims.
8. **Bilingual parity:** preserve key definitions, warnings, reproducible behavior and canonical EN/PT ID.
9. **Release:** technical review of claims and code, automated validation, stable routes, accessibility and QA. CI success is necessary but **not** a reference-grade certification.

Editorial states: `draft` → `review requested` → `examples verified` → `technically reviewed`. Existing chapters are **published**, not automatically reviewed. A second independent human review is required before claiming reference-grade status.

## Primary objective: Amazon SDE II

The dedicated track prioritizes applied data structures and algorithms, syntactically valid coding without an IDE, correctness and edge cases, maintainable object design, system design and evidence-based communication. No core chapter depends on RabbitMQ quorum or PostgreSQL fencing experiments.

Read the [official SDE II OA guide](https://amazon.jobs/content/en/how-we-hire/sde-ii-oa-prep), [interview guide](https://amazon.jobs/content/en/how-we-hire/sde-ii-interview-prep), and [software development topics](https://amazon.jobs/content/en/how-we-hire/interview-prep/software-development-topics). The online assessment includes two coding questions within 90 minutes plus design and work-style sections. Competence is measured with **unfamiliar** exercises and reasoned review, not number of articles.

## Maintenance

The source of truth for precise subject assignment is `content/data/modules.yml`. Existing chapter frontmatter contains a legacy coarse category field, retained temporarily for backward compatibility; the builder applies the precise module registry at load time. Before removing this compatibility, migrate frontmatter in a separately tested change. The registry must classify each published semantic ID exactly once.

Do not publish another specialized lab while P0/P1 foundations remain missing unless correcting a verified defect. Do not append historical release logs to topic chapters; Git history already preserves changes.

## 2026-10-10: Clean Code prerequisite added

New bilingual chapter `clean-code-cohesion-coupling` establishes concrete behavioral contracts, cohesion and coupling with a locally deterministic inventory planner. It precedes object design and SOLID in both the Amazon and the general CS track. The LLD chapter now treats `database-consistency` as an important follow-up rather than a hard prerequisite for its local state-machine example. The implementation workshop was moved behind the rate-limiting section, which it uses as a prerequisite. These are **curricular improvements**, not evidence of complete prerequisite ordering across every advanced chapter. New regression tests verify the relevant relationships.
