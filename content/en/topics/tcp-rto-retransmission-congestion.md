---
id: tcp-rto-retransmission-congestion
title: "TCP Retransmission Timers: RTT Estimation, Karn's Rule and Congestion Windows"
description: "Derive RFC 6298 SRTT/RTTVAR/RTO and backoff, then distinguish a simplified cwnd/ssthresh round model from actual TCP Reno."
category: networking
difficulty: advanced
updated: 2026-10-10
prerequisites: [tcp-byte-stream-framing-flow-control]
sources:
  - {title: "RFC 6298 — Computing TCP's Retransmission Timer", url: "https://www.rfc-editor.org/info/rfc6298", kind: "IETF standards-track RFC"}
  - {title: "RFC 5681 — TCP Congestion Control", url: "https://www.rfc-editor.org/info/rfc5681", kind: "IETF standards-track RFC"}
  - {title: "RFC 9293 — Transmission Control Protocol", url: "https://www.rfc-editor.org/info/rfc9293", kind: "IETF Internet Standard"}
  - {title: "RFC 8985 — RACK-TLP Loss Detection for TCP", url: "https://www.rfc-editor.org/info/rfc8985", kind: "IETF standards-track RFC"}
---
A TCP sender cannot treat a missing acknowledgment as immediate evidence that data has been lost. Networks have variable round-trip times (RTT), queues and reordered segments. The sender needs a **retransmission timeout (RTO)** calibrated from measured RTTs, while a separate congestion-control mechanism decides how aggressively to inject more data into the network [1][2]. These mechanisms solve different problems.

The [TCP byte-stream chapter](/en/topics/tcp-byte-stream-framing-flow-control/) already defines relative byte offsets, cumulative ACKs, `rwnd`, `cwnd` and application message framing. Here we implement (1) a compact estimator following the principal arithmetic of **RFC 6298**, and (2) an explicitly simplified **round-based congestion-window sketch**. The first models timeout estimation; the second illustrates growth and loss reaction. Neither is a complete TCP socket, RFC-compliant sender, packet-recovery engine or congestion-control benchmark [1][2][3].

## Which state belongs to the timer and which to congestion control?

The **smoothed RTT (SRTT)** estimates typical observed delay. **RTT variation (RTTVAR)** captures variation, which helps choose a timeout above typical delay. **RTO** is the time the retransmission timer should wait before reacting to missing acknowledgment. Its value is related to RTT but cannot simply equal the latest observation: jitter would cause false loss alarms [1].

Congestion control tracks different state. **cwnd** limits outstanding sender data based on path conditions; **rwnd** is receiver-advertised capacity; **ssthresh** is a threshold separating slow-start growth from congestion avoidance. FlightSize represents bytes already sent but not cumulatively acknowledged. An RTT estimate is not a congestion window, and an RTO expiration is not the same event as an ACK demonstrating that new bytes were delivered [2].

The simplified examples deliberately use **seconds** for timer values and **whole MSS-sized segment units** for the congestion sketch. Do not combine them as though the sketch's integers were actual TCP bytes. In a production implementation the units, socket state, pacing and accounting boundaries must be consistent.

## RFC 6298 estimator and the order of operations

Before obtaining a usable RTT sample, RFC 6298 recommends an initial RTO of one second; it permits larger values under specified conditions. After the **first** eligible RTT measurement `R`, set `SRTT=R` and `RTTVAR=R/2`. Compute `RTO=SRTT + max(G,4×RTTVAR)`, where `G` is the timer clock granularity. The RFC specifies a one-second lower bound for the computed timer and permits an upper bound of at least 60 seconds [1].

For each subsequent eligible sample `R'`, update **RTTVAR first, using the OLD SRTT**:

`RTTVAR <- 0.75×RTTVAR + 0.25×|old_SRTT − R'|`.

Then update `SRTT <- 0.875×old_SRTT + 0.125×R'` and recompute RTO. Updating SRTT before evaluating the deviation produces a different estimator and violates the stated update ordering [1]. The demonstration fixes `G=0.01` seconds, a 1-second computed floor and a **model-specific 60-second cap**; systems can use different clocks, bounds and implementation techniques.

## Karn's ambiguity rule and retransmission backoff

If a segment is retransmitted and later acknowledged, the ACK alone does not reveal whether the original or retransmitted copy was responsible. Taking that ambiguous delay as an RTT sample can distort the estimator. **Karn's rule** therefore excludes ambiguous retransmitted data from ordinary RTT sampling; timestamp extensions can permit more nuanced measurements in actual stacks [1].

On an RTO expiration, an implementation backs off the timeout, typically **doubling RTO**. The toy model performs `min(60,2×RTO)`, retaining the cap. It does not schedule a timer, resend bytes, track ACK ranges or infer whether actual loss occurred. Its `observe(rtt, retransmitted=True)` flag represents an explicitly excluded ambiguous sample, not a real acknowledgment handler.

~~~python
import math

class RtoEstimator:
    """Illustrative RFC 6298 estimator; seconds, G=10 ms, max RTO=60 s."""
    def __init__(self, granularity=0.01):
        if (type(granularity) not in (int, float)
                or not math.isfinite(granularity) or granularity <= 0):
            raise ValueError("positive finite clock granularity required")
        self.g = float(granularity)
        self.srtt = None
        self.rttvar = None
        self.rto = 1.0

    def observe(self, rtt, retransmitted=False):
        if (type(rtt) not in (int, float)
                or not math.isfinite(rtt) or rtt <= 0
                or type(retransmitted) is not bool):
            raise ValueError("positive finite RTT and boolean flag required")
        if retransmitted:
            return self.rto  # Karn: ambiguous ACK is not an RTT sample
        rtt = float(rtt)
        if self.srtt is None:
            self.srtt = rtt
            self.rttvar = rtt / 2
        else:
            old_srtt = self.srtt
            self.rttvar = 0.75 * self.rttvar + 0.25 * abs(old_srtt - rtt)
            self.srtt = 0.875 * old_srtt + 0.125 * rtt
        self.rto = min(60.0, max(1.0, self.srtt + max(self.g, 4 * self.rttvar)))
        return self.rto

    def timeout(self):
        self.rto = min(60.0, self.rto * 2)
        return self.rto

clock = RtoEstimator()
assert clock.rto == 1.0
assert abs(clock.observe(0.4) - 1.2) < 1e-12
assert abs(clock.observe(0.6) - 1.225) < 1e-12
assert abs(clock.timeout() - 2.45) < 1e-12
before = (clock.srtt, clock.rttvar, clock.rto)
assert clock.observe(0.9, retransmitted=True) == before[2]
assert (clock.srtt, clock.rttvar, clock.rto) == before
assert abs(clock.observe(0.5) - 1.109375) < 1e-12
~~~

The first 400-ms sample yields SRTT=0.4, variation=0.2 and RTO=1.2 seconds. After a 600-ms sample, SRTT becomes 0.425, variation remains 0.2 and RTO becomes 1.225. A timeout doubles it to 2.45. A subsequent ambiguous 900-ms observation **does not change** any timer state. The next eligible 500-ms observation recomputes the timer from valid samples rather than from the backed-off value.

**Estimator invariant:** SRTT and RTTVAR are absent until the first eligible sample, then remain finite and nonnegative; RTO remains in the defined inclusive bounds `[1,60]` seconds. Rejected inputs and ambiguous samples leave estimator state unchanged. Every eligible update consumes a finite positive RTT; a timeout changes only RTO, not the smoothed estimates.

Each sample and timeout uses a constant number of floating-point operations and `O(1)` retained state. This does not establish the correctness of wall-clock timer scheduling or the effect of operating-system clock granularity. Floating-point arithmetic is also approximate; tests compare with appropriate tolerances rather than decimal-string equality.

## Why one ACK is not necessarily one packet or one RTT

A sender may receive delayed ACKs, cumulative ACKs covering multiple segments, duplicate ACKs, selectively acknowledged data or acknowledgments after retransmission. These events do not all license the same updates. RTT samples require identifying a **measurable transmission and its acknowledgment**; otherwise Karn's ambiguity appears [1].

The RTO model receives eligible samples from the caller instead of discovering them from timestamps and sequence numbers. It cannot tell whether a duplicate ACK should trigger fast retransmit, whether a SACK block proves out-of-order delivery, or when the retransmission timer should be restarted or canceled. These require sender-side outstanding-range bookkeeping and protocol state that are absent here [3][4].

## Congestion windows: growth, threshold and loss

Slow start can expand `cwnd` rapidly as new bytes are acknowledged. When `cwnd` reaches a threshold, congestion avoidance grows more gradually. The classic algorithms in RFC 5681 operate **per eligible ACK**, in bytes, with rules for appropriate byte counting, delayed ACKs, loss and recovery. During timeout recovery, `ssthresh` is tied to **FlightSize** (not simply the previous `cwnd`), and `cwnd` is reduced to a loss window [2].

For a transparent hand-computable illustration, define **one successful RTT-level round** as a unit that acknowledges a full previous window. In this deliberately aggregated sketch, if `cwnd<ssthresh`, double the window up to the threshold. Otherwise add one MSS-sized unit. Upon an explicitly signaled timeout, choose `ssthresh=max(2,floor(FlightSize/2))` and reset `cwnd=1`. This is **not an ACK-by-ACK RFC 5681 implementation**; it does not reproduce all gradual growth or fast recovery behavior.

## Executable round-level window sketch

~~~python
class RoundCongestionSketch:
    """One RTT-level aggregate per success event; NOT packet-level TCP Reno."""
    def __init__(self, ssthresh=8):
        if type(ssthresh) is not int or ssthresh < 2:
            raise ValueError("threshold must be at least two segment units")
        self.cwnd = 1
        self.ssthresh = ssthresh

    def successful_round(self):
        if self.cwnd < self.ssthresh:
            self.cwnd = min(self.ssthresh, self.cwnd * 2)
        else:
            self.cwnd += 1
        return self.cwnd

    def timeout(self, flight):
        if type(flight) is not int or flight < 0:
            raise ValueError("nonnegative outstanding segment count required")
        self.ssthresh = max(flight // 2, 2)
        self.cwnd = 1
        return self.cwnd, self.ssthresh

    def available(self, rwnd, in_flight):
        if any(type(x) is not int or x < 0 for x in (rwnd, in_flight)):
            raise ValueError("nonnegative integer segment counts required")
        return max(0, min(self.cwnd, rwnd) - in_flight)

model = RoundCongestionSketch(8)
assert [model.successful_round() for _ in range(5)] == [2, 4, 8, 9, 10]
assert model.available(rwnd=6, in_flight=4) == 2
assert model.timeout(flight=9) == (1, 4)
assert [model.successful_round() for _ in range(4)] == [2, 4, 5, 6]
assert model.available(rwnd=3, in_flight=5) == 0
~~~

With initial threshold eight, five successful rounds yield windows 2, 4, 8, 9 and 10. A receiver advertising six segment units and four already in flight allows only two additional units. A timeout while nine units are outstanding sets threshold to four and congestion window to one; following successful rounds reach 2, 4, 5 and 6.

The window helper computes `max(0,min(cwnd,rwnd)-in_flight)`. This limits **newly sendable data** in the instantaneous toy state. If outstanding data exceed a newly reduced window, it returns zero instead of pretending that packets already sent can be unsent. The sketch does not subtract retransmitted bytes or model how ACKs remove in-flight state; that is caller-supplied for every calculation.

**Sketch invariant:** `cwnd>=1`, `ssthresh>=2` and both remain integral segment units. Each success strictly increases cwnd; each modeled timeout resets cwnd to one. The only upper bound is the number of successful rounds because the sketch has no configured congestion-cap or real path feedback. Test cases check these state transitions, but they cannot assert fairness or attainable throughput.

## RTO is not fast retransmit, and loss does not prove congestion

An RTO expiration indicates that an acknowledgment has not arrived within the timeout policy. Fast retransmit, selective acknowledgment and modern time-based detection such as RACK-TLP can infer loss from different observations without awaiting the full RTO [2][4]. The round sketch has only a **timeout event** and intentionally omits duplicate-ACK recovery.

Loss may be caused by congestion, corruption, wireless variation or other failures; classic algorithms often treat loss as a congestion signal under their design assumptions. Neither the timeout estimator nor our sketch discovers the cause of loss. Simulations using a fixed loss rate without queue dynamics cannot establish behavior on real links, and neither toy model should be presented as Linux's current congestion control.

Timeouts, slow start, congestion avoidance and `rwnd` interact, but they are different contracts: **timer estimation** determines when the sender suspects missing acknowledgment; **loss recovery** chooses what to resend; **congestion control** decides how much traffic to inject; **receiver flow control** limits buffer pressure. This separation is central to debugging intermittent latency.

## Failure budgets and performance implications

An excessive RTO can leave a connection idle after genuine loss, increasing tail latency. A too-small RTO can trigger spurious retransmissions and unnecessarily reduce congestion state. High RTT variance makes a fixed “always retry after 100 ms” rule especially fragile. Real connection behavior depends on connection establishment, RTT sampling eligibility, ACK policy, RTO backoff, application deadlines and other mechanisms [1].

An application request deadline is **not** the same as TCP RTO. A business request may time out while the transport continues, and a transport ACK does not prove that an application transaction committed. For distributed APIs, combine explicit deadlines, idempotency keys and durable operation status rather than treating a TCP timer as an end-to-end correctness proof.

For bandwidth estimation, `cwnd/RTT` gives only a rough upper-bound intuition under stable assumptions. Receiver windows, actual acknowledgments, queueing, packetization and competing flows matter. Our round-level model lacks these inputs and cannot produce measured throughput, goodput or production latency predictions.

## Exercises and verification

1. From RTT samples 0.4 and 0.6 seconds, derive SRTT, RTTVAR and RTO by hand in the correct update order. Compare with the runnable model.
2. Calculate what happens if the old SRTT is accidentally replaced before evaluating RTTVAR; explain the divergence.
3. Apply three timeout events in succession. Distinguish backed-off RTO from unchanged smoothed RTT and deviation.
4. Explain why an ACK for retransmitted data may be ambiguous; identify which extra timestamp information would be needed to disambiguate it.
5. With initial `cwnd=1`, `ssthresh=8`, trace five successful rounds. Then simulate timeout with FlightSize nine and calculate subsequent rounds.
6. Explain why a receiver window of three cannot be bypassed simply because the congestion window is six.
7. Compare a true RFC 5681 ACK-driven update with the aggregated one-RTT-per-event sketch, especially under delayed ACKs and partial acknowledgments.
8. Design an outstanding-range and retransmission-timer state machine, distinguishing fresh transmissions, retransmissions, cumulative ACK progress, duplicate ACKs and timer expiration.
9. Describe an application whose request deadline fires **before** TCP decides to retransmit. Specify how idempotency protects a retry from duplicate business effects.

**Continue:** the [TCP framing and cumulative ACK chapter](/en/topics/tcp-byte-stream-framing-flow-control/) defines the receiver and sender windows; [network protocols](/en/topics/network-protocols/) places them below TLS/HTTP. Packet traces, full congestion algorithms, TCP sequence wrap and security analysis remain separate subjects [1][2][3][4].
