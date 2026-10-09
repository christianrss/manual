---
id: capacity-estimation
title: "Capacity Estimation and System Constraints"
description: "Build capacity estimates from explicit workload assumptions, utilization, peak traffic, storage growth and queueing effects without false precision."
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis]
sources:
  - {title: 'Google SRE Book — Handling Overload', url: 'https://sre.google/sre-book/handling-overload/', kind: engineering book}
  - {title: 'Google SRE Workbook — Implementing SLOs', url: 'https://sre.google/workbook/implementing-slos/', kind: engineering workbook}
---
A system design begins with the workload and constraints, not with a cloud product. Capacity estimation translates business requirements into rates, storage, memory, network bandwidth and failure budgets. An estimate is a **scenario based on assumptions**, not a prediction; document its units and sensitivity [1].

## Workload definitions
- **Request rate:** average requests per second (RPS) equals requests per day divided by 86,400 seconds, assuming an even mean over a day.
- **Peak-to-average ratio:** an assumption such as 8×, which must be measured or treated as hypothetical.
- **Concurrency:** number of overlapping requests, not number of registered accounts.
- **Throughput:** completed operations or transferred bytes per second.
- **Latency:** elapsed time per operation, reported as a distribution including p95/p99 rather than only an average.

Little's law, under stable conditions with consistent observation boundaries, relates average in-system requests `L`, throughput `λ`, and average time `W`: `L=λW`. Thus at 100 RPS and average 0.2 seconds, average concurrency is about 20. This does **not** imply that only 20 requests can overlap during a burst, nor does it predict tail latency near saturation.

## Worked scenario with explicit assumptions
Assume a read-heavy service receives 12 million requests/day; 95% reads; peak load is eight times the average; each response transfers 3 KiB; one application instance sustains 400 RPS **at a tested safe utilization**; and deployed capacity must survive one instance failing.

| Quantity | Calculation | Estimate |
| --- | --- | --- |
| Mean total RPS | `12,000,000 / 86,400` | `139 RPS` |
| Peak total RPS | `139 × 8` | `1,112 RPS` |
| Peak read RPS | `1,112 × 0.95` | `1,056 RPS` |
| Peak outbound payload | `1,112 × 3 KiB` | `~3.26 MiB/s` |
| Instances required at peak | `ceil(1,112 / 400)` | `3` |
| Provisioned for one failure | `3 + 1` | `4`, assuming traffic rebalances |

The 400 RPS limit must come from benchmarking with the intended request mix and downstream dependencies. Choosing a bigger machine does not automatically remove a serialized database bottleneck. Raw payload estimates exclude headers, TLS overhead, retransmissions and replication.

## Estimate storage separately
Suppose 20,000 new records arrive daily, average payload 2 KiB. Raw payload growth is roughly `40,000 KiB/day`, about 14 GiB/year before indexes, replicas, logs, compression and backup copies. Define retention requirements first; multiplying only by the data replication factor still misses operational overhead.

Distinguish **logical size** from provisioned physical disk and **mean throughput** from burst capacity. Store measured assumptions alongside the design and revise them after load tests. A design that cannot state its assumptions cannot be falsified.

## Saturation and resilience
As utilization approaches a constrained resource's limit, queuing delay can increase sharply, even when average request volume remains unchanged. Protect the system with bounded queues, admission control, timeouts, circuit breakers and explicit overload behavior. Availability and latency must be expressed through measurable service-level indicators and objectives (SLIs/SLOs) [1][2].

![A typical stateless request path through a load balancer, application replicas, cache and durable database.](/diagrams/request-path.svg)

The diagram is a **possible read path**, not an instruction to add every component. A small application may correctly start with a single service and relational database.

## Exercises and verification
1. If average traffic doubles but peak ratio stays constant, redo instance provisioning while preserving one-failure tolerance.
2. At 500 RPS and average response time 0.4 seconds, Little's law suggests mean concurrency `200` in a stable system. Explain why p99 latency may still be much higher.
3. List at least three real measurements needed before committing to a cost estimate: request distribution, payload size, service capacity under load and database query distribution are examples.

Good estimates are orders-of-magnitude tools that drive conversations about trade-offs; they should not be presented as precise capacity guarantees.
