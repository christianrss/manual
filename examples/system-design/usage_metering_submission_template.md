# Usage metering — independent system-design submission

This template is a **student submission**, not a solution. Do not copy a vendor architecture without deriving the contracts. The scenario fixtures and arithmetic helper are public: `usage_metering_scenario.json` and `examples/python/usage_metering_design_math.py`.

## 1. Clarifications before architecture (10 points)

State at least five explicit questions and chosen assumptions: event timestamp trust, definition of one billable unit, account/tenant authority, duplicate/replay window, invoice finalization deadline, freshness versus correctness, and retention. Mark each as product/engineering/legal decision. Do not silently invent guarantees.

## 2. Observable API and authority (15 points)

Define at least two endpoints or event interfaces. Show authenticated tenant boundary, operation ID scope, payload conflict response, accepted-but-unprocessed state, and observable status. Distinguish `durably accepted`, `aggregated`, `available for preview`, and `finalized`. Specify authoritative stores for raw event, dedup decision, adjustments and final invoice.

## 3. Storage, consistency and invariants (20 points)

Draw a data model and include at least four invariants: one logical accepted event per (tenant, source, ID); no cross-tenant aggregation; immutable finalized invoice version or auditable correction; no silent drop during successful ACK. Address transaction/outbox boundaries, replay after retention, corrections, stable partition keys, and source timestamp trust.

## 4. Capacity and recovery arithmetic (15 points)

Compute and label units for baseline average events/s, peak ceiling, logical raw bytes over retention, worker throughput at target utilization, one-replica failure tolerance, backlog and drain margin after the given outage. Recompute one value after a constraint change. State what the arithmetic **does not** include: network overhead, replication, index size, backups, retries or service-time tail risk.

## 5. Failure injection and evolution (20 points)

Analyze timeout after accepted ingest, broker replay, partial write, out-of-order/late data, replayed corrections, tenant hotspot, complete worker outage, and a query against stale aggregates. For each give a violated invariant, mitigated architecture and at least one deterministic test. Describe observability from user-impact SLOs, not only CPU utilization.

## 6. Alternatives and decision record (10 points)

Compare at least two credible designs: transactional SQL ingestion plus queue versus append-only log plus derived aggregates, or another defensible pair. State operations, cost, consistency, late corrections and limits; make a choice justified by scale and constraints. A drawing with services is not sufficient.

## 7. Verification and communication (10 points)

Provide a test plan with concurrency, replay, cross-tenant access, invoice reconciliation and backlog-drain measurements. Record two unresolved assumptions and an explicit rollback/fail-closed condition. Separate experimentally measured inputs from scenario assumptions.

## Blocking failures (independent of numeric score)

- Returns invoices based exclusively on a cache or unverified dashboard aggregation.
- Permits a tenant to read or affect another tenant's authoritative usage.
- Treats a broker's delivery guarantee as exactly-once business effects.
- Claims a finalized invoice can be invisibly overwritten without audit.
- Assumes raw event time and processing time are interchangeable for delayed events.
- Claims a fixed drain time when processing capacity is not greater than arrivals.

A score of at least 80/100 with no blocking failure is a **local educational threshold**, not an employer outcome. Scoring requires human review; the repository does not provide an automated system-design judge.

## Decision record

**Decision:** [a single sentence]

**Assumptions and evidence:** [which quantities are known, hypothesized or measured]

**Chosen authority and API contracts:** [who can commit and read]

**Rejected alternatives:** [why]

**Failure recovery:** [what survives a crash]

**Verification:** [workload, tests and expected invariants]

**Remaining risks:** [clearly unproved promises]
