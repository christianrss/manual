---
id: formal-model-checking
title: "Formal Verification: Invariants, State Exploration and TLA+"
description: "Learn safety versus liveness, atomicity and refinement through finite-state model checking of a concurrent reservation protocol, with TLA+ foundations."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [low-level-design, concurrency-synchronization, database-consistency]
sources:
  - {title: "TLA+ Tools — TLC model checker", url: "https://github.com/tlaplus/tlaplus", kind: "official tool repository"}
  - {title: "TLA+ Example Specifications", url: "https://github.com/tlaplus/Examples", kind: "official example collection"}
---
Tests execute chosen inputs and schedules. **Formal modeling** instead represents system states, transitions and properties precisely enough to reason about *all behaviors within a specified model*. A model checker can systematically search a finite state space for a counterexample. It does not automatically prove an implementation correct: results depend on the modeled actions, environmental assumptions, bounds, and how code corresponds to the abstract specification [1].

## Define state, transition and property

A **state** is an assignment to relevant variables, such as the owner of a reserved seat and each worker's control point. An **initial predicate** specifies allowed starting states. A **next-state relation** defines which pairs of states can follow one another under an atomic step. A behavior is a sequence of states satisfying that relation, possibly infinitely long. Correctness properties restrict those behaviors.

A **safety property** says something bad never happens; an observed finite prefix can falsify it. 'No seat is booked by two users' is safety. A **liveness property** says something good eventually happens, for instance every continuously eligible request is eventually decided. Showing a finite prefix without completion does not by itself falsify liveness; progress reasoning needs assumptions about scheduling, failure and fairness.

## Model a non-atomic check-then-commit

Consider two clients A and B reserving one seat. An unsafe protocol performs two separate atomic operations: (1) read that the seat is free and (2) mark the client's booking committed. Between those steps, another client can also read free. A test that only submits requests sequentially will miss the race. The formal model must allow **interleaving**, so a legal behavior can be: A checks free → B checks free → A commits → B commits.

![Unsafe interleavings and atomic reservation resolve the same invariant differently.](/diagrams/formal-reservation-states.svg)

The safety invariant is cardinality of confirmed owners ≤1. Notice that even a unique final ID does not suffice if an external charge or notification executes twice. State definitions should include every effect required by the business correctness claim.

## Exhaustively enumerate a finite protocol in Python

The following bounded checker enumerates reachable states for two workers and tracks a witness trace. The state includes each worker's program stage (0 before checking, 1 passed check, 2 finished) and a boolean for each committed booking. Its steps are abstract atomic transitions; Python is used here as a model-exploration tool, not as evidence about all actual CPU interleavings.

~~~python
from collections import deque

def explore(atomic_commit):
    initial = ((0, 0), (False, False))
    frontier = deque([(initial, [])])
    visited = {initial}
    while frontier:
        state, history = frontier.popleft()
        stages, booked = state
        if sum(booked) > 1:
            return history
        for actor in range(2):
            if stages[actor] == 2:
                continue
            new_stages = list(stages)
            new_booked = list(booked)
            if stages[actor] == 0 and not any(booked):
                new_stages[actor] = 1
                event = f"{actor}:check"
            elif stages[actor] == 1:
                # A correct commit rechecks under the same atomic step.
                if not atomic_commit or not any(booked):
                    new_booked[actor] = True
                new_stages[actor] = 2
                event = f"{actor}:commit"
            else:
                continue
            nxt = (tuple(new_stages), tuple(new_booked))
            if nxt not in visited:
                visited.add(nxt)
                frontier.append((nxt, history + [event]))
    return None

witness = explore(atomic_commit=False)
assert witness is not None
assert set(witness) == {
    "0:check", "1:check", "0:commit", "1:commit"
}
assert explore(atomic_commit=True) is None
~~~

For the unsafe model, both checks can succeed before either commit. The shortest counterexample contains four transitions. For the corrected model, **atomic checking at commit** prevents two confirmed owners. In a real database, this atomic step must be implemented by a constraint/transaction or equivalent authority; merely checking a variable inside a Python function does not guarantee distributed atomicity.

## Why state exploration is stronger than a few tests

Suppose there are n clients each with k relevant local control states and some shared variables. A crude upper bound on local-state combinations is k^n even before shared state is considered. Enumerating all states can quickly become infeasible—**state explosion**. Still, a small model exposes surprising schedules that manually selected tests rarely reproduce. The checker should record visited states and return a minimal or interpretable witness for debugging.

The Python explorer checks finite reachability of its **safety condition**, not liveness or fairness. It makes no promise about network partitions, process crashes, duplicate external effects or durable persistence, because those are absent from its state. If claims depend on those failures, extend the model before treating results as evidence.

## TLA+ describes behaviors declaratively

TLA+ is a language for specifying systems with mathematical actions, sets and temporal formulas. Its TLC tool explores states and checks invariants and temporal properties of finite instances [1]. In a reservation specification, one might write an initial condition `owner = None`, an action that atomically changes an unowned seat to a chosen client, and a property that the owner is either absent or one authorized client. The concrete code must be linked by a **refinement mapping** describing how implementation state represents the abstract owner.

TLA+ and its examples repository provide models of algorithms and systems beyond small concurrency exercises [2]. A model with two clients may verify the two-client instance exhaustively; it does not automatically prove a parametrized implementation correct for any number of clients. Parameterized proof or a justified cutoff argument is a separate task.

## A tiny illustrative TLA+ state contract

~~~text
VARIABLE owner
Init == owner = "none"
Reserve(c) ==
  /\ owner = "none"
  /\ owner' = c
Next == \E c \in {"A", "B"} : Reserve(c)
Safety == owner \in {"none", "A", "B"}
~~~

This fragment illustrates the **atomic guard-and-update** idea and is **not presented as a complete runnable TLA+ module**: TLC also needs the surrounding module, variable tuple, specification/configuration and a treatment of stuttering. More importantly, this Safety predicate alone is weak: a single owner variable cannot represent two independent confirmations. To test the original duplicate-booking bug, the model must explicitly include the two client commitments, as the Python explorer does.

## Fairness and progress are different obligations

If a scheduler can postpone client B forever, 'every client eventually completes' is not guaranteed even when the system never double-books. **Weak fairness** roughly excludes permanently enabled actions from being ignored forever; **strong fairness** deals with repeatedly enabled actions under additional conditions. Neither should be added casually: a network request might never be delivered, or a client may withdraw. A model that assumes a permanently available database cannot establish liveness under arbitrary outages.

A sound model separates safety assumptions from progress assumptions. For example: a unique constraint may protect seat exclusivity under a database transaction even during heavy contention, while an overloaded queue may postpone a particular customer's completion indefinitely unless admission and scheduling guarantees are added.

## Counterexamples, refinement and review

A **counterexample trace** identifies a sequence of allowed steps leading to violation. It should become a regression test when the implementation provides hooks to force that schedule. A failed model check can reveal a bug in the *specification* as well as the design, so review assumptions with domain experts. Conversely, a model that passes with a missing failure transition may be falsely reassuring.

| Technique | What it establishes | What it does not establish |
| --- | --- | --- |
| Unit test | Behavior on chosen cases | All schedules and inputs |
| Finite model checker | Properties for modeled finite states | Unmodeled failures or unlimited scale |
| Mathematical proof | Theorem under stated axioms | Correct implementation mapping by itself |
| Production metrics | Observed real outcomes | Absence of rare reachable bugs |

## Exercises and verification

1. Explain why the history check(A), check(B), commit(A), commit(B) violates the invariant.
2. Modify the explorer to include a third client; measure states explored and discuss growth.
3. Add an external-charge count to state; explain why a booking invariant might hold while charge count exceeds one.
4. Specify a liveness claim and identify its required scheduler or network assumptions.
5. State what implementation mapping would be necessary to trust the atomic commit used in the corrected model.

**Related reading:** [Concurrency](/en/topics/concurrency-synchronization/) introduces interleavings; [database consistency](/en/topics/database-consistency/) describes transactional anomalies; [low-level design](/en/topics/low-level-design/) formalizes local state transitions.
