---
id: cpp17-concurrency-implementation
title: "C++17 Engineering Workshop: Thread-Safe Token Bucket and CI"
description: "Build and test a native C++17 token bucket with steady clock injection, mutex invariants, input validation and compiler-backed CI."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [maintainable-implementation-workshop, concurrency-synchronization]
sources:
  - {title: "C++ reference — steady_clock", url: "https://en.cppreference.com/w/cpp/chrono/steady_clock.html", kind: "language reference"}
  - {title: "C++ reference — mutex", url: "https://en.cppreference.com/w/cpp/thread/mutex.html", kind: "language reference"}
  - {title: "Amazon API Gateway — throttling", url: "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html", kind: "official product documentation"}
---
Correctness and maintainability do not automatically transfer from Python to C++. The same token-bucket requirement must now account for **value types, constness, lifetimes, clock monotonicity, floating-point range, mutex ownership and real data races**. This workshop implements a C++17 version of the previously published rate limiter and compiles its tests as a separate CI quality gate. The full reference file is [token_bucket.cpp](https://github.com/christianrss/manual/blob/main/examples/cpp/token_bucket.cpp), and the repository tests compile it with C++17 and pthread support.

## Re-state the contract independently of language

A bucket owns a capacity C, a refill rate r tokens/s, and balance T with invariant **0 ≤ T ≤ C**. It starts full. On a call at monotonic time t, it computes elapsed seconds since the previous call, refills to min(C, T+rΔt), then approves a finite positive cost only if enough tokens remain. Rejected operations still advance the internal clock observation and preserve replenished tokens. This describes behavior; it does not specify which classes or packages to create.

The Python version used an injected callable clock, so C++ should do the same. A test needs to control elapsed time without sleeping; production needs a source appropriate for durations rather than civil clock corrections. C++ `std::chrono::steady_clock` is designed for monotonic interval measurement [1]. Its time points are not calendar timestamps, and the arithmetic must explicitly convert a duration to seconds.

## Map design choices to C++17 primitives

The implementation's core looks like this (the [complete source](https://github.com/christianrss/manual/blob/main/examples/cpp/token_bucket.cpp) contains the constructor, private fields and standalone assertions).

~~~cpp
// Inside TokenBucket::allow(double cost):
std::lock_guard<std::mutex> guard(mu_);
const auto next = now_();
const double seconds =
    std::chrono::duration<double>(next - last_).count();
if (seconds < 0) throw std::logic_error("clock moved backwards");
tokens_ = std::min(capacity_, tokens_ + seconds * rate_);
last_ = next;
if (tokens_ < cost) return false;
tokens_ -= cost;
return true;
~~~

The lock covers **read, refill, check and subtraction as one critical section**. Putting only the subtraction under a mutex would leave a time-of-check/time-of-use race. A `std::mutex` synchronizes threads sharing the same bucket object, not independent API processes or remote stores. The C++ memory model does not allow treating racy writes as a merely occasional wrong answer: unsynchronized conflicting non-atomic accesses cause undefined behavior [2].

## Type and error boundaries

Validate finite positive capacity, rate and cost with `std::isfinite`, rejecting NaN and infinity before arithmetic. Unlike the Python teaching version, this C++ implementation accepts positive fractional operation costs. That is an explicit **contract difference**, not accidental equivalence; the Python example requires integer costs. The C++ constructor and `allow` can throw for invalid parameters, so callers need an exception policy. Returning false remains reserved for a valid request without enough capacity.

An injected `Now` function must remain callable during object lifetime. A lambda capturing a manual-clock variable by reference is safe only while that variable outlives the bucket. The example defines the clock before the bucket, causing the bucket to be destroyed first. Capturing a temporary local reference and later calling `allow` would be a lifetime bug that Python's reference semantics do not model identically.

## Understand state ownership and object copying

The class contains a mutex and is intentionally **noncopyable** under its default special member semantics. A copy of the tokens without coherent synchronization could duplicate the quota and violate a global limit. Each bucket owns its own `last_` and `tokens_` values. A collection of buckets may hold references or pointers, but the container lifetime and identity map must be designed deliberately.

The mutex is private because callers should receive a single atomic **decision operation**, rather than separate public getter and decrement methods. An interface exposing `get_tokens` followed by `spend` would invite unsafe read-then-act sequences.

## Deterministic clock and concurrency checks

The standalone program uses a controlled `steady_clock::time_point`. It spends two tokens, advances 500 ms twice, verifies a partial refill does not approve a whole-token cost, then confirms the complete refill. It also advances 24 hours to prove capacity saturation. A second test starts twelve `std::thread` workers against a bucket with three initial tokens and a negligible refill rate: exactly three calls should succeed.

The concurrent test **exercises** locking but does not prove every interleaving. A scheduler could execute the workers largely sequentially. The invariant is justified by the lock's mutual exclusion and the arithmetic, not by an assertion that happened to pass once. For deeper race detection, build with ThreadSanitizer where the runner/toolchain supports it and examine any report carefully [2].

## CI as evidence, not documentation decoration

A code sample inside a Markdown `cpp` fence is not executed by the website's existing Python fence runner. This edition adds a dedicated repository test that compiles the **actual C++ file** using `g++ -std=c++17 -Wall -Wextra -Werror -pthread`, runs it with assertions enabled, and fails the pipeline when it fails to compile or exits unsuccessfully. A pass establishes success on that runner/compiler—not portability to every ABI, operating system and toolchain.

The program uses no external libraries and no deployment credentials. The compiler is required on the Linux CI runner; if it is absent, CI fails explicitly rather than silently skipping native verification. Run local commands from the repository root:

~~~text
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pthread examples/cpp/token_bucket.cpp -o /tmp/manual-token-bucket
/tmp/manual-token-bucket
~~~

## Performance, numerics and operational limits

An `allow` decision performs O(1) arithmetic under fixed-width floating-point operations and uses O(1) state per bucket. However, under contention the lock can increase queueing latency. A multi-tenant server with millions of inactive bucket instances needs eviction, memory budgeting and a stable identity key; storing buckets indefinitely gives O(number of observed tenants) memory, not constant system memory.

The toy bucket does not coordinate several replicas or survive process restart. For a globally enforced limit, use an authoritative atomic state transition (for example a database transaction or correctly designed server-side data-store script), and specify behavior during network partitions and store outages [3]. A local mutex cannot make a distributed quota correct.

## Counterexamples and review criteria

| Mistake | Consequence | Safer contract |
| --- | --- | --- |
| Use wall clock for elapsed time | Backward or forward clock adjustments | `steady_clock` |
| Lock only subtraction | Concurrent refill/read race | Lock entire decision |
| Permit NaN cost | Comparisons can bypass expectations | Validate finite positive numbers |
| Copy state to a new bucket | Duplicate quota | Stable authority and identity |
| Keep one bucket per API replica | Aggregate quota multiplies | Coordinated durable authority |
| Skip native compilation | Example may not compile | Dedicated compiler CI test |

## Exercises and verification

1. Explain why a `std::lock_guard` needs to protect both replenishment and consumption.
2. Modify the source to use integral fixed-point microtokens and list precision and overflow trade-offs.
3. Try `-fsanitize=thread` on a supported environment, then intentionally remove the mutex and inspect the observed race report.
4. Explain the lambda lifetime requirement when injecting the manual clock by reference.
5. Sketch a distributed variant and state how you would handle the authoritative store becoming unavailable.

**Related chapters:** [Maintainable Python implementation](/en/topics/maintainable-implementation-workshop/), [memory ordering](/en/topics/memory-ordering-atomics/), [concurrency workshop](/en/topics/concurrency-interview-workshop/) and [rate limiting](/en/topics/rate-limiting/) provide the foundations.
