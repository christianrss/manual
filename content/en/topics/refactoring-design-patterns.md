---
id: refactoring-design-patterns
title: "Refactoring and Design Patterns: Strategy, Adapter and Behavior Preservation"
description: "Refactor safely with behavioral tests; compare Strategy, Adapter and Decorator with concrete Python examples and trade-offs."
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites: [object-oriented-design, solid-dependency-inversion, testing-strategies]
sources:
  - {title: "Martin Fowler — Refactoring Boundary", url: "https://martinfowler.com/bliki/RefactoringBoundary.html", kind: "primary engineering essay"}
  - {title: "Refactoring.Guru — Strategy", url: "https://refactoring.guru/design-patterns/strategy", kind: "pattern reference"}
  - {title: "Refactoring.Guru — Adapter", url: "https://refactoring.guru/design-patterns/adapter", kind: "pattern reference"}
---
**Refactoring** changes a program's internal structure while preserving its externally observable behavior under a stated contract. It differs from adding features or deliberately changing business semantics. Design patterns are **named solutions to recurring design problems**, not a scoreboard of sophistication. Introducing Strategy, Adapter or Decorator is useful only when the variation or interface mismatch is real; unnecessary abstraction can make a simple system harder to debug and modify [1][2].

## Define the behavioral surface before refactoring

Consider a service computing a price with one of two discount policies. Inputs are nonnegative Decimal subtotal and a policy name; outputs are totals rounded once to cents. The current interface may also guarantee which exception is raised on an unknown policy. If a refactor changes rounding from total-level to per-line, changes the exception contract or adds an external side effect, it is **not behavior preserving** relative to that surface.

Write characterization tests for typical data, zero, decimal boundaries and invalid policies before editing the implementation. Tests are evidence for checked cases, not a proof of universal equivalence. When financial regulations are involved, confirm that expected results reflect a separately defined monetary contract rather than copying a flawed implementation.

## Identify a useful seam, not a code smell alone

A code smell suggests investigating design, but does not prove a defect. A short conditional dispatch can be clearer than a class hierarchy. Refactoring becomes attractive when many call sites repeat the same policy selection and new variants cause unrelated edits. Ask which team or rule is changing, how frequently, and whether clients should choose policy at runtime.

For example, a class that computes totals, sends e-mail and writes a database likely has unrelated reasons to change. But extracting every one-line calculation into a new class may create boilerplate without isolating any real dependency. A stable seam should make a likely change cheaper, and keep behavioral contracts visible.

## Before: conditional policy selection

The straightforward version below has an explicit two-case dispatch. It is **not automatically bad**. The actual refactoring opportunity would arise if many features duplicate its branching logic.

~~~python
from decimal import Decimal, ROUND_HALF_UP
CENT = Decimal("0.01")

def old_total(subtotal, policy):
    if subtotal < 0:
        raise ValueError("negative subtotal")
    if policy == "regular":
        multiplier = Decimal("1.00")
    elif policy == "member":
        multiplier = Decimal("0.90")
    else:
        raise ValueError("unknown policy")
    return (subtotal * multiplier).quantize(CENT, rounding=ROUND_HALF_UP)

assert old_total(Decimal("12.55"), "regular") == Decimal("12.55")
assert old_total(Decimal("12.55"), "member") == Decimal("11.30")
~~~

The function has constant-time dispatch for a fixed number of policies, assuming bounded-precision Decimal operations. A larger dictionary of policy implementations gives a different extension mechanism, but neither changes the underlying arithmetic complexity meaningfully. Choose structure by maintainability and contract stability, not premature performance claims.

## After: a Strategy that makes variation explicit

The **Strategy pattern** encapsulates interchangeable algorithms under a common behavior contract [2]. The next implementation uses a dictionary of callables, a lightweight strategy representation in Python. It retains the same validation, rounding and exception semantics. The equality checks compare both versions over a finite grid of inputs.

![A stable price caller delegates to interchangeable policy strategies; a separate adapter translates legacy interfaces.](/diagrams/refactoring-patterns.svg)

~~~python
def regular(subtotal):
    return subtotal

def member(subtotal):
    return subtotal * Decimal("0.90")

POLICIES = {"regular": regular, "member": member}

def new_total(subtotal, policy):
    if subtotal < 0:
        raise ValueError("negative subtotal")
    if policy not in POLICIES:
        raise ValueError("unknown policy")
    return POLICIES[policy](subtotal).quantize(CENT, rounding=ROUND_HALF_UP)

for cents in range(200):
    subtotal = Decimal(cents) / 100
    for name in ("regular", "member"):
        assert old_total(subtotal, name) == new_total(subtotal, name)
for fn in (old_total, new_total):
    try:
        fn(Decimal("1"), "invalid")
        assert False
    except ValueError:
        pass
~~~

Adding a new pricing policy now changes the registry rather than modifying branch internals. But if the requirement is a single fixed policy with no variations, even the registry is unnecessary. Strategy is not the same as storing arbitrary callables from untrusted input: policy names should map to an explicit **server-controlled allowlist**, and their implementations need contract tests.

## Adapter versus Decorator versus Strategy

An **Adapter** translates one interface into another. Suppose a legacy billing library uses `quote_cents(integer)` while the current service requires `total(Decimal)`; an adapter validates conversion and returns the expected type without changing the legacy library [3]. A **Decorator** preserves the outward interface while adding behavior around an existing component, such as tracing or caching. Strategy changes the selected algorithm; Adapter translates compatibility; Decorator wraps behavior [2][3].

~~~python
class LegacyQuote:
    def quote_cents(self, cents):
        return cents + 25

class LegacyAdapter:
    def __init__(self, legacy):
        self.legacy = legacy
    def total(self, amount):
        if amount < 0 or amount != amount.quantize(CENT):
            raise ValueError("amount must be nonnegative cents")
        cents = int(amount * 100)
        return Decimal(self.legacy.quote_cents(cents)) / 100

adapter = LegacyAdapter(LegacyQuote())
assert adapter.total(Decimal("1.50")) == Decimal("1.75")
try:
    adapter.total(Decimal("1.505"))
    assert False
except ValueError:
    pass
~~~

The example assumes the legacy API uses integer cents and adds a fixed 25-cent fee. In a real financial system, the adapter must specify currency, overflow range, failure behavior and whether fees are already included. Translating types does not guarantee the underlying provider is correct, authorized or durable.

## Incremental refactoring and verification

A safe loop is: establish behavioral tests → extract one small operation → run checks → inspect the diff → repeat. Prefer commits that isolate structural edits from requirement changes. Tests should verify outputs and externally meaningful interactions rather than every private method call, so renaming or moving internals does not break tests unnecessarily [1].

When splitting a large class, check callers that rely on shared mutable state, transaction scope and execution order. A pure function extraction is easier to prove than moving database writes across services. Refactoring across a distributed boundary often introduces **new observable behavior**—timeouts, eventual consistency, duplicate messages—and therefore becomes an architecture migration, not a semantics-preserving code cleanup.

## Failure modes and design-pattern selection

| Change pressure | Option | Common mistake |
| --- | --- | --- |
| Several algorithms vary at runtime | Strategy | Class per trivial arithmetic expression |
| Third-party method shape differs | Adapter | Pretending data conversion proves semantics |
| Optional tracing/cache around a call | Decorator | Hidden order-dependent wrappers |
| One growing class owns unrelated concerns | Extract cohesive component | Circular dependency between components |
| Duplicated conditional in two places | Shared registry/function | Abstracting before behavior is understood |
| Cross-service transaction needs split | Explicit workflow redesign | Calling distributed semantic changes refactoring |

Patterns can interact: a payment client might use an Adapter for an external PSP and a Decorator for metrics, while an application selects a retry policy via Strategy. Each layer carries failure and cost. Review the combined contract rather than assuming that matching pattern diagrams gives correctness.

## Exercises and verification

1. Explain why changing rounding from once-per-subtotal to per-line is a feature/behavior change, not a pure refactor.
2. Add a `vip` strategy with 15% discount and test it independently of the existing options.
3. Trace the LegacyAdapter conversion for 1.50 and explain why a value with three decimals must be rejected.
4. Identify one scenario where a simple if/elif is clearer than a Strategy registry.
5. Explain why extracting a database write into a remote service requires revisiting idempotency and transaction assumptions.

**Related chapters:** [Object-oriented design](/en/topics/object-oriented-design/), [SOLID](/en/topics/solid-dependency-inversion/), [testing strategies](/en/topics/testing-strategies/) and [service boundaries](/en/topics/service-boundaries/) provide the surrounding contracts [1].
