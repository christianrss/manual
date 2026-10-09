---
id: rate-limiting
title: "Rate Limiting: Token Buckets and Distributed Guarantees"
description: "Derive token-bucket admission, compare counting windows, enforce HTTP 429 and discuss consistency, concurrency and failure handling."
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites: [capacity-estimation, asynchronous-messaging]
sources:
  - {title: "RFC 6585 — Additional HTTP Status Codes, section 4", url: "https://www.rfc-editor.org/rfc/rfc6585", kind: "internet standard"}
  - {title: "NGINX — HTTP request limiting module", url: "https://nginx.org/en/docs/http/ngx_http_limit_req_module.html", kind: "official software documentation"}
---
**Rate limiting** decides whether a request may consume a bounded resource *now*. It can limit abuse, protect capacity and enforce API quotas. It differs from concurrency limiting (work in flight), load balancing (routing) and backpressure (slowing producers). Even a service within its requests-per-second allowance can overload if each request suddenly becomes much more expensive.


![Token bucket with a finite burst capacity and continuous refill rate, admitting a request only when enough tokens remain.](/diagrams/rate-limiting-invariant.svg)

## Define the contract before choosing an algorithm

Specify the **identity key** (account, API key, tenant or IP), **cost unit** (request, token or computational weight), **time interval**, **burst capacity** and **rejection behavior**. IP alone can be unreliable: many legitimate users share an address behind NAT and abusive users can rotate addresses. An authenticated key is preferable when available, with a separate policy for anonymous clients.

HTTP status **429 Too Many Requests** indicates too many requests from a user in a period. RFC 6585 does not impose a particular counting technique and permits the Retry-After response header to guide subsequent requests [1].

## Common algorithms and their differences

| Method | State | Advantage | Limitation |
| --- | --- | --- | --- |
| Fixed window | Counter and current window | Simple and bounded | Bursts at the window boundary |
| Sliding log | Recent timestamps | Exact rolling allowance | Memory proportional to recorded requests |
| Sliding counter | Neighboring window counts | Bounded state | Approximation error |
| Token bucket | Tokens and refill time | Explicit refill rate and burst | Atomicity and clock requirements |

For example, a fixed window allowing ten calls per minute may admit ten requests at 00:59.9 and another ten at 01:00.1. The client has sent twenty requests within a fraction of a second without violating either fixed-window counter. A true rolling 60-second count would reject part of that cluster.

## Derive the token-bucket invariant

Let B be maximum capacity in tokens, r the refill rate in tokens per second, t the current time, and last the preceding update time. Before admitting an operation, set tokens = min(B, tokens + r × (t-last)). Admit a request of cost c only when tokens is at least c, then subtract c. Provided time is monotone and operations are serialized, tokens stays between zero and B. Across an interval of duration T, admitted work cannot exceed B + rT under one authoritative bucket.

With B=5, r=2 tokens/s and unit cost, five simultaneous requests are accepted and the sixth is rejected. After half a second, one token is restored. Capacity five means an instantaneous burst of five, not five requests *per second*.

~~~python
class TokenBucket:
    def __init__(self, capacity, rate):
        if capacity <= 0 or rate <= 0:
            raise ValueError('positive capacity and rate required')
        self.capacity = float(capacity)
        self.rate = float(rate)
        self.tokens = float(capacity)
        self.last = 0.0

    def allow(self, now, cost=1):
        if cost <= 0 or cost > self.capacity or now < self.last:
            raise ValueError('invalid cost or time')
        self.tokens = min(self.capacity, self.tokens + (now-self.last)*self.rate)
        self.last = now
        if self.tokens < cost:
            return False
        self.tokens -= cost
        return True

b = TokenBucket(5, 2)
assert all(b.allow(0) for _ in range(5))
assert not b.allow(0)
assert b.allow(0.5)
assert not b.allow(0.5)
~~~

This is a **sequential teaching implementation**: it is neither thread-safe nor distributed. The read-modify-write must be atomic when two workers share one bucket.

## Distributed state and error policy

If ten independent application nodes each enforce 100 requests/s for the same customer, that customer may obtain nearly 1,000 requests/s globally. A **local limit is not a global quota**. Options include a centralized gateway, an atomic shared store, or explicitly allocated regional or per-instance budgets. Shared state adds contention, latency and outage decisions: **fail open** accepts excess traffic when the store is down, while **fail closed** rejects possibly legitimate traffic. The correct choice is endpoint-specific.

Monotonic clocks work inside one process but timestamps from unrelated hosts cannot be compared casually. Read-then-write against a shared counter risks both workers accepting the last token. Use a transactional or atomic server-side operation. NGINX implements request limiting based on a leaky-bucket-style mechanism with burst, delay and rejection configuration; its exact semantics are not identical to this educational token-bucket model [2].

## Operations and verification

Choose a clear 429 response body, optionally including Retry-After, and require clients to apply bounded backoff with jitter. Separate expensive operations from lightweight reads when necessary. Track accepted versus rejected requests, per-tenant concentration, backend saturation, store failures and p95/p99 latency. Rate limiting does not replace authentication, authorization or a work-concurrency limit.

## Prove the token-bucket upper bound

Let `b(t)` denote current tokens, capacity `B`, refill rate `r` tokens/s, and admitted work counted in the same token units. Between any times `t0` and `t1`, admitted work cannot exceed `B+r(t1−t0)` under a single serialized bucket, because at most `B` tokens are initially present and refill adds at most `rΔt`. This does **not** guarantee an instantaneous requests-per-second ceiling: a bucket can allow a burst of size B at one moment. Use a concurrency semaphore or active-work limit when work duration, rather than rate alone, risks saturating resources.

## Compare fixed, sliding and leaky models

A fixed counter resets at calendar-window boundaries, so a client can send nearly two windows' worth of requests in a narrow interval spanning a boundary. A sliding-log limiter stores timestamps and can enforce an exact rolling count at the price of more state. A token bucket permits explicit credit accumulation up to B. A leaky-bucket queue drains at a controlled service rate but may add latency or drop requests once full. Vendor implementations may use 'leaky bucket' terminology with specific scheduling rules; test actual semantics rather than assuming equations match [2].

## Atomicity and distributed limits

Suppose a distributed counter shows one remaining token, and two instances concurrently read it. If both decrement through separate read/write steps, both may accept even though capacity was one. Use an atomic server-side transition or transaction and document how the clock is obtained. Partitioning the quota among nodes reduces shared coordination but creates *budget transfer* and fairness questions when traffic is uneven. Fail-open policies preserve availability but risk excess costly work; fail-closed policies can reject authorized customers when the shared limiter is unavailable.

For a hierarchy of limits—per-IP, per-user and global—state evaluation order and whether a rejected request consumes other quotas. The server should avoid leaking identities through timing or detail of error responses. Rate limiting is not authentication, authorization, bot detection or a guarantee of backend capacity.

## HTTP response policy and client behavior

HTTP 429 states that too many requests occurred; a `Retry-After` value may provide a retry delay. A client should not immediately retry all failures in lockstep: synchronized retries can generate another spike. Prefer bounded exponential backoff with jitter and a maximum retry deadline, considering whether the operation is idempotent [1].

```text
POST /v1/expensive-operation
HTTP/1.1 429 Too Many Requests
Retry-After: 5
Content-Type: application/json

{"error":"rate_limited","retryable":true}
```

## Experimental checks

Use a controlled monotonic clock to validate: initial burst B; exactly zero remaining tokens; partial refill; long idle period never increasing above B; fractional operation cost; invalid negative time movement; and two concurrent attempts competing for the final token. The last test **cannot** be proven by the current in-memory sequential demonstration—run it against the intended atomic shared-state implementation. Additionally test regional partitions and limiter-store outages to confirm the documented failure policy.

## Exercises and verification

1. If B=8 and r=1 token/s, eight requests at time zero exhaust tokens; after three seconds exactly three unit-cost requests may pass.
2. Reconstruct the twenty-request fixed-window boundary example and explain why both window counters remain valid.
3. Explain why ten independent nodes of 100 requests/s do not enforce a global 100 requests/s limit.
4. Modify the Python example for fractional cost 2.5. Describe the atomic storage operation required before this could safely serve concurrent clients.
