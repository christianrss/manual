---
id: tcp-byte-stream-framing-flow-control
title: "TCP Byte Streams: Message Framing, ACKs and Flow Control"
description: "Derive TCP stream framing, relative sequence numbers, cumulative acknowledgments and sender windows using independently verified Python models."
category: networking
difficulty: intermediate
updated: 2026-10-10
prerequisites: [ip-routing-dns-resolution, network-protocols]
sources:
  - {title: "RFC 9293 — Transmission Control Protocol", url: "https://www.rfc-editor.org/info/rfc9293", kind: "IETF internet standard"}
  - {title: "RFC 5681 — TCP Congestion Control", url: "https://www.rfc-editor.org/info/rfc5681", kind: "IETF internet standard"}
  - {title: "RFC 7323 — TCP Extensions for High Performance", url: "https://www.rfc-editor.org/info/rfc7323", kind: "IETF internet standard"}
  - {title: "RFC 4632 — Classless Inter-Domain Routing", url: "https://www.rfc-editor.org/info/rfc4632", kind: "IETF best current practice"}
---
TCP carries an **ordered stream of bytes**, not an ordered list of messages. Applications often write complete objects, JSON documents or serialized commands and accidentally assume one `send` maps to one `recv`. No such mapping exists: a receiver can observe half a header, multiple messages in one read, or a boundary at any byte position. TCP sequence numbers refer to **octets in the stream**, and ACK numbers usually acknowledge a contiguous prefix [1].

The earlier [IP routing and DNS](/en/topics/ip-routing-dns-resolution/) chapter explains how an endpoint is selected, and [network protocols](/en/topics/network-protocols/) places TCP between IP and application protocols. This chapter goes one level deeper into **framing**, **out-of-order arrivals**, **cumulative ACKs**, and the distinct controls imposed by the receiver and by congestion. All programs here are deterministic **application/transport teaching models**, not socket code or implementations of RFC 9293.

## A byte stream cannot preserve application message boundaries

Suppose a sender makes three calls: `send(b"AB")`, `send(b"")` and `send(b"C")`. A TCP peer is free to observe the actual three data bytes `ABC` grouped into any receive-call boundaries, and a zero-length application send does **not** create a visible empty message in the TCP stream. If an application needs to distinguish an empty message from the absence of a message, its protocol must explicitly encode the empty message [1].

A **length-prefixed frame** is one solution. We choose exactly **two unsigned big-endian header bytes**, followed by precisely that many payload bytes. Frame `b"AB"` is `00 02 41 42` in hexadecimal; an empty frame is `00 00`, consuming two bytes in the application protocol. The maximum representable payload is 65,535 bytes. That is a property of this chosen framing format, **not a TCP maximum segment size**.

A correct incremental decoder must handle header splits, payload splits, consecutive frames and empty frames. It must also **reject oversize declarations before allocating unbounded application memory**. Here the configured limit can be smaller than the two-byte wire-format maximum. Choosing a format before writing parser code prevents accidental dependencies on the batching behavior of operating-system reads.

## Framing decoder with an explicit failure contract

The encoder validates that payloads are exact Python `bytes`; it rejects text strings, mutable byte arrays and payloads longer than 65,535. The decoder accepts only byte chunks. It collects complete frames and retains any incomplete suffix for the next feed.

A subtle error occurs when invalid input is appended to the persistent buffer **before** size validation. To keep a testable contract, the implementation constructs a candidate byte sequence and changes the live buffer **only after** all complete headers examined are valid. If any advertised length exceeds the configured cap, the call raises `ValueError` and leaves the existing buffered prefix unchanged. It does not offer resynchronization after a malformed stream; the caller should treat the connection as a protocol failure rather than skip arbitrary bytes.

~~~python
def encode_frame(payload):
    if type(payload) is not bytes or len(payload) > 65535:
        raise ValueError("payload must be bytes of at most 65535 octets")
    return len(payload).to_bytes(2, "big") + payload

class FrameDecoder:
    def __init__(self, max_payload=4096):
        if type(max_payload) is not int or not 0 <= max_payload <= 65535:
            raise ValueError("invalid maximum payload")
        self.max_payload = max_payload
        self.buffer = bytearray()

    def feed(self, chunk):
        if type(chunk) is not bytes:
            raise ValueError("TCP chunks must be bytes")
        candidate = bytes(self.buffer) + chunk
        cursor = 0
        completed = []
        while len(candidate) - cursor >= 2:
            length = int.from_bytes(candidate[cursor:cursor + 2], "big")
            if length > self.max_payload:
                raise ValueError("declared frame exceeds configured limit")
            if len(candidate) - cursor < 2 + length:
                break
            completed.append(candidate[cursor + 2:cursor + 2 + length])
            cursor += 2 + length
        self.buffer = bytearray(candidate[cursor:])
        return tuple(completed)

wire = encode_frame(b"AB") + encode_frame(b"") + encode_frame(b"C")
decoder = FrameDecoder(max_payload=8)
assert decoder.feed(wire[:1]) == ()
assert decoder.feed(wire[1:4]) == (b"AB",)
assert decoder.feed(wire[4:]) == (b"", b"C")
assert decoder.buffer == bytearray()
try:
    decoder.feed(b"\x00\x09")  # over the configured 8-byte payload cap
except ValueError:
    pass
else:
    raise AssertionError("oversized frame must fail")
assert decoder.buffer == bytearray()  # rejected input is transactional
~~~

The first `feed` sees only the initial header byte, producing no message. The second call completes the header and body of `AB`. The third call delivers both the explicitly encoded empty frame and the last frame. This trace must not be confused with a packet trace: TCP may deliver these bytes in different-sized reads with the same decoded messages.

**Decoder invariant:** after every successful feed, all returned frames came from a nonoverlapping prefix of the accumulated wire stream; the remaining buffer is exactly the unconsumed suffix. The buffer either contains fewer than two header bytes or a complete header followed by an incomplete payload. An invalid candidate changes neither completed messages already returned in prior calls nor the current persistent buffer.

The straightforward candidate-copy implementation can have **quadratic total copying** under adversarial one-byte feeds into a large, incomplete frame. Per feed, parsing and copying cost `O(buffered_bytes + incoming_bytes)`; retaining a bounded maximum frame length limits unconsumed memory but does not remove the cumulative copying cost. A production parser can maintain a cursor/ring buffer, impose connection-wide quotas and avoid repeatedly copying the prefix. Such optimizations require independent buffer-lifetime and parser-state tests.

## Sequence numbers are per-byte and ACKs are cumulative

Under TCP, the sequence number of data is the position of its **first octet** in a finite 32-bit modular sequence space. A cumulative ACK value `X` says that all data octets before `X` in the current receive sequence have been received. A segment arriving beyond a gap may be buffered, but without selective acknowledgment extensions, the cumulative ACK does **not** advance over a missing earlier byte [1][3].

For a readable model we use **relative integer offsets starting at zero**, without SYN/FIN consuming sequence space, wraparound, timestamps, retransmission timers, selective ACK blocks or connection setup. This is deliberately **not** the arithmetic of 32-bit TCP sequence numbers. Relative offsets make it possible to test continuity without mistakenly implementing unsafe direct numerical comparisons across wraparound.

Consider arrivals of bytes `DEF` at relative offset 3, then `ABC` at 0. After the first arrival, the next expected byte is still zero; the prefix `ABC` is missing. After the second, all six bytes are contiguous and the next expected offset becomes six. Duplicate old data must not advance the cumulative ACK again.

## Executable bounded out-of-order receiver

The receiver holds at most a bounded number of yet-undelivered byte positions in `pending` and accepts a new byte only if its relative offset lies in `[next_seq, next_seq + window)`. This is a **toy constant receive window**; it implicitly assumes that delivered bytes are immediately consumed by the application. A real receiver's advertised window depends on buffer availability and may shrink or grow independently of application framing [1].

When overlapping segments disagree on a byte, this model retains the **first accepted byte**. It is an illustrative deterministic rule, **not** a universal TCP overlap-handling contract. Input consists of complete, uncorrupted Python byte sequences; network checksums, malicious overlaps, retransmission timing and security policy are outside scope.

~~~python
class ToyReceiver:
    def __init__(self, window=8):
        if type(window) is not int or window <= 0:
            raise ValueError("positive integer window required")
        self.window = window
        self.next_seq = 0
        self.pending = {}  # relative byte offset -> byte value
        self.delivered = bytearray()

    def accept(self, seq, payload):
        if type(seq) is not int or seq < 0 or type(payload) is not bytes:
            raise ValueError("nonnegative relative sequence and byte payload required")
        for offset, value in enumerate(payload):
            position = seq + offset
            if self.next_seq <= position < self.next_seq + self.window:
                self.pending.setdefault(position, value)  # first arrival wins
        newly = bytearray()
        while self.next_seq in self.pending:
            newly.append(self.pending.pop(self.next_seq))
            self.next_seq += 1
        self.delivered.extend(newly)
        return self.next_seq, bytes(newly)

receiver = ToyReceiver(window=8)
assert receiver.accept(3, b"DEF") == (0, b"")
assert receiver.accept(0, b"ABC") == (6, b"ABCDEF")
assert receiver.accept(2, b"CDE") == (6, b"")  # duplicate retransmission
assert receiver.accept(8, b"I") == (6, b"")
assert receiver.accept(6, b"GH") == (9, b"GHI")
assert bytes(receiver.delivered) == b"ABCDEFGHI"
assert receiver.pending == {}

def send_allowance(cwnd, rwnd, in_flight):
    if any(type(v) is not int or v < 0 for v in (cwnd, rwnd, in_flight)):
        raise ValueError("windows and in-flight data must be nonnegative integers")
    return max(0, min(cwnd, rwnd) - in_flight)

assert send_allowance(12, 8, 5) == 3
assert send_allowance(8, 12, 5) == 3
assert send_allowance(12, 8, 9) == 0  # windows can shrink
~~~

The second arrival makes `ABCDEF` newly contiguous. The duplicate at offset two delivers nothing. Bytes at offset eight stay pending until `GH` fills the gap; then `GHI` can be delivered. The model reports `(next_expected_offset, newly_delivered_bytes)`. It does **not send real ACK packets** or control actual network traffic.

**Receiver invariant:** for every accepted offset smaller than `next_seq`, one byte has been delivered exactly once; every pending offset lies at or above `next_seq`; no pending offset was already delivered. `next_seq` never decreases. The algorithm stores at most `window` out-of-order bytes at a time, with dictionary expected-constant operations per octet. Work per arrival is linear in input length plus newly deliverable bytes. The model also stores the entire delivered stream for inspection, so total memory is **not bounded by the receive window**; a production consumer can process and release delivered data.

## Flow control protects the receiver, congestion control protects the path

Two independent constraints determine how much data a sender may have outstanding. **Receiver window (`rwnd`)** advertises available receive capacity; **congestion window (`cwnd`)** limits sender in-flight data according to network congestion algorithms and observations. In a simplified stable instant, the sender's amount of new data can be bounded by `max(0, min(cwnd, rwnd) - in_flight)` [2]. The smaller window wins.

For instance, `cwnd=12` and `rwnd=8` permit at most eight outstanding units, so if five are already in flight, three additional units fit. If `rwnd` contracts below the already outstanding nine units, the computed new-send allowance is zero; that does **not** mean the sender magically retracts previously transmitted bytes. The helper validates exact nonnegative integer arguments, not a real TCP congestion-control state machine.

Real TCP has additional constraints: advertised-window updates, sequence arithmetic, retransmission state, persist and zero-window probes, delayed ACKs, slow start, congestion avoidance, fast recovery and optional scaling. RFC 5681 describes core congestion-control principles; RFC 7323 provides window scaling and timestamps. None can be faithfully replaced by subtracting three integers [2][3].

## Loss, retransmission, head-of-line delay and stream framing

If an earlier sequence range is lost, later ranges may arrive, but a TCP application normally cannot consume those later bytes as an ordered stream until the gap is filled. This **transport head-of-line blocking** affects latency even if the application has multiple length-prefixed messages. The receiver example exhibits the same *ordering property*, but not a loss-detection algorithm or retransmission timer.

TCP retransmits missing data according to its protocol, while applications must separately handle uncertainty about **business effects**. A successfully acknowledged TCP byte stream does not mean a database transaction has been committed; conversely, a client timeout after sending a command does not prove the server failed to apply it. Application-level idempotency and durable operation IDs are necessary when retrying non-idempotent commands [1].

Streams are bidirectional; each direction has its own sequence and flow-control state. This chapter demonstrates only a single receive direction. Simultaneous close, half-close, `TIME_WAIT`, RST, state transitions, connection security and the socket API remain excluded.

## Transport boundaries and system-design consequences

A service receiving an unknown amount of input should cap **both** the declared frame size and the number of connections/buffers it will maintain. A two-byte prefix caps one frame to 65,535 bytes, but ten thousand connections each buffering near that maximum can still exhaust application memory. Apply quotas, read deadlines, cancellation and backpressure; do not call a parser “safe” solely because its per-frame length is bounded.

Likewise, a large `rwnd` cannot overcome path congestion, and a large `cwnd` cannot force a saturated receiver to accept more. Bandwidth-delay product helps explain why high-latency fast paths may need larger windows and why optional scaling exists, but a real throughput prediction requires loss, RTT, congestion algorithm, peer behavior and measurements [2][3]. CIDR route selection, described in the [IP chapter](/en/topics/ip-routing-dns-resolution/), chooses a next hop; it does not implement TCP retransmission or message framing [4].

## Exercises and verification

1. Encode the frames `b"A"`, `b""` and `b"BC"` using a two-byte big-endian length. Split the resulting stream after **every possible byte boundary** and verify identical decoded messages.
2. Prove why `send(b"")` cannot function as a message separator in TCP, whereas a two-byte zero-length frame can.
3. Change `FrameDecoder` to retain an existing valid incomplete prefix when a later chunk advertises an oversized frame. State exactly which state must not change when `ValueError` is raised.
4. Trace arrivals at offsets 3, 0, 8 and 6. Draw pending bytes and cumulative ACK after each event, and explain why an out-of-order arrival cannot advance ACK over a gap.
5. Inject a segment partly outside the model window. Explain which bytes are accepted and why a real advertised receive window has more complicated rules.
6. Derive sender allowance for `(cwnd, rwnd, in_flight)=(12,8,5)`, `(8,12,5)` and `(12,8,9)`. Explain why a window shrink does not undo sent bytes.
7. Describe slow start and a loss recovery scenario **without** assuming the arithmetic helper implements them. List state variables a real sender would need.
8. Identify which properties belong to the TCP transport, which belong to application framing, and which require a transaction protocol beyond transport acknowledgment.

**Continue:** [TCP retransmission timers and congestion windows](/en/topics/tcp-rto-retransmission-congestion/) derives RFC 6298 estimation and a bounded round sketch; [network protocols](/en/topics/network-protocols/) covers TLS/HTTP and connection diagnostics; [reliable APIs](/en/topics/api-reliability/) handles retries and durable effects. Kernel TCP implementation, QUIC stream state, real packet capture and congestion simulations remain future independent topics [1][2][3][4].
