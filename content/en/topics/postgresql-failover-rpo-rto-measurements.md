---
id: postgresql-failover-rpo-rto-measurements
title: "PostgreSQL Recovery Measurements: RPO, RTO and Network Split"
description: "Measure controlled PostgreSQL promotion phases, observe a replayed commit and show why an isolated primary still needs fencing."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [postgresql-streaming-promotion, postgresql-failover-fencing-gates]
sources:
  - {title: "PostgreSQL 17 — Standby Failover", url: "https://www.postgresql.org/docs/17/warm-standby-failover.html", kind: "official database documentation"}
  - {title: "PostgreSQL 17 — Warm Standby and Streaming Replication", url: "https://www.postgresql.org/docs/17/warm-standby.html", kind: "official database documentation"}
  - {title: "PostgreSQL 17 — Replication Statistics", url: "https://www.postgresql.org/docs/17/monitoring-stats.html", kind: "official database documentation"}
---
A successful standby promotion does not tell an operator how long the service was unavailable or how much committed data might be missing. **Recovery Time Objective (RTO)** concerns the acceptable duration of service disruption; **Recovery Point Objective (RPO)** concerns the acceptable age or amount of lost data relative to a recovery point. These are **business objectives**, not numbers a database can infer from one status query. This laboratory instruments actual PostgreSQL 17 physical-replication and manual-promotion steps, records phase durations with a monotonic clock, and introduces a live network isolation to illustrate why a reachable server and a safe new primary are different questions [1][2].

## State the measured scope before reporting an RTO

The existing replica experiment creates a PostgreSQL primary and standby in separate Docker containers, takes a physical base backup, streams WAL, and waits until a known committed probe row is visible on the standby. The new instrumentation measures four **timestamps on one CI runner**: just before requesting a controlled stop of the original primary, after Docker confirms it stopped, after \`pg_promote\` completes, and after the first new SQL INSERT on the promoted standby commits.

The elapsed interval between the first and last timestamp is an **observed controller-driven write-restoration interval in this test**, not a customer-facing RTO. It excludes failure detection, upstream request timeout, load balancer updates, DNS propagation, client retries, warm-up and network distance. An end-to-end availability test must begin from an application request and confirm the first successful business operation through the production-equivalent endpoint [1].

![Manual PostgreSQL failover records stop, promotion, and first committed write phases.](/diagrams/postgresql-failover-timing.svg)

## Measure phase ordering without wall-clock ambiguity

An executable helper [failover_metrics.py](https://github.com/christianrss/manual/blob/main/scripts/failover_metrics.py) stores the timestamps, checks their ordering, and returns separate durations for stop, promotion, first new write and total observed restoration. The implementation uses Python's \`time.monotonic()\` so changes to the system wall clock do not distort elapsed time. It does not compare timestamps collected on different hosts or assume synchronized clocks.

~~~python
def measured_phases(start, stopped, promoted, committed):
    instants=(start,stopped,promoted,committed)
    if any(b<a for a,b in zip(instants,instants[1:])):
        raise ValueError("time observations are not ordered")
    return {
        "stop_seconds": stopped-start,
        "promotion_seconds": promoted-stopped,
        "first_write_seconds": committed-promoted,
        "total_seconds": committed-start,
    }

result=measured_phases(10.0,13.0,16.5,17.0)
assert result["stop_seconds"] == 3.0
assert result["promotion_seconds"] == 3.5
assert result["first_write_seconds"] == .5
assert result["total_seconds"] == 7.0
~~~

The test suite includes cases that reject timestamps out of order. Production metrics must also account for percentile distributions across many runs; the duration from one CI execution is a sample, not an operational guarantee.

## Observe a specific replay point, not zero data loss

After a known probe row commits on the primary, the script polls the standby until a fresh SQL connection can read exactly that row. This provides **positive evidence that the identified transaction was replayed**. The new timing output also includes the elapsed observation delay, but that number is affected by polling frequency, query latency and Python process scheduling. It should not be presented as a precise WAL replication latency measurement.

With asynchronous replication, some later committed transactions may not yet be visible at the standby when the primary fails. The replayed probe establishes a **lower bound on known recovered state**, not that the system has RPO=0 for all commits. PostgreSQL exposes WAL receive/replay LSNs and replication statistics that allow more detailed investigation, but a byte difference between LSNs does not directly equal a count of lost business transactions [2][3].

## Reproduce an unfenced network split before promotion

The lab now deliberately removes the **running primary** from the Docker bridge while leaving its process alive. Through the container runtime, the test executes a temporary-table write against that isolated PostgreSQL instance. The operation demonstrates that **loss of peer network communication did not remove local write authority**. The network bridge is then reconnected to the same process and its previously confirmed probe row remains visible on the standby.

This is an intentionally controlled example, not a live production partition. Docker \`exec\` reaches the container through the Docker engine, independent of the isolated database network. A real application may have a different route to the isolated primary. Nevertheless, the key counterexample is concrete: a health check or replication timeout is **not a fence** and cannot authorize promotion by itself.

## Enforce stopped-old-primary before changing authority

After the split heals, the test calls a gate that refuses promotion while Docker reports the old primary is still running. Only a successful controlled stop followed by a second running-state check permits \`pg_promote\` on the standby. It then verifies that recovery mode ended, writes a new record and reads both rows.

The requirement to check the **old writer** is separate from checking that the **new candidate** is current. A fully automated failover stack needs independent fencing, leadership coordination, persistent epochs and client-routing convergence. Docker's stopped-state check is weak compared with power fencing or a correctly implemented consensus-based authority, because another controller could restart the former primary immediately after the check.

## Record measurements as structured test evidence

After the successful promoted write, the script emits one machine-readable line beginning with \`POSTGRES_FAILOVER_METRICS\`, followed by JSON containing \`stop_s\`, \`promotion_s\`, \`new_write_s\`, \`observed_recovery_s\` and \`marker_replay_observed_s\`. The string also identifies the **measurement scope** explicitly so the numbers are not mistaken for a platform SLA.

~~~python
import json

sample={
    "stop_s": 1.2, "promotion_s": .3, "new_write_s": .05,
    "observed_recovery_s": 1.55, "marker_replay_observed_s": .4
}
encoded=json.dumps(sample,sort_keys=True)
decoded=json.loads(encoded)
assert decoded["observed_recovery_s"] == 1.55
assert decoded["stop_s"]+decoded["promotion_s"]+decoded["new_write_s"] == 1.55
~~~

These are **illustrative numbers for testing the serialization format**, not measured durations from GitHub Actions. Consult an actual workflow log for measurements. Comparing separate CI runs requires similar workload and infrastructure settings; noisy shared runners are not a substitute for a dedicated benchmarking environment.

## Interpret replication and promotion failure modes

| Observation | Valid interpretation | Invalid extrapolation |
| --- | --- | --- |
| Probe visible on standby | Specific transaction was replayed | Every prior and later commit guaranteed |
| Primary accepts temporary-table write while isolated | Writer remains locally active | Clients everywhere can reach it |
| Docker confirms old instance stopped | Controlled test excludes that writer | Independent fencing authority exists |
| \`pg_promote\` completes | Standby exits recovery | Every client automatically rerouted |
| First new INSERT commits | New database writes are possible | End-to-end RTO met |
| Reported elapsed time | One CI timing sample | Production p99 RTO or guaranteed SLA |

A failed write from one client also does not prove the **server** is down: client credentials, routing, isolation, transaction conflicts and overload may prevent progress even with a healthy database process.

## RPO/RTO trade-offs and alternatives

Synchronous replication can strengthen which remote acknowledgments a commit waits for, but may increase commit latency or make writes unavailable when the required standby cannot respond [2]. Asynchronous replication avoids that dependency in the common path, at the price of an interval when committed writes are not yet available on the standby. The correct policy depends on the cost of losing transactions versus the cost of delaying or rejecting a write.

For an order system, an RPO permitting a few seconds of order loss may be unacceptable; for a rebuildable search index, such loss may be recoverable. Each domain needs explicit failure semantics, retention and reconciliation plans. **Do not** translate a single PostgreSQL statistic into a business objective without stating exactly which customer-visible transactions are at risk.

## Exercises and verification

1. Explain which intervals are absent from the laboratory's observed recovery measurement.
2. Design a client-side probe that records actual request failures throughout a controlled failover and estimates a customer-visible interruption.
3. Why does visibility of one committed marker on standby not imply RPO=0 for every transaction?
4. Add a test that simulates a failed fencing verifier; confirm no promotion callback can run.
5. Compare synchronous versus asynchronous replication when the standby network disappears and state which business objective each option prioritizes.

**Related chapters:** [Physical standby promotion](/en/topics/postgresql-streaming-promotion/), [fail-closed fencing](/en/topics/postgresql-failover-fencing-gates/), [database replication](/en/topics/database-replication-failover/) and [incident response](/en/topics/production-incident-response/) provide the underlying concepts [1][2][3].
