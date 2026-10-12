---
id: python-error-contracts-resource-cleanup
title: "Python error contracts: exceptions and resource cleanup"
description: "Specify invalid data, propagate exceptions and verify context-manager cleanup with reproducible source streams."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-semantics-contracts, modular-programming-interfaces]
sources:
  - {title: "Python tutorial — Errors and Exceptions", url: "https://docs.python.org/3/tutorial/errors.html", kind: "official tutorial"}
  - {title: "Python language reference — The with statement", url: "https://docs.python.org/3/reference/compound_stmts.html#the-with-statement", kind: "official language reference"}
  - {title: "Python standard library — contextlib", url: "https://docs.python.org/3/library/contextlib.html", kind: "official library documentation"}
---
A function that produces correct results on valid input but hides failures, reports misleading errors or abandons acquired resources does not have a complete contract. Python offers exceptions and context managers to define **what fails, how the failure propagates and which cleanup actions still occur**. These rules are elementary programming concepts rather than properties of a web framework [1][2].

## Specify success and failure together

The worked example accepts the canonical ASCII decimal representation of a count between zero and 1000. Valid strings include 0, 7 and 1000. Invalid ones include empty text, leading-zero forms such as 07, negative values, 1001 and non-ASCII digits. Such restrictions are application choices: Python integer parsing is more permissive than this particular interface.

A successful parse returns a nonnegative integer. A malformed record raises RecordError, a subclass of ValueError. Distinguishing malformed input from an operating-system read failure matters because a caller may recover differently from each. An error is not a valid count disguised as zero [1].

The contract also states that the parser has no side effects on caller data and never returns a partial result. Choosing accepted input forms first makes positive and negative tests precise.

## Exceptions carry a separate control path

Raising an exception interrupts ordinary evaluation until a matching handler is found. A handler can recover, re-raise or add context. Catching every Exception and returning a default may hide programming mistakes, resource failures and corrupt data beneath one plausible value.

The parser raises a named error when its data contract is violated. The surrounding reader catches exactly that type to prepend the line number. It uses exception chaining so the original error remains available. Errors from opening or reading files should propagate with their meaning rather than being rewritten as malformed decimal input [1].

Broad handling is appropriate only at a well-defined outer boundary that can report failure without destroying its diagnostic. The mere presence of a try statement does not mean adequate recovery.

## Side effects and partial work

Suppose multiple lines contain counts. The reader maintains a local accumulator. The invariant after k accepted records is that the accumulator equals their sum, and each value lies between zero and 1000. Processing a valid next record preserves the invariant.

When a line is invalid, the function raises before returning a total. The caller never receives a partially committed result. This does **not** imply external database writes or file writes would be rolled back: local variables and persistent effects have different failure semantics.

The empty stream has total zero under the chosen contract. Each nonempty line contains one count and optionally a normal line ending. An empty line between records is invalid. Numbering lines from one improves diagnostics without changing the input source.

## Context managers delimit resource ownership

A context manager has entry and exit behavior. The with statement calls its exit method when a controlled block completes or raises, provided the manager was successfully entered [2]. An ordinary file manager normally closes the file. A lock manager can release a lock. The action still must be implemented correctly.

A context manager can suppress an exception using its exit return value. Seeing with in the source does not prove every error propagates. Resource release and exception suppression are distinct obligations. The contextlib module supplies utilities to implement lifecycle patterns [3].

The reader receives a factory producing a context manager that yields lines. Tests can inject StringIO, while a real application can inject a function that opens a file. This separates record validation from filesystem availability and permits cleanup testing with a spy.

## Executable example with error chaining

The implementation rejects non-string lines rather than silently converting them. It validates canonical decimal text and range before adding each value. A bad second line raises an error containing the position and links to the original cause.

~~~python
from io import StringIO

class RecordError(ValueError):
    """A record violates the count contract."""

def parse_count(text):
    if (type(text) is not str or not text or len(text) > 4
            or not text.isascii() or not text.isdecimal()
            or (len(text) > 1 and text[0] == "0")):
        raise RecordError("expected canonical ASCII decimal")
    count = int(text)
    if count > 1000:
        raise RecordError("count exceeds 1000")
    return count

def total_from_source(factory):
    total = 0
    with factory() as lines:
        for number, line in enumerate(lines, 1):
            if type(line) is not str:
                raise TypeError("text lines required")
            record = line.removesuffix("\n").removesuffix("\r")
            try:
                total += parse_count(record)
            except RecordError as exc:
                raise RecordError(f"line {number}: {exc}") from exc
    return total

assert total_from_source(lambda: StringIO("4\n9\n0\n")) == 13
assert total_from_source(lambda: StringIO("")) == 0
try:
    total_from_source(lambda: StringIO("4\n01\n"))
except RecordError as exc:
    assert "line 2:" in str(exc)
    assert isinstance(exc.__cause__, RecordError)
else:
    raise AssertionError("invalid record accepted")
~~~

The reader accepts text lines, not arbitrary binary chunks. A caller must select its decoding policy at the file boundary. A source yielding an object other than a string triggers TypeError, signaling misuse of the source interface rather than a malformed decimal record.

## Correctness, costs and failure boundaries

Parsing one record checks at most four ASCII characters. With n input characters distributed over r records, processing performs O(n+r) basic work, with O(1) auxiliary scalar variables under bounded-size arithmetic assumptions. Stream buffering is external to the accumulator and depends on the supplied source.

The loop invariant proves the returned total equals the sum of all valid records. Invalid data cannot return a total because the exception exits the loop. The with semantics guarantee invocation of the exit method after successful entry, even when parsing fails. Tests should verify **observable cleanup**, since a broken custom manager could still fail to close its resource.

A factory can itself raise before providing a context manager; in that case the reader has not entered a managed resource. Any resources partially acquired by that factory are its own responsibility.

Finally blocks also express cleanup but can themselves raise, obscuring the original error. A context manager does not guarantee transactional rollback, and closing a file does not guarantee crash-consistent persistent bytes. Those are separate storage contracts.

## Exercises and verification

1. Classify 0, 07, 1001, empty text and non-ASCII numeral characters using the explicit contract.
2. Trace the accumulator before an invalid third line and explain why no total is returned.
3. Create a context-manager spy that records entry and exit for both success and failure.
4. Make its exit method suppress exceptions and explain why that could hide malformed data.
5. Supply an iterator that raises OSError and confirm it is not converted to RecordError.
6. Explain the difference between releasing a resource and making previously written data durable.

Continue with [programming semantics](/en/topics/programming-semantics-contracts/), [files and JSON](/en/topics/python-files-utf8-json-validation/) and [testing strategies](/en/topics/testing-strategies/).
