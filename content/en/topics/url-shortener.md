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

## Exercises and verification
1. Calculate average redirect RPS for 86.4 million redirects/day: `1,000/s`. Then add an explicit peak factor.
2. Explain why random IDs plus a primary-key constraint are safer than checking existence before insertion without a transaction.
3. Describe what happens during a cache outage without assuming database capacity is unlimited.
4. If an owner edits a destination, define the exact observable consistency guarantee and how the cache will respect it.

A strong design can begin as a monolith. Complexity should be introduced only when a requirement or measured bottleneck justifies it.
