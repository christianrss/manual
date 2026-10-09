---
id: low-level-design
title: "Low-Level Design: Contracts, State Machines and Dependency Boundaries"
description: "Design maintainable components from invariants, state transitions, interfaces and dependency direction, with a tested reservation model."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [testing-maintainability, database-consistency]
sources:
  - {title: "Microsoft Learn — Architectural principles", url: "https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles", kind: "official engineering guide"}
  - {title: "Google Engineering Practices — The Standard of Code Review", url: "https://google.github.io/eng-practices/review/reviewer/standard.html", kind: "engineering guideline"}
---
**Low-Level Design (LLD)** translates product rules into components, interfaces, data structures and permitted state transitions. It is neither a contest to use as many design patterns as possible nor simply drawing a UML class diagram. A design is useful if another engineer can derive its contracts, implement behavior and change it without violating the system's critical invariants [1][2].

## Turn requirements into invariants first

Consider a reservation service. A booking may be **pending**, **confirmed** or **cancelled**. A confirmed booking must not return to pending. Cancellation is terminal under this example's business contract. The identifier never changes after creation. Valid transitions are pending→confirmed, pending→cancelled and confirmed→cancelled. There is no transition cancelled→confirmed; rebooking creates a new reservation. Another business could choose different rules, but those must be explicit before deciding class names.

Distinguish **invariant** ('a cancelled reservation cannot be confirmed') from **workflow** ('the API checks inventory, then reserves'). A class can enforce local state transitions, but a shared seat's global uniqueness across processes belongs in a transactional database or another authoritative coordination mechanism. A local object cannot lock a distributed seat simply because its method is called reserve().

## Model the state machine explicitly

Use a diagram before implementation so reviewers can challenge missing transitions. A transition requires a starting state, an event, preconditions, a resulting state and an error policy when invalid. Decide whether retrying cancellation is a no-op (idempotent) or produces an error; both policies are possible, but ambiguity makes clients unreliable.

![Reservation states and permitted transitions.](/diagrams/reservation-state-machine.svg)

## A reproducible implementation with narrow responsibilities

~~~python
from enum import Enum, auto

class Status(Enum):
    PENDING = auto()
    CONFIRMED = auto()
    CANCELLED = auto()

class Reservation:
    def __init__(self, identifier):
        if not identifier:
            raise ValueError("identifier is required")
        self._id = identifier
        self._status = Status.PENDING

    @property
    def status(self):
        return self._status

    @property
    def identifier(self):
        return self._id

    def confirm(self):
        if self._status != Status.PENDING:
            raise ValueError("only pending reservations can be confirmed")
        self._status = Status.CONFIRMED

    def cancel(self):
        if self._status == Status.CANCELLED:
            return False  # idempotent cancellation
        self._status = Status.CANCELLED
        return True

booking = Reservation("R-1")
assert booking.status == Status.PENDING
booking.confirm()
assert booking.status == Status.CONFIRMED
assert booking.cancel()
assert not booking.cancel()
try:
    booking.confirm()
    assert False
except ValueError:
    pass
~~~

The example is deliberately in-memory. It handles one object, no concurrent database transaction, no ownership check and no durable events. A production implementation would need persistence and authorization. Python's underscore naming convention discourages direct mutation but is **not a hard security boundary**. Encapsulation helps ordinary collaborators follow a contract; it does not replace data-store constraints.

## Separate domain, application and infrastructure

The domain object owns local rules, not HTTP parsing or SQL connection pooling. An **application service** orchestrates a use case: check authenticated actor, call a repository, begin the necessary transaction, invoke domain behavior and persist results. A **repository interface** expresses the contract of loading and saving a reservation; a database adapter implements it. A web controller maps HTTP inputs/outputs to an application service and should not silently reimplement business invariants [1].

The dependency direction matters. A domain model that imports a concrete SQL client is coupled to persistence choices. A service that depends on an interface it controls can use real database adapters in production and a lightweight fake in narrowly scoped tests. That does not mean every single function needs an interface; extra abstraction should correspond to a real seam of variation or testing.

## Decide when a pattern adds value

| Design problem | Reasonable tool | Failure when overused |
| --- | --- | --- |
| Several interchangeable payment providers | Strategy via small provider interface | One interface per trivial helper |
| Construct complex valid object | Builder or named constructor | Boilerplate for two arguments |
| Adapt legacy API response | Adapter at integration boundary | Copies without meaningful semantic change |
| Notify independent observers | Events with clear delivery contract | Hidden side effects and ordering ambiguity |
| Change behavior by business state | Explicit transition table/state machine | Dozens of state classes with no benefit |

SOLID principles provide heuristics, not a proof of correctness. The single responsibility principle is about coherent reasons to change; it does not mean a separate class for every line of code. Dependency inversion protects stable business logic from changeable infrastructure, but adding indirection without an actual boundary can make tracing behavior harder [1].

## Failure modes: concurrency, persistence and ownership

Two API workers may load the same pending reservation, both decide it can be confirmed and overwrite each other. If confirming has external effects, each might also emit a duplicate notification. Add transactional locking or optimistic version checks to the authoritative row, and coordinate external notifications through an outbox or another deliberate protocol. An ORM entity's methods do not automatically solve race conditions, retries or the dual-write problem.

Authorization should be checked against the loaded reservation's tenant and owner, not a caller-supplied tenant identifier. A cancelled reservation existing in memory is not proof that cancellation was durably committed. After a crash, reload must reconstruct the same permitted state; test serialization/mapping and data migrations accordingly.

## Choose tests that prove contracts

Unit tests should enumerate all state/event pairs, not just a happy path: confirm pending succeeds; confirm confirmed fails; confirm cancelled fails; cancel pending succeeds; cancel confirmed succeeds; cancel cancelled returns false. Test identifier immutability through the public interface, and reject empty IDs. Integration tests must verify uniqueness, optimistic-concurrency conflict handling, and atomic event persistence when relevant.

A design review should ask what observable behavior changes if a provider is replaced, if persistence fails halfway through a workflow, and if a call is repeated with the same idempotency key. Google engineering guidelines emphasize improving the overall health of the code rather than requiring theoretical perfection before every change [2].

## Exercises and verification

1. Build a transition matrix with current state as rows and confirm/cancel as columns. Compare each entry with the executable code.
2. Add an expiration transition and explain whether expired should be terminal, whether it can be revived, and who authoritatively decides the time.
3. Draft a repository interface and a transaction boundary for confirming a booking exactly once **within one database**.
4. Explain why a class diagram with ReservationRepository does not prove that distributed cancellation is atomic.
5. Compare a single service class containing HTTP, SQL and business rules with separated domain/application/adapters. Identify the **specific** change that is easier in the latter, and cases where the former remains acceptable.
