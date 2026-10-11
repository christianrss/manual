# IPv4 fragmentation and PMTU — 2026-10-11 technical scope

Complete EN/PT chapter with models for IPv4 fragmentation (20-byte no-options header), eight-byte offsets, MF/DF, bounded reassembly with strict overlap and gap rejection; and idealized iterative DF-based Path MTU probing revealing the first constraining link at each step.

Independent byte-position oracle checks fragment boundaries and another per-byte ownership representation checks reassembly across 2,056 payload-size/MTU combinations per language, plus one maximal 65,515-byte IPv4 payload and adversarial incomplete/invalid sets. An independently implemented per-hop reference compares 930 short path/initial-size combinations per language. Both language variants execute all code fences.

Not modeled: wire headers or checksums, IP options, re-fragmentation, simultaneous datagrams and identification, real ICMP validation, variable routes, spoofing and loss, IPv6 source fragmentation, PLPMTUD/DPLPMTUD or kernel TCP integration. Finite tests are not network conformance or real packet captures.

Standards: RFC 791, RFC 1191, RFC 8200, RFC 8201, RFC 8899.
