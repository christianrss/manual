---
id: system-design-ticket-reservations
title: "System design: ticket holds, concurrent booking and expiry"
description: "Design seat holds with atomic booking, stable idempotency keys, expiration, isolation strategies and tested failure scenarios."
category: system-design
difficulty: advanced
updated: 2026-10-12
prerequisites: [system-design-process, transactional-indexing-isolation, api-reliability, domain-modeling-aggregates-invariants]
sources:
  - {title: "PostgreSQL — Transaction Isolation", url: "https://www.postgresql.org/docs/current/transaction-iso.html", kind: "official database documentation"}
  - {title: "PostgreSQL — Data Consistency Checks at the Application Level", url: "https://www.postgresql.org/docs/current/applevel-consistency.html", kind: "official database documentation"}
  - {title: "AWS Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
---
A ticket-booking service appears to be an ordinary create-and-update application until many buyers attempt to reserve **one last seat**. The core design problem is not drawing load balancers; it is assigning a single authority that decides which reservation may succeed under concurrent requests, timeouts and expiration. This chapter treats system design as a combination of requirements, measurable capacity, state transitions, database isolation and recovery. The behavior is hypothetical and does not describe an existing ticket company.

## Requirements and strict invariants

A buyer views a seat map, requests a temporary hold, confirms a purchase and consults the reservation. Assume numbered seats rather than general-admission capacity. The seat map may be several seconds stale because it is advisory; the hold and final sale require authoritative decisions. The principal invariant is that **at most one confirmed sale exists for each (event, seat)**. At most one unexpired hold should be accepted for a seat at any instant by the booking authority.

A second invariant concerns time: a temporary hold has a deadline, after which confirmation must be rejected. A third concerns retries: the same operation key and identical request must refer to the same logical reservation, while reuse of that key for a different seat, owner or duration must fail. Return a reservation ID and status endpoint so a caller can distinguish hold accepted, expired and confirmed. Repeating a successful old request need not extend its expiration; doing so would allow a client to monopolize seats simply by retrying [3].

## Workload assumptions and sizing

Suppose a hypothetical concert system receives two million seat-map reads and 50,000 hold attempts per day, with a peak-to-average ratio of 20. The average read rate is about 23.15 requests/s and the assumed peak is 463 requests/s. For holds, the average is about 0.579/s and the assumed peak is about 11.57/s. These estimates do not prove that the system needs a specific number of machines. Benchmark database row contention for **popular seats**, not merely aggregate requests/s.

The same seat may attract hundreds of attempted holds during a launch, even when total hold throughput is small. A high cache hit ratio on the seat map does not solve this hotspot: cached availability is an estimate, never proof of a successful reservation. Specify hypothetical SLOs separately for read latency, authoritative hold decisions and payment completion, because a low p95 on seat-map reads tells little about lock wait or payment failures.

## Define the API and state transitions

A proposed interface is POST /events/{eventId}/holds with seat ID and idempotency key, GET /holds/{holdId}, and POST /holds/{holdId}/confirm. Invalid seats fail validation, attempts on sold seats fail with an explicit unavailable result, and reused operation keys with conflicting payload return a conflict. Set an upper bound on hold TTL and require the booking service to control time. Client device clocks are not authoritative.

A finite-state model begins with available → held → confirmed. Held → expired is permitted when the deadline passes, and expired → held is **not** a revival of the old ID: a new operation creates a new reservation. Confirmation is terminal in this simplified example; cancellation, refunds, payment settlement, chargebacks and seat transfers are separate business workflows. Track the meaning of each response: accepting a hold is not the same as charging a card.

## A reproducible local model

The code uses integer logical time supplied by the test to exercise expiry boundaries without real sleeps. Production implementations must use a trusted server clock and an atomic database transaction. The model executes calls serially, so it illustrates **contract semantics**, not safety under threads or multiple server processes. Its records are kept in memory; durable deduplication is a distinct requirement.

~~~python
class ReservationModel:
    def __init__(self, seats):
        if not seats or len(set(seats)) != len(seats):
            raise ValueError("invalid seat inventory")
        self.seats = frozenset(seats)
        self.active = {}       # seat -> reservation key
        self.sold = {}         # seat -> confirmed key
        self.records = {}      # durable in a real implementation

    def hold(self, seat, owner, key, now, ttl):
        if (seat not in self.seats or not isinstance(owner, str) or not owner
                or not isinstance(key, str) or not key
                or type(now) is not int or now < 0
                or type(ttl) is not int or not 1 <= ttl <= 900):
            raise ValueError("invalid request")
        fingerprint = (seat, owner, ttl)
        if key in self.records:
            if self.records[key]["request"] != fingerprint:
                raise ValueError("idempotency conflict")
            return key
        if seat in self.sold:
            raise ValueError("seat already sold")
        prior = self.active.get(seat)
        if prior is not None:
            previous = self.records[prior]
            if now < previous["until"]:
                raise ValueError("seat is held")
            previous["state"] = "expired"
            del self.active[seat]
        self.records[key] = {"request": fingerprint, "seat": seat,
                             "until": now + ttl, "state": "held"}
        self.active[seat] = key
        return key

    def confirm(self, key, now):
        if key not in self.records or type(now) is not int or now < 0:
            raise ValueError("unknown key or time")
        record = self.records[key]
        if record["state"] == "confirmed":
            return "confirmed"
        if record["state"] != "held":
            raise ValueError("not an active hold")
        seat = record["seat"]
        if now >= record["until"]:
            record["state"] = "expired"
            if self.active.get(seat) == key:
                del self.active[seat]
            raise ValueError("hold expired")
        if self.active.get(seat) != key or seat in self.sold:
            raise ValueError("conflicting hold")
        del self.active[seat]
        self.sold[seat] = key
        record["state"] = "confirmed"
        return "confirmed"

    def status(self, key, now):
        if key not in self.records or type(now) is not int or now < 0:
            raise ValueError("unknown key or time")
        record = self.records[key]
        if record["state"] == "held" and now >= record["until"]:
            return "expired"
        return record["state"]

model = ReservationModel(["A1", "A2"])
assert model.hold("A1", "alice", "op-1", 100, 30) == "op-1"
assert model.hold("A1", "alice", "op-1", 120, 30) == "op-1"
try:
    model.hold("A1", "bob", "op-2", 120, 30)
except ValueError:
    pass
else:
    raise AssertionError("double hold accepted")
assert model.confirm("op-1", 129) == "confirmed"
assert model.confirm("op-1", 200) == "confirmed"
assert model.status("op-1", 500) == "confirmed"
try:
    model.hold("A1", "bob", "op-3", 500, 30)
except ValueError:
    pass
else:
    raise AssertionError("confirmed seat resold")
assert model.hold("A2", "bob", "op-4", 100, 30) == "op-4"
assert model.status("op-4", 130) == "expired"
assert model.hold("A2", "cara", "op-5", 130, 30) == "op-5"
assert model.status("op-4", 130) == "expired"
assert model.confirm("op-5", 131) == "confirmed"
~~~

The tests cover conflicting holds, stable replay, repeat confirmation, expiry at the exact deadline, allocation after expiry and the impossibility of selling an already confirmed seat. Replay returns the original key even if the old hold later expired; callers must use the status endpoint rather than treating the replayed key as renewed availability. Retaining operation history indefinitely is not feasible at scale, so production systems need an explicit idempotency retention policy and a post-retention retry contract.

## Authoritative database transaction and concurrency

Model seat identity as (event_id, seat_id). A primary seat row can contain the confirmed reservation ID, current hold ID and expiration. Acquire authority through a conditional database mutation that succeeds only if no sale exists and no unexpired hold exists. The conditional predicate and update must be evaluated in **one atomic transaction**. Separate SELECT availability followed by unconditional UPDATE is unsafe because two workers can observe the same old state.

When confirmation arrives, atomically verify the hold ID, expiration and sold state, then transition the seat to confirmed. PostgreSQL transaction isolation defines which phenomena are prevented and when serialization failures require retries [1]. Explicit locks can protect selected rows, but a lock is not a substitute for updating the authoritative state and checking the predicate [2]. Add a unique constraint protecting the one-sale-per-seat invariant; test the actual database plan and concurrency behavior instead of relying on a Python model.

## Expiry and payment introduce a second authority

A hold TTL is not a guarantee that a payment provider will complete before its deadline. If a payment request times out after a provider captured money, blindly retrying with a new provider operation key can cause double charges. Keep durable payment intent and a stable key, reconcile uncertain outcomes, and define compensation or refund operations. A ticket should not become confirmed merely because a browser showed a payment success screen.

An expiry worker may clean old records for efficiency, but correctness must not depend on the worker running at the exact deadline. The authoritative hold predicate checks time itself. If an old timeout task arrives after a newer reservation acquired the seat, it must identify the **original hold ID** and must not clear the successor. TTL jobs, duplicate delivery and delayed queues require fencing by identity rather than trusting scheduling order.

## Partitioning, hotspots and availability trade-offs

Partition by event ID or a range of seat IDs only after measuring contention and query behavior. Reads can be cached by event; writes for an individual seat must converge on one authoritative decision. A replicated follower that lags behind may display a seat as free after it is sold. That is tolerable for an advisory map only if checkout always revalidates at the authority. Sending competing writes to independent primaries without conflict resolution can oversell during partitions.

The strongest practical design for an individual seat often favors consistency over accepting every request during a database outage: reject or delay holds rather than issue two apparently confirmed promises. Document the availability impact and error budget explicitly. Global multi-region active-active reservations require additional consensus or partition ownership rules, not merely more application replicas.

## Testing, complexity and counterexamples

For s seats and h retained reservation histories, the local model stores O(s + h) state. Dictionary lookups and updates are expected O(1) per operation under usual hashing assumptions, **not** guaranteed worst-case O(1) and not a bound on database latency. Real costs include lock contention, indexes, logs, replication, retries and payment integration.

Test a burst of 100 simultaneous attempts for the same last seat in the actual database, with unique operation keys. Exactly one hold should be accepted while unexpired. Exercise timeout after commit, retry after response loss, held-at-deadline confirmation, two confirmations, expired cleanup arriving late, failover and recovery from persisted state. A test that only calls local methods sequentially cannot establish cross-process isolation or real-world reliability.

## Exercises and verification

1. Derive mean and peak rates from the stated volumes. Explain why total throughput hides contention on one seat.
2. In the local model, expire hold X, create hold Y for the same seat and then replay X. Explain why the replay cannot extend X or clear Y.
3. Sketch an atomic SQL update for hold acquisition and confirmation. Identify its row lock, uniqueness constraint and expected affected-row count.
4. Describe a crash after a payment provider commits but before the ticket service receives a response. Distinguish refund, reconciliation and duplicate charging risks.
5. Design tests with a real database and competing connections. Specify what evidence is missing from the in-memory example.

Related: [transaction isolation](/en/topics/transactional-indexing-isolation/), [API reliability](/en/topics/api-reliability/), [domain invariants](/en/topics/domain-modeling-aggregates-invariants/) and [system design method](/en/topics/system-design-process/).