---
id: tls13-hkdf-handshake
title: "TLS 1.3: Handshake Authentication, HKDF and Traffic Keys"
description: "Trace TLS 1.3 authentication and key derivation, distinguish HKDF from encryption, and verify HKDF-SHA256 and TLS labels against standard vectors."
category: security
difficulty: intermediate
updated: 2026-10-10
prerequisites: [network-protocols, tcp-byte-stream-framing-flow-control]
sources:
  - {title: "RFC 9846 — Transport Layer Security (TLS) 1.3, July 2026", url: "https://www.rfc-editor.org/info/rfc9846", kind: "internet standard"}
  - {title: "RFC 5869 — HMAC-based Extract-and-Expand Key Derivation Function", url: "https://www.rfc-editor.org/info/rfc5869", kind: "internet standard"}
  - {title: "RFC 9525 — Service Identity in TLS", url: "https://www.rfc-editor.org/info/rfc9525", kind: "internet standard"}
  - {title: "RFC 9114 — HTTP/3", url: "https://www.rfc-editor.org/info/rfc9114", kind: "internet standard"}
  - {title: "Python hmac and hashlib reference", url: "https://docs.python.org/3/library/hmac.html", kind: "official standard library documentation"}
---
TLS 1.3 establishes an encrypted, integrity-protected channel **after authenticating a peer according to the application's identity policy**. It is neither a replacement for IP routing and TCP delivery nor an authorization rule for the application. The [network request walkthrough](/en/topics/network-protocols/) distinguishes DNS, TCP, TLS and HTTP; the [TCP byte-stream chapter](/en/topics/tcp-byte-stream-framing-flow-control/) explains the transport behavior that TLS usually consumes [1].

The current TLS 1.3 specification is **RFC 9846 (July 2026)**, which supersedes RFC 8446 while retaining wire compatibility and tightening requirements such as forbidding reuse of KeyShare values between connections. Its key derivation still uses HKDF. The executable part of this chapter examines **only HKDF-SHA256 and TLS's structured derivation label** using public, synthetic test values. It does not implement a handshake, certificate validation, key exchange, AEAD, nonce management or TLS record parsing [1][2].

## Security goals, threat model and trust boundaries

For an ordinary certificate-authenticated HTTPS connection, the client needs to authenticate the **server identity** and negotiate fresh traffic keys. TLS offers confidentiality and integrity against an attacker who can observe, replay or modify network packets under the protocol's cryptographic assumptions. It does not keep DNS queries private by itself, conceal connection metadata such as peer IP, secure a compromised endpoint or grant a user permission to access an API [1].

**Encryption**, **integrity** and **authentication** are related but separate: an encryption algorithm hides plaintext, a message authentication tag detects unauthorized modification, and an authenticated handshake ties agreed secrets to an identity and a transcript. TLS 1.3 record protection uses **AEAD** ciphers, such as AES-GCM or ChaCha20-Poly1305 when negotiated. A raw hash of a message does not authenticate its origin; an unkeyed SHA-256 digest can be recomputed by an attacker who changes the message [1].

The peer identity check must compare the presented certificate identities against the **service identity the application intended to reach**. Merely having a syntactically valid certificate chain is not sufficient. Certificate trust anchors, validity, hostname/SAN matching, permitted uses and implementation policy matter, and RFC 9525 documents service-identity practices [3]. A pre-shared-key connection follows a different authentication path and should not be silently described as certificate-authenticated.

## Handshake sequence: which messages do what?

A simplified full, non-PSK TLS 1.3 handshake has these conceptual steps:

1. **ClientHello:** advertises supported protocol parameters and a fresh key share; often includes SNI and ALPN information.
2. **ServerHello:** selects parameters and supplies its own fresh key share. Both participants compute an ECDHE shared secret; it is **not transmitted as a ready-made symmetric traffic key**.
3. **EncryptedExtensions and Certificate:** the server provides additional encrypted negotiation parameters and certificate material for identity validation; a certificate is *not* an alternative symmetric encryption key.
4. **CertificateVerify:** proves possession of the signing credential over handshake context; **Finished** verifies negotiated handshake integrity using a derived key.
5. **Application traffic:** client and server derive separate application traffic secrets and per-direction AEAD keys/IVs, then exchange authenticated records [1].

The actual transcript hash incorporates **typed, length-encoded handshake messages**, not arbitrary strings concatenated without framing. Error and retry paths, client certificates, session resumption, HelloRetryRequest and post-handshake operations add branches. The outline is a learning map, not complete wire-protocol serialization.

## Key agreement, HKDF and the transcript are not substitutes

An ephemeral ECDHE operation produces a shared value using fresh private key material. **HKDF-Extract** turns input keying material (IKM) and salt into a pseudorandom key (PRK). **HKDF-Expand** turns a PRK and labeled context into derived output keying material. Transcript hashes bind derivations to the messages exchanged; finished-message checks authenticate the transcript under established secrets [1][2].

HKDF does **not** prove a remote party owns a certificate, securely generate ECDHE keypairs, encrypt application bytes or validate an AEAD tag. Key agreement without authentication is vulnerable to man-in-the-middle substitution; independently extracting a pseudorandom key cannot solve that identity problem.

TLS 1.3's schedule incorporates PSK (or an all-zero placeholder), ECDHE material and increasingly specific handshake transcript inputs. It derives distinct handshake and application traffic secrets for client and server. In RFC 9846, the conceptual value formerly named *master secret* is called **main secret** in the explanatory text; some standardized label strings retain older spelling for wire compatibility [1]. Terminology is not permission to change literal protocol labels.

## RFC 5869: extract then expand, implemented for inspection

The RFC 5869 SHA-256 variant uses `PRK=HMAC-SHA256(salt, IKM)`. With absent/empty salt, its default is 32 zero bytes. Expansion computes blocks `T(i)=HMAC-SHA256(PRK, T(i-1) || info || i)`, using `T(0)` as empty bytes and a **single unsigned byte** for block number `i` [2]. The output is the required prefix of concatenated blocks.

The one-byte counter means at most **255 SHA-256 blocks**, i.e. 8160 bytes. Our example enforces that bound and requires a PRK of at least the hash output length. Treating the bytes in the official RFC test vector as public fixtures is fine; **never copy these fixed, public bytes into deployed traffic secrets**.

~~~python
import hashlib
import hmac

HASH_LENGTH = hashlib.sha256().digest_size

def hkdf_extract(salt, ikm):
    if type(salt) is not bytes or type(ikm) is not bytes:
        raise ValueError("salt and input keying material must be bytes")
    key = salt if salt else bytes(HASH_LENGTH)
    return hmac.new(key, ikm, hashlib.sha256).digest()

def hkdf_expand(prk, info, length):
    if type(prk) is not bytes or len(prk) < HASH_LENGTH:
        raise ValueError("PRK must be at least 32 bytes")
    if type(info) is not bytes:
        raise ValueError("info must be bytes")
    if type(length) is not int or not 0 <= length <= 255 * HASH_LENGTH:
        raise ValueError("invalid HKDF output length")
    blocks = []
    previous = b""
    for counter in range(1, (length + HASH_LENGTH - 1) // HASH_LENGTH + 1):
        previous = hmac.new(prk, previous + info + bytes([counter]),
                            hashlib.sha256).digest()
        blocks.append(previous)
    return b"".join(blocks)[:length]

# RFC 5869 Appendix A.1, SHA-256: published public test values, NOT keys.
test_ikm = bytes([0x0b]) * 22
test_salt = bytes(range(13))
test_info = bytes(range(0xf0, 0xfa))
prk = hkdf_extract(test_salt, test_ikm)
assert prk.hex() == (
    "077709362c2e32df0ddc3f0dc47bba63"
    "90b6c73bb50f9c3122ec844ad7c2b3e5"
)
assert hkdf_expand(prk, test_info, 42).hex() == (
    "3cb25f25faacd57a90434f64d0362f2a"
    "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
    "34007208d5b887185865"
)
assert hkdf_expand(prk, b"", 0) == b""
~~~

This code is a learning implementation backed by Python's tested HMAC/hash primitives. It does **not** make ad hoc cryptographic programming appropriate for production. An established TLS stack should own entropy, secret lifetimes, constant-time behavior, side-channel hardening, error handling and algorithm negotiation.

## TLS HKDF-Expand-Label: canonical bytes matter

TLS 1.3 wraps HKDF's `info` input in a precisely serialized structure: a **two-byte big-endian desired output length**, a **one-byte-prefixed label** consisting of ASCII `tls13 ` plus the caller's label, and a **one-byte-prefixed byte-string context**. The resulting structure is then passed to HKDF-Expand [1].

A label that differs by even one byte generates different secrets; so do a different transcript hash, an omitted context field, incorrect UTF-8 conversion or a missing length prefix. The minimum encoded label length is seven bytes due to the six-byte `tls13 ` prefix plus a nonempty suffix. The total prefixed label must fit one byte; context is at most 255 bytes. These are **encoding constraints**, separate from HKDF's output limit.

~~~python
def tls13_hkdf_label(label, context, length):
    if type(label) is not str or not label or not label.isascii():
        raise ValueError("TLS label must be nonempty ASCII")
    if type(context) is not bytes or len(context) > 255:
        raise ValueError("TLS context must be at most 255 bytes")
    if type(length) is not int or not 0 <= length <= 65535:
        raise ValueError("TLS length must fit a two-byte integer")
    label_bytes = b"tls13 " + label.encode("ascii")
    if len(label_bytes) > 255:
        raise ValueError("TLS prefixed label exceeds one byte of length")
    return (
        length.to_bytes(2, "big")
        + bytes([len(label_bytes)]) + label_bytes
        + bytes([len(context)]) + context
    )

def tls13_expand_label(secret, label, context, length):
    return hkdf_expand(secret, tls13_hkdf_label(label, context, length), length)

assert tls13_hkdf_label("key", b"", 16).hex() == (
    "001009746c733133206b657900"
)
# Public, synthetic material ONLY; this does not negotiate any TLS keys.
synthetic_secret = hashlib.sha256(b"public teaching example, no secret").digest()
demo_key = tls13_expand_label(synthetic_secret, "key", b"", 16)
demo_iv = tls13_expand_label(synthetic_secret, "iv", b"", 12)
assert len(demo_key) == 16 and len(demo_iv) == 12
assert demo_key != tls13_expand_label(synthetic_secret, "iv", b"", 16)
assert tls13_expand_label(synthetic_secret, "key", b"A", 16) != demo_key
~~~

The `"key"` example produces the fixed serialized bytes `001009746c733133206b657900`: 16 requested bytes, nine bytes of prefixed label and an empty context. The sample synthetic traffic secret is public and reproducible. It is **not the result of a real TLS handshake**. TLS separately derives an IV using label `"iv"`; it is incorrect to reuse a traffic key as an IV or to treat them as interchangeable [1].

In real TLS, an application record's nonce is constructed from the traffic IV and sequence number according to the record specification, and the AEAD key usage limits must be respected. This chapter does **not** implement per-record nonces or AEAD authentication, so its output must never be used directly as an application encryption scheme.

## Certificate authentication and deployment failures

Operational TLS failures commonly involve a different layer than key derivation. Examples include expired certificates, wrong hostname/SAN, incomplete chain, untrusted roots, wrong time, unsupported ALPN, obsolete TLS versions, mismatched cipher suites and load-balancer or reverse-proxy TLS termination. Each must be diagnosed against its relevant stage; being able to resolve DNS or connect on TCP port 443 does **not** mean the certificate matches the intended service [1][3].

A proxy terminating TLS authenticates the TLS connection **to that termination point**; any separate proxy-to-origin hop needs its own explicit transport-security policy. End-to-end claims must account for every termination and forwarding boundary. Neither TLS nor a valid certificate inherently prevents authenticated users from misusing application APIs: authorization, audit, token handling and business access policies remain separate concerns.

TLS 1.3 resumption can reduce setup costs, while **0-RTT early data has replay risks** and is not automatically safe for non-idempotent operations. A write endpoint should not assume that a successful TLS negotiation makes early data replay-proof. The standards discuss constraints and mitigations rather than promising global replay prevention [1].

## TLS over TCP versus QUIC, performance and measurement

The network layering discussed here primarily describes TLS running over a **reliable in-order byte stream**, often TCP. QUIC uses TLS 1.3 handshake and cryptographic negotiation integrated with a different transport packet-protection design; **HTTP/3 runs over QUIC**, not over a conventional TLS-record stream on top of TCP. Copying this chapter's TLS record assumptions into QUIC would be incorrect [1][4].

Handshake latency depends on RTT, reuse and server/client processing; simplifying every TLS 1.3 connection to a fixed number of RTTs ignores resumed sessions, transport variants, application data timing and connection reuse. For measurements, collect DNS time, connection setup, TLS handshake time, certificate failures and time to first byte **separately**. A low median cannot exclude tail latency or handshake failures under load.

## Verification approach and limitations

The repository's companion tests check RFC 5869 **known-answer vectors** and compare HKDF-SHA256 against a separate reference that computes HMAC from inner/outer padding with `hashlib`, rather than reusing `hmac.new`. They inspect TLS label bytes independently, test output-length and byte-boundary validation, and compare results for multiple public inputs and contexts in **both languages**. This establishes bounded functional evidence for two derivation helpers.

It does **not** establish entropy quality, certificate verification, protocol conformance, traffic confidentiality, identity assurance, transcript integrity under attack or resistance to timing attacks. Those would require interoperable TLS implementations, standardized handshake transcripts, cryptographic library review and adversarial integration testing.

## Exercises and verification

1. Explain why DNS resolution, TCP connection establishment, TLS authentication and HTTP authorization answer **four different questions**.
2. Derive the first two HMAC blocks of HKDF-Expand and explain the single-byte counter bound of `255 × 32` bytes for SHA-256.
3. Decode `001009746c733133206b657900` field by field. Change the label to `"iv"` and explain why the derived bytes are different.
4. Prove that HKDF-Expand-Label cannot produce a 9000-byte result when this chapter's underlying hash is SHA-256, despite the label structure using a two-byte desired length.
5. Describe a man-in-the-middle attack against unauthenticated ECDHE and identify which TLS messages and identity checks address it.
6. Identify why a valid certificate for one hostname must not be accepted for a different requested hostname.
7. Map a realistic 0-RTT request that changes database state and explain what additional replay policy the application requires.
8. Contrast TLS records over TCP and QUIC's packet protection for HTTP/3. Specify what cannot be reused from this teaching code.
9. Design negative tests for missing context length, non-ASCII label, excessive output length and too-short PRK, and verify failures occur before output is produced.

**Next:** stronger treatments of AEAD and nonce safety, signatures and X.509/PKI validation, DNSSEC and full TLS interoperability remain separate security topics. The [network request article](/en/topics/network-protocols/) and [API security](/en/topics/api-security/) place TLS in the larger service stack [1][2][3][4][5].
