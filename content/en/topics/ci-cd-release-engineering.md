---
id: ci-cd-release-engineering
title: "CI/CD and Release Engineering: Canary, Schema Evolution and Rollback"
description: "Design CI gates, immutable artifacts, canary decisions, safe database migrations, secrets and recovery procedures."
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites: [testing-strategies, production-incident-response]
sources:
  - {title: "Google SRE Workbook — Canarying Releases", url: "https://sre.google/workbook/canarying-releases/", kind: "engineering workbook"}
  - {title: "GitHub Docs — Deployment environments", url: "https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments", kind: "official CI/CD documentation"}
---
Continuous integration (CI) checks each proposed change against automated quality gates. Continuous delivery makes a tested artifact **eligible for release**; continuous deployment automatically releases qualifying changes. Release engineering covers how source, dependencies, build artifacts, approvals, database migrations and production traffic are controlled. These are related workflows, not synonyms. A green CI job proves only the conditions the job actually tested; it does not prove a safe deployment under every production workload [1][2].

## Trace changes from commit to production

A robust path is: reviewed source commit → reproducible build → unit and contract tests → static/security checks → immutable versioned artifact → controlled environment → partial rollout → metrics evaluation → expansion or rollback. The exact same built artifact should advance through environments when feasible, avoiding an unreviewed rebuild that silently changes dependencies.

Pin dependency versions and record a content digest or immutable artifact identifier. Protect production credentials with environment-scoped secrets, restricted permissions and short-lived authentication. GitHub Actions supports environments, approvals, deployment protection rules and concurrency controls, but such features must be explicitly configured and tested [2]. A workflow YAML file alone is not evidence that a production gate exists.

## Decide which checks block a merge

Fast unit tests give short feedback. Build and lint enforce syntax and conventions. Type checking checks declared contracts to the degree the language supports. Integration tests exercise real database constraints; consumer/provider contract tests detect API drift. A small critical end-to-end suite verifies user journeys, while performance and security checks may have staged execution. Assign **owners** to flaky tests rather than allowing indefinite retries until the pipeline becomes green.

The test matrix should match changed risk. A CSS-only change may not warrant database load testing, but altering money arithmetic or transaction isolation needs targeted failure and concurrency cases. All merge gates must be deterministic enough to distinguish new regression from unrelated infrastructure outage. If an emergency bypass exists, audit who used it and how the skipped checks will be compensated.

## Progressive delivery, canary and control

A **canary release** deploys a change to a limited slice of production, compares it with an unaffected control, and expands only if predefined signals support safety [1]. Possible steps are 1%, 5%, 25%, 100% of eligible traffic, but fractions are examples, not universal best practice. Choose rollout intervals long enough to capture representative load, and maintain rollback switches for the affected feature.

Measure request error rate, p95/p99 latency, saturation and a product-specific business outcome. Compare canary and control **in comparable traffic cohorts**; a low-volume canary may look healthy by chance. A canary with zero requests cannot be promoted on the basis of an apparently zero error rate.

![CI gates promote one immutable build through canary evaluation and rollback.](/diagrams/cicd-rollout.svg)

## A deliberately simple canary guardrail

The following pure function models **a teaching exercise**, not production-grade inference. It requires a minimum sample in both groups, stops a clearly worse canary by absolute error-rate thresholds, and otherwise allows progression. It does not calculate statistical confidence, check latency, seasonality or traffic-mix skew; use sequential testing or appropriate uncertainty models for real release decisions.

~~~python
def rollout_decision(canary_errors, canary_total,
                     control_errors, control_total):
    values = (canary_errors, canary_total, control_errors, control_total)
    if any(not isinstance(v, int) or v < 0 for v in values):
        raise ValueError("nonnegative integer counts required")
    if canary_errors > canary_total or control_errors > control_total:
        raise ValueError("error count exceeds sample")
    if min(canary_total, control_total) < 200:
        return "hold"
    c = canary_errors / canary_total
    base = control_errors / control_total
    if c > 0.02 or c - base > 0.01:
        return "rollback"
    return "eligible_for_review"

assert rollout_decision(1, 1000, 2, 1000) == "eligible_for_review"
assert rollout_decision(40, 1000, 2, 1000) == "rollback"
assert rollout_decision(0, 25, 1, 1000) == "hold"
try:
    rollout_decision(11, 10, 0, 100)
    assert False
except ValueError:
    pass
~~~

The last result means *eligible for further human or automated review*, not guaranteed promotion. It is especially unsafe to base a full release on request error rate alone when a payment double-charge or privacy leak could affect few requests yet constitute a critical incident.

## Database schema changes and rolling deployment

Application rollback can be impossible if a new release destructively changes shared database schema. Use **expand → migrate → contract** for breaking changes. Example: to rename `customer_name` to `buyer_name`, first add the new nullable field; deploy readers that tolerate both; backfill historical values; move writers under an explicit transition policy; verify all active readers; and only later remove the old field.

During the coexistence period, dual-writing needs a **single authority and reconciliation policy**. Simply updating two columns in unrelated asynchronous transactions creates divergence. For a single relational row, one transaction can update both fields; if old and new services write conflicting versions, require a version check and prohibit stale readers from silently overwriting the authoritative value.

An online schema migration may still lock tables or consume substantial I/O depending on engine/version, operation and traffic. Benchmark migrations on representative data, monitor replication lag and preserve a tested restore path. Backups are not interchangeable with rollback; restoring them can discard valid writes after the backup.

## Rollbacks, flags and irreversible effects

A binary rollback changes the application version, not the world. It cannot undo an email already sent, a payment captured or data already deleted. Feature flags can disable a risky path rapidly but introduce their own configuration and lifecycle complexity. Track flag owners, default and expiry; otherwise long-lived toggles become hidden branches with poor coverage.

A production incident response may require **roll forward** to repair records while stopping traffic to a broken feature. Define recovery point (RPO) and recovery time (RTO) objectives for persisted data separately from web request availability. A canary should limit blast radius but can still trigger irreversible side effects within its small audience.

## Security, supply chain and audit trail

CI runners consume potentially hostile pull-request code. Restrict token permissions, avoid exposing deployment secrets to untrusted forks, pin trusted build actions/dependencies, record provenance where applicable and protect artifact promotion. Production access should depend on an auditable identity and explicit environment policy, not a shared personal credential [2].

For each release retain commit SHA, artifact digest, migration revision, rollout start/end, approver if required, affected cohorts, measured guardrails and rollback action. This allows responders to connect changes with regressions without relying on memory. Rebuilding old source does not necessarily regenerate identical binary bits unless build inputs are reproducible.

## Failure table and release checklist

| Failure | Defense | What to observe |
| --- | --- | --- |
| Tests pass but migration fails | Representative migration rehearsal | Schema lock/lag |
| Canary has little traffic | Minimum exposure or hold | Sample size |
| Cache masks canary defects | Compare comparable cohorts | Cache hit and p99 |
| Rollback binary cannot read new schema | Expand-contract compatibility | Mixed-version tests |
| External payment already performed | Compensating/reconciliation process | Durable provider references |
| Secrets leaked into CI job | Least privilege and environment controls | Access audit |

A mature pipeline is measured by recovery capability and change safety, not by deployment frequency alone. Automated release is useful when validation and rollback are equally well engineered.

## Exercises and verification

1. Distinguish continuous delivery from continuous deployment and specify which step requires promotion authority.
2. Explain why the example guardrail returns `hold` for 25 requests even with zero errors.
3. Plan an expand-migrate-contract renaming that tolerates two concurrently running application versions.
4. Explain why rolling back code cannot undo a PSP charge and identify the reconciliation workflow required.
5. List the minimum artifact, migration and telemetry data you would attach to an incident caused by a release.

**Related chapters:** [Testing strategies](/en/topics/testing-strategies/), [production incident response](/en/topics/production-incident-response/), [API contracts](/en/topics/api-contracts-pagination/) and [database replication](/en/topics/database-replication-failover/) cover supporting practices [1][2].
