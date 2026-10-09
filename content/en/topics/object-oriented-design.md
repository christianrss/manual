---
id: object-oriented-design
title: "Object-Oriented Design: Encapsulation, Composition and Polymorphism"
description: "Design object-oriented boundaries with encapsulation, composition, polymorphism, contracts and a tested order-pricing model."
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites: [testing-maintainability]
sources:
  - {title: "Microsoft Learn — Architectural principles", url: "https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles", kind: "official engineering guide"}
  - {title: "Python typing — Protocols and structural subtyping", url: "https://typing.python.org/en/latest/reference/protocols.html", kind: "language typing documentation"}
---
Object-oriented design organizes behavior around **objects with responsibilities and enforceable contracts**. A class is a blueprint for constructing objects; an object has identity, state and operations. Good design is not measured by the number of classes or UML boxes. It is measured by whether invariants survive legal operations, collaborators can be substituted safely and a change can be understood without editing unrelated components [1].

## From requirement to object responsibility

Consider an order containing product lines. Business rules state that each quantity must be positive, unit prices are nonnegative, totals are monetary values with two decimal places, and a submitted order cannot accept more lines. An order object should **own** its mutable line collection and decide whether adding an item is allowed. A controller or UI may request an operation, but should not bypass that object's transition rules by editing its list directly.

**Encapsulation** means the public interface limits what clients can do to internal state; it is not achieved merely by prefixing a Python attribute with an underscore. A caller could still mutate an exposed list reference. Defensive copies or immutable views are needed if the data crosses a trust boundary. A module boundary can be equally effective for a simple immutable value object; avoid inventing a class for every integer.

## Identity, value and invariants

Two different orders can have the same total and item list yet remain separate objects with different identifiers and histories. That illustrates **identity**. A money amount such as USD 12.50 is often better modeled as a **value**, where equality of amount and currency matters rather than allocation identity. Mixing identity and value semantics leads to faulty equality, caching and persistence assumptions.

Python floats represent binary approximations and are unsuitable for exact decimal business rounding. In the example, Decimal is constructed from strings, and discounts are rounded with an explicit rule. The contract applies one rule to the **order subtotal**; applying it independently to each line could produce different cents and must be specified separately.

## Build an order with a composed pricing policy

Composition makes an order refer to a pricing policy rather than inheriting from a specialized order class. A policy defines a behavior contract: calculate a valid total from a nonnegative subtotal. Python's typing.Protocol can express structural compatibility to a static type checker, but the example's runtime safety still comes from explicit validation and tests [2].

![An order composes a pricing policy and retains control of its lines.](/diagrams/oop-composition.svg)

~~~python
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

CENT = Decimal("0.01")

class PricePolicy(Protocol):
    def total(self, subtotal: Decimal) -> Decimal: ...

class PercentageDiscount:
    def __init__(self, fraction: Decimal):
        if not Decimal("0") <= fraction <= Decimal("1"):
            raise ValueError("fraction must be in [0,1]")
        self.fraction = fraction

    def total(self, subtotal: Decimal) -> Decimal:
        return (subtotal * (1 - self.fraction)).quantize(
            CENT, rounding=ROUND_HALF_UP)

class Order:
    def __init__(self, policy: PricePolicy):
        self._lines = []
        self._submitted = False
        self._policy = policy

    def add(self, unit_price: Decimal, quantity: int):
        if self._submitted or unit_price < 0 or quantity <= 0:
            raise ValueError("invalid order change")
        if unit_price != unit_price.quantize(CENT):
            raise ValueError("price needs two decimals")
        self._lines.append((unit_price, quantity))

    def submit(self) -> Decimal:
        if self._submitted or not self._lines:
            raise ValueError("cannot submit")
        subtotal = sum((p * n for p, n in self._lines), Decimal("0"))
        total = self._policy.total(subtotal)
        if not Decimal("0") <= total <= subtotal:
            raise ValueError("invalid pricing policy")
        self._submitted = True
        return total

order = Order(PercentageDiscount(Decimal("0.10")))
order.add(Decimal("12.50"), 2)
assert order.submit() == Decimal("22.50")
try:
    order.add(Decimal("3.00"), 1)
    assert False
except ValueError:
    pass
~~~

The example is intentionally **in-memory**. It does not guarantee uniqueness across processes, perform persistence, or authorize callers. The policy is assumed to be deterministic and without external side effects; if a policy invokes a remote pricing service, failures and idempotent retries must be designed separately.

## Polymorphism, interfaces and substitution

**Polymorphism** means different objects can satisfy the same behavioral contract. A second policy—for example a fixed amount capped at the subtotal—can be passed into Order without changing its method calls. Structural Protocol types describe callable shapes, while contracts also include semantic rules such as not returning a negative total. Passing a class that has method total but secretly charges a credit card would satisfy a shape and violate the intended behavior.

An **interface** is the collection of supported operations and expected behavior. Python may represent this using Protocol or an abstract base class, while Java or C# use other language features. Interface compatibility alone does not imply semantic substitutability. Use explicit preconditions, postconditions and tests when callers rely on guarantees such as monotonic nonnegative prices.

## Inheritance versus composition

Inheritance models an **is-a relationship** and can share implementation. It is appropriate when subtype instances honor the parent contract. A Square subclass that changes a Rectangle's independent width and height setters can break clients expecting those setters to be independent—a classic substitution trap. Composition models a **has-a/collaborates-with** relation and allows explicit replacement of one behavior without inheriting unrelated methods.

A single-level class hierarchy can be economical; composition is not a universal commandment. Prefer it when variation is behavior-oriented, when policies change independently, or when inheritance would expose protected internals. An excessive number of tiny strategies, however, can make a simple algorithm harder to understand.

## Object lifecycle and failure transitions

The order begins in a mutable **draft** state and becomes immutable after submit in this model. The invariant is _submitted implies no further modifications_. Checking that invariant only in a controller is insufficient because other callers may invoke the object from background jobs or tests. Check it inside each state-changing operation.

If submit triggers external persistence or payment, a local boolean cannot make a distributed transaction atomic. The domain model can express transitions; a repository and durable idempotency mechanism must enforce persistence and retry semantics. Do not mistake a well-encapsulated object for a distributed lock or database constraint.

## Performance and observability considerations

The current submit sums n lines, so its time is O(n) assuming Decimal arithmetic bounded by reasonable precision and the pricing policy is O(1). add is O(1) amortized for a Python list under its resizing model. The object stores O(n) line records. Recomputing subtotal may be safer than maintaining a mutable cached sum that every edit must update; choose based on measured workload.

| Design question | Useful approach | Wrong assumption |
| --- | --- | --- |
| Prevent post-submit edits | Guard every mutator | Private naming alone enforces it |
| Vary discount rules | Compose policy contract | Inheritance is always required |
| Represent money | Decimal with rounding policy | Binary float is exact decimal |
| Share order across processes | Durable repository and concurrency control | Python object enforces global uniqueness |
| Swap implementations | Check shape **and** behavior | A matching method name is sufficient |

## Exercises and verification

1. Explain how an Order object's identity differs from the value represented by a monetary subtotal.
2. Replace PercentageDiscount with a fixed discount that clamps its result to zero; test exact rounding.
3. Demonstrate that a caller cannot add a new line after a successful submit, including a second attempted submission.
4. Describe why exposing a mutable list of lines breaks the encapsulation contract, even if its attribute name begins with an underscore.
5. Identify the authority boundary where payment persistence, access control and duplicate submission require infrastructure beyond the in-memory class.

**Related chapters:** [Low-level design](/en/topics/low-level-design/) introduces state transitions; [testing and maintainability](/en/topics/testing-maintainability/) explains verifiable contracts [1].
