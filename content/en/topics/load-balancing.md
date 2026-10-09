---
id: load-balancing
title: "Load Balancing: Capacity, Routing and Failure Recovery"
description: "Design HTTP load balancing with explicit routing algorithms, quantitative capacity, health checks, failure budgets and retry safety."
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites: [capacity-estimation, caching]
sources:
  - {title: "NGINX — Using nginx as HTTP load balancer", url: "https://nginx.org/en/docs/http/load_balancing.html", kind: "official software documentation"}
  - {title: "AWS — What is an Application Load Balancer?", url: "https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html", kind: "official cloud documentation"}
---
A **load balancer** receives traffic and chooses a destination among multiple application instances. It does not create backend capacity by itself. Capacity increases only when instances are independently scalable and shared dependencies do not become the next bottleneck. The load balancer also creates a component whose own failure and configuration must be considered [1][2].

## Derive a capacity plan

Assume a stateless HTTP service receives a **hypothetical** peak of 3,000 requests per second. Tests under a representative request mix show that one instance can sustain 500 requests per second at the desired latency target. Six instances would meet the average arithmetic only at full utilization. If the planning ceiling is 60%, each instance contributes 500 × 0.60 = 300 requests per second. Thus at least ceil(3000/300) = **10 healthy instances** are needed. To survive one instance failing while maintaining that same utilization ceiling, provision **11**: ten remain after the failure.

These are example assumptions, not measured industry constants. Real sizing must check database throughput, queueing latency, memory, network bandwidth and load spikes. See [Capacity Estimation](/en/topics/capacity-estimation/) to distinguish requests per second from concurrency.

## Choosing the routing algorithm

| Policy | Rule | Strength | Limitation |
| --- | --- | --- | --- |
| Round robin | Rotate through destinations | Simple when backends are similar | Ignores slow requests |
| Weighted round robin | Favor by configured weights | Handles heterogeneous servers | Weights can become stale |
| Least connections | Pick fewest active connections | Useful for variable request durations | Connections do not measure CPU work |
| IP hash | Associate clients by address | Approximate server affinity | NAT skews traffic; membership changes disrupt mapping |

NGINX documents round robin, least connections, IP hash, weights and passive health handling [1]. Each policy optimizes a different proxy for backend load; performance must be measured with real traffic.

## Statelessness and request semantics

A stateless backend should not require consecutive requests from the same user to reach the same machine. Shared session state can live in an appropriate external store, or credentials can contain signed claims where applicable. Sticky sessions may simplify legacy migrations but make backend replacement harder. Application load balancers work at the HTTP layer and may select a destination based on host or route; transport-layer load balancing uses connection information instead [2].

![HTTP requests flow from clients through a load balancer to application instances.](/diagrams/load-balancing.svg)

**Do not blindly retry a request after timeout.** A payment POST may commit successfully, yet its response may be lost. Retrying without an idempotency guarantee risks charging twice. Set bounded end-to-end deadlines, retry budgets and exponential backoff with jitter. A global outage plus retries can otherwise multiply requests just when capacity is least available.

## Health checks, draining and observability

Separate **liveness** (process responds), **readiness** (should receive traffic) and actual dependency health. If every readiness check fails as soon as the same database is unavailable, the balancer may remove every app instance at once. Tune probe thresholds to prevent flapping. For rolling deploys, stop assigning new requests to an instance, let in-flight operations finish up to a bounded deadline, and then terminate it. NGINX documents passive checks; details of active checks depend on the product and edition [1].

Monitor per-backend request rates, active connections, error ratio, p95/p99 latency, saturation and retry counts. Deploy backends across independent failure domains where possible. Treat client-IP forwarding headers as trusted only when set by a verified proxy; otherwise attackers can forge identity. State explicitly what happens when no healthy instance remains.

## Architectural limits

~~~text
Client -> DNS -> load balancer -> app A / app B / app C
                                    |       |       |
                                    +-------+-------+--> shared data tier
~~~

Adding app replicas cannot solve a single-database bottleneck. Likewise, a load balancer does not guarantee correctness of concurrent writes; see [Transaction Consistency](/en/topics/database-consistency/). Estimate whether the shared data tier can handle the full traffic and the bursts created by retries.

## Exercises and verification

1. At 2,400 requests/s and 400 requests/s per instance with 50% planned utilization, ceil(2400/200) = 12 healthy instances; 13 survive one failure with that target.
2. Explain when least connections may outperform round robin for a mixture of 5-millisecond and 5-second tasks, and why connection counts still do not measure CPU demand.
3. Describe a timeout after successful payment commit. Specify which idempotency key contract makes retry safe.
4. In a staging environment, remove one backend and confirm readiness, draining, error budget and database behavior under peak load.
