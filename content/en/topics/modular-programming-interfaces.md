---
id: modular-programming-interfaces
title: "Modular programming: cohesion, explicit interfaces and pure functions"
description: "Learn how to decompose programs into cohesive modules, separate computation from input/output and test boundaries without frameworks."
category: engineering
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-control-flow-functions, programming-semantics-contracts]
sources:
  - {title: "Python tutorial — Modules", url: "https://docs.python.org/3/tutorial/modules.html", kind: "official programming tutorial"}
  - {title: "Python language reference — Import system", url: "https://docs.python.org/3/reference/import.html", kind: "official language reference"}
  - {title: "Python standard library — unittest", url: "https://docs.python.org/3/library/unittest.html", kind: "official testing documentation"}
  - {title: "Python standard library — decimal", url: "https://docs.python.org/3/library/decimal.html", kind: "official numeric documentation"}
---
A growing program becomes difficult to change when every function reads global variables, opens files, formats output and implements business calculations simultaneously. **Modular programming** assigns distinct responsibilities to functions and modules and makes their collaboration explicit. It precedes object-oriented architecture, dependency inversion and distributed services: a small procedural program can be well designed with no classes at all. Python modules are namespaces loaded through the import system, and their public names form a practical interface for callers [1][2].

## Functions, modules and program boundaries

A function abstracts a computation behind a name and a contract. A module groups related definitions into a separate source file and namespace. A package organizes modules under a common import path. These are different levels of organization: putting 40 unrelated functions into one file does not make them cohesive, and splitting a three-line calculation across many packages does not automatically improve it.

A useful boundary has a concise purpose, input assumptions, returned results and stated side effects. A parser interprets raw representations. A calculator works on validated values. A presenter formats a result. A composition or entry-point function connects these stages with actual input and output. Separating them lets each component be understood and tested without reproducing the entire application.

## Cohesion versus coupling

**Cohesion** asks whether elements of one module belong to one understandable responsibility. **Coupling** asks how much one component needs to know about another. High cohesion and limited coupling usually make change more local, but neither term is a score that can be inferred from file count. A module that parses text, connects to a database, sends email and calculates averages has multiple reasons to change. A module exposing a single operation that delegates trivial work through 15 layers can have excessive indirection.

Coupling includes more than imports. Two modules may import only one another's small functions while still share undocumented global state or depend on output formatting details. Conversely, importing a standard library module does not imply harmful coupling. The key question is whether a change to one responsibility forces unrelated consumers to change.

## Pure functions and side effects

A **pure function** returns the same result for the same input values, under its declared evaluation model, and produces no observable side effect. Mathematical calculations and validation are good candidates. Reading a file, printing, making network requests and updating external state are side effects. Not every function can or should be pure: applications must interact with the world. The engineering choice is to keep effects visible at narrow boundaries and ordinary computations independent of them.

A function that reads `global current_temperature` has a hidden input. A function that logs, mutates an argument and returns a number has three observable outcomes rather than one. Prefer explicit parameters and return values when possible. A mutable argument is not copied merely because the callee has a different parameter name; Python's object-binding rules still apply.

## Derive a small program from one requirement

Suppose a classroom exercise processes decimal temperature readings, computing their minimum, maximum and arithmetic mean. Input consists of a finite sequence of nonblank decimal strings. Empty input is invalid for a mean; NaN and infinities are not measurements in this model. The core computations should not open a file or print directly, so they can be reused from a command-line program, notebook or web request handler. This design deliberately omits units, sensor calibration and time-series statistics, which would require additional contracts.

We identify four responsibilities: parse text, compute values, render a summary and coordinate the actual read/write dependencies. The orchestrator receives callable arguments for reading and writing. This is straightforward parameter passing, not a requirement to introduce abstract classes or a dependency-injection framework.

~~~python
from decimal import Decimal, InvalidOperation

def parse_readings(lines):
    """Parse one decimal reading per line, without I/O side effects."""
    if not isinstance(lines, (list, tuple)):
        raise TypeError("lines must be a sequence")
    values = []
    for raw in lines:
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("invalid reading")
        try:
            number = Decimal(raw.strip())
        except InvalidOperation as exc:
            raise ValueError("invalid decimal") from exc
        if not number.is_finite():
            raise ValueError("non-finite reading")
        values.append(number)
    return tuple(values)

def summarize_readings(readings):
    """Return a value summary, never mutate input."""
    if not readings:
        raise ValueError("empty readings")
    total = sum(readings, Decimal("0"))
    return (min(readings), max(readings), total / len(readings))

def render_summary(summary):
    low, high, mean = summary
    return "min=" + str(low) + "; max=" + str(high) + "; mean=" + str(mean)

def run_report(read_lines, write_text):
    """Orchestrate data access; dependencies are passed explicitly."""
    readings = parse_readings(read_lines())
    result = render_summary(summarize_readings(readings))
    write_text(result)
    return result

messages = []
result = run_report(lambda: ["18.5", "20.0", "21.5"], messages.append)
assert result == "min=18.5; max=21.5; mean=20.0"
assert messages == [result]
assert parse_readings(["1", "2"]) == (Decimal("1"), Decimal("2"))
for invalid in (["NaN"], [""], ["abc"]):
    try:
        parse_readings(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid reading accepted")
try:
    summarize_readings(())
except ValueError:
    pass
else:
    raise AssertionError("empty summary accepted")
~~~

## Verify each boundary independently

`parse_readings` has a representation contract: accept a list or tuple of nonblank decimal strings and return an immutable tuple of finite Decimal values. Its errors reject invalid input before calculation. `summarize_readings` assumes validated Decimal values and raises on an empty sequence; it does not parse, print or mutate. `render_summary` concerns representation only. `run_report` performs orchestration and delegates actual I/O to the supplied callables.

This decomposition allows a test to pass a lambda as a fake reader and `messages.append` as a fake writer. No real file or network is required. More importantly, the fake writer makes it possible to assert **exactly one output** and inspect the string. Unit tests for parsing and arithmetic should not need the orchestrator at all. Real integrations would then test whether their file or network adapters satisfy these same interfaces [3].

## Complexity and resource accounting

For n readings and a total of L input characters, parsing requires work proportional to L for bounded-size decimal operations, plus O(n) references to parsed values. Computing min, max and sum makes a bounded number of passes over n values, so O(n) arithmetic operations, again with operand precision affecting costs [4]. The output format has constant structural size but value representations may be arbitrarily long. The entire pipeline retains O(n) Decimal objects in this example. A streaming solution could maintain running sum, minimum, maximum and count with O(1) number of retained values, but would change which stage owns validation and error handling.

Avoid saying that pure functions are always faster or that allocating a module guarantees performance. Their primary benefit here is **local reasoning and testability**. Profiling and memory constraints may justify combining passes later, provided behavior remains testable.

## Interfaces, import direction and dependency cycles

Suppose the code lives in `parsing.py`, `statistics.py`, `presentation.py` and `main.py`. A straightforward dependency direction is main → parser/statistics/presentation; the pure core modules do not import `main`. If presentation imports main for configuration while main imports presentation, a circular import may encounter partially initialized module state, depending on import order and execution [2]. Move shared constants to a lower-level module or pass them as parameters instead of working around cycles with hidden imports.

An interface need not be an inheritance tree. Here the reader is any zero-argument callable returning a sequence and the writer any callable accepting a string. If these contracts become complex, define a protocol or type annotation and add stronger runtime validation at external entry points. Python annotations do not enforce all runtime types automatically. Keep the interface as small as the consumer needs.

## Counterexamples and refactoring practice

Making every one-line arithmetic expression a separate module scatters a coherent operation. For a throwaway script with three readings, direct code can be easier to understand than four abstractions. Conversely, a single function containing file opening, parsing, calculations and output formatting is hard to reuse or test without side effects. Choose boundaries in response to concrete variation: a new input format should not require rewriting the mean; a new display format should not affect parsing.

A refactor should preserve an explicit observable contract. Compare results, errors, output count and mutation behavior before and after extraction. Adding a new method is not automatically improvement if it changes when exceptions are raised or which invalid values are accepted. Keep the original tests as regression evidence.

## Exercises and verification

1. Rewrite the program as four physical modules and draw only their permitted import arrows. Explain why none of the pure modules should import `main`.
2. Change output to JSON. Identify which module should change and why the arithmetic remains unaffected.
3. Add a CSV reader adapter without touching `summarize_readings`; state the expected input contract of the parser.
4. Construct a fake writer that records calls; prove `run_report` writes exactly once for valid input and not at all for a parse error.
5. Replace the entire in-memory list with an iterator and implement a streaming accumulator. Explain how empty input and late parse errors affect the contract.
6. Compare two module designs for a five-line script and a 10,000-line application, explaining the costs of premature abstraction.

Continue with [program semantics](/en/topics/programming-semantics-contracts/), [cohesion and coupling](/en/topics/clean-code-cohesion-coupling/) and [object-oriented design](/en/topics/object-oriented-design/).