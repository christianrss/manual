---
id: clean-code-cohesion-coupling
title: "Clean Code Fundamentals: Cohesion, Coupling and Change-Safe Design"
description: "Derive readable and maintainable code boundaries using cohesion, coupling, pure functions, explicit contracts, refactoring and tested inventory examples."
category: engineering
difficulty: intermediate
updated: 2026-10-10
prerequisites: [complexity-analysis, arrays-and-strings]
sources:
  - {title: "Google Engineering Practices — What to Look for in a Code Review", url: "https://google.github.io/eng-practices/review/reviewer/looking-for.html", kind: "primary engineering guidance"}
  - {title: "Martin Fowler — Refactoring Boundary", url: "https://martinfowler.com/bliki/RefactoringBoundary.html", kind: "primary engineering essay"}
  - {title: "Python Standard Library — dataclasses", url: "https://docs.python.org/3/library/dataclasses.html", kind: "official language documentation"}
---
Clean Code is not a mechanical checklist of short methods, zero comments, or class counts. It is an engineering objective: a reader must be able to understand a program's **behavior, invariants, ownership and likely change points**, and then change it without introducing unrelated regressions. Google engineering review guidance evaluates design, correctness, complexity, naming and tests as related dimensions rather than rewarding arbitrary stylistic rules [1]. This chapter develops those principles **before** applying SOLID, inheritance or design patterns.

## Readability is a property of decisions, not formatting alone

Indentation, consistent names and uncomplicated control flow help reviewers, but a beautifully formatted incorrect program is still incorrect. In a function that processes inventory, the name `x` tells little; `available_quantity` identifies both purpose and units. The name `validate_inventory` must match observable behavior: quietly repairing invalid stock figures would violate what readers expect of a validator. Good comments state **why** a surprising constraint exists, not translate obvious source code into prose.

Measure readability by whether another engineer can answer: Which inputs are allowed? Who owns mutable state? What must always remain true? Which dependencies can fail? Where does a future business rule change? Where is the behavior tested? These are review questions, not universal numeric thresholds. An extra helper function can clarify a decision, or merely scatter related logic across files [1].

## Cohesion: keep one reason to change in each boundary

**Cohesion** concerns how closely the responsibilities in a unit belong together. Business policy for calculating replenishment belongs together because it changes when the replenishment rule changes. Opening an HTTP connection, authenticating a vendor and sending a purchase request change for infrastructure reasons. Combining both in one function makes a local policy test require a network or an elaborate mock.

This does **not** imply a class for every line. A small function can validate inputs and compute one result coherently. Likewise, one object may legitimately contain multiple operations that maintain a single invariant. The useful question is not “Does it have only one method?” but “Would two independent stakeholders have to edit it for unrelated reasons?” Splitting validation into a different service solely to meet a method-count rule can reduce clarity and introduce unnecessary coordination.

## Coupling: distinguish semantic dependencies from infrastructure dependencies

**Coupling** is the extent to which changing one unit forces changes elsewhere. Some coupling is essential: a purchasing rule must understand inventory quantities and thresholds. Coupling to the schema of an external HTTP vendor, the current database connector or a global environment variable can be avoidable when business policy does not need those details.

A boundary is justified when its collaborators evolve independently or need independent test/failure handling. The direction matters: a pure planning function should receive data and return a plan; a coordinator can decide when to call a vendor. Dependency injection may be as simple as **passing an object with a documented method**. A container, service locator and full plugin platform are not prerequisites for clean design.

| Change | Prefer to edit | What should normally stay unchanged |
| --- | --- | --- |
| Minimum-stock policy changes | Planning logic and its tests | Vendor transport adapter |
| Vendor API changes | Transport adapter | Replenishment arithmetic |
| Invalid quantities must be rejected | Input contract and tests | Network credentials |
| Business chooses a new unit of measure | Domain model, callers and migrations | Unrelated UI formatting |

Reducing coupling does not mean having zero dependencies. Introducing an interface for every arithmetic expression may make coupling **harder to see**, even if the diagram has more boxes [1].

## Case study: derive a pure inventory planner from a contract

Assume a **single inventory snapshot**, with unique, nonblank SKU strings and nonnegative **integer** quantities. Each item carries `available` and `minimum`. The desired replenishment is `max(0, minimum - available)`. We output only positive replenishment lines, preserving input order. Duplicate SKUs, invalid types and negative quantities are rejected before any external action. An empty inventory produces an empty plan.

These are local teaching requirements, not a full warehouse model: outstanding purchases, damaged stock, supplier minimum order quantity, reserved inventory and concurrent stock changes are outside the contract. The input is a sequence that this function iterates once. The result is immutable records in a tuple. Python's `dataclass(frozen=True)` restricts assignment to record fields; it is not deep immutability for arbitrary mutable field contents [3].

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Stock:
    sku: str
    available: int
    minimum: int

@dataclass(frozen=True)
class Reorder:
    sku: str
    quantity: int

def plan_reorders(stocks):
    seen = set()
    plan = []
    for item in stocks:
        if not isinstance(item, Stock):
            raise ValueError("expected Stock item")
        if (not isinstance(item.sku, str) or not item.sku.strip()
                or item.sku != item.sku.strip()):
            raise ValueError("invalid SKU")
        if (type(item.available) is not int or type(item.minimum) is not int
                or item.available < 0 or item.minimum < 0):
            raise ValueError("quantities must be nonnegative integers")
        if item.sku in seen:
            raise ValueError("duplicate SKU")
        seen.add(item.sku)
        missing = item.minimum - item.available
        if missing > 0:
            plan.append(Reorder(item.sku, missing))
    return tuple(plan)

stocks = [Stock("A", 1, 3), Stock("B", 9, 5), Stock("C", 0, 4)]
assert plan_reorders(stocks) == (Reorder("A", 2), Reorder("C", 4))
assert plan_reorders([Stock("X", 4, 4)]) == ()
assert plan_reorders([]) == ()
assert stocks[0] == Stock("A", 1, 3)
```

The loop invariant is: after consuming the first `k` records, `seen` contains exactly their distinct identifiers; `plan` contains exactly the positive deficits for those records, in their original order. The validation ensures the invariant is not extended with a duplicate or malformed record. Each iteration consumes one item, so the algorithm terminates for finite inputs. Expected time is `O(n)` and auxiliary memory `O(n)` under bounded SKU length, bounded integer size and expected constant-time set operations. Hash collision worst cases and long string hashing invalidate unconditional constant-time claims. The function does not read clocks, global state or networks; equal input snapshots produce equal outputs.

## Put side effects at a narrow composition boundary

A **coordinator** can deliver the completed plan to an external collaborator, but a pure computation should not know SMTP, REST endpoints, SQL connections or retries. A recording adapter proves that the coordinator dispatches the expected plan, not that a remote purchase is actually accepted.

```python
class RecordingSink:
    def __init__(self):
        self.submissions = []

    def submit(self, plan):
        self.submissions.append(tuple(plan))

def execute_plan(stocks, sink):
    plan = plan_reorders(stocks)
    if plan:
        sink.submit(plan)
    return plan

sink = RecordingSink()
plan = execute_plan(stocks, sink)
assert sink.submissions == [plan]
assert execute_plan([Stock("X", 5, 5)], sink) == ()
assert len(sink.submissions) == 1
try:
    execute_plan([Stock("A", 0, 1), Stock("A", 0, 1)], sink)
except ValueError:
    pass
else:
    raise AssertionError("duplicate SKU must fail")
assert len(sink.submissions) == 1
```

The ordering is deliberate: **validate and compute the entire plan before submitting** it. If a later record is invalid, no submit call occurs. Once a real sink starts a network request, failure can be ambiguous: the vendor might accept the request even when the client receives a timeout. Neither composition nor a recording fake grants end-to-end atomicity or idempotency. A durable operation key, transactional record of intent and provider-specific reconciliation would need separate design and integration tests.

## Refactoring requires behavioral equivalence under an explicit surface

Suppose the first implementation duplicated a threshold calculation in two routes. A safe extraction first records input/output behavior, including duplicate rejection, stable ordering, invalid input and the fact that **no send occurs for an empty plan**. Then move the computation to `plan_reorders`, compare the public outcomes and introduce the adapter at the edge. As Martin Fowler notes, refactoring is a sequence of small structural changes that preserve chosen observable behavior, not an excuse to silently change business policy [2].

Be precise about the observable surface. If an API previously sent each reorder individually and now sends one batch, the externally visible request count and failure semantics have changed even when the computed quantities match. That is an integration behavior change requiring a separate contract and rollout plan. Similarly, silently fixing a previously allowed duplicate SKU changes accepted inputs: document it as a bug fix or policy change rather than claiming a pure refactoring.

## Counterexamples: when abstraction and apparent cleanliness hurt

Extracting `subtract(a,b)` into a class `SubtractionStrategyFactory` without a real variation point adds names, indirection and tests but no independent change boundary. Replacing every condition with a design pattern can obscure the policy's truth table. Splitting an operation across asynchronous services to achieve “single responsibility” introduces partial failures, latency, retries and consistency costs. A local cohesive function often provides **more** maintainability than an elaborate distributed graph.

Conversely, keeping business calculations inside a vendor SDK callback couples testing and release cycles to external infrastructure. If there are genuinely multiple vendors with independent API revisions, an adapter may be valuable. The engineering judgment lies in finding the **smallest boundary that isolates a demonstrated source of change** [1][2].

## Independent exercises and verification

1. **Contract table:** enumerate `available` = 0, 2, 5 and `minimum` = 0, 2, 5; compute all nine expected replenishments independently of the code.
2. **Adversarial cases:** reject duplicate SKUs even when no replenishment is needed; reject `True` for quantity (Python `bool` subclasses `int`); reject negative and fractional quantities.
3. **Metamorphic property:** holding `minimum` constant, increasing valid `available` must never increase `quantity`; the SKU must still be present or absent according to the same threshold.
4. **Dependency exercise:** replace `RecordingSink` with a failing sink and explain what the caller knows after an exception and why retries require an operation identifier.
5. **Change review:** specify an amendment that reserves part of the stock for pending orders. Identify which policy, record fields, tests and consumers change. Avoid inventing a new pattern until independent variation is demonstrated.
6. **Performance:** explain when set membership changes the time bound (unbounded SKU length, adversarial hashing, or a nonterminating input iterator), and why such assumptions belong in an interview explanation.

**Next:** [Object-oriented design](/en/topics/object-oriented-design/) models protected state; [testing and maintainability](/en/topics/testing-maintainability/) develops verification; [SOLID](/en/topics/solid-dependency-inversion/) evaluates interfaces and substitution; [design patterns](/en/topics/refactoring-design-patterns/) studies justified structural transformations.
