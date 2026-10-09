---
id: testing-strategies
title: "Software Testing Strategies: Units, Contracts, Integration and E2E"
description: "Separate unit, property, integration, contract and end-to-end tests with executable examples and clear limits of evidence."
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites: [object-oriented-design, testing-maintainability]
sources:
  - {title: "Martin Fowler — The Practical Test Pyramid", url: "https://martinfowler.com/articles/practical-test-pyramid.html", kind: "engineering article"}
  - {title: "Python unittest — official documentation", url: "https://docs.python.org/3/library/unittest.html", kind: "official language documentation"}
  - {title: "Google Engineering Practices — Code review", url: "https://google.github.io/eng-practices/review/", kind: "engineering guideline"}
---
A useful test suite provides **evidence about behavior at a defined boundary**, not a high number of assertions. Unit, integration, contract, end-to-end and load/fault tests answer different questions. They cannot be substituted freely: a fake database makes a decision test fast but cannot prove real uniqueness constraints; a successful end-to-end test proves one exercised path but does not exhaustively cover concurrent interleavings. This boundary perspective is more important than any fixed numerical test-pyramid ratio [1].

## Start with a written behavioral contract

Before choosing a framework, specify allowed inputs, outputs, side effects, error policy and invariants. Consider an order subtotal from line prices and positive quantities, with a tax policy that must return a nonnegative total. The basic observable contract is that empty input totals zero, adding a zero-price line does not change the total, and negative amounts or nonpositive quantities are rejected.

Tests should cover ordinary values, **boundary values**, malformed input and historically observed regressions. A list of example assertions is useful, but an assertion that copies the implementation's formula can reproduce the same mistake. Derive expected results from business requirements and an independently understandable calculation.

## Unit tests isolate a decision

A **unit test** executes a small decision boundary while controlling expensive or nondeterministic collaborators. It should be quick and repeatable, with failures that point to a local behavior. A unit can be a function, an object or a cohesive set of collaborating functions; there is no universal rule of one class per unit test.

Python's unittest supplies fixtures, assertions and subTest for repeating a contract over many input cases [2]. The following policy uses Decimal values created from strings to avoid unintended binary floating-point rounding. It returns a tax-inclusive total by rounding **once at the final aggregate**; a jurisdiction requiring line-level rounding would need another contract.

~~~python
import io
import unittest
from decimal import Decimal, ROUND_HALF_UP

def billed_total(lines, tax_rate):
    if not Decimal("0") <= tax_rate <= Decimal("1"):
        raise ValueError("invalid tax rate")
    subtotal = Decimal("0")
    for price, quantity in lines:
        if price < 0 or quantity <= 0:
            raise ValueError("invalid line")
        subtotal += price * quantity
    return (subtotal * (1 + tax_rate)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)

class BillingTests(unittest.TestCase):
    def test_examples(self):
        cases = [
            ([], "0", "0.00"),
            ([(Decimal("10.00"), 2)], "0.10", "22.00"),
            ([(Decimal("0.00"), 3)], "0.21", "0.00"),
        ]
        for lines, rate, expected in cases:
            with self.subTest(lines=lines, rate=rate):
                self.assertEqual(
                    billed_total(lines, Decimal(rate)), Decimal(expected))

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            billed_total([(Decimal("-1"), 1)], Decimal("0"))
        with self.assertRaises(ValueError):
            billed_total([(Decimal("1"), 0)], Decimal("0"))

result = unittest.TextTestRunner(
    stream=io.StringIO(), verbosity=0
).run(unittest.defaultTestLoader.loadTestsFromTestCase(BillingTests))
assert result.wasSuccessful()
~~~

A passing suite verifies the listed examples and validations in the **local model**. It does not establish the correctness of accounting regulations, exchange rates or database settlement. The implementation assumes all prices share one currency and that tax_rate was already authorized and sourced correctly.

## Property and metamorphic tests

Example-based tests check selected values. A **property** specifies a relation expected for many inputs. For nonnegative prices and quantities, adding a line priced zero should not change the computed total; increasing a quantity should not reduce it when tax rate is nonnegative. A **metamorphic relation** compares results after a controlled input transformation and is useful when an external expected answer is hard to calculate.

~~~python
from itertools import product

for quantity, cents in product(range(1, 5), range(4)):
    lines = [(Decimal(cents) / 100, quantity)]
    original = billed_total(lines, Decimal("0.10"))
    with_free = billed_total(
        lines + [(Decimal("0"), 1)], Decimal("0.10"))
    assert with_free == original
    assert billed_total(
        [(lines[0][0], quantity + 1)], Decimal("0.10")) >= original
~~~

This checks a small finite grid, not all monetary inputs. A property-based testing tool can generate more cases and shrink failing examples. For randomized checks, fix seeds when appropriate, preserve the failing input and ensure that the property itself is justified independently of the code.

## Integration tests verify the real boundary

An **integration test** checks components operating together across a real boundary: database schema/constraints, serialization, network client, message broker or file system. Replacing a relational database with an in-memory dictionary can invalidate the test's assumptions about transactions, isolation, collations and indexes. To prove uniqueness under concurrency, use a real database in an isolated environment, separate connections and a barrier so conflicts occur.

External services can be unreliable or costly, so integration tests should use controlled service instances and data cleanup. Unit tests may run on every edit; slower integrations can run in CI gates or relevant stages, but delaying all critical integration checks until production is poor risk management.

## Contract testing and compatibility

A **consumer contract test** records expectations for a service/API response shape, error semantics, field types and version compatibility. A provider contract check verifies that the actual service honors those expectations. These tests detect breaking integration changes, but they cannot prove that every business operation is correct or that access control is sound.

For example, a client may require that pagination returns a stable cursor string and that a missing resource returns a documented error. An implementation can satisfy this wire contract while returning another tenant's data; a separate authorization test is required. Similarly, an API mock that matches an OpenAPI schema cannot prove production latency or database transaction behavior.

## End-to-end and failure testing

An **end-to-end (E2E)** test exercises a user-relevant path through deployed components: placing an order, persisting it, generating an event and reading its resulting state. This is valuable because integration failures often occur at boundaries not visible to isolated tests. But large E2E suites can be slow and flaky if they depend on uncontrolled clocks, shared state, external rate limits or asynchronous eventual-consistency delays [1].

A **fault test** deliberately injects errors: timeouts, unavailable dependencies, duplicate events, process crashes, or partial writes. If an API promises idempotency, test the same key and payload repeated, the same key with different payload, and replay after a crash. A successful retry under a mock is insufficient to prove exactly-once external billing; verify durable keys and reconciliation in an integration environment.

## Test doubles: mocks, stubs and fakes

A **stub** supplies canned responses. A **fake** implements useful simplified behavior, such as an in-memory repository. A **mock** verifies interactions—for example that a sender receives one call. These names overlap in some frameworks, but their critical distinction is **what claim the test is making**. Interaction assertions can expose unnecessary implementation coupling, while state assertions may better survive refactoring.

A fake is not a faithful substitute for a real distributed store. A mock that confirms send() was called does not confirm the remote message was accepted, delivered or observed by a user. Prefer assertions on externally meaningful outcomes; use interaction checks when interaction count or order is itself part of the contract.

## Determinism, isolation and CI reliability

Tests should control randomness, time, storage state and concurrency where possible. Inject a clock rather than sleeping to wait for tomorrow. Use temporary databases, unique test records and cleanup. Parallel suites must avoid shared mutable global fixtures; otherwise a test passes alone and fails depending on order. Retrying flaky tests until green can hide regressions rather than improving confidence.

A release pipeline needs tests at different boundaries: fast unit/property checks, focused integrations, a small set of critical E2E flows, performance/fault checks when risks justify them, and observability after deployment. Passing a pipeline supports a **bounded evidence claim**, not universal proof that the system is correct [1][3].

| Test type | Strongest evidence | What it cannot establish alone |
| --- | --- | --- |
| Unit | Local rule and edge cases | Real DB/network semantics |
| Property | Broad relations over generated cases | Unmodeled requirements |
| Integration | Actual component compatibility | Entire user workflow |
| Contract | Client/provider API expectations | Authorization and business correctness |
| E2E | Critical path across components | Every rare race and failure mode |
| Fault/load | Behavior in induced conditions | All disaster scenarios |

## Exercises and verification

1. Add a boundary test for tax_rate 1 and rejection of tax_rate greater than 1.
2. Explain why a test with a dictionary cannot demonstrate SQL UNIQUE under concurrent inserts.
3. Define a metamorphic property for item-order permutation and explain why monetary rounding policy matters.
4. Describe an E2E scenario that passes while a second concurrent request breaks an invariant.
5. Propose a CI matrix that preserves quick feedback but tests real storage and external API contracts before release.

**Related chapters:** [Maintainability and testing](/en/topics/testing-maintainability/) establishes invariants; [object-oriented design](/en/topics/object-oriented-design/) supplies seams; [transactional indexing](/en/topics/transactional-indexing-isolation/) explains concurrency constraints [1].
