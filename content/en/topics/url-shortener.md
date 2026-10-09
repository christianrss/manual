---
id: url-shortener
title: "Case Study: Design a URL Shortener"
description: "Design a URL-shortening service from requirements through ID generation, storage, redirects, caching, abuse prevention and measured capacity."
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites: [capacity-estimation, caching, database-consistency]
sources:
  - {title: 'RFC 3986 — Uniform Resource Identifier Syntax', url: 'https://www.rfc-editor.org/rfc/rfc3986', kind: internet standard}
  - {title: 'OWASP — Unvalidated Redirects and Forwards', url: 'https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html', kind: security guidance}
  - {title: 'RFC 9110 — HTTP Semantics', url: 'https://www.rfc-editor.org/rfc/rfc9110', kind: internet standard}
---
A URL shortener is a small interface with nontrivial architecture behind it. It accepts a long destination URL, issues a short code and redirects subsequent visitors. The evaluation is not whether you can draw a database; it is whether you can make explicit, testable decisions about durability, uniqueness, latency, abuse and scale [1].

## Requirements before components
Functional requirements: create a mapping, resolve an active code to a destination and optionally expire or revoke a mapping. Clarify whether codes are custom, whether owners can edit a destination, whether analytics are required and whether redirects must survive region failures.

Nonfunctional requirements: write and read rates, target latency percentiles, retention, authorization to create mappings, availability objective and acceptable staleness after revocation. A safety policy must address phishing and malicious URLs; a valid URI string does not imply a safe destination [2].

## Capacity scenario
Suppose the service creates 1 million links/day and serves 100 million redirects/day. Average rates are about 12 writes/s and 1,157 reads/s. If traffic peaks at 10 times average, peak redirects are roughly 11,574/s. Assume a mapping record consumes **200 bytes of logical data**. The new mapping payload is about 200 MB/day, or about 73 GB/year before replicas, storage-engine indexes, metadata and operational overhead. These numbers are hypothetical; they exist to make bottlenecks discussable.

## API contract and source of truth
A minimal API might be:

```text
POST /api/links  {"destination":"https://example.org/article"}
  -> 201 {"code":"7Qp3A", "short_url":"https://s.example/7Qp3A"}
GET /7Qp3A
  -> 302 Location: https://example.org/article
```

Choose `302` if the system needs destinations to remain changeable without permanent browser caching assumptions. A permanent redirect such as `301` has distinct semantics and caching consequences [3]. Validate URL syntax and scheme, forbid disallowed target categories according to policy and rate-limit link creation. Do not accept arbitrary redirect destinations from untrusted query parameters.

Schema: `links(code PRIMARY KEY, destination, owner_id, created_at, expires_at, state, version)`. A unique database constraint guarantees no duplicate active primary key even under concurrent creators. The database is authoritative; caches are derived acceleration.

## Code generation and collisions
A base-62 alphabet holds `62^k` possible fixed-length codes of length `k`. With 7 characters that is about 3.52 trillion possible strings. This **does not guarantee collision-free random generation**. The birthday effect means collisions become likely earlier than exhausting the whole space; therefore insert atomically under a unique constraint and regenerate on conflict. Alternative: allocate unique sequential numeric IDs and encode them in base 62, accepting that sequential IDs may expose creation patterns.

## Redirect read path and failure handling
![A possible stateless request path, including cache and durable database.](/diagrams/request-path.svg)

`GET /code` can first consult a local/distributed cache; on miss it reads the mapping database. Cache entry versioning or short TTL limits stale destinations, but fast revocation may require bypass/invalidation guarantees. A nonexistent code should return `404`; an intentionally expired mapping may use `410 Gone` if that distinction is part of the public contract [3]. Do not invent an expiration rule implicitly.

A production design also needs metrics (read success rate, p99 latency, cache hit rate, blocked abuse), backups and restore tests, ownership/audit changes, and protection against a popular code becoming a hot key. Analytics should not synchronously block redirects unless required.

## Trade-offs that should be challenged
- A globally distributed database is not automatically needed for 12 average writes/s; start with simpler replication and measured read latency.
- Caching every redirect can propagate unsafe or revoked destinations if invalidation is weak.
- Custom aliases require a uniqueness and namespace policy; case sensitivity must be explicit.
- A short code should not be treated as an authorization token. Unpredictability may reduce enumeration, but access control is a separate requirement.

## Make URL identity and redirect semantics explicit

A short code is a public identifier, **not an access token**. If private destinations exist, authentication and authorization must be performed independently of how difficult a code is to guess. Decide whether links are mutable or immutable, when expiration is enforced, whether custom aliases may be reassigned, and whether case matters. Those choices determine cache keys, schemas and potential abuse cases. Validate schemes against an allowlist and inspect redirects according to a clearly stated safety policy; a syntactically valid URL can still lead to a malicious destination.

For redirects, `301` and `308` communicate permanence whereas `302` and `307` are temporary, with differences in how methods and bodies are preserved. Browser/proxy caching can make a revoked or edited destination difficult to invalidate if permanent caching was previously allowed. Choose status codes according to the product contract and test the actual client behavior [3].

## Derive identifier-space constraints

A fixed-length alphabet of size `b` and code length `k` yields `b^k` possible codes. For Base62 and 7 symbols, there are `62^7=3,521,614,606,208` values. This is capacity, not random collision protection. With uniformly random independent samples from a space `M`, the birthday approximation for **at least one pairwise collision** among `n` generated samples is `1-exp[-n(n-1)/(2M)]` when the approximation's conditions hold. Enforce a unique database key and retry collisions atomically; never rely on 'check availability then insert' without atomic uniqueness.

## A consistency-aware read path

On `GET /{code}`, validate code syntax, find mapping in a cache if allowed, otherwise in the authoritative datastore, check expiration/revocation, and return the specified redirect status. Negative caching of unknown codes can improve abuse handling but delays visibility when a previously missing custom alias is created. A deletion or destination update must document the maximum staleness allowed in caches. If revocation is security-critical, a long TTL without coordinated invalidation is inconsistent with the requirement.

## Capacity and hot-key analysis

For 100 million redirects/day, mean rate is about 1,157 RPS; a 10× assumed peak is ~11,574 RPS. A single popular link may receive a large fraction of reads, so uniform partitioning by key does **not** guarantee uniform traffic. A CDN or replicated cache can absorb hotspots if stale data is permissible; analytics can be asynchronously processed with explicit duplicate-delivery handling. URL writes and redirects have distinct scaling patterns and therefore separate performance budgets.

## Failure-mode matrix

| Event | Expected behavior | Design consideration |
| --- | --- | --- |
| Duplicate random code | Retry insert | Unique constraint and bounded retries |
| Database unavailable, cache miss | Controlled error or explicitly allowed stale response | SLO and staleness agreement |
| Cached revoked URL | Must satisfy revocation policy | Versioned keys / invalidation |
| Popular code overloads one shard | Queue/retry pressure | Hot-key replication or front cache |
| Malicious redirect submitted | Reject/quarantine according to policy | Abuse detection and audit |

**Architecture review:** the simplest viable deployment may be one stateless web service and relational database, with a cache only after measured need. Do not add distributed coordination to solve a scale that the measurements do not establish.

## Exercises and verification
1. Calculate average redirect RPS for 86.4 million redirects/day: `1,000/s`. Then add an explicit peak factor.
2. Explain why random IDs plus a primary-key constraint are safer than checking existence before insertion without a transaction.
3. Describe what happens during a cache outage without assuming database capacity is unlimited.
4. If an owner edits a destination, define the exact observable consistency guarantee and how the cache will respect it.

A strong design can begin as a monolith. Complexity should be introduced only when a requirement or measured bottleneck justifies it.
