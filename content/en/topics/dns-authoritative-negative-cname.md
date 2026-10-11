---
id: dns-authoritative-negative-cname
title: "DNS Authority, CNAME Chains and Negative Caching"
description: "Derive DNS zone authority, recursive referrals, CNAME chains, NXDOMAIN/NODATA cache keys and SOA-based negative TTLs with independent tests."
category: networking
difficulty: intermediate
updated: 2026-10-10
prerequisites: [ip-routing-dns-resolution]
sources:
  - {title: "RFC 1034 — Domain Names: Concepts and Facilities", url: "https://www.rfc-editor.org/info/rfc1034", kind: "IETF internet standard"}
  - {title: "RFC 1035 — Domain Names: Implementation and Specification", url: "https://www.rfc-editor.org/info/rfc1035", kind: "IETF internet standard"}
  - {title: "RFC 2308 — Negative Caching of DNS Queries", url: "https://www.rfc-editor.org/info/rfc2308", kind: "IETF internet standard"}
  - {title: "RFC 4035 — DNS Security Extensions", url: "https://www.rfc-editor.org/info/rfc4035", kind: "IETF internet standard"}
  - {title: "RFC 8767 — Serving Stale Data to Improve DNS Resiliency", url: "https://www.rfc-editor.org/info/rfc8767", kind: "IETF internet standard"}
---
DNS names map to resource record sets (RRsets) maintained by **authoritative zone operators**, while recursive resolvers can answer clients using previously cached responses. The [IP routing and DNS primer](/en/topics/ip-routing-dns-resolution/) introduces positive TTL caching and longest-prefix IP forwarding; those are separate from DNS authority. This chapter adds two missing, testable contracts: **negative DNS answers** and **canonical alias chains**. It also distinguishes authoritative referrals from recursive resolution and clarifies what DNSSEC validation would add [1][2][3].

A production recursive resolver needs to handle delegation, validation, retry, timeouts, EDNS, truncation, DNS-over-TCP and many other features. Neither Python example below is a DNS server, wire-format parser or DNSSEC validator. Their purpose is narrow: reason precisely about DNS decision keys and record lifetime, then test those claims independently.

## Zones, delegation, recursion and glue

A **zone** is a portion of the DNS namespace administered by particular authoritative servers. It is not synonymous with a domain name or a single server. The parent zone can delegate a child namespace through NS records at a zone cut. A resolver may start from known root hints and follow referrals through a top-level zone to the destination's authoritative servers; it does not ask the root for arbitrary leaf-host A records in a complete authoritative database [1].

A stub resolver normally contacts a recursive resolver, which performs that iterative work or uses a cache. **Recursion** describes the service offered to the client; **iteration** describes the resolver querying successive authorities. Authoritative servers hold zone data and generally do not perform the client's entire recursive resolution. Referrals provide candidate NS hostnames. Address records in an additional section, known as **glue** when needed to reach an in-bailiwick delegated server, assist bootstrap but do **not** themselves establish trust in the host or replace the authority chain [1][2].

For example, a delegation for `child.example.` might name `ns.child.example.`. Without address information available by another path, reaching the server would require asking DNS for the server's address inside the same unresolved child. Parent-provided glue breaks that lookup dependency. A resolver must apply bailiwick and validation rules when using additional records; blindly accepting arbitrary addresses from unrelated responses risks cache poisoning. This chapter does not implement those safeguards.

## Record sets, CNAME semantics and query types

Each DNS question has a **QNAME**, **QTYPE** and **QCLASS**. For our examples we use class `IN` only, and limited types A, AAAA and TXT. A hostname can have separate A and AAAA RRsets, possibly containing multiple addresses. A **CNAME** points one owner name to another canonical name; at that owner it cannot coexist with ordinary data records, subject to specialized DNSSEC metadata exceptions not modeled here [1][2].

To resolve `www.example.` through `CNAME app.example.` then `CNAME edge.example.`, a client or resolver follows aliases until it reaches the target RRset or encounters an error. A cycle such as A→B→A is not a useful resolution. A chain whose target lies outside the locally available zone data requires further resolution; it is **not automatically proof of NXDOMAIN**. Even a successful alias chain has multiple independently changing TTLs. A cached synthesized response cannot outlive the shortest positive TTL among its required chain elements.

The code's type-limited record dictionary is an **offline teaching dataset**. It has no delegation, CNAME synthesis over the network, wildcard expansion, RRset signatures, class differences, referral responses or data verification. It treats unknown owners and missing types as exceptions, not as authenticated negative DNS answers.

## Why NXDOMAIN is different from NODATA

**NXDOMAIN** indicates that the queried name does not exist in the relevant authoritative namespace; **NODATA** indicates an existing name without the requested RR type (NOERROR with no matching answer, with the relevant SOA evidence). The two must not share the same negative-cache key [3].

For one class `IN`, an NXDOMAIN entry applies to the **name**, independently of the requested type; its lookup key is `(QNAME,QCLASS)`. A NODATA entry applies to a particular type at that name, so its key is `(QNAME,QTYPE,QCLASS)`. A missing AAAA for an existing host must not suppress a valid A response. Conversely, an NXDOMAIN for that host should not need a second negative entry just because the client next asks for AAAA [3].

CNAME and delegations complicate negative-answer interpretation: an answer containing a CNAME may report a negative outcome for the **canonical target** rather than for the original alias, and the semantics of signed denial-of-existence are still more demanding. A resolver must parse the actual authority and answer sections before choosing the key. Our small cache explicitly receives a normalized outcome selected by a trusted caller; it does **not** parse raw DNS packets or decide whether a server's response deserves trust.

## Derive negative TTL from SOA

RFC 2308 defines the cache lifetime of a negative answer from the SOA carried in the authority section. With positive integers expressed in seconds, its negative TTL is bounded by **the smaller of the SOA record's presented TTL and the SOA MINIMUM field**: `negative_ttl = min(soa_ttl, soa_minimum)` [3].

If a response arrives at time `t`, it expires at `t + negative_ttl`. At any query time `u`, it remains usable only if `u < expiry`; exactly at `u = expiry`, its remaining lifetime is zero and it must be considered expired. A zero TTL must not create a reusable cached answer. This model uses explicit nonnegative integer times, **not a wall clock**, so unit tests avoid real sleeps and race conditions.

An authoritative response might have SOA TTL 120 s and SOA MINIMUM 30 s, giving a **30 s** negative lifetime. Caching it for 120 seconds would disobey the intended limit. Conversely, when the SOA TTL is shorter, that shorter TTL wins. Practical resolvers may impose stricter local upper bounds or have separate cache and policy settings. They must not fabricate infinite negative caching because the requested name did not exist once [3].

## Executable negative cache with precise keys

The function below accepts only simple ASCII owner names and class `IN`. It canonicalizes lower/upper case and optional final dot; it does not perform IDNA or validate complete DNS wire-format names. A domain is represented as a lowercase absolute name ending in a period. The cache stores only **trusted normalized NXDOMAIN/NODATA events** with SOA-derived TTL and positive lifetime.

~~~python
import re
from dataclasses import dataclass

NAME_PART = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

def dns_name(value):
    if not isinstance(value, str) or not value:
        raise ValueError("nonempty ASCII DNS name required")
    name = value.lower().removesuffix(".")
    parts = name.split(".")
    if (len(name) > 253 or any(not NAME_PART.fullmatch(part)
                                for part in parts)):
        raise ValueError("invalid teaching DNS name")
    return name + "."

def dns_type(value):
    if value not in ("A", "AAAA", "TXT"):
        raise ValueError("A/AAAA/TXT only in this model")
    return value

class NegativeDNSCache:
    def __init__(self):
        self.entries = {}

    def store(self, name, outcome, qtype, soa_ttl, soa_minimum, now):
        owner = dns_name(name)
        dns_type(qtype)
        if outcome not in ("NXDOMAIN", "NODATA"):
            raise ValueError("invalid negative outcome")
        if any(type(v) is not int or v < 0
               for v in (soa_ttl, soa_minimum, now)):
            raise ValueError("nonnegative integer TTL and clock required")
        ttl = min(soa_ttl, soa_minimum)
        key = (owner, None if outcome == "NXDOMAIN" else qtype)
        # A zero TTL means do not cache this answer.
        if ttl:
            # Avoid contradictory NXDOMAIN and NODATA entries in this
            # deliberately single-zone, single-class teaching cache.
            for previous in list(self.entries):
                if previous[0] == owner and (outcome == "NXDOMAIN"
                                             or previous[1] is None):
                    del self.entries[previous]
            self.entries[key] = (outcome, now + ttl)
        return ttl

    def lookup(self, name, qtype, now):
        owner = dns_name(name)
        dns_type(qtype)
        if type(now) is not int or now < 0:
            raise ValueError("nonnegative integer clock required")
        for key in ((owner, None), (owner, qtype)):
            entry = self.entries.get(key)
            if entry is None:
                continue
            outcome, expiry = entry
            remaining = expiry - now
            if remaining > 0:
                return (outcome, remaining)
            del self.entries[key]
        return None

cache = NegativeDNSCache()
assert cache.store("missing.example.", "NXDOMAIN", "A", 120, 30, 10) == 30
assert cache.lookup("MISSING.EXAMPLE", "AAAA", 39) == ("NXDOMAIN", 1)
assert cache.lookup("missing.example.", "A", 40) is None
assert cache.store("host.example", "NODATA", "AAAA", 60, 20, 50) == 20
assert cache.lookup("host.example", "A", 60) is None
assert cache.lookup("host.example", "AAAA", 60) == ("NODATA", 10)
assert cache.lookup("host.example", "AAAA", 70) is None
~~~

The example caches `missing.example.` as NXDOMAIN for 30 seconds. At time 39 it returns one remaining second even for AAAA; at 40 it misses. In contrast, `host.example.` has a type-specific AAAA NODATA at time 50, which does not imply the A record is absent. A later AAAA lookup at the expiry boundary returns no negative cache hit.

**State invariant:** each cached entry has one name-scoped NXDOMAIN key or one name-and-type-scoped NODATA key, with an integer expiry. Lookup uses the name-scoped entry before a type-scoped entry, checks strict expiry, and drops expired entries on access. When replacing a name with NXDOMAIN, the teaching cache removes conflicting type-specific entries; storing NODATA removes a conflicting NXDOMAIN. This conservative local invalidation keeps the model internally coherent but is **not** a specification for how an actual recursive resolver reconciles changing, possibly inconsistent authority responses.

The scan for stale/contradictory entries during `store` makes that operation `O(m)` in the number of cached entries; `lookup` inspects at most two dictionary keys with expected `O(1)` lookup. The model does not limit memory or implement eviction, DNSSEC status, negative caching across ancestor/descendant names, serving stale results, TTL countdown in DNS packet replies, or multi-class records. It cannot detect a malicious forged SOA.

## Executable CNAME chain with cycle and hop checks

A separate function resolves a small **fully materialized local map**. Each owner has either a CNAME or one or more A/AAAA RRsets; every RRset has its own nonnegative TTL. Input validation rejects mixed CNAME and address records and duplicate owner names after normalization. It caps alias hops and detects cycles, returning a canonical target and the minimum TTL among records actually used [1][2].

~~~python
@dataclass(frozen=True)
class AliasAnswer:
    name: str
    data: tuple
    ttl: int
    chain: tuple

def follow_cname(records, name, qtype="A", max_hops=8):
    if type(max_hops) is not int or max_hops < 0:
        raise ValueError("nonnegative integer hop limit required")
    dns_type(qtype)
    if qtype not in ("A", "AAAA"):
        raise ValueError("only address lookups are modeled")
    if not isinstance(records, dict):
        raise ValueError("records must be a mapping")

    validated = {}
    for owner, rrsets in records.items():
        key = dns_name(owner)
        if key in validated or not isinstance(rrsets, dict) or not rrsets:
            raise ValueError("invalid or duplicate normalized owner")
        if "CNAME" in rrsets and len(rrsets) != 1:
            raise ValueError("CNAME owner cannot have address RRsets")
        typed = {}
        for record_type, record in rrsets.items():
            if record_type not in ("CNAME", "A", "AAAA"):
                raise ValueError("unsupported record type")
            if (not isinstance(record, tuple) or len(record) != 2
                    or type(record[1]) is not int or record[1] < 0):
                raise ValueError("record must be (value, nonnegative TTL)")
            value, ttl = record
            if record_type == "CNAME":
                typed[record_type] = (dns_name(value), ttl)
            else:
                if (not isinstance(value, tuple) or not value
                        or any(not isinstance(v, str) or not v for v in value)):
                    raise ValueError("address RRset must be a nonempty tuple")
                typed[record_type] = (value, ttl)
        validated[key] = typed

    current = dns_name(name)
    visited = set()
    path = []
    budget = []
    while True:
        if current in visited:
            raise ValueError("CNAME cycle")
        visited.add(current)
        rrsets = validated.get(current)
        if rrsets is None:
            raise KeyError(current)  # no delegation/wildcards in this model
        if "CNAME" not in rrsets:
            if qtype not in rrsets:
                raise KeyError((current, qtype))  # no SOA proof modeled here
            addresses, ttl = rrsets[qtype]
            return AliasAnswer(current, addresses,
                               min([ttl] + budget), tuple(path))
        if len(path) >= max_hops:
            raise ValueError("CNAME hop limit exceeded")
        target, ttl = rrsets["CNAME"]
        path.append(current)
        budget.append(ttl)
        current = target

zone = {
    "www.example": {"CNAME": ("app.example", 50)},
    "app.example": {"CNAME": ("edge.example", 40)},
    "edge.example": {"A": (("192.0.2.10", "192.0.2.11"), 20)},
}
result = follow_cname(zone, "WWW.EXAMPLE.", max_hops=2)
assert result == AliasAnswer(
    "edge.example.", ("192.0.2.10", "192.0.2.11"), 20,
    ("www.example.", "app.example."))
assert follow_cname(zone, "edge.example").chain == ()
try:
    follow_cname(zone, "www.example", max_hops=1)
except ValueError:
    pass
else:
    raise AssertionError("hop limit must be enforced")
~~~

The initial name is an alias, not the final canonical target. The chain `www.example.`→`app.example.`→`edge.example.` has TTLs 50, 40 and 20 seconds; the complete positive answer has a safe combined upper lifetime of **20 seconds**. If the last target had TTL 60, the alias with TTL 40 would still cap the lifetime at 40. A cycle raises an error rather than hanging.

**Loop invariant:** after each hop, `current` is the next canonical owner, `visited` contains every owner already examined, and `budget` contains the TTL of each followed alias. Either a terminal RRset is found, a cycle is discovered, or the hop limit is reached. With `r` record entries and `h` followed aliases, full map validation costs `O(r)` over bounded record sizes; the lookup loop costs `O(h)` expected with dictionary indexing. Memory is `O(r+h)` including validated copy and chain. A real recursive resolver must resolve references across zones and may make many network queries; these bounds are **not** remote DNS latency estimates.

## DNSSEC: authenticated data is not encrypted DNS

DNSSEC adds signed RRsets, DNSKEY and DS trust links, and authenticated proofs of certain negative answers. A validator must build a chain from an accepted **trust anchor**, verify signatures and key/digest relationships, and authenticate denial of existence where applicable [4]. Merely seeing an RRSIG field or relying on the resolver's apparent authority is not validation.

A child zone may be delegated without a corresponding authentication link (an **insecure delegation**, depending on validated denial of a DS). This is conceptually distinct from a **bogus** response that fails required validation. Neither is the same as NXDOMAIN or NODATA. DNSSEC authenticates DNS data under its trust assumptions; it does **not** conceal queries from a passive observer or guarantee that an application behind an IP address is trustworthy. HTTPS still requires its own server authentication.

This chapter **does not implement DNSSEC**, cryptographic signing, NSEC/NSEC3 or wildcard denial. Storing a Boolean `signed=True` next to a record would not be meaningful validation. The difference between secure, insecure, bogus and indeterminate responses requires a separate protocol-and-cryptography study grounded in RFC 4035, beyond these small cache and alias functions [4].

## Failures, serve-stale and measurement boundaries

A recursive resolver can fail because authorities are unreachable, a referral forms a loop, DNSSEC validation fails, transport times out, or the query name truly does not exist. **SERVFAIL is not NXDOMAIN.** Storing SERVFAIL as a permanent nonexistence result can break correct hosts. In operational troubleshooting, inspect query type, authoritative vs recursive answers, TTL, DNSSEC validation status and resolver path before assuming a hostname has been deleted [1][3][4].

RFC 8767 specifies an optional **serve-stale** mechanism: under defined conditions, a resolver may answer with previously cached but expired data to improve resilience. This requires an explicit policy, timeout behavior and refreshed responses; it is not a license to treat all expired entries as normal unexpired hits. The models here strictly expire at TTL zero and implement **no serve-stale** [5].

DNS caches can improve latency and shield authorities from repeated queries, but cache correctness depends on origin trust, time, negative-key scope and invalidation. A cache hit says only that a response is inside its modeled lifetime; it does not prove the destination is reachable, that a TCP connection is available, or that an HTTPS certificate matches the hostname. Those checks belong to later layers of the [network request path](/en/topics/network-protocols/).

## Exercises and verification

1. Derive NXDOMAIN and NODATA cache keys for `host.example.` queried as A, AAAA and TXT. Explain why NODATA for AAAA must not suppress A.
2. Given SOA TTL 75 and SOA MINIMUM 20, calculate remaining negative TTL at times 10, 29 and 30 for insertion at time 10.
3. Explain why an NXDOMAIN returned for the **target** of a CNAME chain cannot automatically be treated as proof that the original alias name is nonexistent.
4. Draw the referral sequence for a zone delegated to a nameserver inside that delegated zone. Explain why glue is needed, and why glue is not by itself authenticated address data.
5. Write an independent reference implementation of the negative cache using a list of historical events, not the dictionary algorithm. Compare expiry boundaries and conflict replacement.
6. Build a CNAME cycle, a chain exceeding the hop limit and a chain terminating at a name with A but no AAAA. State precisely which errors this teaching function returns and why they differ from real authoritative DNS responses.
7. Given three aliases with TTLs 30, 10, 60 and a terminal A RRset with TTL 45, derive the maximum cache lifetime of the combined positive answer.
8. Contrast DNSSEC authenticated denial of existence, ordinary unsigned NXDOMAIN and a timeout from an unreachable authority. Identify which requires cryptographic proof.
9. Design a separate serve-stale policy with a maximum stale duration and explicit behavior when a refreshing query returns a negative answer. Do not silently change the baseline TTL contract.

**Next:** [DNS/TCP/TLS/HTTP networking](/en/topics/network-protocols/) connects DNS answers to actual transport and authenticated application behavior. Full DNSSEC validation, DNS wire parsing, glue/bailiwick acceptance and live authoritative referral testing remain separate implementation tasks [1][2][3][4][5].
