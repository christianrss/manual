---
id: api-security
title: "API Security: Identity, Authorization and Threat Models"
description: "Distinguish authentication from object authorization, analyze OAuth and JWT boundaries, and derive tenant isolation and API threat controls."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [network-protocols, database-consistency, rate-limiting]
sources:
  - {title: "OWASP API Security Top 10 — 2023", url: "https://owasp.org/API-Security/editions/2023/en/0x11-t10/", kind: "security project"}
  - {title: "RFC 9700 — Best Current Practice for OAuth 2.0 Security", url: "https://www.rfc-editor.org/info/rfc9700", kind: "internet standard"}
  - {title: "RFC 7519 — JSON Web Token (JWT)", url: "https://www.rfc-editor.org/info/rfc7519", kind: "internet standard"}
---
**Authentication** establishes a caller's identity under a defined trust model. **Authorization** decides whether that identity may perform a particular operation on a particular resource. The two checks are independent: a correctly signed token that identifies Alice does not imply that Alice may read Bob's records. A secure API defines resource ownership and enforceable permissions in the authoritative backend, not only in the browser interface [1].

## Model assets, actors and trust boundaries

Start with assets such as account data, orders, access tokens, secrets and audit events. Actors include legitimate users, administrators, automated clients and attackers controlling their own accounts. Draw trust boundaries between browser, identity provider, API gateway, service and database. A malicious caller may modify URLs, IDs, HTTP methods and request bodies even when the official interface hides these controls.

For each sensitive operation, specify **subject** (actor), **action**, **resource**, **context** and the authority that decides access. A vague rule 'must be authenticated' is not enough for a multi-tenant application: a user in tenant A must not receive data from tenant B merely by guessing an order ID. OWASP highlights broken object-level authorization among central API risks [1].

## Enforce object-level authorization on every request

Suppose a GET request addresses /orders/42. Validate the authentication credential, extract an authenticated principal and query the order under a **tenant and authorization constraint**. If the database row is absent or outside the principal's authorized scope, return the policy-defined response without leaking private details. Do not trust tenant_id supplied by the caller when the effective tenant should come from validated credentials or server-maintained membership.

![Authorization checks the principal and resource in an authoritative boundary.](/diagrams/api-authorization-boundary.svg)

~~~python
from dataclasses import dataclass

@dataclass(frozen=True)
class Principal:
    user_id: int
    tenant_id: int
    roles: frozenset[str]

def may_read_order(principal, order):
    if principal is None or order is None:
        return False
    if order["tenant_id"] != principal.tenant_id:
        return False
    return order["owner_id"] == principal.user_id or "tenant_auditor" in principal.roles

alice = Principal(10, 2, frozenset())
order = {"tenant_id": 2, "owner_id": 10}
other_tenant = {"tenant_id": 3, "owner_id": 10}
assert may_read_order(alice, order)
assert not may_read_order(alice, other_tenant)
assert not may_read_order(Principal(11,2,frozenset()), order)
assert may_read_order(Principal(11,2,frozenset({"tenant_auditor"})), order)
~~~

This is a **policy predicate only**, not a production identity verification or complete authorization system. It assumes the principal and order were loaded from trusted sources and that the tenant_auditor role is scoped to the correct tenant. Production policy may incorporate status, confidentiality labels, explicit grants, delegations and organizational boundaries. The security invariant is that changing an arbitrary resource ID never widens the authenticated caller's authority.

## OAuth is delegation; JWT is a token format

OAuth 2.0 provides authorization flows through which clients obtain access to protected resources. An OAuth **access token** is intended for a resource server; it is not interchangeable with an OpenID Connect **ID token** used to describe authentication to a client. JWT is a possible **format** carrying claims, not itself a complete authorization protocol. Some access tokens are opaque and must be introspected through the issuer's defined mechanism [2][3].

When using signed JWTs, validation must include trusted issuer, intended audience, permitted algorithm and keys, expiration and relevant not-before constraints. Decoding a token's JSON payload **without verifying its signature** is not authentication. Do not accept an attacker-selected key or algorithm based only on untrusted headers. Key rotation, clock skew, revocation and short-lived credentials require explicit policy.

## Choose a modern authorization flow

For redirect-based OAuth clients, current security practice favors authorization-code flows with proof key for code exchange (PKCE) and strict redirect URI matching. Public clients must use PKCE; confidential clients are also recommended to use it. Do not introduce insecure legacy implicit or password grant flows merely to reduce implementation work. Transaction-specific state/nonce or an appropriate equivalent protects against request substitution and some CSRF threats according to the chosen protocol [2].

Tokens should be kept out of URL query strings, logs, analytics parameters and error reports. Server-side sessions may simplify revocation and secret handling for traditional web applications. Browser cookies introduce CSRF considerations; bearer tokens in JavaScript introduce theft risks under cross-site scripting. There is no universal 'JWT is always more secure' answer.

## Defense in depth beyond permission checks

Validate input shapes and business invariants, bound payload sizes and execution cost, and parameterize database queries rather than assembling SQL from user input. Limit outbound URL fetching to prevent server-side request forgery (SSRF) across metadata endpoints or internal administration services. Restrict secrets to least-privilege identities, use short rotation/retention windows appropriate to your environment and segregate duties for privileged operations.

| Risk | Example | Control |
| --- | --- | --- |
| Object-level authorization failure | Change order ID in path | Check principal against *loaded resource* |
| Excessive data exposure | API returns hidden private fields | Explicit response schema by privilege |
| Broken authentication | Accept unverified token | Verify issuer, audience, signature and time |
| Resource exhaustion | Very costly filter query | Bound cost, concurrency and pagination |
| SSRF | Server fetches caller-supplied URL | Restrict destinations and resolve safely |

Rate limiting is valuable against resource exhaustion but does not replace authorization, and CORS is a **browser-enforced access policy**, not an authorization check for arbitrary HTTP clients [1].

## Auditing, privacy and key operations

Security logs should capture actor, operation, resource identity, outcome and correlation ID without writing passwords, access tokens or unnecessary personal data. Ensure unauthorized attempts are detectable but do not reveal sensitive resource existence or internal architecture in public error responses. Audit records must be trustworthy enough for investigation: applications able to rewrite their own audit history defeat the mechanism.

Establish a procedure for credential compromise: revoke or expire credentials, rotate signing keys carefully, invalidate affected sessions and examine access history. A short JWT lifetime reduces some exposure but does not instantly revoke an already issued token. For systems with long-lived refresh tokens, use rotation and replay detection mechanisms consistent with issuer capabilities [2].

## Verify the real boundary, not only a helper function

Unit-test the policy, then test the HTTP endpoint with a real identity-validation configuration and database constraints. Include two users in one tenant, one user in another tenant, revoked credentials, forged signatures, missing claims, expired tokens and concurrent membership changes. A front-end 'hidden' button must not be the only barrier. Where privileges change during an active session, define when the service must observe the new policy and whether caches may serve stale decisions.

**Related chapters:** [Database consistency](/en/topics/database-consistency/) discusses state authority; [network protocols](/en/topics/network-protocols/) introduces TLS trust; [reliable APIs](/en/topics/api-reliability/) addresses retries without bypassing access controls.

## Exercises and verification

1. Why does a token with valid signature and a broad scope not automatically authorize reading every order ID?
2. Design an API integration test that proves tenant A cannot read tenant B's records even when numeric resource IDs overlap.
3. Distinguish an ID token from an access token and a signed JWT from an opaque token. Which party validates each?
4. Explain why enabling CORS protection does not stop curl from making unauthorized requests.
5. Build an incident response checklist for a leaked refresh token without asserting that changing an access-token signing key alone solves every session risk.
