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

## Routing policies and queueing behavior

**Round robin** distributes requests in sequence but assumes approximately equal request cost and compatible instance capacity. **Weighted round robin** reflects known differences in host capacity but not instantaneous saturation. **Least connections** directs work to a node with fewer active connections; it can be misleading when a connection is idle or multiplexes many requests. A latency-aware policy uses feedback but must avoid oscillation and unfair concentration caused by noisy measurements. The algorithm is a workload assumption, not an unconditional ranking of strategies [1].

Distinguish layer-4 routing (transport tuples and connections) from layer-7 routing (HTTP method, path, headers, host or cookies). TLS may terminate at the gateway or be passed through; the choice affects certificate ownership, observability and the trust boundary. Never assume a client IP header can be trusted when the proxy chain is not authenticated.

## Stateful traffic and connection draining

A stateless application can route successive requests from the same user to different instances because session state lives in a durable or appropriately shared component, or is explicitly self-contained and validated. **Sticky sessions** can preserve in-memory state temporarily but complicate failover and unevenly distribute hot users; they are not a substitute for a deliberate session model.

When removing a node, first stop admitting new work, then allow in-flight requests to finish until a bounded deadline. Different protocols need different semantics: a WebSocket may remain open for hours, while an HTTP request may last milliseconds. A node that passes TCP health checks can still be broken at the application layer; use readiness checks for routing and a separate process liveness policy.

## Health checks and correlated failures

For `N` healthy instances each providing `C` sustainable requests per second at the required latency, rough provisioned capacity is `N×C`, but correlated dependencies such as one saturated database invalidate independent-server arithmetic. Active checks detect known failure conditions; passive checks use observed traffic but may react too slowly or mark nodes bad during a shared downstream outage. Retry amplification from gateways can make the incident worse.

A **single load balancer** is itself a failure domain. Redundancy may require multiple gateways and a strategy for DNS, anycast or managed failover. A successful failover test should verify routing convergence and client behavior, not merely that the second gateway is reachable [2].

## Capacity example and observability

For peak 3,000 RPS and 500 RPS measured maximum *per healthy instance*, planning at 60% yields 300 RPS planned per node; ten nodes cover peak, and eleven allow one failure at the same target. Yet if 20% of operations cost five times as much CPU as the others, a simple RPS metric hides the shift in resource consumption. Segment load tests by endpoint and use completed RPS, p95/p99, error rate, active requests and saturation.

| Failure | Visible symptom | Engineering response |
| --- | --- | --- |
| One instance stops | 5xx/connection failures | Health detection, retry budget and drain |
| All instances share failing database | Correlated failures | Shed work; do not route endlessly |
| Client session held only in memory | Logout after failover | Shared/durable session contract |
| Slow requests dominate connections | Uneven work despite equal RPS | Prefer workload-aware health/cost metrics |

**Review question:** If you split a service into more replicas, which parts of state must also move? If the answer is 'none' but workers keep mutable session data in local RAM, the proposed scalability claim is incomplete.

## Exercises and verification

1. At 2,400 requests/s and 400 requests/s per instance with 50% planned utilization, ceil(2400/200) = 12 healthy instances; 13 survive one failure with that target.
2. Explain when least connections may outperform round robin for a mixture of 5-millisecond and 5-second tasks, and why connection counts still do not measure CPU demand.
3. Describe a timeout after successful payment commit. Specify which idempotency key contract makes retry safe.
4. In a staging environment, remove one backend and confirm readiness, draining, error budget and database behavior under peak load.
