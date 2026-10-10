---
id: ip-routing-dns-resolution
title: "IP Routing and DNS: Prefix Selection, Resolution and TTL Caches"
description: "Derive IPv4 longest-prefix routing and DNS resolver caching, record TTL expiry and failure semantics with independent Python test oracles."
category: networking
difficulty: intermediate
updated: 2026-10-10
prerequisites: [processes-virtual-memory, complexity-analysis]
sources:
  - {title: "RFC 1812 — Requirements for IPv4 Routers", url: "https://www.rfc-editor.org/info/rfc1812", kind: "IETF internet standard"}
  - {title: "RFC 1034 — DNS Concepts and Facilities", url: "https://www.rfc-editor.org/info/rfc1034", kind: "IETF internet standard"}
  - {title: "RFC 1035 — DNS Implementation and Specification", url: "https://www.rfc-editor.org/info/rfc1035", kind: "IETF internet standard"}
  - {title: "RFC 2308 — DNS Negative Caching", url: "https://www.rfc-editor.org/info/rfc2308", kind: "IETF internet standard"}
  - {title: "RFC 8767 — DNS Serve-Stale", url: "https://www.rfc-editor.org/info/rfc8767", kind: "IETF internet standard"}
  - {title: "RFC 8200 — IPv6 Specification", url: "https://www.rfc-editor.org/info/rfc8200", kind: "IETF internet standard"}
---
**IP forwarding** and **DNS name resolution** solve different problems. IP decides where to send a packet with a destination address; DNS helps applications discover addresses and other resource records associated with a name. Neither guarantees that a selected application endpoint will accept a request or that a successful TCP handshake proves service health. The [network request overview](/en/topics/network-protocols/) connects those layers to transport, TLS and HTTP, whereas this chapter defines their lower-level data and decision contracts [1][2].

This text introduces two deliberately small executable models: one chooses an IPv4 static route using longest-prefix matching, and one caches positive A/AAAA DNS records until their absolute expiration time. They are **not** router forwarding code, a production DNS resolver, packet capture or a security protocol. Their purpose is to expose selection rules and invariants in a form that can be checked against independently written reference algorithms.

## IP packets, subnets and the routing decision

IP addresses identify network interfaces or endpoints for routing purposes, not individual HTTP services. A router receives a packet, examines its destination IP and selects an outgoing next hop according to the forwarding table. The application hostname that originally led to the address does not participate in this ordinary forwarding lookup [1].

In IPv4, a CIDR route such as `192.0.2.0/24` defines a prefix of 24 fixed bits, covering addresses `192.0.2.0` through `192.0.2.255`. A route `192.0.2.128/25` is more specific and covers only the upper half of that range. The `0.0.0.0/0` route is the **default** catch-all if no more specific route matches. The `192.0.2.0/24`, `198.51.100.0/24`, and `203.0.113.0/24` ranges used in this example are reserved for documentation and should not be interpreted as a production network plan [1].

**Longest-prefix match** means choose the most specific prefix that contains the destination. For two equally specific routes, production routers may consider administrative distance, protocol preference, metrics, policy and equal-cost multipath, depending on configuration. Our fixed teaching convention is simpler: **lowest metric**, then **earliest route entry**. Never claim that these tie-breakers describe all IPv4 routers.

## Forwarding is not path discovery

A route selects an immediate next hop, not necessarily the final end host. A gateway on the same link must be reachable by a link-layer mechanism; IPv4 Ethernet networks typically use ARP, while IPv6 neighbor discovery has different behavior. A router may reject an otherwise matching route if its interface is unavailable, a route is prohibited, or filtering policy applies. None of those checks exists in our pure matching function [1][6].

IPv4 TTL and IPv6 Hop Limit bound forwarding across hops to reduce damage from routing loops. They are **packet header** fields, not a DNS cache expiration and not a service request timeout. IPv6 forwarding semantics are described in RFC 8200, and IPv6 route lookup uses 128-bit addresses rather than the 32-bit IPv4 example below [6].

Path MTU, fragmentation, ICMP diagnostics and network address translation are additional boundaries. A route may correctly match yet the packet fail because an interface, MTU or policy prevents delivery. Treating the route selection result as proof of delivery is a correctness error.

## Executable longest-prefix routing contract

The model takes a tuple or list of `(CIDR, gateway, metric)` entries. Both prefix and next hop must be syntactically valid IPv4 strings, and metric must be a nonnegative integer rather than a Python boolean. CIDR prefixes are required to be **canonical network addresses**: `192.0.2.1/24` is rejected rather than silently converted to `192.0.2.0/24`.

The function validates **every route**, including ones that would not match the destination, before returning an answer. That avoids silently accepting malformed configuration just because a prior default route matched. It returns `(matched_prefix, gateway)` or `None` when there is no route. It makes no reachability claims.

~~~python
from ipaddress import IPv4Address, IPv4Network

def choose_ipv4_route(entries, destination):
    if not isinstance(entries, (tuple, list)):
        raise ValueError("routes must be a sequence")
    if type(destination) is not str:
        raise ValueError("destination must be an IPv4 string")
    try:
        address = IPv4Address(destination)
    except ValueError as exc:
        raise ValueError("invalid IPv4 destination") from exc
    candidates = []
    for index, entry in enumerate(entries):
        if (not isinstance(entry, tuple) or len(entry) != 3
                or type(entry[0]) is not str or type(entry[1]) is not str
                or type(entry[2]) is not int or entry[2] < 0):
            raise ValueError("expected (CIDR, gateway, nonnegative metric)")
        prefix, gateway, metric = entry
        try:
            network = IPv4Network(prefix, strict=True)
            next_hop = IPv4Address(gateway)
        except ValueError as exc:
            raise ValueError("invalid IPv4 route") from exc
        if address in network:
            candidates.append((-network.prefixlen, metric, index,
                               str(network), str(next_hop)))
    if not candidates:
        return None
    _, _, _, prefix, gateway = min(candidates)
    return (prefix, gateway)

routes = (
    ("0.0.0.0/0", "198.51.100.1", 100),
    ("192.0.2.0/24", "198.51.100.2", 10),
    ("192.0.2.128/25", "198.51.100.3", 20),
    ("192.0.2.128/25", "198.51.100.4", 5),
)
assert choose_ipv4_route(routes, "192.0.2.200") == (
    "192.0.2.128/25", "198.51.100.4")
assert choose_ipv4_route(routes, "192.0.2.50") == (
    "192.0.2.0/24", "198.51.100.2")
assert choose_ipv4_route(routes, "203.0.113.1") == (
    "0.0.0.0/0", "198.51.100.1")
assert choose_ipv4_route((), "203.0.113.1") is None
~~~

The most specific `/25` route beats the `/24` and `/0` even when its metric is numerically higher than one of the less-specific routes. Among the two `/25` entries, metric 5 beats metric 20. Without a matching prefix or default, the model returns `None` rather than guessing a route.

Correctness follows from a simple invariant: every element in the candidate set is a fully validated route whose prefix includes the destination; choosing the lexicographic minimum of `(-prefix_length, metric, original_index)` selects the longest prefix, then smallest metric, then earliest entry. Scanning `r` routes uses `O(r)` route checks for fixed-width IPv4 addresses; the candidate collection adds `O(r)` space. A production forwarding engine may use tries, tables or hardware TCAM and has a different cost model.

## DNS hierarchy, zones and resolver responsibilities

A DNS question normally identifies **owner name**, **record type** and **class**. The hierarchy is distributed among authoritative zones; recursive resolution follows referrals or uses cached delegation information until an authoritative answer or another response is obtained. A stub resolver, a caching recursive resolver and an authoritative server have different responsibilities [2][3].

An A record contains an IPv4 address and an AAAA record contains an IPv6 address. CNAME represents an alias and requires additional resolution rather than magically becoming an A record. NS delegates authoritative responsibility; SOA contains zone metadata relevant to negative caching. DNS does not require every name to have both A and AAAA records, and a missing AAAA response is not necessarily the same as a nonexistent name [2][3][4].

DNS transport may use UDP or TCP according to packet size, truncation, configuration and modern resolver policy. DNS is **not synonymous with UDP port 53 only**. A DNS result may have several addresses, and choosing among them or racing IPv4/IPv6 connection attempts is a client policy distinct from routing each selected address.

## Positive caching, TTL and a precise expiration boundary

A DNS RR TTL is a duration in seconds for which caching is allowed under the relevant standards and resolver policies. Caches count it down. For a simple positive answer inserted at time `t` with TTL `q`, we model validity for `t <= now < t+q`; at `now=t+q`, the entry has expired. **TTL zero** does not create a reusable cached entry [2][3].

This model chooses an abstract **monotone integer clock**, not a wall-clock timestamp. It requires queries and insertions to use nondecreasing instants; otherwise someone could rewind time to make expired data appear valid again. We normalize ASCII names to lowercase and accept an optional single terminal dot to avoid treating differently capitalized owner names as different cache keys. A and AAAA caches are **separate** because their record types differ.

Real DNS names have more forms than this validated teaching subset, including internationalized names after appropriate encoding, different classes, non-address types and referrals. The example intentionally handles only positive IN A/AAAA answers and assumes they are trustworthy input. It does **not** verify DNSSEC, detect poisoning, implement recursion or check domain delegation.

## Executable positive-answer cache

~~~python
from ipaddress import ip_address

class PositiveDnsCache:
    def __init__(self):
        self.entries = {}
        self.last_time = 0

    @staticmethod
    def _key(name, kind):
        if type(name) is not str or type(kind) is not str:
            raise ValueError("name and type must be strings")
        lowered = name.lower()
        if lowered.endswith("."):
            lowered = lowered[:-1]
        labels = lowered.split(".")
        if (not lowered.isascii() or len(lowered) > 253
                or any(not 1 <= len(label) <= 63
                       or label[0] == "-" or label[-1] == "-"
                       or any(not (char.isascii() and
                                   (char.isalnum() or char == "-"))
                              for char in label)
                       for label in labels)
                or kind not in ("A", "AAAA")):
            raise ValueError("unsupported name or record type")
        return (lowered, kind)

    def _clock(self, now):
        if type(now) is not int or now < self.last_time:
            raise ValueError("clock must be monotone integer seconds")
        self.last_time = now

    def put(self, name, kind, addresses, ttl, now):
        key = self._key(name, kind)
        if (not isinstance(addresses, tuple) or not addresses
                or type(ttl) is not int or ttl < 0
                or type(now) is not int or now < self.last_time):
            raise ValueError("invalid answer, TTL or clock")
        expected_version = 4 if kind == "A" else 6
        try:
            valid = all(type(item) is str
                        and ip_address(item).version == expected_version
                        for item in addresses)
        except ValueError as exc:
            raise ValueError("invalid IP address record") from exc
        if not valid:
            raise ValueError("address family mismatch")
        self._clock(now)
        if ttl == 0:
            self.entries.pop(key, None)
            return False
        self.entries[key] = (addresses, now + ttl)
        return True

    def get(self, name, kind, now):
        key = self._key(name, kind)
        self._clock(now)
        value = self.entries.get(key)
        if value is None:
            return None
        addresses, expires_at = value
        if now >= expires_at:
            del self.entries[key]
            return None
        return (addresses, expires_at - now)

cache = PositiveDnsCache()
assert cache.put("WWW.Example.test.", "A", ("192.0.2.9",), 5, 10)
assert cache.get("www.example.test", "A", 13) == (("192.0.2.9",), 2)
assert cache.get("www.example.test", "AAAA", 14) is None
assert cache.get("www.example.test", "A", 15) is None
assert not cache.put("www.example.test", "A", ("192.0.2.10",), 0, 16)
assert cache.get("www.example.test", "A", 16) is None
~~~

The record inserted at time 10 with TTL 5 remains available at time 13 with two seconds remaining. At **time 15**, the answer is no longer returned. Requesting an AAAA answer never repurposes an A record. Inserting a zero-TTL record removes a cached value for the same key in this teaching model; real resolver behavior can be more nuanced because zero-TTL data remains usable within the current transaction [3].

The cache invariant is: each stored entry has a validated (name, type), a nonempty tuple of addresses matching that address family, and an absolute expiration time; every returned entry has strictly positive time remaining. Invalid writes must not mutate entries or the clock. The storage required is proportional to total cached record data. A lookup uses expected-constant dictionary time plus normalization of the query name; validation of a new answer also scans its address tuple.

## NXDOMAIN, NODATA and serve-stale cannot be omitted from production

The example handles **positive cache entries only**. RFC 2308 treats negative answers separately: **NXDOMAIN** says a queried name does not exist, while **NODATA** says no record of the requested type exists at a name. Cache scope and negative TTLs differ, typically involving SOA metadata. Treating negative replies as ordinary empty tuples would incorrectly conflate the two outcomes [4].

There is also a standards-defined resilience exception: RFC 8767 allows qualified resolvers to **serve stale DNS data** under specific conditions when authoritative data cannot be refreshed. Therefore it is inaccurate to state that *all* compliant resolvers **must never** return a record after its original TTL. Our cache explicitly **does not implement serve-stale**, so it drops the record at the exact modeled expiration [5].

DNSSEC is a separate authentication mechanism for DNS data, not merely an HTTPS certificate check. Encrypted DNS transports such as DoT or DoH protect a query's transport to the chosen resolver under their trust models, but they do not by themselves authenticate the original authoritative resource record. Those security layers need independent chapters.

## From resolved address to TCP and HTTP

After a resolver returns candidate IP addresses, a client still needs to choose a destination, establish transport and validate the intended service identity. TCP provides an ordered **byte stream**, not application message boundaries; UDP offers datagrams with different delivery guarantees; HTTP/3 runs over QUIC/UDP rather than raw TCP. The existing [network protocols overview](/en/topics/network-protocols/) describes those later phases and the TLS trust boundary [1][6].

When debugging, use a layer-specific hypothesis. An NXDOMAIN answer suggests DNS namespace or resolver configuration. A valid A response coupled with a missing route indicates a forwarding issue, not name resolution. A successful TCP connection followed by HTTP 503 means the destination is reached at one layer while an application/gateway dependency can still be unhealthy. Changing a DNS TTL cannot repair a route-table bug.

## Exercises and verification

1. For destinations `192.0.2.50`, `192.0.2.200` and `203.0.113.5`, derive all matching routes and select the longest prefix, then metric and input index.
2. Remove the `/0` entry. Explain why returning `None` for unmatched destinations is preferable to inventing a gateway.
3. Add a second identical prefix and metric; show how the stable input-index tie-breaker affects the chosen next hop.
4. Construct a bad network such as `192.0.2.7/24`. Prove that the validator rejects it before returning any match.
5. Trace a positive A record cached at t=100 with TTL=30, queried at t=129 and t=130. Explain zero-TTL behavior and the limits of this toy cache.
6. Explain separately why a nonexistent name and an existing name without AAAA require different negative-cache keys under RFC 2308 [4].
7. Model a serve-stale extension. State the exceptional network condition, maximum staleness policy, output TTL and failure semantics before changing code [5].
8. Draw recursive resolution from an uncached stub request through parent delegation to an authoritative server. Label which entities can answer from cache and which own zone data.
9. Distinguish IP packet TTL, DNS RR TTL, TCP retransmission timers and HTTP request deadlines, and propose measurements for each layer.

**Continue:** [DNS/TCP/TLS/HTTP request walkthrough](/en/topics/network-protocols/) applies these foundations to application connectivity. TCP sequence arithmetic, retransmission, congestion control, DNSSEC and BGP route policy remain separate advanced topics [1][2][3][4][5][6].
