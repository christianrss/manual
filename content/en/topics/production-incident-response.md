---
id: production-incident-response
title: "Production Incident Response, Recovery and Postmortems"
description: "Build an incident command structure, stabilize service, quantify user impact, preserve evidence and write testable postmortem actions."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [distributed-observability, api-reliability]
sources:
  - {title: "Google SRE Workbook — Incident Response", url: "https://sre.google/workbook/incident-response/", kind: "site reliability engineering guide"}
  - {title: "Google SRE Book — Postmortem Culture", url: "https://sre.google/sre-book/postmortem-culture/", kind: "site reliability engineering guide"}
  - {title: "NIST SP 800-61 Rev. 3 — Incident Response Recommendations", url: "https://csrc.nist.gov/pubs/sp/800/61/r3/final", kind: "security incident response standard"}
---
A production incident is a disruption or risk to an agreed service contract that requires coordinated action. The first objective is **reduce user harm and stabilize the system**, not prove an elegant root-cause theory. Root-cause investigation continues after safety is restored. Reliable response depends on explicit authority, shared evidence, decision records and communication, especially when several teams and services are involved [1].

## Declare severity using observable impact

Define severity before an incident in terms of business-critical functions, affected users, duration, data integrity and security exposure. A 5xx spike affecting one low-traffic test endpoint may deserve a different response from lost payments or cross-tenant exposure. Use measured request failures, latency and impacted population; if data are incomplete, state that uncertainty rather than invent exact percentages.

An SLI measures an operational population over a defined interval. If 1,200 of 60,000 eligible requests failed during a 20-minute window, the observed failure ratio is 2%. It does not imply exactly 2% of users were affected: one user may issue many requests. A report should distinguish calls, unique users, transactions and durable business effects where those differ.

## Incident command and operational roles

Google's incident management model emphasizes **coordinate, communicate and control**, often with an incident commander, operations lead and communications lead [1]. The commander maintains priority and decides who may act. Operations owners perform rollback, traffic shifting or other mitigation. Communications provides timely updates to stakeholders and users. On a small incident these roles can be combined deliberately; on a large one they should be separated to avoid interrupting debugging with unbounded communication requests.

![Incident lifecycle: detect, assess, contain, recover and learn.](/diagrams/incident-lifecycle.svg)

Establish one authoritative incident channel, a timeline with timestamps and sources, and an explicit owner for each action. Freeze unrelated risky deployments and avoid multiple people changing the same resource without coordination. A mitigation that improves one region but degrades another must be reported as a scoped experiment, not global recovery.

## Mitigate first, diagnose safely

Begin with reversible, low-risk responses matched to evidence: rollback a suspect release, disable a failing feature behind a flag, shed excess requests, or fail over only when the data and authority constraints support it. A rollback is not always safe after incompatible schema changes or new-format writes. If the system may have been compromised, preserving forensic evidence and containment requirements can restrict ordinary debugging actions [3].

Choose actions by expected harm reduction, reversibility, execution risk and observability. If a dependency is overloaded, increasing upstream retries can intensify the incident. If one database is locked, doubling application replicas may increase lock contention. Use the system's failure model rather than action lists detached from diagnosis.

## Quantify timeline and user impact

Maintain at least **start of customer impact, detection, acknowledgment, mitigation and verified recovery** timestamps. Detection time is not necessarily failure onset; monitoring could discover a problem late. Acknowledge is not mitigation, and mitigation is not full recovery. To calculate mean time to detect (MTTD) or restore (MTTR), first define the population of incidents and exact endpoints; a single incident's duration is not a mean.

~~~python
from datetime import datetime, timezone

def incident_durations(impact, detected, mitigated, recovered):
    times = [datetime.fromisoformat(value.replace("Z", "+00:00"))
             for value in (impact, detected, mitigated, recovered)]
    if any(t.tzinfo is None for t in times) or times != sorted(times):
        raise ValueError("timestamps must be ordered and timezone-aware")
    start, detect, mitigate, recover = times
    minutes = lambda a,b: (b-a).total_seconds() / 60
    return {
        "detection_minutes": minutes(start, detect),
        "mitigation_minutes": minutes(start, mitigate),
        "recovery_minutes": minutes(start, recover),
    }

times = incident_durations(
    "2026-01-01T10:00:00Z", "2026-01-01T10:07:00Z",
    "2026-01-01T10:22:00Z", "2026-01-01T10:36:00Z"
)
assert times == {
    "detection_minutes": 7.0,
    "mitigation_minutes": 22.0,
    "recovery_minutes": 36.0,
}
~~~

The timestamps are **hypothetical**. This code measures elapsed durations under a selected definition; it does not infer when the first user was affected or whether system state was safe. If clocks differ among systems, reconcile them or record uncertainty. A service can show healthy HTTP responses while an asynchronous queue still contains permanently failed work.

## Incident communications as an operational contract

A good update states what is affected, when it began if known, current mitigation status, what users should do, and the next update cadence. Avoid speculative causes and definite 'all clear' language without verification. Internal logs may identify an individual or customer; external communications should respect confidentiality and security obligations. A named communications owner helps engineers continue mitigation without introducing silence or contradictory claims [1].

A status page is not the source of truth for data loss. If financial or security effects are uncertain, report uncertainty and outline how reconciliation will determine them. For regulated incidents, legal notification windows and preservation obligations require specific handling beyond normal service status updates [3].

## Verification before closure

Reopen traffic gradually if the mitigation changed load distribution. Verify error rate, p95/p99 latency, saturation, durable side effects, queued work, replica lag and affected user paths. A restored frontend does not imply a previously damaged backend is consistent. If transactions were accepted during an outage, reconcile them against authoritative storage. Record known remaining defects and owners; 'looks normal' is not a rigorous exit criterion.

| Question | Closure evidence |
| --- | --- |
| Are requests succeeding? | SLI at agreed traffic volume |
| Is all work finished? | Queue and reconciliation state |
| Is data consistent? | Business invariants and authoritative comparisons |
| Can the incident recur immediately? | Trigger disabled or controlled |
| Have users been informed? | Final update consistent with evidence |

## Blameless postmortems with specific causes

A postmortem records customer impact, timeline, detection gap, contributing factors, mitigation decisions and follow-up actions [2]. **Blameless** means analyzing why actions made sense given the information and tooling available; it does not mean omitting inaccurate decisions or granting unaccountable privileges. Avoid fictional 'single root causes' for multi-factor incidents. Separate triggering event (for example a rollout) from systemic weaknesses (missing guardrails, unsafe retries or absent capacity tests).

Every corrective item should have an owner, measurable acceptance test and deadline or prioritization decision. 'Improve monitoring' is vague. 'Alert within five minutes when 5xx exceeds the specified error-budget burn rate across two windows, verified by a synthetic failure test' is testable. Preventive work should be regression-tested, not merely marked complete in an issue tracker.

## SRE incidents versus cybersecurity response

Service reliability incidents and cybersecurity incidents overlap but are **not identical**. NIST SP 800-61 Revision 3 integrates cybersecurity incident response into ongoing risk management: security incidents may require containment, evidence integrity, coordinated legal and stakeholder action, and threat-driven recovery [3]. The general operational command structure can help, but do not treat an outage playbook as sufficient for compromised credentials or an active adversary.

## Exercises and verification

1. If failures are 1,200 of 60,000 eligible calls, compute 2% and explain why the fraction of impacted users may differ.
2. From impact at 10:00, detection at 10:07 and recovery at 10:36, separate detection time from total recovery time.
3. Write a three-sentence status update that gives scope and next steps without asserting a root cause.
4. Propose a rollback and describe a schema migration that would make it unsafe.
5. Convert 'prevent another incident' into one owned and measurable testable action, then state what proof is needed to close it.

**Related chapters:** [Observability](/en/topics/distributed-observability/) defines evidence and SLOs, [reliable APIs](/en/topics/api-reliability/) covers retries and overload, and [replication failover](/en/topics/database-replication-failover/) addresses data loss during recovery.
