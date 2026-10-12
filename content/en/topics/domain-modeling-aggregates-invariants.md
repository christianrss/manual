---
id: domain-modeling-aggregates-invariants
title: "Domain modeling: entities, value objects and aggregate invariants"
description: "Distinguish identity from immutable values, select aggregate boundaries and enforce order invariants with executable contracts."
category: engineering
difficulty: intermediate
updated: 2026-10-12
prerequisites: [object-oriented-design, low-level-design, architecture-dependency-boundaries]
sources:
  - {title: "Microsoft Learn — Tactical DDD", url: "https://learn.microsoft.com/en-us/azure/architecture/microservices/model/tactical-ddd", kind: "official architecture guidance"}
  - {title: "Microsoft Learn — Domain model design", url: "https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/ddd-oriented-microservice", kind: "official architecture guidance"}
  - {title: "Python — decimal module", url: "https://docs.python.org/3/library/decimal.html", kind: "language documentation"}
---
Domain modeling translates business rules into **identities, values, state transitions and consistency boundaries**. It is not the act of naming database tables or generating classes from an ORM. A useful model makes invalid operations rejectable and explains which authority must preserve each invariant when multiple requests race. Tactical domain-driven design (DDD) distinguishes entities, value objects and aggregates so that developers can reason about these responsibilities explicitly [1].

## Identity versus equality

An **entity** is tracked by stable identity across time: order O-41 remains the same order when its status changes. Two orders with the same contents are not interchangeable. A **value object** is compared by its attributes rather than a persistent identifier: the amount 12.50 in a specified currency is a value. Values are useful for enforcing representation and arithmetic contracts near their construction. A frozen data class does not automatically make all nested fields immutable, so the example intentionally stores only immutable strings and Decimal numbers [1][3].

A customer address may be a value within an order, even if a separate address-book record has its own entity identity. Choosing entity or value depends on **how the domain uses it**, not on whether the object has columns in a database. Avoid treating every row as an aggregate root. The root defines the permitted entry points for mutations and is responsible for keeping its local invariants true.

## Define the invariants before a class diagram

Consider a simplified order: it has a stable ID, one currency, a collection of distinct SKUs, quantities that are strictly positive integers and prices with no more than two decimal places. The order is editable while open; once placed, lines cannot change. A placed order must contain at least one line. Its total is the exact sum of quantity times unit price. Discounts, tax, returns and payment capture are excluded, so this is deliberately not an accounting or commerce production model.

These rules produce testable postconditions. An invalid add must not change the line collection. A repeated SKU must fail rather than silently overwrite a price. A total must never mix currencies, because adding 10 USD and 10 EUR without conversion has no defined monetary meaning. For nonnegative finite Decimal amounts, total is finite and nonnegative under ordinary bounded input sizes; production systems still need precision limits and an explicit rounding policy [3].

## Implement an immutable value and an aggregate root

The following Python contract checks incoming types and preserves values across caller operations. The frozen Money object rejects imprecise scales instead of silently rounding. Order keeps its mutable state private by convention and exposes immutable tuples of lines. The tuple snapshot guarantees callers cannot append directly, although Python underscores are not a security boundary.

~~~python
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self):
        if (type(self.amount) is not Decimal or not self.amount.is_finite()
                or self.amount < 0 or self.amount.as_tuple().exponent < -2):
            raise ValueError("invalid monetary amount")
        if (not isinstance(self.currency, str) or len(self.currency) != 3
                or not self.currency.isascii() or not self.currency.isalpha()
                or self.currency != self.currency.upper()):
            raise ValueError("invalid currency")

@dataclass(frozen=True)
class OrderLine:
    sku: str
    quantity: int
    unit_price: Money

    def __post_init__(self):
        if not isinstance(self.sku, str) or not self.sku.strip():
            raise ValueError("missing sku")
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError("invalid quantity")
        if not isinstance(self.unit_price, Money):
            raise ValueError("invalid price")

class Order:
    def __init__(self, order_id, currency):
        Money(Decimal("0"), currency)
        if not isinstance(order_id, str) or not order_id.strip():
            raise ValueError("missing order id")
        self._id, self._currency = order_id, currency
        self._lines = ()
        self._status = "open"

    @property
    def lines(self):
        return self._lines

    @property
    def status(self):
        return self._status

    def add(self, line):
        if self._status != "open":
            raise ValueError("order is closed")
        if not isinstance(line, OrderLine) or line.unit_price.currency != self._currency:
            raise ValueError("incompatible line")
        if any(previous.sku == line.sku for previous in self._lines):
            raise ValueError("duplicate sku")
        self._lines = self._lines + (line,)

    def total(self):
        return Money(sum((line.unit_price.amount * line.quantity
                          for line in self._lines), Decimal("0")), self._currency)

    def place(self):
        if self._status != "open" or not self._lines:
            raise ValueError("cannot place order")
        self._status = "placed"
        return self.total()

order = Order("O-41", "USD")
first = OrderLine("BOOK", 2, Money(Decimal("12.50"), "USD"))
order.add(first)
snapshot = order.lines
order.add(OrderLine("PEN", 1, Money(Decimal("1.25"), "USD")))
assert len(snapshot) == 1 and len(order.lines) == 2
assert order.total() == Money(Decimal("26.25"), "USD")
assert order.place() == Money(Decimal("26.25"), "USD")
try:
    order.add(first)
except ValueError:
    pass
else:
    raise AssertionError("placed order was modified")
try:
    Money(Decimal("1.234"), "USD")
except ValueError:
    pass
else:
    raise AssertionError("excessive scale accepted")
~~~

At most n stored lines are scanned by add, so it takes O(n) time; copying the tuple also takes O(n) references per successful addition. Building n lines by repeated appends costs O(n²) aggregate work and O(n) retained line storage. This prioritizes snapshot safety and a small example, not throughput. A dictionary keyed by SKU can reduce expected duplicate checks, but its mutability and iteration order require a clear contract. Computing total scans n lines, taking O(n) arithmetic operations, with Decimal operand precision affecting actual CPU cost.

## Derive an aggregate boundary rather than an object graph

An aggregate is a transactional consistency boundary around a root and its owned entities or values [1]. Order and its lines form one possible aggregate because the root can enforce “placed orders have validated lines and a stable total” within one local transition. Stock availability, however, is not an attribute that this Order can safely promise from memory: other orders compete for the same units. Placing an order does **not** make a stock reservation succeed. Inventory requires its own authoritative transaction or reservation protocol.

A common modeling error is a giant aggregate containing order, customer, stock, payments and shipment. If all entities require one atomic lock, unrelated operations contend, availability couples to every dependency and cross-service consistency becomes impractical. Use the smallest boundary that encloses the invariants actually requiring immediate consistency, not every object reachable by an ORM relation [1][2].

## Separate local validity from concurrent correctness

The local root prevents duplicate SKUs in its tuple, but two processes editing copies of order O-41 can both accept an update and later overwrite each other. Persisted aggregates usually require an expected-version conditional update, row locking or an isolation strategy supported by the database. The version must be checked atomically with the write. A Python property, frozen value object or “private” field cannot guarantee isolation across workers.

Authorization is another independent concern. A client may pass a valid order ID and valid OrderLine but still lack permission to update that order. The application boundary should authenticate the actor, load the authorized aggregate and run an atomic transition. Domain invariants ensure a transition is meaningful; they do not decide who is entitled to request it.

## Failure modes and when DDD is too expensive

Domain objects are not mandatory for trivial CRUD with little behavior. A simple validated SQL row and clear service function can be more maintainable than a deep inheritance hierarchy. Conversely, storing a complex workflow as freely writable columns lets invalid state combinations enter the database. DDD terminology becomes harmful when it hides where actual transactions occur, duplicates repository methods or treats delayed messages as synchronous operations.

Money illustrates another boundary: Decimal avoids binary floating-point surprises for decimal arithmetic, but it does not define exchange rates, taxation rules, legal rounding or payment-settlement accuracy [3]. Preventing negative amount here is a domain decision that would be wrong for a signed ledger entry or refund adjustment. A robust model makes those assumptions visible rather than generalizing them to unrelated domains.

## Exercises and verification

1. Enumerate invalid OrderLine inputs (boolean quantity, duplicate SKU, currency mismatch, missing identifier and three-decimal price). For each, check that the aggregate's previous state remains unchanged.
2. Derive the O(n²) total cost of n immutable-tuple appends. Implement an alternative keyed collection and explain the new mutation and iteration contracts.
3. Add an explicit order version and an expected-version command. Then explain why an in-memory comparison alone cannot stop a lost update between two servers.
4. Draw separate boundaries for order, inventory and payment. Identify an invariant that can be enforced within one aggregate and another requiring coordination across authorities.
5. Explain why a valid, immutable Money object does not prove correctness of refunds or tax calculations.

Continue with [architecture boundaries](/en/topics/architecture-dependency-boundaries/), [SOLID](/en/topics/solid-dependency-inversion/) and [transaction isolation](/en/topics/transactional-indexing-isolation/).