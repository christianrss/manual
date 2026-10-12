---
id: versioned-bytecode-serialization
title: "Versioned Bytecode Serialization, Integrity Checks and Verified Loading"
description: "Design a bounded, versioned bytecode wire format with deterministic JSON, integrity checking, strict decoding and mandatory VM verification."
category: foundations
difficulty: advanced
updated: 2026-10-11
prerequisites: [lexical-addresses-bytecode-verification]
sources:
  - {title: "RFC 8259 — The JavaScript Object Notation (JSON) Data Interchange Format", url: "https://www.rfc-editor.org/rfc/rfc8259", kind: "Internet standard"}
  - {title: "Python Standard Library — json", url: "https://docs.python.org/3/library/json.html", kind: "official standard library documentation"}
  - {title: "Python Standard Library — hashlib", url: "https://docs.python.org/3/library/hashlib.html", kind: "official standard library documentation"}
  - {title: "Java Virtual Machine Specification — Verification of Class Files", url: "https://docs.oracle.com/javase/specs/jvms/se25/html/jvms-4.html#jvms-4.10", kind: "official virtual machine specification"}
---
The [lexical-slot compiler and verifier](/en/topics/lexical-addresses-bytecode-verification/) operate on immutable Python objects in memory. That is enough to compile and execute during one process, but it does not define how to write a program to disk, read it in another process, distinguish incompatible compiler releases, or reject damaged data before execution. This chapter supplies a **bounded, versioned wire representation** for the existing educational VM. It deliberately separates four concerns: serialization, format validation, accidental-corruption detection and bytecode verification [1][2][4].

A file format is a contract between a producer and a consumer. Merely converting a dataclass to a dictionary does not establish that contract: internal Python object identity, tuple types, recursive function descriptors and opcodes all need explicit representations and limits. The new implementation remains **opt-in**. It does not modify the previous instruction set, runtime behavior or language syntax.

## The v1 envelope and deterministic encoding

The format consists of a UTF-8 JSON object with precisely four keys: `magic`, `version`, `sha256` and `payload`. Its magic marker is `CHRIS-VM-SLOT` and the initial integer version is **1**. The payload contains exactly `result_type` and `code`. A code object contains captured lexical scope descriptors, parameter descriptors, its return type and a sequence of instructions. An instruction is a three-element array: opcode, operand and nonnegative source offset. Nested closures use nested code objects rather than executable host-language source.

The encoder uses sorted JSON object keys, compact separators and ASCII escape sequences, so the same verified program produces the same byte sequence under this defined encoder. This is a **project-specific canonicalization convention**, not a claim of conformance with the JSON Canonicalization Scheme (JCS). JSON itself permits a wider range of equivalent lexical spellings [1]. Stable encoding is useful for regression fixtures, caching and computing an unambiguous digest.

Static types receive explicit tags: `["base","Int"]`, `["base","Rat"]`, `["base","Bool"]` or `["fn",[argument types],result type]`. Lexical slots carry the name, type and three Boolean fields describing mutability, recursion and initialization. A lexical address `(distance,index)` becomes a two-element JSON array and is converted back to a strict integer tuple by the loader. This prevents an incidental Python class layout from silently becoming part of the persisted format.

## Decode boundaries and rejecting ambiguous input

A decoder must not assume that a valid JSON document is valid bytecode. The entry point `load_bytecode` first requires genuine `bytes` and caps the document size at **131,072 bytes**. Parsing requires valid UTF-8, rejects duplicated JSON object keys and does not accept floating-point or non-finite numeric literals. Integer text is limited to 80 decimal digits. Field lists are exact: an unexpected top-level field, a missing code field or an unrecognized type tag is rejected. Array lengths, code nesting, total instructions and total code objects are bounded.

The decoder reconstructs `SlotInfo`, `FunctionType`, `SlotCode` and `VerifiedProgram` through explicitly enumerated constructors. It never calls `pickle`, `eval`, `exec` or imports a function named in the file. Nested closure code is reconstructed as data. Unsupported magic markers or format versions fail immediately; there is no speculative fallback from v2 to v1. Version negotiation would require a separate, deliberate compatibility design.

The implementation also validates argument shapes by opcode: `LOAD_SLOT` and `STORE_SLOT` require exactly two nonnegative integer coordinates, `PUSH_BOOL` requires a Boolean, jump and call operands require bounded integers, and nested `CLOSURE_SLOT` contains a code object. A malicious payload may be valid JSON and pass these structural checks but still be **invalid VM code**; therefore decoding is never the final acceptance step.

## Checksum integrity is not authentication

The encoder computes a SHA-256 digest of the canonical **payload**, then includes its lowercase hexadecimal digest in the outer envelope [3]. The decoder recomputes the digest and uses a constant-time comparison operation on the encoded hexadecimal strings. If ordinary storage corruption changes a byte in the payload without updating the digest, the decoder rejects it. That is an **integrity checksum**, not proof that a trusted author produced the file.

An attacker able to change both payload and digest can calculate a new SHA-256 value. Neither the digest nor its constant-time comparison prevents this. Authenticating a bytecode producer would require a separate trust model and a keyed MAC or digital signature with securely managed verification keys. The chapter does not implement authentication, confidentiality, process isolation or a secure plugin/runtime loader. Keep the difference between corruption detection and origin authentication explicit whenever a checksum appears in a software architecture.

## Mandatory bytecode verification and execution

After decoding, the loader invokes the already implemented `verify_slots`, which abstract-interprets reachable instruction paths, checks typed operand stacks, lexical addresses, scope transitions, return types, control-flow joins and restricted recursive initialization [4]. Only a program that passes this check is returned to the caller. The execution entry point `run_slots` also verifies before dispatch; the duplicate validation is intentional defense in depth. A regenerated SHA-256 checksum cannot make `ADD` with an empty stack, or an out-of-bounds `LOAD_SLOT`, pass the verifier.

The [versioned bytecode module](https://github.com/christianrss/manual/blob/main/examples/python/versioned_bytecode.py) provides `dump_bytecode`, `load_bytecode`, `evaluate_wire` and `WireFormatError`. This executable example performs the full round trip:

~~~python
from fractions import Fraction
from examples.python.lexical_slot_verifier import compile_slots, run_slots
from examples.python.versioned_bytecode import (
    dump_bytecode, load_bytecode, WireFormatError,
)

source = ("let rec fact:Fn(Int)->Int="
          "fn(n:Int)->Int=>if n<2 then 1 else n*fact(n-1) "
          "in fact(5)")
blob = dump_bytecode(compile_slots(source))
restored = load_bytecode(blob)
assert run_slots(restored) == Fraction(120)
assert blob == dump_bytecode(restored)

try:
    load_bytecode(blob.replace(b'"version":1', b'"version":2'))
    assert False, "unsupported format versions must fail"
except WireFormatError:
    pass
~~~

The [independent wire contracts](https://github.com/christianrss/manual/blob/main/tests/test_versioned_bytecode_contracts.py) compare decoded execution to the earlier stateful language's separate direct AST evaluator and to the prior slot program. They also recompute checksums over **intentionally invalid programs** to prove that schema and VM verification, rather than SHA-256 alone, reject bad addresses, unknown opcodes, malformed branch structures and incompatible result types.

## Bounds, residual risks and compatibility policy

Encoding a program requires visiting each code object and instruction, while serializing its lexical type descriptors; let m be emitted instructions and s be serialized descriptor fields. Its data traversal is proportional to the encoded representation size, **not just m**. Hashing and JSON encoding also process the serialized bytes. The size cap is 128 KiB, and the educational decoder has explicit limits for code objects and instruction count. These limits reduce exposure to malformed inputs but are not a proof of bounded CPU or RAM usage in an adversarial deployment.

Most importantly, the source language still supports exact arbitrary-precision rational arithmetic and recursive calls. One valid instruction may perform expensive mathematical work; a structurally verified program can still hit the VM's instruction/frame budgets or raise division by zero. Code objects remain in-memory Python data, not signed executable artifacts. The decoder does not implement a cryptographic signature, streaming parser, compression, cross-version migration, bytecode optimizer or OS-level sandbox.

The format policy is deliberately conservative: version **1** rejects unknown fields and unknown versions. A future v2 must document whether it introduces new opcodes, field encodings or verifier invariants. Backward compatibility must be demonstrated by fixtures from genuine previous versions, not assumed from a matching file extension.

## Exercises and verification

1. Explain why two equivalent JSON texts can hash differently without canonicalization. **Check:** whitespace and key order affect raw bytes; this encoder normalizes both in its own convention.
2. Change the payload while leaving the checksum unchanged. **Check:** `load_bytecode` rejects it before reconstructing executable code.
3. Recompute the checksum for code containing `ADD` without operands. **Check:** checksum verification passes, but the typed bytecode verifier rejects stack underflow.
4. Change the format version from 1 to 2. **Check:** the decoder fails; no silent compatibility fallback occurs.
5. Explain why a 128 KiB file cap does not guarantee 128 KiB runtime memory. **Check:** parser objects, nested type descriptions, VM frames and arbitrary-precision values require additional memory.
6. Identify an additional mechanism needed to verify who issued a program. **Check:** a signature or keyed MAC with an explicit trust and key-management design, not an unkeyed SHA-256 checksum.

The next layers are persistent fixture compatibility, authenticated distribution, and a separate heap-reachability model. None of these is implemented by the v1 serializer itself.
