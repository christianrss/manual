---
id: programming-semantics-contracts
title: "Programming Semantics, Aliasing and Executable Contracts"
description: "Reason about evaluation, equality, mutation, exceptions and function contracts before using language features in algorithmic solutions."
category: foundations
difficulty: foundational
updated: 2026-10-10
prerequisites: [logic-proofs-invariants]
sources:
  - {title: "Python Language Reference — Execution Model", url: "https://docs.python.org/3/reference/executionmodel.html", kind: "official language reference"}
  - {title: "Python Language Reference — Expressions", url: "https://docs.python.org/3/reference/expressions.html", kind: "official language reference"}
  - {title: "Python Language Reference — Simple Statements", url: "https://docs.python.org/3/reference/simple_stmts.html", kind: "official language reference"}
  - {title: "Python Standard Library — unittest", url: "https://docs.python.org/3/library/unittest.html", kind: "official language documentation"}
---
Two implementations can express the same mathematical formula and still behave differently because a language determines evaluation order, conversions, object identity, mutation, exception propagation and resource lifetime. An engineer must know which properties are guaranteed by the chosen language and which are merely observed in one runtime. This chapter works through explicit Python contracts; it does not claim that every rule generalizes to C++, JavaScript, Rust or Java. The Python language reference documents execution and expression semantics, including name binding, evaluation and operators [1][2].

## Values, objects, identity and equality

In Python a name is bound to an object; assignment does not generally copy that object. Equality compares values using an object's equality operation, while identity asks whether two references designate the same object. These questions differ even if a particular example happens to give identical answers. A collection can also hold references to mutable objects, so copying the outer collection does not automatically copy the graph of reachable objects [1][2].

~~~python
first = [[1], [2]]
shallow = first.copy()
assert first == shallow
assert first is not shallow
assert first[0] is shallow[0]
shallow[0].append(3)
assert first == [[1, 3], [2]]
~~~

The postcondition "the copied list is independent of every nested list" is false: the reference inside the first nested position is shared. A deep copy has a different contract and may not be appropriate for arbitrary object graphs. Prefer explicit ownership and mutation rules rather than adding copying by habit.

## Evaluation order and short-circuit behavior

An expression has both a value and possible effects. In Python, the Boolean operators and and or evaluate only as far as required, and return one of their operands; they are not guaranteed to return bool. This matters for defaults and input validation, especially when valid values such as zero and empty strings are falsy [2].

~~~python
def choose_port(requested, default):
    return default if requested is None else requested

assert choose_port(0, 8080) == 0
assert choose_port(None, 8080) == 8080
assert (0 or 8080) == 8080
assert (3 and 5) == 5
~~~

Replacing a missing-value check by "requested or default" silently changes the behavior of zero. Thus **a truthiness shortcut is not equivalent to an explicit optional-value contract**. Side-effecting operands create additional hazards: short-circuit evaluation may prevent function calls from happening. In an interview, state whether inputs are optional, empty, null or invalid instead of collapsing them into one category.

## Mutable defaults, aliasing and local reasoning

Function parameters are bound to argument objects. A mutable default object, if declared as a default value, can be shared across calls because the default expression is evaluated when the function is defined, not every time it is invoked. This is a semantics issue, not simply a naming-style problem [2].

~~~python
def accumulate(value, collected=None):
    if collected is None:
        collected = []
    collected.append(value)
    return collected

one = accumulate(1)
two = accumulate(2)
assert one == [1] and two == [2]
assert one is not two
explicit = []
assert accumulate(3, explicit) is explicit
assert explicit == [3]
~~~

The contract above intentionally mutates an explicitly supplied list but allocates a new list when none is supplied. It would be incorrect to claim the function is pure or that all outputs are independent of their inputs. An API may instead copy input data, return an immutable tuple or document ownership transfer. Each choice trades allocation against observable side effects.

## Errors are part of the contract

Preconditions should specify invalid-input behavior. For a positive divisor, a function may reject zero with ValueError, while a different API may return an error-result object. Allowing a raw ZeroDivisionError to escape could be acceptable internally but not under a public contract that guarantees structured validation errors. Exceptions are control-flow and interface behavior; they must be considered alongside successful values [3].

~~~python
def divide_by_positive_count(total, count):
    if type(total) not in (int, float) or type(count) is not int:
        raise TypeError("expected numeric total and integer count")
    if count <= 0:
        raise ValueError("count must be positive")
    return total / count

assert divide_by_positive_count(9, 3) == 3.0
for bad in (0, -1):
    try:
        divide_by_positive_count(9, bad)
        raise AssertionError("should reject invalid count")
    except ValueError:
        pass
try:
    divide_by_positive_count(9, "3")
    raise AssertionError("should reject wrong type")
except TypeError:
    pass
~~~

This example only enforces count positivity and basic types. Its name promises a positive count, not a nonnegative total. Do not infer requirements that the implementation or the documented contract do not actually enforce. Avoid leaving a name and its precondition inconsistent. IEEE floating-point NaN and infinities, overflow in other languages, exact rational arithmetic and precision requirements demand separate explicit policies.

## Invariants and substitution across interfaces

Suppose a function processes a batch of commands. A useful invariant is "each accepted command either produces exactly one result or causes the operation to report failure." That is a contract over observable behavior, not over a concrete class hierarchy. A substitute implementation that silently drops commands violates the contract even if its method signatures match.

Mutation complicates substitution: a handler that changes the caller's input can break clients that rely on unchanged arguments. The principle of behavioral substitutability demands compatible preconditions, postconditions and failure behavior. Before applying SOLID or a design pattern, state the externally observable obligations. When describing performance, account for dynamic dispatch, object allocation and copying only after correctness has been established.

For a pure function, a useful property is referential transparency: replacing a call by its result should not change observable behavior in the modeled context. The accumulating function above is intentionally not pure when passed an existing list. This distinction makes test design and caching decisions more reliable.

## Verification by examples and independent tests

Running a few assertions detects regressions but cannot prove behavior for every possible Python object or concurrent access pattern. Use boundary tests, negative tests, and state-transition tests. Python's unittest supports isolated test methods, shared fixtures and explicit exception assertions [4]. For a list-handling API, compare calls with omitted and explicit empty arguments, repeated calls, shared nested objects and incorrect types. An executable example should avoid depending on object IDs, interning choices or unspecified timing.

An independent oracle is especially useful. A parser can be checked by a slower reference implementation; an optimizer by exhaustive enumeration over small inputs. Keep the oracle simpler than the optimized algorithm, and check both outputs and forbidden side effects. Distinguish a contract such as "does not modify input" from an implementation tactic such as "uses a dictionary."

## Exercises

1. Predict the effect of assigning the same nested list to two names, then copying only the outer list. **Answer:** the outer containers differ, but nested mutable objects can remain aliased; mutating a nested object may affect both views.
2. Explain why default = requested or fallback is not equivalent to using fallback only when requested is None. **Answer:** zero, False and empty collections are false-valued but can be valid requested values.
3. State a complete contract for a function that returns a list's median: domain, behavior for empty input, whether input is changed, handling of even lengths and costs. **Check:** different even-length conventions give different valid APIs.
4. Propose a failing test for a batch handler that promises no input mutation. **Answer:** preserve a deep-enough snapshot of the documented input structure, invoke it, then compare input to snapshot; a shallow snapshot is insufficient when nested elements may mutate.

Only the documented Python behavior and concrete examples are established here. This material precedes language-specific memory models, compilation, virtual machines and concurrency, which require additional chapters.