---
id: network-protocols
title: "Networking Fundamentals: DNS, TCP, TLS and HTTP"
description: "Trace a web request through DNS, transport, TLS and HTTP; derive latency and failure budgets and distinguish TCP from QUIC."
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites: [capacity-estimation, processes-virtual-memory]
sources:
  - {title: "RFC 9293 — Transmission Control Protocol", url: "https://www.rfc-editor.org/info/rfc9293", kind: "internet standard"}
  - {title: "RFC 9846 — TLS Protocol Version 1.3", url: "https://www.rfc-editor.org/info/rfc9846", kind: "internet standard"}
  - {title: "RFC 9114 — HTTP/3", url: "https://www.rfc-editor.org/info/rfc9114", kind: "internet standard"}
  - {title: "RFC 8305 — Happy Eyeballs Version 2", url: "https://www.rfc-editor.org/info/rfc8305", kind: "internet standard"}
---
A web request crosses several protocols with distinct guarantees. **DNS** helps discover network endpoints; **IP** routes packets; **TCP** provides a reliable ordered byte stream; **TLS** protects a connection against interception and tampering under its authentication assumptions; **HTTP** specifies application-level request and response semantics. Confusing these layers produces incorrect diagnoses, such as treating a successful TCP connection as proof that the application is healthy [1][2].

## Start with an explicit request path

Consider a new browser session requesting an HTTPS resource on a hostname. The client needs an address, a route to the selected endpoint, a transport connection and a security handshake before exchanging application data. Depending on caches, session reuse, proxies, protocols and configured DNS, some stages may already be complete. A DNS answer gives a candidate destination but does not authenticate an application's business behavior. The operating system's resolver, browser, recursive resolver and authoritative DNS infrastructure play different roles.

![Request sequence through name resolution, transport, encryption and HTTP.](/diagrams/network-request-sequence.svg)

A domain may resolve to IPv4 and IPv6 addresses, potentially through a CDN. Connection establishment strategies can attempt families in a staggered way rather than waiting too long on an unreachable first address; Happy Eyeballs defines one such approach [4]. A resolver result is not a permanent mapping: address sets and DNS TTLs change, and service deployments can move endpoints.

## TCP means bytes, not messages

TCP identifies a connection using network addresses and ports and presents applications with a **reliable, in-order byte stream**. It detects loss using sequence and acknowledgment information and retransmits as needed [1]. It does **not** preserve boundaries between successive application writes. One send call may be received in several read calls; several writes may be observed in a single read. An application protocol needs its own framing, for example length prefix, delimiter, or a structured HTTP message.

TCP also distinguishes **flow control**, which limits outstanding data according to receiver capacity, from **congestion control**, which protects the shared network against excessive sending. A large receive window does not imply the path can carry unlimited traffic. Conversely, a server can complete a TCP handshake and still reject or time out the subsequent application request.

## TLS and the trust boundary

TLS 1.3 negotiates cryptographic parameters, authenticates endpoints according to the chosen authentication mechanism and derives session keys that protect subsequent records. A certificate chain and verified hostname are central for typical public HTTPS server authentication; encryption without correct peer authentication does not protect against an active impersonator [2]. Modern TLS handshakes have different cost and reuse characteristics from obsolete versions, and 0-RTT early data can be replayed: it must not be treated as a general safe transport for non-idempotent side effects.

TLS termination at a reverse proxy changes which hop is encrypted and who is trusted with plaintext. If the proxy forwards requests to the application over another connection, the security of that **second** hop must be evaluated independently. Trusted forwarding headers such as client IP must only be accepted from a defined proxy chain, never from arbitrary direct clients.

## HTTP semantics survive a transport change

HTTP methods and status codes are **application protocol** semantics, not transport-layer acknowledgments. A 200 status is not a guarantee that downstream asynchronous effects have completed. A successful POST might also represent acceptance for later processing; its documented response contract must specify when work is durable. Connection loss after a server commits a command leaves the client unsure whether the effect happened; retrying can create duplicates unless the command is designed for idempotence.

HTTP/3 maps HTTP semantics to **QUIC**, which runs over UDP and supplies its own encrypted transport and stream management [3]. Therefore 'HTTP runs only over TCP' is false. HTTP/2 multiplexes streams over a TCP connection, but packet loss can delay delivery of the TCP byte stream; QUIC provides stream-level mechanisms that reduce some head-of-line blocking across streams. Neither eliminates bandwidth limits, server overload or application dependencies.

## Derive latency by stages, not guesses

Let total end-to-end time be T. A simplified cold-request budget is T = T_dns + T_connect + T_tls + T_request + T_server + T_response. Terms may overlap with modern connection setup, so adding them naively can overestimate a protocol with integrated handshakes. Use a real trace to measure each phase. For a **hypothetical sequential** request with 15 ms DNS, 35 ms transport setup, 40 ms TLS, 25 ms transfer and 85 ms server execution, T = 200 ms. With connection reuse and cached DNS, the first three terms might be absent, but server time and network transfer still matter.

A percentiles warning: p99(T) is **not generally** the sum of the p99 of its components. The slowest one percent of each stage may occur on different requests. Correlation and conditional failure behavior matter, so compute percentiles from complete traced requests rather than adding independent summary statistics.

## A small reproducible address exercise

~~~python
from ipaddress import ip_network, ip_address

service_subnet = ip_network("192.0.2.0/27")
assert service_subnet.num_addresses == 32
assert ip_address("192.0.2.30") in service_subnet
assert ip_address("192.0.2.32") not in service_subnet

def total_latency_ms(dns, connect, tls, transfer, service):
    values = [dns, connect, tls, transfer, service]
    if any(x < 0 for x in values):
        raise ValueError("negative latency")
    return sum(values)

assert total_latency_ms(15,35,40,25,85) == 200
~~~

This calculation teaches units and decomposition; it does **not** measure a live network or account for parallel connection attempts. The address range is a reserved documentation subnet, not a deployment recommendation. For actual production diagnosis, use DNS query inspection, TLS validation, packet/connection counters, and distributed tracing at service boundaries.

## Common failure modes and architecture decisions

| Symptom | Possible layer | Verification |
| --- | --- | --- |
| Name does not resolve | DNS/resolver | Query configured resolvers and authoritative records |
| TCP connects, HTTP returns 503 | Application or gateway | Inspect upstream health and saturation |
| Certificate error | TLS identity/chain | Check SAN, trust and expiry |
| Some regions slow | Routing, distance, dependencies | Trace complete requests by region |
| Repeated writes after timeout | Application retry semantics | Confirm operation ID and durable effect |

Do not assume one timeout setting covers DNS, connect, TLS handshake, first byte and complete response. Use separate budgets when the client library supports them. Closing an idle connection can save resources but increases future handshake cost; pooling reduces handshakes but needs limits and health policies.

**Related chapters:** [Load balancing](/en/topics/load-balancing/) addresses traffic routing; [capacity estimation](/en/topics/capacity-estimation/) quantifies demand; [reliable APIs](/en/topics/api-reliability/) develops timeout and retry contracts.

## Exercises and verification

1. Explain why a TCP read returning 100 bytes does not prove a whole HTTP message arrived.
2. Trace a successful HTTPS response from hostname lookup through authentication and server execution. Mark which stages can be reused.
3. Compare a cache-hit request with a new TLS connection and a cold origin lookup; identify assumptions before claiming which is faster.
4. Explain why retrying an ambiguous POST after connection loss needs an application-level operation identity.
5. Given a 250 ms overall deadline and a downstream call that may use 150 ms, allocate a realistic budget for connection, parsing, retries and response, explaining why every layer cannot each receive 250 ms.
