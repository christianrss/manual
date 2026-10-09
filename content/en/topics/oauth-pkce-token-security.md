---
id: oauth-pkce-token-security
title: "OAuth 2.0 Security: PKCE, Token Binding and Replay"
description: "Derive the authorization-code PKCE flow, threat boundaries, refresh-token rotation, audience checks and replay resistance from IETF standards."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [api-security, network-protocols]
sources:
  - {title: "RFC 9700 — OAuth 2.0 Security Best Current Practice", url: "https://www.rfc-editor.org/rfc/rfc9700.html", kind: "IETF standard"}
  - {title: "RFC 7636 — Proof Key for Code Exchange", url: "https://www.rfc-editor.org/rfc/rfc7636.html", kind: "IETF standard"}
  - {title: "RFC 9449 — OAuth 2.0 Demonstrating Proof of Possession (DPoP)", url: "https://www.rfc-editor.org/rfc/rfc9449.html", kind: "IETF standard"}
---
OAuth 2.0 lets a client obtain authorization to access protected resources through an authorization server without receiving the resource owner's password. The flow is not equivalent to identifying a person: **OAuth grants access**, while authenticating a user to a client normally requires an additional identity protocol, such as OpenID Connect. A robust integration needs to identify the issuer, client, resource server, token audience, authorization boundary and attacker capabilities before implementing a redirect [1].

## Parties, assets and the attacker model

The resource owner controls protected resources; the client requests access; the authorization server issues authorization codes or tokens; and the resource server enforces token validity and authorization. These are logically distinct roles even when some run under one organization. An attacker might intercept an authorization code, substitute a redirect, steal a bearer token from logging or inject an authorization response from a different issuer. HTTPS is necessary, but an HTTPS connection alone does not prove that the received token belongs to the intended transaction.

The **access token** is meant for an API/resource server. An **ID token** is not interchangeable with it; it describes an authentication result for its intended relying party. A bearer access token may be reused by anyone possessing it unless additional sender constraints are enforced. A token's scopes and claims must be interpreted for the correct audience and checked against the requested resource, rather than treated as a universal permission [1].

## Authorization code flow and PKCE as two linked values

For a public client using the authorization-code grant, the client generates a cryptographically random **code verifier**. It derives an S256 **code challenge** and sends that challenge in the initial authorization request. After the user authorizes, the authorization server redirects the browser to the previously registered redirect URI carrying an authorization code. The client redeems the code at the token endpoint while presenting the original verifier. The server verifies that this verifier corresponds to the challenge attached to that code [2].

![PKCE binds code redemption to the client instance that began authorization.](/diagrams/oauth-pkce-flow.svg)

An attacker who sees only the authorization code cannot normally redeem it without the code verifier. PKCE does not authorize a user to access arbitrary resource IDs and does not make a malicious browser environment trustworthy. RFC 9700 requires public clients to use PKCE in authorization-code flows and recommends it for confidential clients; the challenge must be transaction-specific [1].

## Reproduce S256 without generating real credentials

The example uses the published RFC 7636 test verifier to demonstrate the transformation; do not hardcode this value as an application verifier. Real verifiers must use a cryptographically secure random generator and satisfy the RFC's permitted character set and length.

~~~python
import base64
import hashlib

def pkce_challenge(verifier):
    if not isinstance(verifier, str) or not 43 <= len(verifier) <= 128:
        raise ValueError("invalid PKCE verifier length")
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    if any(ch not in allowed for ch in verifier):
        raise ValueError("invalid verifier character")
    raw = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

rfc_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
assert pkce_challenge(rfc_verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
try:
    pkce_challenge("short")
    assert False
except ValueError:
    pass
~~~

The code computes a challenge, **not** a complete authorization flow, authorization server or secure verifier generator. It cannot validate issuer identity or prove that an authorization code belongs to a session. Verification of the incoming redirect and authenticated client binding belongs to the complete protocol implementation [2].

## Redirect binding, CSRF and mix-up

An authorization server must compare registered redirect URIs precisely according to the standard rules; permissive prefix or wildcard matching can leak a code to a destination controlled by an attacker. A client must correlate the callback to the browser session and initiated transaction using a suitable CSRF defense, for example a transaction-bound state token or the applicable PKCE/OIDC protection under its stated requirements [1]. In multi-issuer clients, defend against **mix-up attacks** by validating the authorization-server issuer in the response or using an approved alternative, not assuming that any response delivered to a callback came from the expected provider.

An **open redirector** on the client or authorization-server domain can undermine carefully registered callbacks. Do not forward authorization response parameters to URLs supplied by untrusted query strings. Authorization codes are typically short-lived and single-use, but implementation must still handle duplicate callbacks and failures during token exchange.

## Access-token replay and sender-constraining

A bearer token can be replayed after theft while it remains accepted. **Sender-constrained** tokens narrow this threat by requiring proof from the legitimate sender, such as mutual TLS or Demonstrating Proof of Possession (DPoP) [1][3]. DPoP attaches a signed, request-specific proof involving an HTTP method and URI and typically includes protections around timestamps, replay identifiers and key binding. The resource server must validate the proof and match it to the presented access token; simply adding a DPoP header without cryptographic validation provides no security.

DPoP is not a complete solution to malicious script executing inside the legitimate client or exfiltrating a usable signing capability. Threat analysis must consider key custody, request canonicalization, clock skew, replay caches and how the resource server validates the expected HTTP endpoint.

## Refresh tokens, expiration and revocation

Refresh tokens can allow new access tokens without repeating interactive authorization. RFC 9700 calls for stronger protection of refresh tokens, including sender constraint or rotation for public clients under relevant conditions [1]. With **rotation**, exchanging one refresh token returns a replacement and invalidates the previous token; repeated use of the previous token can signal compromise. A race between two legitimate tabs can also trigger rotation conflicts unless the session architecture coordinates refresh. Error handling should never expose refresh tokens in analytics, URL query parameters or client-visible diagnostic logs.

| Asset | Validated by | Typical failure |
| --- | --- | --- |
| Authorization code | Authorization server/token endpoint | Wrong client or missing PKCE proof |
| Access token | Resource server | Wrong audience or expired credential |
| DPoP proof | Resource server | Invalid signing key or replay |
| Refresh token | Authorization server | Reuse after rotation or revoked session |
| Business resource ID | Application policy | Cross-tenant access despite valid token |

Revocation speed depends on token design and resource-server checks. A short-lived signed JWT may remain accepted until expiration if resource servers have no revocation mechanism. Strong identity and token verification still does not substitute for **object-level authorization** [1].

## Verification and negative tests

Test the full flow with a trusted provider's test environment: reject a mismatched verifier, tampered state, invalid redirect, wrong issuer, duplicate code, expired code, access token for another audience, replayed DPoP proof and refresh-token reuse. Check that logs and tracing never record secrets. Production correctness depends on the provider's supported modes and validated protocol library rather than on a hand-written toy redirect handler.

## Exercises and verification

1. Describe which credential an attacker needs if they stole only the authorization code of a PKCE-protected public client.
2. Derive S256 for the RFC test verifier and explain why URL-safe base64 padding is removed.
3. Explain why a signed access token accepted by service A must not automatically be accepted by service B.
4. Contrast PKCE (code redemption binding) with DPoP (sender proof for access tokens).
5. Sketch a refresh-token rotation race and identify a safe client-side coordination or recovery policy.

**Prerequisites:** [API authentication and authorization](/en/topics/api-security/) describes resource-level access, while [network protocols](/en/topics/network-protocols/) explains TLS identity boundaries.
