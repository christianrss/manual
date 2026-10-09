---
id: api-reliability
title: "Reliable APIs: Timeouts, Retries, Idempotency and Backpressure"
description: "Derive deadline budgets, retry amplification and idempotent commands; design failure responses, admission control and API problem details."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [network-protocols, asynchronous-messaging, rate-limiting]
sources:
  - {title: "RFC 9457 — Problem Details for HTTP APIs", url: "https://www.rfc-editor.org/info/rfc9457", kind: "internet standard"}
  - {title: "AWS Builders Library — Timeouts, Retries and Backoff with Jitter", url: "https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/", kind: "engineering article"}
  - {title: "Google SRE Book — Handling Overload", url: "https://sre.google/sre-book/handling-overload/", kind: "engineering reference"}
  - {title: "RFC 6585 — Additional HTTP Status Codes", url: "https://www.rfc-editor.org/info/rfc6585", kind: "internet standard"}
---
An API is reliable when its **observable contracts** remain understandable under timeouts, duplicated messages, overloaded dependencies and partial failures. Successful calls are straightforward; ambiguous calls are not. A timeout tells the caller that the response was not observed within the deadline, **not** that the server made no durable change. Reliability therefore begins with operation identity, effect boundaries and explicit failure semantics rather than a choice of framework [2].

## Distinguish request completion from business completion

Consider a client submitting an order. An HTTP request may be validated and placed on a durable queue, while actual fulfillment happens later. The response must distinguish **accepted for processing** from **completed**. A 202 response is appropriate when the resource's contract genuinely represents asynchronous acceptance; do not claim it means the operation already succeeded. Record a durable operation identifier, status endpoint or event mechanism so the client can learn what happened.

Another case is worse: the database commits and the server loses its connection before sending success. The client cannot infer whether its command executed. Retrying the same POST with a fresh identity may repeat the charge. For this reason, idempotency is a semantic property of the **effect**, not simply a property of an HTTP verb.

## Design idempotency around a persistent key

A client can attach an idempotency key unique within an operation scope. The server associates that key with request identity and a durable result; a repeated request with the same key and same semantic payload returns the prior outcome or its status, instead of executing another effect. A repeated key with a **different** payload must be rejected rather than silently reused. The key namespace should include tenant and operation kind to avoid cross-user confusion.

The durable idempotency record and local business mutation must share a valid atomicity boundary. An in-memory cache is insufficient after restart, and a read-then-write check can race. When an external payment processor is involved, propagate an appropriate idempotency key to that processor or implement reconciliation; a local database transaction cannot atomically commit the remote provider's effect.

![Retrying an ambiguous write with an idempotency key.](/diagrams/idempotent-request.svg)

## Timeouts are parts of an end-to-end deadline

Suppose an incoming request has a **hypothetical** 800 ms deadline. The handler spends 80 ms validating data, 120 ms consulting an account service and 250 ms writing to the database. Only 350 ms remain for other work and reply, excluding scheduling and network overhead. Each nested dependency must observe the **remaining** budget; assigning every dependency its own 800 ms timeout can violate the customer's real deadline.

Connect timeout, read timeout, total call deadline and application work cancellation are different concepts. After a caller stops waiting, the server may keep executing unless cancellation propagates and the handler honors it. Cancellation does not automatically roll back a previously committed database transaction. Choose which side effects must be permitted even after the client has disconnected.

## Retry amplification and jitter

If service A invokes B, which invokes C, retries at every layer can multiply attempts. With up to **three total attempts per layer**, one original operation may cause as many as 3×3 = 9 downstream attempts across two independently retrying layers, before additional fan-out. The failure of C may therefore create more traffic precisely when C is least capable of serving it [2].

Retry only when errors are likely transient and the operation is safe to repeat. Use a bounded exponential schedule with random jitter and an overall deadline. Jitter reduces synchronized retry storms; it does not turn a non-idempotent operation into an idempotent one. Rate limiting, retry budgets and circuit breakers should work together to prevent infinite overload loops [2][3].

~~~python
def capped_backoff_ms(attempt, base=100, cap=1600):
    if attempt < 0 or base <= 0 or cap <= 0:
        raise ValueError("invalid retry parameters")
    return min(cap, base * (2 ** attempt))

def retryable_status(status, operation_idempotent):
    transient = status in (429, 502, 503, 504)
    return transient and operation_idempotent

assert [capped_backoff_ms(i) for i in range(6)] == [100,200,400,800,1600,1600]
assert retryable_status(503, True)
assert not retryable_status(503, False)
assert not retryable_status(400, True)
~~~

The function returns a **maximum backoff envelope**, not randomized jitter. A production retry policy samples a delay under an explicitly selected jitter rule and respects server Retry-After and the remaining deadline. Real clients must handle transport exceptions separately from status codes. A 429 signals rate limiting under defined conditions [4].

## Backpressure, load shedding and bounded work

A service's admission rate cannot exceed sustainable completion capacity indefinitely without queue growth. If offered load is λ jobs/s and workers finish μ jobs/s with λ>μ, an unbounded queue grows approximately by (λ−μ) per second until constraints change. One thousand requests/s admitted into a system completing 700/s creates about 18,000 pending jobs in one minute, ignoring cancellation and retries. Returning quick 503/429 responses under deliberate overload may be better than accepting tasks that cannot meet their deadlines [3].

**Backpressure** signals producers to slow or cease submitting work; **load shedding** rejects work to protect the service; **concurrency limiting** caps simultaneous executions. These act on different variables. A rate limit of 100 RPS is not a guarantee of safety if each request suddenly requires 20 seconds instead of 20 milliseconds.

## Design machine-readable error contracts

RFC 9457 specifies a JSON problem-details format with properties such as type, title, status, detail and instance [1]. The error body is part of the public contract: clients should rely on documented stable type identifiers, not parse English message text. Avoid returning secret internal stack traces. Include a correlation ID where appropriate and specify retryability and user-facing remediation without disclosing sensitive implementation details.

~~~json
{
  "type": "https://example.org/problems/upstream-unavailable",
  "title": "Service temporarily unavailable",
  "status": 503,
  "detail": "Retry later using the same operation identifier."
}
~~~

The example type URL is illustrative; a real service should publish stable documentation there. Keep HTTP status, content type and response body consistent. Standard error shape does not prescribe whether the underlying operation is safe to retry.

## Fault injection and observable guarantees

Build a matrix: crash before transaction; crash after commit but before response; duplicate concurrent keys; timed-out downstream with unknown outcome; full queue; overloaded database; and reverse proxy returning an error while the backend keeps running. Check durable state, duplicate **business effects**, latency percentiles and time to recovery, not only response codes.

| Failure | Required design decision |
| --- | --- |
| Timeout after write | How does client retrieve result by operation ID? |
| Duplicate concurrent POST | Which unique constraint serializes one effect? |
| Dependency overloaded | Which layer sheds load and which retries? |
| Partial regional outage | Which data/operations can fail over safely? |
| Downstream returns malformed error | How does caller classify uncertainty? |

## Exercises and verification

1. With initial deadline 500 ms and 200 ms already spent, explain why a new call cannot receive an independent 500 ms budget.
2. Compute worst-case attempts when three layers each perform two total attempts: 2³ = 8, assuming no early termination. Why is this a poor retry policy?
3. Sketch a transaction that inserts an operation record under a unique key and applies one local change. Show why two concurrent clients cannot both commit the same effect.
4. Compare explicit rejection with endless buffering when λ>μ for ten minutes; estimate backlog and customer-observed delays.
5. Explain why the retry classifier above is necessary but **not sufficient**: transport ambiguity, Retry-After, operation semantics and request identity are external to that function.
