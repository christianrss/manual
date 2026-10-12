---
id: error-handling-contracts-resource-cleanup
title: "Error handling: contracts, exceptions and resource cleanup"
description: "Distinguish domain failures and programmer mistakes, preserve exception causes and manage resource lifetimes."
category: engineering
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-semantics-contracts, modular-programming-interfaces]
sources:
  - {title: "Python tutorial — Errors and exceptions", url: "https://docs.python.org/3/tutorial/errors.html", kind: "official Python tutorial"}
  - {title: "Python standard library — contextlib", url: "https://docs.python.org/3/library/contextlib.html", kind: "official Python documentation"}
  - {title: "Python language reference — The with statement", url: "https://docs.python.org/3/reference/compound_stmts.html#the-with-statement", kind: "official language reference"}
  - {title: "Python standard library — Built-in exceptions", url: "https://docs.python.org/3/library/exceptions.html", kind: "official Python documentation"}
---
Correct programs do more than return results for valid input. They also define what happens when input is malformed, a resource is unavailable or the caller violates a programming contract. Treating every failure as zero or ignoring it entirely makes success indistinguishable from failure. Error handling must be designed alongside the ordinary function interface [1][4].

## Domain errors and programming errors

A contract should specify accepted types, ranges, side effects, successful return values and predictable failures. Supplying a list when a string was required represents a wrong argument type. Supplying a string that cannot be interpreted as a temperature reading is instead invalid domain data. A program can represent the first by TypeError and the second by a domain-specific ValueError subclass.

The distinction matters because different callers may react differently. Invalid domain data could be rejected and reported to its source. A programming error might indicate that an internal interface was used incorrectly and should normally be repaired in code. Both must remain distinguishable from a legitimate zero temperature.

Never infer that exceptions are the only possible mechanism: a language can use explicit result values or sum types. What matters is a precise separation between successful and rejected operations and a clear rule governing caller-owned state.

## Catch exceptions at meaningful boundaries

Catch an exception where there is a defensible recovery action or valuable additional context. For example, conversion of a temperature string to an integer can produce ValueError. A parser can translate that into ReadingError and preserve the original cause using explicit exception chaining. An aggregator can then report which line contained the invalid value [1][4].

Catching every possible exception and returning a fabricated default conceals defects. Capturing a failure only to rethrow an unrelated generic message destroys useful evidence. Tracebacks are more informative when they preserve the low-level cause and describe the higher-level operation that failed.

A function that cannot recover may correctly propagate an exception. Retry should not be automatic: malformed numeric input generally remains malformed, whereas transient external resource failures may warrant a separate bounded retry policy.

## Worked example: bounded measurement records

Consider lines formatted as STATION,CENTIDEGREES. Station identifiers contain two through eight ASCII uppercase letters, and the signed integer measurement must fall within [-4000,8500]. Surrounding whitespace is accepted, but a record must contain exactly two comma-separated fields. The values represent hundredths of a degree to avoid introducing floating-point rounding into this example.

A parser validates the textual structure and returns station and integer measurement. A separate aggregator consumes a finite iterable of records, calculates totals by station and returns a new dictionary. Neither component modifies the caller's input strings. The aggregator adds a record number when it encounters a domain error.

The example will include independent checks of legal boundaries, invalid numeric text, wrong types and missing fields. It does not invent missing measurements or attempt to infer a station from an invalid identifier.

~~~python
import io

class ReadingError(ValueError):
    """Invalid temperature reading."""

def parse_reading(text):
    if type(text) is not str:
        raise TypeError("record must be text")
    fields = text.strip().split(",")
    if len(fields) != 2:
        raise ReadingError("expected STATION,CENTIDEGREES")
    station, value_text = (field.strip() for field in fields)
    if (not 2 <= len(station) <= 8 or not station.isascii()
            or not station.isalpha() or not station.isupper()):
        raise ReadingError("station must be uppercase ASCII letters")
    try:
        value = int(value_text)
    except ValueError as exc:
        raise ReadingError("temperature must be an integer") from exc
    if not -4000 <= value <= 8500:
        raise ReadingError("temperature outside permitted range")
    return station, value

def sum_by_station(records):
    totals = {}
    for line_no, record in enumerate(records, 1):
        try:
            station, value = parse_reading(record)
        except ReadingError as exc:
            raise ReadingError(f"record {line_no}: {exc}") from exc
        totals[station] = totals.get(station, 0) + value
    return dict(sorted(totals.items()))

with io.StringIO("SP,120\nSP,150\nRJ,-50\n") as stream:
    assert sum_by_station(stream) == {"RJ": -50, "SP": 270}
assert stream.closed

bad_stream = io.StringIO("SP,120\nRJ,invalid\n")
try:
    with bad_stream:
        sum_by_station(bad_stream)
except ReadingError as exc:
    assert "record 2" in str(exc)
else:
    raise AssertionError("invalid input accepted")
assert bad_stream.closed
~~~

## Derive the exception-safety property

After processing i accepted records, the local totals dictionary holds the sum of values of each station in precisely those first i records. This statement is the loop invariant. Initially the mapping is empty, and adding the next valid station measurement maintains the property. At normal termination the returned mapping therefore satisfies the entire input's postcondition.

If record i is invalid, the function raises without returning the partly constructed local dictionary. The caller receives no incomplete summary. That is an observable exception-safety guarantee, but it is not a general rollback mechanism: a generator that supplies records may mutate global variables or send requests while yielding values. The aggregator cannot undo those side effects.

The strongest truthful contract here is that the function does not publish a partial result or mutate the supplied text records. More powerful claims require control over the input source and any external resources involved.

## Cleanup and context managers

Resource cleanup is another independent concern. A file, stream or lock should have an explicit acquisition and release policy. The Python with statement invokes exit behavior when its controlled block finishes normally or when an exception propagates [2][3]. A closable in-memory stream provides a reproducible demonstration: after leaving the block, closed is true even if parsing failed.

However, closing a file does not undo previously written bytes, and releasing a lock does not reverse state mutations performed while it was held. The existence of a with block does not by itself guarantee a transaction. A particular context manager might implement rollback, but that must be its documented behavior.

A finally block is another way to execute cleanup regardless of normal return or exception propagation. Cleanup can itself fail, and a successful close does not necessarily promise persistence across a power loss. Resource release and crash durability are different properties.

## Observability, tests and costs

Tests should assert expected exception classes, causal information, caller-state preservation and successful resource closure. Avoid relying on exact human-oriented message wording unless the message is explicitly part of a protocol. Log unexpected failures at appropriate application boundaries rather than printing potentially sensitive raw records repeatedly at each layer.

If n input records contain L total characters and there are k distinct stations, input parsing takes time proportional to L, dictionary updates take expected O(n), and sorting result keys costs O(k log k). Expected time is O(L+n+k log k), and result state is O(k). This is not an unconditional worst-case bound for hashing, and nonterminating input iterables do not produce a final result.

Counterexamples include returning zero for malformed input, swallowing every exception, exposing partial totals and assuming that a context manager reverses writes. Each violates a different stated contract.

## Exercises and verification

1. Distinguish TypeError caused by a nonstring argument from invalid numeric text.
2. Exercise the exact temperature bounds and reject one value beyond each limit.
3. Prove that a failing third record cannot cause a returned partial dictionary.
4. Confirm that a stream closes when an exception leaves a with statement.
5. Give an example of input generator side effects that this algorithm cannot reverse.
6. State why resource cleanup, logical rollback and crash durability must be considered separately.

Continue with [programming semantics](/en/topics/programming-semantics-contracts/), [safe JSON files](/en/topics/file-io-json-schema-safe-updates/) and [testing contracts](/en/topics/testing-maintainability/).
