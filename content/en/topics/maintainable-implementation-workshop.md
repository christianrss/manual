---
id: maintainable-implementation-workshop
title: "Maintainable Implementation Workshop: Token Bucket, Clock Injection and Tests"
description: "Implement a reviewable token-bucket limiter with an injected clock, explicit invariants and deterministic tests; assess distributed limits."
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites: [object-oriented-design, testing-strategies, rate-limiting]
sources:
  - {title: "AWS Architecture Blog — Rate limiting best practices", url: "https://aws.amazon.com/blogs/architecture/throttling-a-tiered-multi-tenant-rest-api-at-scale-using-api-gateway-part-1/", kind: "original engineering guidance"}
  - {title: "Amazon API Gateway — Throttle API requests", url: "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html", kind: "official vendor documentation"}
  - {title: "Python — time.monotonic", url: "https://docs.python.org/3/library/time.html#time.monotonic", kind: "official Python documentation"}
---
An interview solution that returns the expected values can still be difficult to maintain, test or deploy. This workshop implements a **token-bucket rate limiter** as a small domain component. The goal is not just the algorithm, but a reviewable contract: explicit units, injected time source, edge-case handling, stable state ownership, deterministic tests, and a clear statement of where an in-memory implementation stops being sufficient. Token buckets are widely used in rate control because they limit long-run throughput while permitting bounded bursts [1].

## Convert a fuzzy request to a contract

The initial request is “limit requests to ten per second”. It is ambiguous: may a client send ten requests in the same millisecond? Can unused capacity accumulate? Is the limit per user or global? What should happen after a system clock correction? Define one concrete behavior: each independent bucket holds at most C tokens, starts full, refills at r tokens per second using **elapsed monotonic time**, and each accepted operation spends a positive integer cost. Rejected operations do not consume tokens.

At time t, if the previous observation is t₀ and current tokens are T₀, the new balance is **min(C,T₀ + r·(t−t₀))**. Accept an operation if the balance is at least its cost. This yields a maximum burst of C and long-run budget around r per second, but it is **not** the same as a guarantee of exactly r operations in every sliding one-second interval.

## Identify authority, state and failure scope

An in-process bucket can enforce one logical client limit **only while all its requests reach the same stateful object** and updates are synchronized. With four stateless API replicas, each maintaining ten tokens, a client can potentially spend forty tokens across replicas. For a globally enforced quota, an authoritative distributed store or routing/sharding policy must own the state and atomic updates. A Redis script or transactional database operation may implement atomicity, but the choice affects latency and failure policy [2].

Treat the bucket as **business decision logic** independent of HTTP. Authentication and principal identity belong to the surrounding request boundary; a client must not choose another tenant's bucket key. HTTP 429 and Retry-After are responsibilities of the adapter after the limiter returns a decision. Separating these responsibilities makes tests focus on the algorithm without starting a web server.

## Inject a clock instead of sleeping

Calling real time inside a rate limiter makes tests slow and nondeterministic. Pass a callable clock through the constructor; use a monotonic source in production and a manual clock in tests. Monotonic time is intended for intervals, while calendar/wall-clock timestamps can jump due to synchronization or administrative changes. An injected clock also makes time-related edge cases directly reproducible [3].

![Token-bucket state transitions with refill, consumption and rejected requests.](/diagrams/maintainable-token-bucket.svg)

~~~python
from time import monotonic

class TokenBucket:
    def __init__(self, capacity, rate_per_second, clock=monotonic):
        if not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("positive integer capacity required")
        if rate_per_second <= 0:
            raise ValueError("positive refill rate required")
        self.capacity = capacity
        self.rate = rate_per_second
        self._clock = clock
        self._last = clock()
        self._tokens = float(capacity)

    def allow(self, cost=1):
        if not isinstance(cost, int) or cost <= 0:
            raise ValueError("positive integer cost required")
        now = self._clock()
        elapsed = now - self._last
        if elapsed < 0:
            raise ValueError("clock moved backwards")
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last = now
        if cost > self._tokens:
            return False
        self._tokens -= cost
        return True

class ManualClock:
    def __init__(self):
        self.now = 0.0
    def __call__(self):
        return self.now
    def advance(self, seconds):
        if seconds < 0:
            raise ValueError("negative advance")
        self.now += seconds

clock = ManualClock()
bucket = TokenBucket(2, 1, clock)
assert bucket.allow() and bucket.allow()
assert not bucket.allow()
clock.advance(0.5)
assert not bucket.allow()
clock.advance(0.5)
assert bucket.allow()
assert not bucket.allow()
~~~

The implementation uses floating-point tokens for a teaching example. For billing-grade quotas or very long-running systems, choose precision and overflow policies deliberately; numeric input validation may also reject NaN, infinity and arbitrary user-defined numeric types. The code assumes a trusted finite refill rate and trusted clock. It is intentionally **not thread safe** without an enclosing lock and is not durable across restarts.

## Boundary tests and the rejected-request invariant

The **rejected-request invariant** means a failed `allow` does not debit the current balance. Time still advances, and refilling that occurs during a rejected attempt remains part of the state. Verify zero tokens, partial refill, full saturation after a long pause and invalid cost. A common bug is subtracting cost before checking availability, creating negative tokens.

~~~python
clock2 = ManualClock()
limiter = TokenBucket(3, 2, clock2)
assert limiter.allow(3)
assert not limiter.allow(1)
clock2.advance(0.25)
assert not limiter.allow(1)
clock2.advance(0.25)
assert limiter.allow(1)
clock2.advance(100)
assert limiter.allow(3)
assert not limiter.allow(1)
for invalid in (0, -1, 1.5):
    try:
        limiter.allow(invalid)
        assert False
    except ValueError:
        pass
~~~

This test asserts **observable decisions** rather than inspecting the private `_tokens` field. Private-field assertions may be appropriate for an internal invariant test, but relying on them for every test couples the suite to implementation details unnecessarily. Prefer a stable behavioral interface.

## Proof sketch and complexity

With trusted finite inputs, the invariant is **0 ≤ tokens ≤ C** after each `allow` call. At initialization tokens=C. During refill, elapsed≥0 and rate>0 imply the balance cannot decrease; taking min(C,...) keeps it at most C. The method subtracts only when available tokens≥cost and cost>0, so it cannot make the balance negative. Rejection leaves the balance unchanged after refill. Induction on the number of calls proves the invariant.

Each decision takes O(1) arithmetic operations and O(1) instance storage **under fixed-precision arithmetic**. That is local computational complexity, not wall-clock response time of a remote quota database. Under concurrent calls without a lock, separate reads and writes can violate the invariant; atomicity must be addressed independently of arithmetic correctness.

## Counterexamples: fixed windows and replication

A fixed-window counter can allow nearly 2C operations at the boundary between adjacent windows: send C just before one window ends, and C immediately after the next begins. Token bucket instead constrains accumulated tokens and refill behavior, though it still permits some bursts by design. A **sliding-window** limiter may be more appropriate if the product demands an exact maximum in every window, at higher accounting cost.

Another counterexample occurs when the same client is routed to separate processes whose buckets are independent. Each process can approve its own budget, violating a global per-client contract. Sticky sessions help only while routing and failure handling preserve the mapping; they do not replace a single authoritative decision when clients can reach multiple nodes.

## Design review and extensibility

| Engineering decision | Benefit | Limitation |
| --- | --- | --- |
| Inject `clock` | Fast deterministic tests | Requires trusted monotonic source |
| Keep HTTP out of core | Reusable decision logic | Adapter must map 429 and headers |
| Reject invalid costs | Clear input contract | Need request-cost policy |
| Start full | Supports burst capacity | May surprise strict per-second limits |
| Use in-memory state | Simple low-latency prototype | No cross-process durability |
| Lock per bucket | Protects threads sharing bucket | Does not coordinate independent replicas |

A class is justified because the bucket **owns evolving state** and protects a coherent invariant. Do not introduce strategy factories, databases and message brokers unless a specific requirement warrants them. A code review should discuss input typing, fairness, eviction of inactive client buckets, unbounded cardinality, authentication, metrics and what happens when the authoritative limiter fails.

## Exercises and verification

1. Calculate the decisions for C=3, r=2 tokens/s under calls at times 0, 0, 0, 0.25 and 0.5, all cost one.
2. Explain why a bucket starting full is different from an exact sliding-window limit.
3. Add a synchronized wrapper using `threading.Lock`; test it with two threads and shared state.
4. Design a distributed storage schema for tenant-scoped buckets with an atomic conditional update.
5. Specify metrics that reveal rejected requests, high-cardinality bucket explosion, replica drift and quota store outages.

**Related chapters:** [Rate limiting architecture](/en/topics/rate-limiting/), [object-oriented contracts](/en/topics/object-oriented-design/), [testing strategies](/en/topics/testing-strategies/) and [concurrency workshop](/en/topics/concurrency-interview-workshop/) explain the surrounding trade-offs [1][2].
