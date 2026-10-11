# Engineering Manual — Curriculum and Editorial Governance

Review date: 2026-10-11. This manual is an independent educational reference, not official Amazon material or a guarantee of hiring.

## Curriculum, in prerequisite order

1. **Mathematical and computational reasoning:** discrete logic, proof techniques, program semantics, sets, counting, probability, number representation, asymptotic complexity, recursion.
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
| Data structures and algorithms | Logic/proof obligations, Python semantics, finite sets, combinatorial counting, exact conditional probability/expectation, equivalence relations, partitions and finite partial orders, arrays, lists, maps, heaps, trees, graph problems, DP, sorting and search | Advanced number theory, uneven-split and higher-order recurrences, computability and independent adversarial unseen exercises | P0 |
| Software quality and design | Clean Code/cohesion/coupling worked primer, OOP, SOLID, patterns, refactoring, tests and LLD | Additional specialized patterns, independent review, assessed refactorings | P0 |
| System design | Capacity, service boundaries, caching, queues, complete cases | More entry-level-to-intermediate worked reviews and independent evaluations | P0 |
| Computer architecture | Binary representation, ISA, direct-mapped cache mapping, plus modeled pipeline hazards, forwarding and two-bit prediction | Digital logic, detailed processor implementations, branch target structures, cache coherence, DRAM and quantitative memory hierarchy | P1 |
| Operating systems and concurrency | Processes, virtual memory, first-fit/best-fit arena allocation and coalescing, file descriptors/open descriptions, abstract fsync/crash boundaries, inode/block allocation and metadata redo recovery models, FCFS/Round Robin, introductory MLFQ and priority donation, locks and atomics | Real multicore kernel scheduling, actual buffered-device experiments, production memory allocators, real filesystem formats and tested crash consistency | P1 |
| Computer networks | Network overview, IPv4 longest-prefix, positive DNS TTL cache, NXDOMAIN/NODATA keys, CNAME TTL bounds and authoritative delegation concepts, TCP frames/cumulative ACKs, independently tested RTO smoothing/backoff and illustrative congestion rounds | Real TCP modular sequence wrap, sender retransmission and ACK-driven congestion algorithms, full DNSSEC validation and authoritative referral implementation, advanced HTTP and full TLS interoperability | P1 |
| Cryptography and security | API security, OAuth/PKCE, TLS 1.3 handshake concepts and RFC-tested HKDF-SHA256/TLS label encoding | AEAD/nonce use, signatures, complete PKI/certificate validation, real TLS interoperability | P1 |
| Theory of computation | Logic, proof and invariants primer; asymptotic analysis | Automata, computability, reductions, P, NP and NP-completeness | P2 |
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

## 2026-10-10 — Pattern families integrated

Added bilingual `design-pattern-families` after `refactoring-design-patterns` in both core tracks. New examples test Builder's immutable snapshot and validation, Facade's missing-data contracts, and Observer's callback mutation and failure semantics. Advanced GoF families are **not** fully covered. Fixed the CS-core ordering of capacity estimation before the general system-design method. See `tests/test_pattern_family_contracts.py` for independently authored behavior probes.

## 2026-10-10 — First computer-architecture dependency

The new EN/PT chapter `machine-representation-isa-cache` fills the previously empty `computer-architecture` module with a tightly scoped introduction to two's complement, byte order, ISA versus implementation, a **non-RISC-V toy executor**, and a **direct-mapped cache model**. Both algorithm/CS reading paths place it before virtual-memory and concurrency. The processes-and-virtual-memory chapter now explicitly depends on it and distinguishes cache tags from page tables. Source-based claims are grounded in the RISC-V ratified RV32I document, Intel optimization manuals, and Python byte-conversion documentation. Exhaustive eight-bit arithmetic and independent cache trace tests enforce the stated contracts. The material is **not** full CPU architecture coverage, and its simplified models are not hardware timing or ISA conformance tests.

## 2026-10-10 — Pipelining, forwarding and two-bit predictor

Added bilingual `cpu-pipeline-hazards-branch-prediction` to the computer-architecture module and both foundational tracks immediately after machine representation and before processes/virtual memory. The worked model explicitly distinguishes **instruction latency** and **throughput**, derives **RAW hazard timing inequalities**, tests a **single-issue five-stage scheduler**, and checks **pre-update two-bit branch predictions** against a separate transition-table oracle. The simulator has no speculative execution, timing measurements, ISA instruction encoding or multicore coherence. Remaining topics include OS scheduling, real CPU pipelines, performance counters and coherent caches.

## 2026-10-10 — FCFS and Round Robin scheduling

Bilingual `cpu-scheduling-fcfs-round-robin` is placed between processes/virtual memory and concurrency in both core tracks. The single-CPU event-driven models define strict arrivals, positive bursts, idle gaps, and explicit arrival-before-requeue behavior at quantum boundaries. Tests compare exact CPU-owner timelines and three job metrics with an independent tick-by-tick oracle. This proves only those finite checked contracts: no claims about real context switching, priorities, multicore behavior, blocked I/O or unbounded-stream starvation.

## 2026-10-10 — MLFQ and priority inversion

Published `mlfq-priority-inheritance` in both languages after scheduling and concurrency prerequisites, with explicitly defined tick order, three priority queues, preemption with retained allotment, optional periodic global boosts, and a **separate** acyclic wait-graph priority inheritance calculation. The independent test uses a different ready-queue representation and priority-ticket comparator to validate finite MLFQ traces, and compares donation to graph traversal under small acyclic waiting configurations. References: OSTEP MLFQ, official Linux rt-mutex and EEVDF docs. EEVDF is **not** modeled by the teaching MLFQ. Kernel context switches, real mutexes, infinite arrival streams and deadlines remain outside this evidence.

## 2026-10-10 — Heap free-space allocation and fragmentation

Added a bilingual, prerequisite-led `heap-allocation-fragmentation` chapter immediately after processes/virtual memory in both core tracks. It implements first-fit/best-fit with address-ordered free intervals, split/coalescing, handle lifecycle and deterministic external-fragmentation measures, and a separate rounded-reservation demonstration of internal slack. Independent **bitmap-owner** tests enumerate bounded allocation/free histories and verify exact chosen addresses, conservation, free-span normalization and failure non-mutation. Sources include OSTEP's free-space management chapter and current Linux physical-memory and memory-API references. This is **not** a physical page allocator, a kernel buddy or slab allocator, a native malloc implementation, an alignment-aware arena, a compactor, nor a thread-safe subsystem. Linux APIs and virtual/physical contiguity remain distinguished.

## 2026-10-10 — File descriptors and durability boundaries

Bilingual `file-descriptors-buffering-fsync` follows processes and heap allocation in both foundational curricula. Its executable, single-process descriptor-table model distinguishes FD numbers, shared `dup` open-description offsets, independent `open` offsets and shared bytes, with lowest-available-descriptor reuse. A **separate** abstract crash snapshot model separates visible writes from a synchronized snapshot and explicitly excludes real hardware/FS guarantees. Independent event-trace tests compare FD operations against an oracle storing open-description IDs rather than shared Python references, and validate snapshot state over short append/sync/crash sequences. OSTEP plus Linux man pages `open(2)`, `dup(2)`, `fsync(2)`, `write(2)` are cited. **Not implemented**: filesystems, inodes/renames, partial writes, real kernel page cache, atomic replacement, directory syncing, power failure experiments, remote storage or concurrent I/O.

## 2026-10-10 — Filesystem inodes and metadata journal

Added bilingual `inode-directories-journaling-recovery` after descriptors and heap allocation in the two core reading tracks. One model stores inode IDs, directory names and block ownership with **preflight capacity checks** and noncontiguous block assignment; another models **redo journal commit/replay** separately with abstract durable log records and idempotent recovery. Independent reference tests rebuild data and allocation counts from content-level maps and enumerate finite crash windows before/after commit and during checkpoint. Primary references: MIT xv6 file system/logging, OSTEP, ext4 jbd2 and fsync man pages. The models do **not** implement inode persistence, hard links or open-FD lifetime, real journal ordering, fsync, torn writes, ext4, kernel I/O, multiple concurrent transactions or physical power-loss tests. All claims are restricted to explicitly tested finite state spaces.

## 2026-10-10 — IPv4 routing and DNS TTL cache models

Published bilingual `ip-routing-dns-resolution` before the existing `network-protocols` chapter in Amazon SDE II and CS core. The static IPv4 forwarding example uses longest-prefix match, then lower metric and stable input index; an independent bit-mask oracle checks decisions on bounded route tables and destinations. The separate positive-answer cache models A/AAAA addresses, case-insensitive ASCII owner names, monotonically increasing integer timestamps and expiration at TTL boundary; its independent state oracle verifies expiry, overwrites, zero-TTL behavior, and negative validation. The article explicitly **does not** claim to implement routing protocol selection, ARP/ND, DNS recursive resolution, NXDOMAIN/NODATA, DNSSEC, RFC 8767 serve-stale, TCP, TLS, or live network measurements. RFCs 1812, 1034, 1035, 2308, 8767 and 8200 ground the explanations.

## 2026-10-10 — TCP stream framing and cumulative ACK contracts

Added PT/EN `tcp-byte-stream-framing-flow-control` after network-protocols in Amazon SDE II and CS core, with an executable two-byte big-endian frame parser/encoder and an independent per-byte relative-sequence receiver demonstrating cumulative ACK behavior. An arithmetic sender allowance illustrates `min(cwnd, rwnd) − in_flight` with nonnegative clamping; **it is not a congestion-control implementation**. Independent regression tests enumerate bounded frame/chunk boundary partitions and out-of-order events using a separate per-position array oracle, with validation and failure-state checks. References RFC 9293, RFC 5681, RFC 7323 and CIDR RFC 4632. This is **not** real TCP 32-bit sequence wrap, SYN/FIN, retransmission, SACK, socket I/O, transport security or packet measurement; those remain explicit gaps.

## 2026-10-10 — TCP retransmission timer and congestion-round models

Added bilingual `tcp-rto-retransmission-congestion` after the TCP stream chapter in both core curricula. RFC 6298-style RTO smoothing uses SRTT/RTTVAR, eligible RTT measurements, old SRTT in deviation updates, Karn ambiguous-retransmission rejection, min 1 s, illustrative max 60 s and exponential timeout backoff. A **separate**, intentionally nonconformant one-successful-RTT-per-event congestion sketch distinguishes cwnd, ssthresh and receiver-window constraints. A Decimal numerical oracle and finite round-event reference independently check transitions, rejection and bounds in both translations. RFCs 6298, 5681, 9293 and 8985 ground the chapter. No compliant TCP Reno sender, retransmission packet schedule, real ACK processing, SYN/FIN, RACK-TLP, kernel trace, throughput benchmark or live network experiment is claimed.

## 2026-10-10 — TLS 1.3 authentication and HKDF

Added complete PT/EN `tls13-hkdf-handshake` to the security module and both core tracks after TCP/network prerequisites, with reciprocal navigation from the request walkthrough. References **RFC 9846 (July 2026)** as the current TLS 1.3 specification (replaces RFC 8446), RFC 5869 HKDF vectors, RFC 9525 identity and RFC 9114 QUIC context. Python examples encode HKDF-SHA256 extract/expand and `HKDF-Expand-Label` bytes with official known-answer vectors and independent manual-HMAC oracle tests in both languages. The chapter is a derivation lesson **not** a TLS implementation: no ECDHE, X.509 chain building, AEAD records/nonces, production secrets, constant-time analysis or authenticated channel proof. The current gap remains concrete crypto/PKI and handshake interoperability, not the absence of an HKDF introduction.

## 2026-10-10 — DNS authority, negative answers and aliases

Published bilingual `dns-authoritative-negative-cname` immediately after IPv4 routing/positive DNS cache and before the end-to-end network protocol path in Amazon SDE II and CS core. Implements **two separate finite teaching contracts**: NXDOMAIN versus NODATA with RFC 2308 SOA TTL expiry and scope, plus CNAME-chain traversal with terminal RRset TTL bounds, cycle and hop protections. Independent test oracles compare negative-cache event histories and alias chains against separately represented expectations. RFCs 1034, 1035, 2308, 4035 and 8767 anchor delegation, negative caching, DNSSEC boundary and serve-stale discussion. This is **not** a recursive resolver, DNS packet parser, bailiwick security policy or cryptographic DNSSEC validator; real authoritative/recursive query experiments and security validation remain gaps.

## 2026-10-10: Proof and programming-language foundations

The new bilingual chapters `logic-proofs-invariants` and `programming-semantics-contracts` precede asymptotic analysis and arrays in both core tracks. Their executable models derive universal versus existential obligations, induction, partial/total correctness, aliasing, short-circuit evaluation and error contracts. `complexity-analysis` now requires proof techniques, and `arrays-and-strings` requires both complexity analysis and program semantics. This closes an *introductory* gap, not the broader mathematics, programming-language theory, compiler, type-system or independent evaluation gaps. The registry, bilingual tracks and editorial gates remain authoritative.

## 2026-10-10 — Sets, counting and exact probability

Published bilingual `discrete-counting-probability` after logic and programming semantics and before complexity analysis in Amazon SDE II and CS core. Independent verifiers enumerate finite subsets, combinations, permutations, Cartesian collision spaces, expected distinct outcomes and conditional/Bayes weighted outcomes against exact rational formulas. References: MIT 6.042J, Stanford CS109 and Python standard documentation. Mathematical arguments are distinct from finite tests, which cannot prove unbounded identities or real-world random distributions. Full discrete mathematics, computability, number theory, statistics and unseen evaluations remain gaps.

## 2026-10-11 — IPv4 fragmentation and Path MTU

Added bilingual ipv4-fragmentation-path-mtu after IP routing and before authoritative DNS in both main tracks. It derives MF/DF flags, eight-byte fragment offsets, strict single-datagram reassembly, and ideal iterative classical PMTUD. Independent byte-coverage and per-hop oracle tests validate finite models. Scope excludes IP header serialization/options, multi-flow identification, live ICMP, re-fragmentation, full IPv6 fragments and DPLPMTUD. Standards: RFCs 791, 1191, 8200, 8201 and 8899.
