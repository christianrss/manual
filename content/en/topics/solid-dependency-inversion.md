---
id: solid-dependency-inversion
title: "SOLID, Dependency Inversion and Behavioral Contracts"
description: "Apply SRP, OCP, LSP, ISP and DIP pragmatically with Python protocols, stable boundaries and verified behavior tests."
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites: [object-oriented-design, low-level-design]
sources:
  - {title: "Microsoft Learn — Architectural principles", url: "https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles", kind: "official engineering guide"}
  - {title: "Python typing — Protocols and structural subtyping", url: "https://typing.python.org/en/latest/reference/protocols.html", kind: "language typing documentation"}
  - {title: "Google Engineering Practices — Code review", url: "https://google.github.io/eng-practices/review/", kind: "engineering guideline"}
---
SOLID names five object-design heuristics: single responsibility, open/closed, Liskov substitution, interface segregation and dependency inversion. They are **trade-off guides**, not mathematical axioms and not a mandate to maximize abstraction. Their practical goal is to keep changes localized, make behavioral promises explicit and support testing without requiring a full production system. An abstraction is useful when it protects a real policy or seam; it is harmful when it merely duplicates a single obvious call [1].

## Cohesion before classes

A component has **high cohesion** when its methods support one identifiable responsibility. The single-responsibility principle (SRP) is often summarized as having one reason to change. This refers to actors or policies causing changes, not literally one public method per class. A temperature alert rule can decide whether a reading exceeds a threshold; a network adapter can send the resulting message. Combining their internals in a class that reads hardware, compares numbers, sends email and persists audit rows makes unit testing dependent on unrelated infrastructure.

A cohesive service can still have several operations. Conversely, splitting each getter or single-line operation into a separate service creates indirection and coordination work. The practical check is whether a new delivery channel should force changes to the threshold rule; if not, those responsibilities probably deserve separation.

## OCP: extension with controlled variation

The **open/closed principle** favors extending a stable contract rather than editing central business logic for every new variation. A series of if/elif branches selecting SMTP, SMS and push delivery might be better expressed through a small MessageSender interface when new channels are a real requirement. However, building a plugin framework for an application that has one fixed email sender can be speculative complexity.

Do not mistake 'open for extension' for 'never modify an existing class'. Defects and changing requirements legitimately require edits; the goal is to minimize unrelated edits and preserve compatibility for clients. Use composition where possible, but require each added implementation to honor both input and output contracts [1].

## LSP: substitution is semantic, not nominal

The **Liskov substitution principle** means a subtype or implementation can replace another without violating the expectations of clients written against the contract. Method signatures alone are insufficient. Suppose an interface promises that read(key) returns None for a missing key. An implementation that instead throws an unexpected exception breaks clients even if a static type checker accepts its signature. Similarly, an alternative notifier that silently discards every message when it claims success violates an observable guarantee.

A classic geometry trap is making a mutable Square inherit from a Rectangle with independent set_width and set_height methods. Changing width on a square also changes height, invalidating client assumptions. The problem is the inherited **behavioral promise**, not that squares are unrelated to rectangles in mathematics.

## ISP: narrow operations for distinct clients

The **interface-segregation principle** suggests clients should depend only on operations they use. A read-only reporting screen should not be forced to implement write, delete, begin_transaction and migrate_schema merely to look up one record. Separate reading and writing contracts where clients have different needs or permissions. But avoid subdividing a compact interface into dozens of one-method types absent a substantive boundary.

A narrow contract makes test doubles smaller and limits access. It does **not** enforce authorization by itself: a service can implement a safe-looking read protocol yet still access unauthorized tenant data internally. Domain policy and identity context need separate checks.

## DIP: policy above infrastructure

**Dependency inversion** means high-level policy should depend on abstractions of the behavior it needs, not construct concrete infrastructure in its core implementation. In the following example, AlertRule knows only a message sender contract. The application wires a real sender or a collecting test double. Python Protocol provides structural checking, so an implementing class need not inherit from the protocol to satisfy it [2].

![The alert policy depends on a sender contract; adapters provide delivery implementations.](/diagrams/solid-boundaries.svg)

~~~python
from decimal import Decimal
from typing import Protocol

class MessageSender(Protocol):
    def send(self, destination: str, message: str) -> None: ...

class AlertRule:
    def __init__(self, sender: MessageSender, threshold: Decimal):
        if threshold < 0:
            raise ValueError("threshold must be nonnegative")
        self._sender = sender
        self._threshold = threshold

    def check(self, destination: str, value: Decimal) -> bool:
        if not destination:
            raise ValueError("destination required")
        if value > self._threshold:
            self._sender.send(destination, f"above {self._threshold}")
            return True
        return False

class CollectingSender:
    def __init__(self):
        self.messages = []
    def send(self, destination: str, message: str) -> None:
        self.messages.append((destination, message))

fake = CollectingSender()
rule = AlertRule(fake, Decimal("30"))
assert not rule.check("ops", Decimal("30"))
assert rule.check("ops", Decimal("30.01"))
assert fake.messages == [("ops", "above 30")]
try:
    AlertRule(fake, Decimal("-1"))
    assert False
except ValueError:
    pass
~~~

The example is **synchronous and local**. It does not guarantee delivery, retries, rate limiting or durability. If send raises an exception, check propagates it, and the caller must decide how to recover. Real integrations also need a distinction between a notification intent and confirmed delivery: no object-interface pattern can make an external network operation atomic.

## Composition root and control of dependencies

The **composition root** is the application boundary that creates objects and wires dependencies. Application code may instantiate SMTP adapters, file stores or HTTP clients there, while the domain policy takes an interface. This keeps environment configuration out of core rules and lets tests use a deterministic double.

Dependency injection is simply one way to supply dependencies. It does not require a container framework or service locator. Passing a collaborator through a constructor, as above, is often sufficient. A service locator hidden inside the domain can make dependencies harder to discover and test, despite claiming to support inversion.

## Test seams and contract tests

A fake sender tests that the policy invokes the right action when the threshold is exceeded. It cannot prove that SMTP, HTTP, authentication or remote quotas work. **Adapter contract tests** should verify each real sender obeys the expected semantics; integration tests are needed for network behavior. The domain policy can be verified with exact boundary values such as 30, 30.01 and negative threshold rejection.

Good tests also seek **substitutability failures**: an implementation that sends twice for one call or mutates destination may violate the declared contract. Test observable outputs and error behavior rather than specific private method names, which makes refactoring safer [3].

## Costs, failure modes and overengineering

| Principle | Targeted change | Failure when overused |
| --- | --- | --- |
| SRP | Separate unrelated change reasons | Class-per-line fragmentation |
| OCP | Add a genuine variation | Unnecessary plugin framework |
| LSP | Preserve behavioral contracts | Overly weak interfaces hiding failures |
| ISP | Narrow each client's dependency | Too many tiny protocols |
| DIP | Isolate infrastructure from policy | Service locator / abstract-everything design |

Every new interface adds vocabulary and maintenance cost. If only one implementation exists and no test isolation or policy boundary requires abstraction, a clear direct function might be better. Conversely, direct infrastructure calls embedded inside many business rules make fault injection, migration and review difficult. Measure designs by change scenarios, not acronym compliance.

## Exercises and verification

1. Identify which parts of an alert service must change if a new delivery channel is added without changing the threshold rule.
2. Explain why a sender that returns successfully while silently discarding messages may violate LSP.
3. Add a second collecting sender with a different internal representation but the same observable contract.
4. Test exactly-on-threshold, just-over-threshold and invalid-destination cases without network access.
5. Describe why sending a message and committing a database transaction require more than dependency inversion to provide reliable behavior.

**Related chapters:** [Object-oriented design](/en/topics/object-oriented-design/) introduces composition and polymorphism; [low-level design](/en/topics/low-level-design/) focuses on transitions and boundaries; [testing](/en/topics/testing-maintainability/) develops contract thinking [1][3].
