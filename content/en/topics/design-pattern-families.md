---
id: design-pattern-families
title: "Design Pattern Families: Builder, Facade and Observer"
description: "Derive creational, structural and behavioral design choices using tested Builder, Facade and Observer examples and explicit failure contracts."
category: engineering
difficulty: intermediate
updated: 2026-10-10
prerequisites: [clean-code-cohesion-coupling, refactoring-design-patterns]
sources:
  - {title: "Refactoring.Guru — Design patterns catalog", url: "https://refactoring.guru/design-patterns/catalog", kind: "technical pattern catalog"}
  - {title: "Refactoring.Guru — Builder", url: "https://refactoring.guru/design-patterns/builder", kind: "technical pattern reference"}
  - {title: "Refactoring.Guru — Facade", url: "https://refactoring.guru/design-patterns/facade", kind: "technical pattern reference"}
  - {title: "Refactoring.Guru — Observer", url: "https://refactoring.guru/design-patterns/observer", kind: "technical pattern reference"}
---
A design pattern is a reusable response to a **recurring pressure on responsibilities**, not a certificate of good architecture. First state the change requirement, public behavior, failure semantics and simpler alternative; only then name the pattern. The established catalog distinguishes **creational** patterns (construction), **structural** patterns (composition of collaborating components), and **behavioral** patterns (algorithms, events and interactions) [1]. These categories are not runtime guarantees, and multiple patterns can coexist.

The existing [Strategy, Adapter and Decorator](/en/topics/refactoring-design-patterns/) chapter already implements algorithm selection, interface translation and behavior wrapping. We will add one **worked and executable** example from each family: Builder, Facade and Observer. A catalog is useful as vocabulary; engineering competence requires recognizing when **not** to use a pattern.

## Choose from an actual change scenario

| Change pressure | Candidate | Simpler option | Principal cost |
| --- | --- | --- | --- |
| Product assembled in optional validated steps | Builder | Constructor with named arguments | Mutable construction state |
| Client must coordinate multiple subsystem calls | Facade | Small application function | Indirection and hidden failures |
| Listeners independently join or leave | Observer | Direct callback | Exceptions, ordering and delivery |
| Algorithms vary behind one promise | Strategy | Condition on small fixed set | Unnecessary hierarchy |
| Third-party protocol incompatible | Adapter | Conversion function | Semantic mismatches |
| Cross-cutting behavior surrounds an operation | Decorator | Explicit wrapper | Ordering and side effects |

The right choice depends on independently changing actors and required contracts. A two-line calculation is not automatically better after introducing a factory, a strategy and a mediator. Conversely, directly coupling business logic to a vendor SDK makes business decisions harder to test [1].

## Creational pattern: Builder for a validated report

A report must have a nonblank title, at least one section and **unique section headings**. Sections are added in steps, but a completed report must remain unchanged when the builder is later reused. This is a meaningful Builder scenario: the construction sequence and validation deserve one owner [2]. If all fields were known and required at once, a simple constructor could be preferable.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Report:
    title: str
    sections: tuple[tuple[str, str], ...]

class ReportBuilder:
    def __init__(self, title):
        if not isinstance(title, str) or not title.strip() or title.strip() != title:
            raise ValueError("invalid report title")
        self._title = title
        self._sections = []
        self._headings = set()

    def add(self, heading, body):
        if (not isinstance(heading, str) or not heading.strip()
                or heading.strip() != heading or not isinstance(body, str)
                or not body.strip()):
            raise ValueError("invalid section")
        if heading in self._headings:
            raise ValueError("duplicate heading")
        self._headings.add(heading)
        self._sections.append((heading, body))
        return self

    def build(self):
        if not self._sections:
            raise ValueError("at least one section required")
        return Report(self._title, tuple(self._sections))

builder = ReportBuilder("Operations").add("Risks", "Low")
first = builder.build()
builder.add("Actions", "Review")
second = builder.build()
assert first.sections == (("Risks", "Low"),)
assert len(second.sections) == 2
try:
    builder.add("Risks", "Repeated")
except ValueError:
    pass
else:
    raise AssertionError("duplicate was accepted")
```

**Invariant:** after every successful add, `_headings` equals the headings in `_sections`. Because validation runs before either mutation, a failed add does not change state. Converting the list to a tuple means earlier products are not changed by later builder mutations; `Report` contains only immutable strings and tuples. With bounded string size and expected constant-time set membership, each add is expected `O(1)`; building a `k`-section report copies `O(k)` references and uses `O(k)` additional memory. This builder is *not* thread safe or a persistence layer.

**Builder versus Factory:** Builder controls **steps of constructing** one product. A factory chooses which product or implementation to instantiate. In classic Factory Method, subclasses override the creation hook; a dictionary of constructors in Python is merely a simple factory, not necessarily the classic pattern. Do not call every helper that returns an object a Builder or Factory Method [1][2].

## Structural pattern: Facade over separate data sources

Suppose a screen needs both a product label and its stock quantity. Without a boundary, every consumer must know the names of both collaborators, missing-value policies and ordering of calls. A Facade exposes one narrow entry point; unlike Adapter, its purpose is **simplification of a subsystem**, not mapping one incompatible method into another [3].

```python
class Catalog:
    def __init__(self, names):
        self.names = dict(names)

    def label(self, sku):
        return self.names.get(sku)

class StockBook:
    def __init__(self, amounts):
        self.amounts = dict(amounts)

    def quantity(self, sku):
        return self.amounts.get(sku)

class ProductView:
    def __init__(self, catalog, stock):
        self.catalog, self.stock = catalog, stock

    def summary(self, sku):
        if not isinstance(sku, str) or not sku:
            raise ValueError("invalid sku")
        label = self.catalog.label(sku)
        if label is None:
            raise KeyError(sku)
        count = self.stock.quantity(sku)
        if type(count) is not int or count < 0:
            raise ValueError("stock missing or invalid")
        return (sku, label, count)

view = ProductView(Catalog({"A": "Notebook"}), StockBook({"A": 4}))
assert view.summary("A") == ("A", "Notebook", 4)
try:
    ProductView(Catalog({"A": "Notebook"}), StockBook({})).summary("A")
except ValueError:
    pass
else:
    raise AssertionError("missing stock accepted")
```

The two dictionary lookups have expected `O(1)` time under conventional hashing assumptions. The returned tuple is an immutable **local result**, not a proof of a consistent database snapshot: data may change between the two reads, and remote calls carry latency and failure conditions. A Facade does not automatically provide atomicity, authentication, transaction isolation or retries. It becomes harmful when it hides every failure by returning an invented success or grows into a single object that performs every application responsibility [3].

## Behavioral pattern: Observer with defined callback semantics

Observer allows a publisher to notify independently registered listeners [4]. Its name alone leaves critical questions unanswered: do callbacks run synchronously, what happens on exceptions, how does unregistering during notification work, and are events persisted? We define these answers before writing the implementation.

Here callbacks run **synchronously on one thread**, in registration order. A snapshot of listeners is taken at the beginning of each publication. Unsubscribing during delivery therefore affects **later** publications, not the current one. Duplicate subscriptions are rejected; callback exceptions propagate and prevent later callbacks from running. This is deliberately *not* a durable message bus.

```python
class EventSource:
    def __init__(self):
        self.handlers = []

    def subscribe(self, handler):
        if not callable(handler) or handler in self.handlers:
            raise ValueError("invalid or duplicate subscriber")
        self.handlers.append(handler)

    def unsubscribe(self, handler):
        if handler not in self.handlers:
            raise ValueError("subscriber not found")
        self.handlers.remove(handler)

    def publish(self, event):
        for handler in tuple(self.handlers):
            handler(event)

source = EventSource()
events = []

def first_handler(event):
    events.append(("first", event))
    source.unsubscribe(first_handler)

def second_handler(event):
    events.append(("second", event))

source.subscribe(first_handler)
source.subscribe(second_handler)
source.publish("created")
source.publish("updated")
assert events == [
    ("first", "created"), ("second", "created"), ("second", "updated")
]
```

The subscriber-list snapshot is an invariant of **one publication**, not a lock. A second thread may still modify registrations concurrently; recursive publish may execute handlers again and cause unbounded recursion. A slow subscriber holds up all later subscribers. A failing subscriber makes the result **partially delivered**; retrying the entire event would repeat earlier side effects. To guarantee durability or asynchronous delivery, one must redesign event identities, acknowledgments, failure isolation, ordering, replay and backpressure rather than silently adding a broker [4].

## Differentiate neighboring patterns by responsibility

**State versus Strategy:** both delegate behavior, but State reflects an object's valid transitions; Strategy selects an algorithm under a stable input/output contract. A confirmed booking cannot return to pending merely because a Strategy can be swapped. **Facade versus Mediator:** Facade simplifies access from *outside* a subsystem; Mediator coordinates interactions *among* peers. **Observer versus Command:** Observer notifies subscribed consumers; Command represents a requested action and may be stored or retried only under an expressly defined execution contract. These distinctions guide design; they are not claims of transactional correctness [1].

Avoid unexamined Singleton global registries: they can make mutable state, test isolation and lifecycle less visible. Also avoid claiming all patterns require inheritance: Python functions, composition and small objects can express many of their intents more simply. Choose based on change pressure rather than drawing extra class boxes.

## Exercises and verification

1. Construct a report, reuse its Builder and verify the first immutable snapshot remains unchanged. Check empty build, duplicate headings and invalid whitespace.
2. Introduce a catalog-only product and demonstrate that Facade rejects the missing stock instead of assuming zero. How would you guarantee a consistent snapshot if catalog and stock were different services?
3. During Observer notification, register a third callback. Predict whether it executes in the *current* or the *next* publication. Verify with an independent test.
4. Make the first subscriber raise. Trace which subscribers ran. Compare propagation with an alternative that collects errors, and explain the changed contract.
5. Explain when a direct function, simple factory, Builder, Strategy and Facade would each avoid *or introduce* unnecessary coupling.
6. Derive the expected time to build a report after `k` valid additions, and state the assumptions concerning hashing and string length.
7. Explain why switching from synchronous Observer callbacks to a broker changes externally observable failure semantics and is not a pure refactoring.

**Prerequisites and further work:** [Clean Code](/en/topics/clean-code-cohesion-coupling/) defines cohesion and coupling; [SOLID](/en/topics/solid-dependency-inversion/) develops behavioral substitution; [Strategy/Adapter/Decorator](/en/topics/refactoring-design-patterns/) supplies the other worked patterns. [Low-level design](/en/topics/low-level-design/) covers state machines, and [messaging](/en/topics/asynchronous-messaging/) discusses durable asynchronous boundaries.
