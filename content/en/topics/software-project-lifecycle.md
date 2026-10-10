---
id: software-project-lifecycle
title: "Software Project Lifecycle: From Requirements to Operations"
description: "Trace a software project from acceptance criteria and design through tested delivery, measured releases, incident learning and maintenance."
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites: [testing-strategies, ci-cd-release-engineering]
sources:
  - {title: "Google Engineering Practices — Code review", url: "https://google.github.io/eng-practices/review/", kind: "original engineering guideline"}
  - {title: "Google SRE — Postmortem Culture", url: "https://sre.google/resources/book-update/postmortem-culture/", kind: "official SRE resource"}
---
A software project is not complete when a pull request merges. Engineering ownership connects **discovery, decision records, delivery, operation, and feedback** into one accountable lifecycle. Each stage produces an artifact whose claims can be checked: a problem statement, explicit invariants, a design decision, tests, a release record, and operational evidence. The sequence is iterative rather than a mandatory waterfall. A defect in production may change the requirements, while a prototype can invalidate the architecture before the first release [1][2].

## Start with a customer problem and acceptance criteria

Imagine a team building a private export endpoint for an account's orders. The observed problem is that customers cannot retrieve their transaction history in a machine-readable format. A vague ticket such as “add CSV export” omits limits and access controls. A useful **problem statement** identifies the actor, the desired outcome, the scope of data, business restrictions and how success will be observed.

A concrete acceptance contract might say: an authenticated account owner can request an export of only their own orders; the export remains available for 24 hours; the result is ordered by an immutable order ID; concurrent requests with the same operation key produce one logical job; and an unauthorized account cannot read the generated file. Data retention, audit logging and failure handling are product requirements, not implementation trivia. Decide whether the API returns synchronously or accepts a job for asynchronous completion.

## Feasibility, risk and design alternatives

Before coding, identify the uncertain parts: maximum account size, database scan cost, privacy classification, object-storage access policy, and whether CSV quoting rules preserve user-supplied text safely. Model one small benchmark using representative data and a realistic query plan. Do not extrapolate throughput from one tiny fixture or silently assume that disk exports take constant time.

Compare at least two designs. **Synchronous export** offers simple client behavior but can tie up web workers and fail on request deadlines. **Asynchronous export** creates a durable job and stores the artifact after a worker finishes; it adds a state machine, retries and cleanup. Choose on measured size distribution, latency objective and user experience, and record why the rejected alternative was insufficient. A design decision record should list assumptions, consequences, reversibility and the signal that would reopen the choice.

## Decompose work into testable vertical slices

A vertical slice spans enough layers to demonstrate one user capability: authorize the requester, accept an export command, persist a job, and expose its status. A later slice creates the file and handles expiry. This provides feedback before every subsystem is complete. Define interfaces between API, job authority, storage and notification, and specify who owns each invariant.

Avoid an implementation plan that lists “build database, then API, then UI” but never produces a useful end-to-end path. Equally, resist splitting every method into a separate independently deployed service. A modular monolith may be sufficient initially. Break down work by user-observable outcomes and high-risk assumptions rather than by fashionable technologies.

## Model the lifecycle as explicit state transitions

The export job has states `requested`, `running`, `ready`, `failed`, and `expired`. The server must not claim `ready` until a durable object exists and its access policy is valid. Expiry is allowed only after completion in this simplified model; cancellation and timed-out running jobs would need extra transitions in a production system.

![A software delivery cycle connects discovery, design, implementation, verification and operation.](/diagrams/software-project-lifecycle.svg)

~~~python
TRANSITIONS = {
    "requested": {"running"},
    "running": {"ready", "failed"},
    "ready": {"expired"},
    "failed": set(),
    "expired": set(),
}

def advance(state, target):
    if target not in TRANSITIONS.get(state, set()):
        raise ValueError(f"forbidden transition: {state} -> {target}")
    return target

job = "requested"
job = advance(job, "running")
job = advance(job, "ready")
job = advance(job, "expired")
assert job == "expired"
for source, target in (("requested", "ready"), ("failed", "ready"),
                       ("expired", "running"), ("unknown", "running")):
    try:
        advance(source, target)
        assert False
    except ValueError:
        pass
~~~

This function is a **local policy check**, not a durable concurrency primitive. Two workers may both read `requested` and each attempt to start. A database compare-and-swap of job version or guarded state transition must enforce exclusivity. State transitions, object persistence, and outbox messages should be coordinated by the authority responsible for the job. Retries need stable identities, and a failed worker lease needs a recovery path.

## Code review and automated verification

Implement in small changes that keep the system buildable. A review should inspect **design, functionality, complexity, tests, naming, comments, documentation, and integration with the codebase**; these categories appear in Google's published engineering review guidance [1]. The reviewer also checks that an export does not expose another account's orders or allow spreadsheet formula injection in an output format that downstream software interprets.

Verification should be layered: unit tests for transition rules and CSV escaping; authorization tests across tenants; integration tests using a real database and object-storage contract; an end-to-end test that requests, generates and retrieves an export; and failure injection when a worker crashes after object upload but before status persistence. Merely mocking the storage adapter does not demonstrate durable access-control behavior.

## Deploy through a measured release

A release candidate is a **versioned artifact** associated with a commit and dependency set. Promote the reviewed artifact through automated checks, test a schema migration against representative data, then release behind a limited exposure or feature flag when justified. The flag can disable new export requests during a failure, but it cannot revoke a file already made public by an incorrect storage permission without a separate cleanup operation.

Observe queue age, export size, job failure rate, p95 completion latency, unauthorized access attempts, worker resource usage and storage expiry backlog. Establish a service-level objective only with a defined denominator and window. A 202 response is evidence of job acceptance, not successful generation. Business completion must be monitored separately from HTTP availability.

## Incident learning and maintenance after launch

When an export fails or leaks data, stop the harmful behavior, preserve evidence, restore service, then write a **blameless postmortem** describing timeline, contributing conditions, detection gaps, customer impact and prioritized actions [2]. Blameless does not mean unaccountable: owners still need specific follow-up work and verification. Avoid superficial conclusions such as “engineer should have been more careful”; fix mechanisms that allowed a defective change to pass.

Maintenance includes library updates, dependency vulnerability review, data retention audits, performance optimization based on measurements, and retiring obsolete flags. Track operational toil and error-budget consumption. The delivery loop closes when incidents and product usage alter the next iteration's requirements.

## Decision matrix and failure examples

| Stage | Durable evidence | Anti-pattern |
| --- | --- | --- |
| Discovery | Actor, problem, measurable acceptance | Ticket without a failure or success criterion |
| Design | Invariants, alternatives, decision record | Architecture selected before workload |
| Implementation | Cohesive vertical slices | One giant unreviewable change |
| Review and tests | Reproducible checks and security cases | Mock-only proof of external behavior |
| Release | Artifact identity, rollout and rollback | Rebuild unpinned sources in production |
| Operation | SLI/SLO, alerts and incident records | Monitoring only successful HTTP responses |

A team can use agile iterations, staged milestones or another workflow; no process label replaces observable acceptance and responsible ownership. The strongest lifecycle argument traces one user requirement through design, code, tests, release and measured outcome.

## Exercises and verification

1. Write three acceptance tests for an export endpoint, including one cross-tenant authorization failure.
2. Explain why the transition checker cannot prevent two independent workers from claiming the same job.
3. Select synchronous or asynchronous export for an account with ten million orders and list which measurements could reverse your choice.
4. Propose a failure injection test for a crash after file upload but before `ready` is committed.
5. Name the metrics and postmortem actions that show whether the export feature is truly reliable after deployment.

**Related chapters:** [Testing strategies](/en/topics/testing-strategies/), [CI/CD and release engineering](/en/topics/ci-cd-release-engineering/), [service boundaries](/en/topics/service-boundaries/) and [incident response](/en/topics/production-incident-response/) provide the specialized methods.
