---
id: caching
title: "Caching: Correctness, Invalidation and Failure"
description: "Reason about cache-aside, TTL, stampedes, stale reads, hit rates and invalidation under explicit consistency and availability requirements."
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites: [hash-tables, capacity-estimation]
sources:
  - {title: 'RFC 9111 — HTTP Caching', url: 'https://www.rfc-editor.org/rfc/rfc9111', kind: internet standard}
  - {title: 'AWS Builders Library — Caching challenges and strategies', url: 'https://aws.amazon.com/builders-library/caching-challenges-and-strategies/', kind: engineering article}
---
A cache stores a reusable result nearer to its consumers, often lowering latency or origin load. It creates a second representation of state, which introduces consistency and failure questions. **Caching is not only a performance optimization; it changes the system's correctness model** [1][2].

## Define the cache contract
Before introducing a cache, define its key, value, validity period and invalidation authority. A cache key must encode every input that materially changes the answer. A response dependent on user identity or permissions must not be globally keyed only by URL; that could leak private data. Decide whether stale data is acceptable and for how long.

A cache hit rate `H` means `H` fraction of requests are served from cache during an observed window. Approximate backend read rate is `(1-H) × total_read_rate`, **only if** misses each produce a single backend read and there is no refresh traffic, batching or stampede. At 10,000 RPS and hit rate 90%, a simplistic estimate is 1,000 origin RPS, not zero.

## Cache-aside read path
In cache-aside (lazy loading), the application checks the cache; on a miss it fetches from the source of truth and attempts to populate the cache. This avoids storing never-read entries. It also means a cold cache can suddenly expose the database to full traffic [2].

```text
GET(key) → cache hit? → return cached value
                  no → read database
                     → set cache with TTL
                     → return value
```

The **TTL** limits how long an untouched cache entry is considered reusable, but it does not prove data is immediately consistent after a write. A write to the database followed by invalidation creates a race: concurrent readers may fetch and reinsert an old value unless invalidation/versioning is designed carefully.

## Cache stampede and failure handling
If a popular key expires during a traffic spike, hundreds of concurrent requests may query the origin. Common mitigations include per-key request coalescing (single-flight), TTL jitter, proactive refresh and serving bounded stale values when permitted. Each policy needs a bound: indefinite stale-if-error behavior is unacceptable for critical balances or authorizations.

When the cache becomes unavailable, decide deliberately whether requests bypass it or fail closed. Bypassing a cache is not always a safe fallback: the resulting surge may overload the database and convert a small cache incident into a larger outage [2].

| Strategy | Benefit | Risk / assumption |
| --- | --- | --- |
| Cache-aside | Simple, on-demand | Cold misses and stampedes |
| Write-through | Cache updated as part of write path | Adds latency and failure coupling |
| Short TTL | Bounds ordinary staleness | More misses and origin load |
| Versioned keys | Avoids ambiguous overwrites | Old entries consume capacity until expiry |
| CDN / HTTP cache | Close to users | Must respect cache-control and privacy directives [1] |

## HTTP cache semantics versus application cache
HTTP defines explicit freshness, validation and cache-control rules; `Cache-Control: no-store` is not interchangeable with `no-cache`. The latter ordinarily requires successful validation before reuse, while `no-store` forbids intentional storage by compliant caches [1]. A Redis-based application cache has different semantics and must implement its own coherency rules.

## Exercises and verification
1. Two users request `/profile` with different identities. What belongs in the cache key or why should the response not be shared?
2. After invalidation, an old in-flight read attempts to repopulate a key. Design a version token or compare-and-set rule to reject stale writes.
3. At 4,000 reads/s and 95% hit rate, estimate baseline database reads (`200/s`) and explain why a correlated expiration burst may be much higher.

A correct cache design must document how it fails, which data it can serve stale, and how origin overload is prevented.
