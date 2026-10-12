---
id: file-io-json-schema-safe-updates
title: "File and JSON fundamentals: schema validation and safe replacement"
description: "Read UTF-8 JSON, validate a minimal record schema and replace files using a same-directory temporary file."
category: engineering
difficulty: foundational
updated: 2026-10-12
prerequisites: [error-handling-contracts-resource-cleanup, process-cli-arguments-environment-exit-status]
sources:
  - {title: "Python standard library — json", url: "https://docs.python.org/3/library/json.html", kind: "official Python documentation"}
  - {title: "Python standard library — pathlib", url: "https://docs.python.org/3/library/pathlib.html", kind: "official Python documentation"}
  - {title: "Python standard library — tempfile", url: "https://docs.python.org/3/library/tempfile.html", kind: "official Python documentation"}
  - {title: "Python standard library — os.replace", url: "https://docs.python.org/3/library/os.html#os.replace", kind: "official Python documentation"}
---
Many introductory programs store data in JSON before using a database. This is an opportunity to learn a complete **file contract**, not merely to call json.dump and hope the result is correct. A file has an encoding, a serialization format, a schema, failure modes and a replacement policy. Each property matters even for a small local application [1][2].

## Separate bytes, text, JSON and domain values

A file on disk contains bytes. Decoding those bytes as UTF-8 produces text, which may or may not contain valid JSON syntax. JSON parsing produces generic values: objects, arrays, numbers, strings, booleans and null. Only then can application validation establish that the result represents a valid domain record [1].

A syntactically valid JSON document is not automatically a valid application document. The value 42 is valid JSON but not a list of notes. A list containing an object with a missing title may parse successfully and still violate the application schema. These levels should be kept separate in code and tests.

The example deliberately supports only a small local JSON document. It is not a network service, SQL database, streaming parser or full implementation of a JSON Schema standard.

## Specify the schema before writing a parser

The application stores a list of note records. Each record has exactly three fields: id, title and completed. The id is a positive exact Python integer no larger than one million. The title is a nonempty string of at most 80 characters, with no leading or trailing whitespace. The completed field is an actual Boolean value. All identifiers within one document must be unique.

Exact types matter. In Python, bool is a subclass of int, so a loose isinstance(value, int) check would wrongly accept true as an id. A schema checker must reject extra or missing fields if the interface promises an exact structure. Empty lists are permitted, but null and arbitrary JSON objects are not valid top-level values.

The schema returns newly constructed dictionaries and a new list to prevent validation from mutating the caller's original containers. Strings, integers and booleans are immutable values under the chosen model.

## Read through a context manager and validate

A file reader opens a path with explicit UTF-8 decoding and closes the handle when leaving a with block [2]. JSON syntax errors should be reported separately from application schema errors: one means the representation cannot be parsed; the other means it parsed but does not satisfy the contract.

Python's JSON decoder can accept duplicate object names by keeping one value. That creates ambiguity for records carrying identifiers or flags. This example uses an object-pairs hook to reject duplicate object keys explicitly. It also rejects the nonstandard NaN and Infinity tokens through a parse-constant hook, rather than silently accepting values outside standard JSON [1].

For simplicity the reader limits the textual input to 100000 characters. This is not a byte-limit guarantee or a defense against all resource-exhaustion attacks, but it illustrates bounding work on an intended small local document. Missing files and operating-system read errors propagate as ordinary I/O exceptions.

## Write only validated data

The writer validates the entire document and serializes it to a complete UTF-8 payload **before touching the destination file**. It uses JSON serialization with non-ASCII characters preserved, human-readable indentation and non-finite numerical values rejected. Newline termination is a formatting policy, not a requirement of the JSON format [1].

If serialization or validation fails, the previous file is not opened for overwriting. A new temporary file is then created in the destination directory, its contents are written and the handle is closed. The code uses os.replace to replace the destination name after the temporary file has been successfully written [3][4].

Using the same directory keeps the temporary file on the destination filesystem under normal directory behavior and avoids relying on cross-filesystem rename. On supported POSIX systems, a successful rename replacement is atomic at the namespace level. This is not a promise of durability after power loss.

## Worked example and negative cases

The accompanying executable code defines a schema validator, a JSON reader and a writer that uses a temporary file. Its own assertions write two records, read them back and reject an invalid title before modifying the existing file.

A failure after creating the temporary file but before replacement causes best-effort cleanup of that temporary file. The old destination remains unchanged until replacement is attempted. If replacement itself fails, the caller receives that exception and the temporary name is cleaned up where possible.

This is not a transactional system for multiple files. Two concurrent writers can still overwrite each other's logically valid updates, and neither a temporary file nor rename solves concurrency without a separate policy.

## Atomic naming is not crash durability

The guarantees must be stated precisely. Completing the serialization in memory prevents partially validated content from replacing existing content. Writing to a temporary file prevents an ordinary failed write before replacement from truncating the old destination. Replacing the path changes which complete file a reader opens, subject to filesystem and platform semantics [4].

None of those steps by itself proves the new data will survive sudden power loss. Crash durability may require flushing file data and directory metadata, and those guarantees vary by filesystem and operating system. Those advanced details belong to the separate chapter on descriptors, buffering and fsync.

A path can also be replaced concurrently between a read and a write. If the application must avoid lost updates, introduce version checks, locking or a transactional storage system. This basic example makes no concurrency guarantees.

## Complexity, correctness and test evidence

For a document of n records and L characters, decoding, parsing, validation and serialization require work related to L+n in the ordinary linear-processing model. The uniqueness set needs O(n) space. The writer additionally stores the serialized payload in memory, O(L). Hash-table operations have expected rather than unconditional constant-time behavior.

The correctness invariant of validation is that each accepted prefix contains only records satisfying the field contract, and all identifiers are unique within that prefix. On normal return, the complete new list satisfies the schema. A rejected record causes an exception without modifying the caller's list or the existing file.

Tests must cover invalid JSON, duplicated keys, nonstandard nonfinite values, wrong field types, repeated ids, missing files, Unicode titles and a successful round trip. An injected failure before os.replace should also verify that the previous file is preserved and temporary files are cleaned up.

## Exercises and verification

1. Explain why valid JSON syntax is insufficient to validate an application record.
2. Show why true must not be accepted as an integer identifier.
3. Test duplicate keys, duplicate record identifiers and a title exceeding the length limit.
4. Inject a write failure before replacement and verify that the previous destination remains unchanged.
5. Distinguish atomic pathname replacement from crash durability and concurrent lost updates.
6. Derive the memory cost of loading and reserializing the entire JSON document.

Continue with [exception contracts](/en/topics/error-handling-contracts-resource-cleanup/), [file descriptors and fsync](/en/topics/file-descriptors-buffering-fsync/) and [SQL integrity](/en/topics/relational-model-sql-basics/).
