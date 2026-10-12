---
id: state-command-design-patterns
title: "State and Command patterns: transitions, replay and failure contracts"
description: "Use explicit state transitions and command objects to separate business decisions from requests, with tests for versions and duplicate execution."
category: engineering
difficulty: intermediate
updated: 2026-10-12
prerequisites: [low-level-design, design-pattern-families]
sources:
  - {title: "Refactoring.Guru — State", url: "https://refactoring.guru/design-patterns/state", kind: "technical pattern reference"}
  - {title: "Refactoring.Guru — Command", url: "https://refactoring.guru/design-patterns/command", kind: "technical pattern reference"}
  - {title: "AWS Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
---
State and Command are **behavioral design patterns**, but they solve different problems. State delegates behavior according to the current lifecycle phase; Command packages a request so that the caller is separated from the operation's executor [1][2]. Neither pattern guarantees persistence, thread safety, authorization or reliable messaging. Those properties require separate mechanisms and contracts. This chapter derives both patterns from a document-review workflow and checks the exact boundary at which a repeated action becomes unsafe.

## Define the workflow before selecting a pattern

Suppose a document starts as draft, enters review, and is then published. Publication must not occur before review. A published document is immutable in this simplified workflow. The operations are submit and publish; errors must leave the state unchanged. Version numbers start at zero and increment once for each accepted transition. The rules exclude withdrawal, moderation roles and concurrent external edits unless explicitly introduced later.

A state transition can be written as a partial function T(state, operation) → new_state. Partial means some pairs are invalid. For three phases and two operations there are six combinations, of which only draft+submit and review+publish are allowed. Enumerating the finite space first prevents a class hierarchy from hiding missing requirements. The [low-level design chapter](/en/topics/low-level-design/) uses explicit state machines without necessarily creating one class per state.

## When the State pattern adds value

A transition table or a small conditional is usually simpler when there are two actions and three phases. Introduce concrete State classes when states accumulate distinct behavior, rules change independently, or large conditional branches duplicate code. The State pattern makes the document context delegate the action to its current state object; that object determines the permitted transition [1]. This is different from Strategy: a consumer chooses Strategy to vary an algorithm, while a document lifecycle constrains what operations remain legal as state changes.

The State implementation below deliberately remains local. Its invariant is: an accepted action increments version exactly once, and a rejected action changes neither version nor state. The current State object itself has no durable identity; only the document lifecycle phase and version would need to be persisted in a database.

~~~python
class Draft:
    name = "draft"
    def submit(self):
        return Review()
    def publish(self):
        raise ValueError("review required")

class Review:
    name = "review"
    def submit(self):
        raise ValueError("already in review")
    def publish(self):
        return Published()

class Published:
    name = "published"
    def submit(self):
        raise ValueError("immutable document")
    def publish(self):
        raise ValueError("already published")

class Document:
    def __init__(self):
        self.state = Draft()
        self.version = 0
    def apply(self, action):
        if action not in ("submit", "publish"):
            raise ValueError("unknown action")
        next_state = getattr(self.state, action)()
        self.state = next_state
        self.version += 1
        return self.state.name

d = Document()
assert (d.state.name, d.version) == ("draft", 0)
try:
    d.apply("publish")
except ValueError:
    pass
else:
    raise AssertionError("draft was published")
assert (d.state.name, d.version) == ("draft", 0)
assert d.apply("submit") == "review"
assert d.apply("publish") == "published"
assert (d.state.name, d.version) == ("published", 2)
for invalid in ("publish", "submit", "delete"):
    try:
        d.apply(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid action accepted")
assert d.version == 2
~~~

The classes encode a *design choice*, not a proof that every lifecycle is better with polymorphism. Adding a new state requires reviewing the interface and transitions of other states. Dynamic getattr here is safe only because input is restricted to an explicit allowlist. Without the guard, arbitrary attribute access could expose operations never intended as public commands.

## Command separates intent from execution

A Command stores the request's intended action and arguments; an invoker decides when to call the receiver [2]. This is useful for queues, command histories, HTTP handlers and task scheduling. A command is an instruction, **not evidence that a side effect committed**. Retrying the same command after a timeout may repeat an operation unless the receiver implements a stable deduplication rule.

Our local example uses an expected version as optimistic precondition. Commands with a stale version fail instead of silently overwriting a newer lifecycle state. The command object delegates to the receiver; its constructor performs no mutation.

~~~python
from dataclasses import dataclass

@dataclass(frozen=True)
class TransitionCommand:
    action: str
    expected_version: int
    def execute(self, receiver):
        if not isinstance(self.expected_version, int) or self.expected_version < 0:
            raise ValueError("invalid version")
        if receiver.version != self.expected_version:
            raise ValueError("version conflict")
        return receiver.apply(self.action)

doc = Document()
cmd = TransitionCommand("submit", 0)
assert doc.version == 0
assert cmd.execute(doc) == "review"
try:
    cmd.execute(doc)
except ValueError:
    pass
else:
    raise AssertionError("stale command replayed")
assert (doc.state.name, doc.version) == ("review", 1)
assert TransitionCommand("publish", 1).execute(doc) == "published"
~~~

Notice that refusing duplicate execution is **not the same as idempotent success**. A client replaying submit with expected version zero receives a version conflict, not the first successful response. A production idempotency contract may require storing (caller, operation_id, payload hash, completed result) durably, in the same transactional boundary as the state change. A repeated key with different payload must be handled explicitly. The Builders Library describes why stable request identity matters under retries [3].

## Complexity and consistency boundaries

Each local transition performs a constant number of attribute lookups and assignments, so its time and additional memory are O(1) for fixed-size actions in this in-memory example. A durable implementation is not O(1) by this argument: indexes, locking, network access, transaction logs and contention have their own costs. The simple version check is also unsafe across multiple processes if read and write occur separately.

An authoritative database implementation can use an atomic conditional update equivalent to UPDATE documents SET state=?, version=version+1 WHERE id=? AND version=? AND state=?. Exactly one concurrent winner may succeed for a given version when the database enforces the predicate atomically. Read the number of affected rows and distinguish stale version, invalid state and absent document according to your API contract. The statement alone does not authorize the actor, publish external notifications or guarantee side-effect exactly-once semantics.

## Failure scenarios and counterexamples

If publishing means issuing an external notification, calling it before committing may notify about a document that rolls back. Calling it after committing may lose the notification after a crash. Use an outbox or another explicit commit-to-delivery protocol when reliable notification is required. A relay can still deliver duplicates; consumers need event IDs and their own replay policy [3].

An audit queue full of Command objects does not provide event sourcing automatically. A command describes **what was requested**, while an event describes **what occurred**. A rejected command must not be reconstructed as a successful domain event. Undo is also not intrinsic: reversing a transfer or publication can require a new authorized compensating operation rather than restoring an in-memory snapshot.

## Pattern selection as an engineering decision

Use a table for a small, stable transition set; State classes for substantial phase-specific behavior; Command for deferred or decoupled invocation; and Strategy for interchangeable algorithms. If queue delivery and persistence are introduced, design retry and deduplication first. Avoid a command class per one-line function merely to match a diagram. Resist mixing command execution, permission checks, lifecycle rules and transport retries into one large object.

Review the resulting code against the concrete behavior, not the names of the classes. Version change, invalid action handling, actor identity, durability and recovery are independently testable promises. The patterns help locate their implementation; they cannot replace the tests.

## Exercises and verification

1. Enumerate all six phase/action combinations. For each, state whether it succeeds and the resulting version; derive why a rejected action preserves state.
2. Add a withdraw operation that is legal only during review. Extend both the transition model and tests; discuss the effect of adding a new method to every State class.
3. Run two requests with expected_version=1 against one durable document. Specify an atomic conditional update and expected outcome for the loser.
4. Compare two replay contracts: reject duplicate with conflict, or return the previously stored result. Identify which metadata must be stored to support the second.
5. Distinguish Command, domain event, Strategy and State in a payment authorization workflow. Explain why an in-memory history cannot establish a reliable financial ledger.

Related: [pattern families](/en/topics/design-pattern-families/), [refactoring patterns](/en/topics/refactoring-design-patterns/), [API reliability](/en/topics/api-reliability/).