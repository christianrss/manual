---
id: python-files-utf8-json-validation
title: "File and data fundamentals: bytes, UTF-8, JSON schemas and safe boundaries"
description: "Read bounded UTF-8 JSON files, reject ambiguous or malformed data and write validated records with explicit failure limits."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [python-error-contracts-resource-cleanup, data-types-bytes-and-representation]
sources:
  - {title: "Python standard library — json", url: "https://docs.python.org/3/library/json.html", kind: "official library documentation"}
  - {title: "Python Unicode HOWTO", url: "https://docs.python.org/3/howto/unicode.html", kind: "official language guide"}
  - {title: "Python standard library — io", url: "https://docs.python.org/3/library/io.html", kind: "official library documentation"}
---
Files and structured data connect a running program to the outside world. To use them correctly, distinguish **bytes on disk, decoded text, structured syntax and validated domain data**. Each stage has a different failure mode. Successfully decoding JSON does not mean the received object has the correct fields, types or values. This chapter implements a finite, testable boundary before addressing databases, network messages or operating-system durability [1][2].

## Bytes are not automatically characters

A file consists of bytes. Text is produced by decoding those bytes according to a selected character encoding. UTF-8 is a variable-width encoding for Unicode characters; an accented letter may use more than one byte. Indexing bytes is therefore not the same as indexing Unicode code points or human-perceived grapheme clusters [2].

An invalid UTF-8 sequence should not silently be replaced when the interface demands exact text. Use strict decoding so malformed input triggers UnicodeDecodeError. Do not infer encoding from the file extension alone; the format contract must specify it. A byte-order mark is not required for UTF-8 and the chosen JSON decoder may reject one at the document start.

Text-mode I/O can also translate newline representations depending on configuration. Binary reading first and explicit UTF-8 decoding make the byte boundary visible, though a simple text-mode reader with an explicit encoding is appropriate in many ordinary applications [3].

## Serialization has syntax and data contracts

JSON provides strings, numbers, Boolean values, null, arrays and objects. It cannot directly represent arbitrary Python objects or guarantee a domain schema. For this exercise, a document contains exactly two top-level fields: version equal to integer 1 and records containing at most 100 entries. Each record has exactly id and count.

An id must have one to 32 lowercase ASCII letters, digits, hyphens or underscores. Ids must be unique. A count must be a Python integer from 0 to 1000, excluding Boolean values. These are *application invariants*, not universal JSON requirements. A parser that accepts a JSON Boolean for count because bool is an int subclass in Python would violate the declared schema.

The schema rejects unknown fields rather than ignoring them. A version field allows future incompatible formats to be distinguished instead of silently interpreted as today's data. Other formats may require optional fields or different forward-compatibility choices; they need an explicit contract.

## Duplicate fields and nonfinite numbers

Python's standard JSON decoder ordinarily accepts repeated object names and retains the last value. Such a choice can be ambiguous across producers and consumers. The object_pairs_hook option receives object entries in order, allowing the application to reject duplicate keys *before* constructing an object [1].

The Python JSON decoder also accepts nonstandard NaN and Infinity tokens by default. JSON's interoperable number syntax does not include them. The parse_constant hook can reject these spellings, while allow_nan=False prevents the encoder from outputting nonstandard floating values [1].

Rejecting duplicates and constants does not replace domain validation. A syntactically correct value can still have a wrong version, duplicated record IDs, too many records, invalid character sets or unsupported field types.

## Bound memory before decoding

Untrusted files can be too large for an application. The example reads at most MAX_BYTES+1 bytes. If the length exceeds MAX_BYTES, it rejects the file rather than trying to parse its entire contents. This is a bounded-input strategy, not a promise to resist every resource-exhaustion attack in Python's JSON parser [1].

With a maximum of 16384 bytes and 100 records, input size is finite and easy to test. The function still allocates Python objects proportional to accepted input and incurs decoder overhead. Actual memory use exceeds the raw byte length; no precise runtime memory cap is inferred from the input limit alone.

The example distinguishes invalid bytes or malformed JSON, which become DocumentError, from OSError failures opening or reading the file. The latter are environmental errors and remain observable in their original type.

## Implement validation and round-trip I/O

The loader reads bytes with a context manager, checks size, decodes strict UTF-8 and parses JSON with strict hooks. Validation reconstructs the allowed data in a new object, avoiding accidental reliance on unknown fields. The writer validates and serializes **before** opening the destination, so malformed in-memory data cannot truncate an existing file.

~~~python
import json
from pathlib import Path

MAX_BYTES = 16384

class DocumentError(ValueError):
    pass

def unique_fields(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise DocumentError("duplicate object field")
        obj[key] = value
    return obj

def reject_constant(value):
    raise DocumentError("nonfinite numeric token")

def validate_document(doc):
    if (type(doc) is not dict or set(doc) != {"version", "records"}
            or type(doc["version"]) is not int or doc["version"] != 1):
        raise DocumentError("invalid document header")
    records = doc["records"]
    if type(records) is not list or len(records) > 100:
        raise DocumentError("invalid record collection")
    seen = set()
    normalized = []
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    for record in records:
        if type(record) is not dict or set(record) != {"id", "count"}:
            raise DocumentError("invalid record fields")
        ident, count = record["id"], record["count"]
        if (type(ident) is not str or not 1 <= len(ident) <= 32
                or any(ch not in alphabet for ch in ident) or ident in seen
                or type(count) is not int or not 0 <= count <= 1000):
            raise DocumentError("invalid record value")
        seen.add(ident)
        normalized.append({"id": ident, "count": count})
    return {"version": 1, "records": normalized}

def read_document(path):
    with open(path, "rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise DocumentError("file too large")
    try:
        text = raw.decode("utf-8")
        parsed = json.loads(text, object_pairs_hook=unique_fields,
                            parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocumentError("invalid UTF-8 JSON") from exc
    return validate_document(parsed)

def write_document(path, doc):
    checked = validate_document(doc)
    raw = (json.dumps(checked, ensure_ascii=False, sort_keys=True,
                      allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise DocumentError("serialized file too large")
    with open(path, "wb") as destination:
        destination.write(raw)

example = {"version": 1, "records": [{"id": "a-1", "count": 7}]}
assert validate_document(example) == example
~~~

The example uses binary file operations deliberately so the encoding step is explicit. It does not normalize Unicode identifiers because the selected identifier contract uses only ASCII. If human names are added later, text normalization and length semantics must be defined separately.

## Correctness invariants and round trips

After validation, each record has exactly the allowed fields, valid ranges and a unique identifier. The seen set contains precisely the identifiers accepted so far. A new record is rejected if its identifier already belongs to seen, preserving uniqueness by induction.

The writer constructs a normalized object before serialization; the JSON encoder transforms it to UTF-8 bytes. The reader reverses these steps. For any accepted document whose serialized byte length fits MAX_BYTES, a write/read round trip yields an equal validated structure, assuming successful I/O and no intervening modification. The same **object identity** is not preserved because deserialization constructs new objects.

For n input bytes and r records, decoding, parsing and validation require work proportional to the parsed representation, with O(n+r) additional memory in the usual bounded-field model. String and dictionary allocations carry overhead. A set detects duplicate IDs in expected constant time per lookup under the ordinary hash-table model; adversarial collision behavior and interpreter costs are outside a simplistic constant-time guarantee.

## What writing a file does not guarantee

Opening a file with write mode may truncate its previous contents. Validation-before-open protects against semantic input failures, but **not** against storage errors or a crash after truncation and before completion. Neither closing the file nor successful writing alone proves atomic replacement or durable persistence.

A production replacement strategy may use a temporary file, carefully scoped permissions, flushing and an atomic rename on a filesystem offering the required guarantees. Its correctness depends on platform and crash model. The operating-systems chapter on file descriptors and fsync covers the relevant boundaries; this lesson makes no claim of crash-safe replacement.

## Exercises and verification

1. Save and load a valid document in a temporary directory; compare the decoded structure.
2. Inject duplicate JSON object keys and verify the loader rejects them.
3. Test a Boolean count, nonfinite numeric token, invalid UTF-8 sequence and an unknown field.
4. Place invalid in-memory data beside an existing valid file and confirm rejection leaves that file unchanged.
5. Write a document larger than MAX_BYTES and verify the loader rejects it.
6. Explain why decoding JSON, validating a schema and guaranteeing atomic file replacement are three different responsibilities.

Continue with [error contracts](/en/topics/python-error-contracts-resource-cleanup/), [data representation](/en/topics/data-types-bytes-and-representation/) and [file descriptors and durability](/en/topics/file-descriptors-buffering-fsync/).
