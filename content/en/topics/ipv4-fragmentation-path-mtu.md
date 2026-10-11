---
id: ipv4-fragmentation-path-mtu
title: "IP Packet Size: IPv4 Fragmentation and Path MTU Discovery"
description: "Derive the 8-byte IPv4 fragment offset, MF/DF semantics, ordered reassembly, and classical PMTUD under explicit finite models."
category: networking
difficulty: intermediate
updated: 2026-10-11
prerequisites: [ip-routing-dns-resolution]
sources:
  - {title: "RFC 791 — Internet Protocol", url: "https://www.rfc-editor.org/info/rfc791", kind: "IETF protocol specification"}
  - {title: "RFC 1191 — Path MTU Discovery", url: "https://www.rfc-editor.org/info/rfc1191", kind: "IETF standards-track specification"}
  - {title: "RFC 8200 — IPv6 Specification", url: "https://www.rfc-editor.org/info/rfc8200", kind: "IETF internet standard"}
  - {title: "RFC 8201 — IPv6 Path MTU Discovery", url: "https://www.rfc-editor.org/info/rfc8201", kind: "IETF internet standard"}
  - {title: "RFC 8899 — Datagram Packetization Layer Path MTU Discovery", url: "https://www.rfc-editor.org/info/rfc8899", kind: "IETF standards-track specification"}
---
A route determines the *next hop*, but that does not ensure an IP packet can cross every link **at its original size**. Each link has a maximum transmission unit (MTU), measured at the relevant network-layer interface. The **path MTU (PMTU)** is the minimum usable MTU along the chosen path; tunnels and encapsulation can further reduce the packet space available to the original payload [1][2].

The [IP routing and DNS chapter](/en/topics/ip-routing-dns-resolution/) covers address selection and forwarding. Here we derive the actual IPv4 **fragment offset**, the More Fragments (MF) and Don't Fragment (DF) flags, reassembly invariants and feedback-driven PMTU discovery. We deliberately do **not** simulate TCP segmentation, a live router, ICMP wire checksums, IPv4 options, fragmentation of existing fragments, IPv6 extension headers or actual network security.

## MTU, datagram length and the network/transport boundary

For an IPv4 packet with an options-free **20-byte header**, the total packet length is `20 + payload bytes`. The IPv4 Total Length field is 16 bits, so this teaching model rejects payloads above **65,515 bytes**. An MTU concerns the entire IP packet, **not just TCP application data**. TCP's maximum segment size and options add transport-layer constraints; a DNS response, UDP datagram and TCP segment must not be treated as equivalent-sized packets [1].

A network path can include links with MTUs 1500, 1200 and 900 bytes. If a 1500-byte IP packet is allowed to cross the first link, it may still be too big for the second. Merely seeing a valid route does not prove it can traverse the path without size adaptation. The sender may reduce future packets, or—in IPv4 when fragmentation is allowed—a router may fragment eligible packets [1][2].

## Eight-byte offsets and fragment flags

IPv4's **Fragment Offset** field expresses the start of the fragment's data in **units of eight octets**, relative to the original unfragmented payload. The **MF** flag says more fragments follow; only the final fragment clears MF. The **DF** flag prohibits fragmentation. When a packet exceeds a link MTU while DF is set, a router cannot repair it by fragmenting; it must drop the packet and may return an applicable ICMP fragmentation-needed message [1][2].

Each fragment is a separate IP packet with its own IPv4 header. In the fixed-20-byte-header model, a link MTU of **68 bytes** admits at most **48 bytes of payload per packet**. With 100 bytes of original payload, the correct layout is 48, 48 and 4 bytes, with offsets **0, 6 and 12** in eight-byte units. Every non-final fragment has a payload length divisible by eight; the final fragment may be shorter. This last-fragment exception is part of the protocol, not an implementation convenience [1].

| Original payload range | Offset units | Payload length | MF | Total IP length |
| --- | ---: | ---: | --- | ---: |
| 0–47 | 0 | 48 | 1 | 68 |
| 48–95 | 6 | 48 | 1 | 68 |
| 96–99 | 12 | 4 | 0 | 24 |

The sender and destination need more context than these fields to distinguish simultaneous datagrams: source, destination, protocol and identification also matter [1]. Our `Fragment` records intentionally represent **one already-associated datagram**, never a global multi-flow reassembly table. In real networks, fragments may be lost, delayed, duplicated or delivered out of order.

## Model fragmentation and strict single-datagram reassembly

The following code models a **fresh, options-free IPv4 datagram**. It validates payload and MTU before constructing fragments, uses eight-byte-aligned non-final slices, and rejects an oversized request when DF is set. For convenience this example requires MTU **at least 68**, the IPv4 router forwarding minimum specified by RFC 791. That precondition is a **modeling bound**, not a universal statement that all operational link MTUs are exactly or above 68 [1].

For reassembly, a complete input needs **exactly one final fragment**, no gaps and no overlaps. The code uses a byte-position table rather than inferring completeness from last offset alone, so a duplicated or overlapping fragment fails. This is a pedagogical **strict** policy: it does not implement actual Linux IPv4 reassembly policies, timeouts, memory quotas, header checksums or the identification space. It permits reordering the input records while requiring their covered byte ranges to form one contiguous payload.

~~~python
from dataclasses import dataclass

@dataclass(frozen=True)
class Fragment:
    offset_units: int
    more: bool
    payload: bytes

def fragment_ipv4(payload, mtu, df=False):
    if type(payload) is not bytes:
        raise ValueError("payload must be bytes")
    if (type(mtu) is not int or not 68 <= mtu <= 65535
            or type(df) is not bool or len(payload) > 65515):
        raise ValueError("invalid fixed-header IPv4 datagram")
    capacity = mtu - 20
    if len(payload) <= capacity:
        return (Fragment(0, False, payload),)
    if df:
        raise ValueError("DF prohibits fragmentation")
    aligned = (capacity // 8) * 8
    fragments = []
    start = 0
    while len(payload) - start > capacity:
        fragments.append(Fragment(start // 8, True,
                                  payload[start:start + aligned]))
        start += aligned
    fragments.append(Fragment(start // 8, False, payload[start:]))
    return tuple(fragments)

def reassemble_ipv4(fragments):
    parts = tuple(fragments)
    if not parts or any(not isinstance(p, Fragment) for p in parts):
        raise ValueError("expected fragment records")
    end = None
    occupied = {}
    for p in parts:
        if (type(p.offset_units) is not int
                or not 0 <= p.offset_units < 8192
                or type(p.more) is not bool
                or type(p.payload) is not bytes
                or (p.more and (not p.payload or len(p.payload) % 8))):
            raise ValueError("invalid fragment")
        start = 8 * p.offset_units
        stop = start + len(p.payload)
        if stop > 65515:
            raise ValueError("reassembled IPv4 length exceeded")
        if not p.more:
            if end is not None:
                raise ValueError("multiple final fragments")
            end = stop
        for i, octet in enumerate(p.payload, start):
            if i in occupied:
                raise ValueError("overlapping fragments")
            occupied[i] = octet
    if end is None or len(occupied) != end or any(i not in occupied for i in range(end)):
        raise ValueError("incomplete fragment set")
    return bytes(occupied[i] for i in range(end))

data = bytes(range(100))
parts = fragment_ipv4(data, mtu=68)
assert [(p.offset_units, p.more, len(p.payload)) for p in parts] == [
    (0, True, 48), (6, True, 48), (12, False, 4)]
assert reassemble_ipv4(parts[::-1]) == data
assert fragment_ipv4(b"", mtu=68) == (Fragment(0, False, b""),)
try:
    fragment_ipv4(data, mtu=68, df=True)
except ValueError:
    pass
else:
    raise AssertionError("oversized DF packet must be rejected")
~~~

**Correctness invariants:** for every fragment, `start = 8 × offset_units`; every MF=1 payload has positive length divisible by eight; `header + payload ≤ MTU` for fragments produced by the specified MTU; each original byte appears exactly once in the generated records. On reassembly, each covered byte index has exactly one owner, and the final fragment determines the expected total. After checking that every position in `[0,end)` exists, reconstructing bytes in increasing index order recovers the original payload.

If payload length is `n` and there are `k` fragments, fragment construction is `O(n+k)` for output copies and records. This reassembler builds a Python dictionary over `n` bytes and checks the interval, using expected `O(n+k)` time and `O(n)` additional space under standard hash assumptions. These are algorithmic costs of the Python example, **not** costs or constraints of a production IP stack.

## Path MTU Discovery: a sequence of feedback, not one guess

Classical IPv4 **Path MTU Discovery** sets DF on probe traffic and adapts the effective send size when a router cannot forward a packet of that size. An applicable ICMPv4 error identifies “fragmentation needed” (Destination Unreachable **type 3, code 4**) and may include the next-hop MTU [2]. In the idealized path (1500, 1200, 900), a 1500-byte packet reaches the bottleneck at the **second link**, revealing 1200; the next 1200-byte attempt reaches the **third link** and reveals 900. The final 900-byte attempt can traverse all links.

The following simulator visits link MTUs in order and reports only the **first** link too small for the attempted packet. A separate trace function reduces to that value until delivery. This is more faithful to classical iterative discovery than simply returning `min(all MTUs)` as if the sender already knew the entire path.

~~~python
def probe_df_path(link_mtus, packet_size):
    hops = tuple(link_mtus)
    if (not hops or any(type(x) is not int or not 68 <= x <= 65535
                        for x in hops)
            or type(packet_size) is not int
            or not 20 <= packet_size <= 65535):
        raise ValueError("invalid path or IPv4 packet length")
    for position, hop_mtu in enumerate(hops):
        if packet_size > hop_mtu:
            return ("too-big", position, hop_mtu)
    return ("delivered", None, None)

def classical_pmtud_trace(link_mtus, initial_size):
    hops = tuple(link_mtus)
    current = initial_size
    trace = []
    while True:
        status, position, reported_mtu = probe_df_path(hops, current)
        trace.append((current, status, position, reported_mtu))
        if status == "delivered":
            return tuple(trace)
        current = reported_mtu  # ideal, authenticated, delivered ICMP feedback

assert classical_pmtud_trace((1500, 1200, 900), 1500) == (
    (1500, "too-big", 1, 1200),
    (1200, "too-big", 2, 900),
    (900, "delivered", None, None))
assert probe_df_path((1500, 1400), 1400) == ("delivered", None, None)
~~~

This function deliberately assumes accurate, delivered and trustworthy feedback, a fixed route, constant link MTUs and immediate retry. A real sender must validate ICMP reports, account for potentially forged or missing responses, retransmission timing, path changes and the packetization layer's own constraints. An ICMP message reporting a smaller MTU is not interchangeable with a TCP congestion signal. Sending a smaller packet may work without proving the application or transport state is correct [2][5].

## IPv4 versus IPv6: do not copy fragmentation rules

**IPv6 routers do not fragment transit packets.** IPv6 fragmentation, when used, is performed by the source with a Fragment extension header; the IPv6 base header is 40 bytes and has different length/extension semantics from IPv4. IPv6 Path MTU Discovery uses ICMPv6 **Packet Too Big**, and IPv6 has a minimum link MTU of **1280 bytes** under RFC 8200 [3][4]. The IPv4 code above therefore cannot be reused by changing the header length from 20 to 40.

Fragmentation also creates security and availability concerns: incomplete sets cannot be delivered as original payloads, overlapping fragments are hazardous, and stateful network controls may see only part of the transport header. IPv6 specifies strict handling of overlapping fragment data; our strict Python validation is a didactic choice and not a claim to implement that entire RFC behavior [3].

## PMTU black holes and packetization-layer probing

Classical PMTUD can fail when required ICMP feedback is dropped by firewalls or middleboxes, leading to a **PMTU black hole**: small packets and handshakes work, but larger transfers stall. This failure is easy to confuse with an application timeout or congestion [4][5].

**DPLPMTUD** in RFC 8899 probes at the packetization layer and can learn suitable sizes from success and failure signals without requiring receipt of every ICMP error. It also introduces validation/probing procedures and bounds, rather than the toy “reduce immediately to the reported value” loop [5]. We **do not** implement DPLPMTUD. The chapter's simulator cannot establish an actual PMTU through live measurements, nor can it infer a packet's delivery solely from the lack of an error.

## Verification and failure contracts

The repository tests use **independent arithmetic and a byte-ownership bitmap oracle**. The fragmenter is checked over varied payload lengths and MTUs, verifying every chosen offset and MF flag against expected size boundaries. Reassembly is separately checked against a shuffled collection of generated fragments, with overlapping, missing, duplicate-final and malformed inputs rejected. The PMTU trace is compared with a per-link reference model that simulates each attempted packet's first failing hop.

Two nonnegotiable boundaries remain: no multi-flow fragment identification table and no model of time or ICMP trust. Finite exhaustive tests establish the stated **bounded software contracts**, not full conformance to all IPv4/IPv6 packet formats or correctness under packet loss and adversarial traffic. Avoid converting an idealized trace into a production availability or security guarantee.

## Exercises and verification

1. Fragment a 150-byte IPv4 payload with 20-byte headers over MTU 68. Derive every offset, MF bit and packet size manually.
2. Explain why **non-final** fragment lengths must be multiples of eight. Show what goes wrong if a 45-byte intermediate fragment is assigned an integer offset for the next fragment.
3. Reassemble three fragments in reverse order; identify the validations needed before trusting the result. Then remove the middle fragment.
4. Compare a 20-byte IP header and an IP header with options. Why is the fixed-header fragmenter insufficient for the latter?
5. Derive the link that first rejects a DF packet of 1500 bytes over MTUs 1500/1200/900; repeat after receiving an ideal reported MTU.
6. Describe how a PMTU black hole differs from a DNS lookup failure, TCP congestion and a server-side HTTP timeout.
7. Compare IPv4 router fragmentation with IPv6 source-only fragmentation and the ICMPv6 Packet Too Big mechanism.
8. Design an experimental DPLPMTUD probe sequence that adapts without trusting arbitrary ICMP data, and list what outcomes would be ambiguous.

**Continue:** [DNS authoritative resolution](/en/topics/dns-authoritative-negative-cname/) treats naming and caching, [TCP flow control and framing](/en/topics/tcp-byte-stream-framing-flow-control/) addresses reliable streams, and [TCP retransmission timers](/en/topics/tcp-rto-retransmission-congestion/) addresses a different kind of loss response [1][2][3][4][5].
