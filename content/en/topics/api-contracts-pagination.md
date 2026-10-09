---
id: api-contracts-pagination
title: "HTTP API Contracts: Pagination, Idempotency and Conditional Updates"
description: "Design HTTP resources, cursor pagination, ETags, idempotent commands, error representations and compatible API evolution."
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites: [network-protocols, api-reliability, transactional-indexing-isolation]
sources:
  - {title: "RFC 9110 — HTTP Semantics", url: "https://www.rfc-editor.org/rfc/rfc9110.html", kind: "IETF standard"}
  - {title: "AWS Builders Library — Timeouts, retries and backoff with jitter", url: "https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/", kind: "engineering source"}
  - {title: "RFC 9457 — Problem Details for HTTP APIs", url: "https://www.rfc-editor.org/rfc/rfc9457.html", kind: "IETF standard"}
---
An API contract is the **shared protocol between clients and a service**, not merely a URL list. It defines resources, authentication, input constraints, successful effects, errors, caching, pagination, compatibility and what clients should do when a response disappears. HTTP defines the semantics of its methods and status codes; an application must then specify its business meaning without contradicting those semantics [1].

## Model resources and permissions before routes

Consider a private notes API: each note has an immutable identifier, an owner, creation timestamp and text. A user may create and list their own notes and read a note they own. Clients must not be able to supply owner_id and thereby impersonate another account; derive ownership from authenticated identity in the server. Authorization is **object-specific**, even when a bearer token is valid. Record whether a missing or unauthorized note should be indistinguishable to avoid disclosing identifiers.

One candidate interface is GET /v1/notes/{id}, GET /v1/notes?limit=...&cursor=..., POST /v1/notes and PUT /v1/notes/{id} only if full replacement is supported. Route names are less important than coherent contracts. Specify UTF-8 text size, accepted media types, maximum page size, sorting, timeouts, and access policies so independently developed clients can reproduce the behavior.

## GET, POST, PUT and HTTP idempotency

GET retrieves a resource and has safe/read semantics under HTTP. PUT requests creation or replacement of a specifically addressed resource and is an **idempotent method**: repeating an identical request has the same intended effect as applying it once. POST asks a target resource to process a representation under resource-defined semantics and is not generally idempotent. Even an idempotent method may create server logs or other internal side effects on each request; the method property concerns its intended effect on the target resource [1].

For a completed create, return **201 Created** with an identifier/location. For a command merely accepted for later processing, **202 Accepted** may fit, but then expose a durable operation status and do not claim the business task has completed. A DELETE can be idempotent even though a repeat may return 404 after the initial deletion; response codes need not remain identical for the intended effect to be idempotent.

## The ambiguous response and idempotency key

A server can commit a write and lose its connection before delivering the response. The client's timeout does **not** establish that the server rolled back. If the client repeats POST without a stable operation identity, duplicates can result. Define an `Idempotency-Key` header with scope (for example authenticated owner plus endpoint), lifetime and canonical request fingerprint. Persist the key, fingerprint and result **atomically** with the business effect. A repeated matching request returns the stored logical outcome; a reused key with a different payload is rejected under the application contract.

A process-local dictionary is insufficient across server replicas or restarts. Uniqueness must be enforced at the persistence boundary and race behavior specified. When a charge is sent to an external provider, local idempotency is only one part of the contract: the provider's own idempotency and reconciliation determine whether a duplicate charge can occur [2].

## Page boundaries: offset versus keyset

Offset pagination uses LIMIT plus OFFSET. On a live collection, concurrent inserts can shift positions, causing duplicates or omissions between pages. Large offsets can also require the database to scan or discard substantial rows. **Keyset/cursor pagination** instead remembers the last stable ordering key and asks for strictly later entries in that order. A cursor is continuation state, **not** a security credential or proof of authorization.

![A composite cursor separates two pages in a stable descending order.](/diagrams/api-keyset-pagination.svg)

For notes ordered by (created_at DESC, id DESC), page two should filter `(created_at,id) < (:last_time,:last_id)` under a compatible lexicographic ordering. The id tie-breaker is necessary because two notes can share a timestamp. Use an index including owner and both order keys. The query must always enforce the authenticated owner; decoding a cursor cannot grant access to another owner's records.

A keyset cursor does not automatically provide a perfectly frozen snapshot across page requests. New items inserted **ahead** of the cursor may be absent from later pages by design; existing items can be updated or deleted. If the product requires snapshot consistency, establish a snapshot or versioned-read mechanism and define its retention window and cost.

## Demonstrate opaque, integrity-protected cursors

This self-contained Python model encodes owner, timestamp and identifier in a URL-safe token, authenticating the payload with HMAC. It demonstrates preventing **cursor tampering**, not a production token subsystem. In a deployed design the HMAC key is random, managed securely, rotated with a key identifier and never hardcoded; expiry, token size and canonical encoding rules must be specified.

~~~python
import base64
import hashlib
import hmac
import json

DEMO_KEY = b"example-only-key-do-not-use-in-production"

def b64_encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

def b64_decode(raw):
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))

def make_cursor(owner, timestamp, note_id):
    payload = json.dumps({"v": 1, "owner": owner, "time": timestamp,
                          "id": note_id}, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(DEMO_KEY, payload, hashlib.sha256).digest()
    return b64_encode(payload) + "." + b64_encode(sig)

def read_cursor(token, expected_owner):
    try:
        encoded, signature = token.split(".")
        payload = b64_decode(encoded)
        expected = hmac.new(DEMO_KEY, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, b64_decode(signature)):
            raise ValueError("invalid signature")
        data = json.loads(payload)
        if data["v"] != 1 or data["owner"] != expected_owner:
            raise ValueError("wrong cursor scope")
        if not isinstance(data["time"], int) or not isinstance(data["id"], int):
            raise ValueError("invalid position")
        return (data["time"], data["id"])
    except (KeyError, ValueError, TypeError, UnicodeError) as error:
        raise ValueError("invalid cursor") from error

token = make_cursor("alice", 1700000100, 42)
assert read_cursor(token, "alice") == (1700000100, 42)
for bad_owner in ("bob", ""):
    try:
        read_cursor(token, bad_owner)
        assert False
    except ValueError:
        pass
try:
    read_cursor(token[:-1] + ("A" if token[-1] != "A" else "B"), "alice")
    assert False
except ValueError:
    pass
~~~

The demonstration assumes integer epoch timestamps and integer IDs; the real API needs validated bounds and rate limiting. Tampering with a base64 signature must not be relied on as encryption: the cursor payload can be decoded by clients and should not contain secrets. Authorization must still be checked for each returned object.

## ETags and concurrent writes

Suppose two editors retrieve the same representation. Both modify the note and PUT their changes. Without a precondition, the later request silently overwrites the earlier update. An **ETag** identifies a resource representation version. With `If-Match: "version"`, the server applies a change only if the current resource validator still matches; otherwise respond **412 Precondition Failed** [1]. The check and write must be atomic in the authority, not separate unsafe reads.

Optimistic concurrency control does not guarantee that the changed text is semantically compatible. A successful compare-and-swap avoids *lost updates* under the specified version, but cannot resolve conflicting human intentions. For PATCH, define the patch media type and semantics explicitly, rather than assuming all PATCH bodies mean partial JSON replacement.

## Error representations, status codes and retry policy

RFC 9457 defines a standard **problem details** representation with fields including type, title, status and detail, plus extension members [3]. Use a stable problem type and avoid leaking private identifiers, credentials or stack traces. HTTP status distinguishes categories, while domain-specific codes support machine decisions. An error response should make it clear which conditions are retryable.

| Condition | Example code | Client behavior |
| --- | --- | --- |
| Invalid input | 400 or 422 by contract | Correct request |
| Missing/invalid authentication | 401 | Obtain credentials |
| Authenticated but forbidden | 403 or privacy-preserving 404 | Do not retry blindly |
| Entity created durably | 201 | Use Location/ID |
| Command accepted asynchronously | 202 | Poll status resource |
| Idempotency-key payload conflict | 409 by defined contract | Use a new valid operation |
| If-Match validator failed | 412 | Refetch and reconcile |
| Request over policy limit | 429 | Respect Retry-After if supplied |
| Temporary server failure | 503 | Bounded retry under budget |

A 5xx response does not necessarily mean a POST had no effect. Bounded retries with backoff and jitter are appropriate only when the effect is retry-safe or protected by a durable idempotency mechanism [2]. Clients must obey a total deadline to avoid unbounded amplification of overload.

## Evolution and compatibility

API changes include **syntactic** differences, such as field names, and **semantic** changes, such as when a successful response is considered committed. Adding optional response fields can be backward-compatible for tolerant clients; changing a required field's meaning or converting a synchronous command to asynchronous behavior may not be. Test consumer/provider contracts rather than merely bumping /v1 to /v2.

Version identifiers do not automatically solve compatibility. Maintain an explicit deprecation policy, an error taxonomy, schema change plan and migration tests. Audit authorization and pagination contracts after adding indexes, caches or read replicas, because those architectural improvements can affect freshness and security.

## Exercises and verification

1. Explain why retrying POST after a timeout can produce duplicates even if the server never returned 201.
2. Construct two notes with identical timestamps and show why sorting only by time gives an ambiguous cursor.
3. Explain why an HMAC cursor must still be authorized against the authenticated owner on every request.
4. Show a concurrent update interleaving that fails without If-Match and how an atomic ETag condition prevents silent overwrite.
5. Specify success/error responses for a valid create, an unauthorized read, a stale update and a rate-limited request.

**Related chapters:** [API reliability](/en/topics/api-reliability/) treats retries and backpressure; [transactional indexing](/en/topics/transactional-indexing-isolation/) handles concurrency; [system design process](/en/topics/system-design-process/) connects contracts to architecture.
