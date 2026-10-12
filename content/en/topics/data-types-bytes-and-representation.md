---
id: data-types-bytes-and-representation
title: "Data types and representation: integers, bytes, text and precision"
description: "Learn type contracts, integer bounds, byte order, UTF-8 lengths and numeric precision through a reproducible binary record format."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-control-flow-functions]
sources:
  - {title: "Python language reference — Data model", url: "https://docs.python.org/3/reference/datamodel.html", kind: "official language reference"}
  - {title: "Python tutorial — Floating-point arithmetic", url: "https://docs.python.org/3/tutorial/floatingpoint.html", kind: "official language tutorial"}
  - {title: "Python standard library — Binary sequence types", url: "https://docs.python.org/3/library/stdtypes.html#binary-sequence-types-bytes-bytearray-memoryview", kind: "official language reference"}
  - {title: "Python Unicode HOWTO", url: "https://docs.python.org/3/howto/unicode.html", kind: "official language documentation"}
---
Every program operates on **values represented in memory**. A type specifies which values exist and which operations are meaningful; a representation specifies how those values are encoded. Confusing the two explains common defects: a price silently rounded by binary floating-point arithmetic, a Boolean accepted as an integer quantity, a multibyte character counted as one transmitted byte, or a value truncated when converted to a fixed-width integer. These errors arise before an application needs object-oriented design or system architecture.

## Values, types and operations

A value is a mathematical or language-level object such as the integer 7, the Boolean True or the string "Ação". A type supplies operations and interpretation: addition on integers differs from concatenation on strings. Python dynamically associates objects with types rather than requiring a statically declared type for each variable name. Names refer to objects; assigning a different object to a name does not necessarily mutate the old one [1].

An **input contract** restricts a type further. A positive quantity is not merely "an int": it is an integer satisfying quantity > 0, perhaps also having a maximum bound. An identifier may be a string but still reject empty or whitespace-only content. Type annotations can communicate expectations without automatically validating all incoming runtime values. Domain restrictions must be enforced where invalid input may enter.

Consider `isinstance(True, int)`, which is true in Python because bool is a subtype of int [1]. A function that needs an integer measurement but forbids Boolean values may check `type(x) is int`. This is a Python-specific design choice; don't generalize it to all languages or assume subclassing is intrinsically undesirable.

## Integer ranges and fixed-width storage

Mathematical integers have no fixed largest value, but machine representations often allocate a fixed number of bits. An unsigned w-bit integer can represent values from 0 to 2^w−1; a conventional signed two's-complement w-bit integer represents −2^(w−1) to 2^(w−1)−1. For eight unsigned bits, there are 2^8 = 256 possible bit patterns, giving values 0 through 255.

For sixteen unsigned bits, the maximum is 65535. A program writing 65536 into exactly two bytes must reject, saturate, or explicitly wrap it; silently treating these choices as interchangeable can corrupt data. Python's ordinary int is not limited to 16 bits, but serialization into a fixed-width field reintroduces that bound. Specify whether overflows are errors, and apply the same rule in the encoder and decoder.

A bit is one binary digit, and eight bits form a byte in the representation discussed here. When a protocol stores multiple bytes, **byte order** (endianness) defines which byte contains the less-significant bits. For 513, hexadecimal 0x0201, little-endian bytes are [0x01, 0x02], while big-endian bytes are [0x02, 0x01]. Neither ordering is globally correct; the contract must select one [3].

## Floating-point and exact decimal arithmetic

Python float usually represents finite values using binary floating-point. The decimal fraction 0.1 has no finite base-two fractional representation, so an expression such as `0.1 + 0.2 == 0.3` can evaluate to False. This is a property of representation and rounding, not proof that the addition algorithm is wrong [2]. Approximate physical measurements often tolerate controlled rounding errors; exact cents and accounting policies require other choices.

Alternatives include integer counts of the smallest defined unit (for example cents), Decimal arithmetic using strings for exact decimal inputs, and rational numbers where appropriate. Even Decimal cannot supply domain rules such as exchange rates, currency scale or tax law. Converting an already imprecise float into Decimal does not magically recover the originally intended decimal fraction. Prefer representing quantities according to their **meaning and allowed error**, rather than adopting float or int indiscriminately.

## Text is not a raw byte sequence

A Unicode string is a sequence of code points in Python, whereas bytes stores integers in the range 0..255. UTF-8 encodes Unicode text as a variable-length byte sequence [4]. Therefore `len("Ação")` is four code points, while `len("Ação".encode("utf-8"))` is six bytes because both "ç" and "ã" require two UTF-8 bytes. A user-perceived grapheme can even contain multiple code points, so neither count automatically gives the number of visual characters.

Use `str.encode("utf-8")` to obtain bytes and `bytes.decode("utf-8", errors="strict")` to restore text. Invalid byte sequences can be rejected rather than silently replaced. Some systems normalize Unicode text before comparing identifiers; that policy is separate from UTF-8 encoding. Never cut a UTF-8 sequence at an arbitrary byte offset and assume the result still decodes.

## Derive an explicit record format

Define a minimal teaching format for a labeled unsigned counter. Its wire representation is: one byte N, followed by exactly N UTF-8 bytes for a nonempty label, followed by a two-byte unsigned count in little-endian order. Require 1 ≤ N ≤ 255 and 0 ≤ count ≤ 65535. The decoder must consume **the entire record**: accepting extra bytes would make the interpretation ambiguous when the caller assumes there is only one record.

For label "Ação", UTF-8 uses six bytes, so the first byte must be 6. For the count 513, the final bytes are 1 and 2. A valid record is therefore nine bytes total: one length byte, six text bytes and two count bytes. The encoder and decoder must agree on both length and endianness. This is deliberately a small representation exercise, not a production protocol: it has no version field, authentication, checksum or framing across multiple records.

~~~python
def encode_record(label, count):
    if not isinstance(label, str) or not label.strip():
        raise ValueError("invalid label")
    if type(count) is not int or not 0 <= count <= 65535:
        raise ValueError("count outside uint16")
    name_bytes = label.encode("utf-8")
    if not 1 <= len(name_bytes) <= 255:
        raise ValueError("label exceeds byte limit")
    return bytes([len(name_bytes)]) + name_bytes + count.to_bytes(2, "little")

def decode_record(data):
    if not isinstance(data, bytes) or not data:
        raise ValueError("invalid record")
    name_size = data[0]
    if name_size == 0 or len(data) != 1 + name_size + 2:
        raise ValueError("invalid record length")
    label = data[1:1 + name_size].decode("utf-8", errors="strict")
    if not label.strip():
        raise ValueError("invalid label")
    count = int.from_bytes(data[-2:], "little")
    return (label, count)

example = encode_record("Ação", 513)
assert example[0] == len("Ação".encode("utf-8")) == 6
assert example[-2:] == bytes([1, 2])
assert decode_record(example) == ("Ação", 513)
assert decode_record(encode_record("max", 65535)) == ("max", 65535)
for invalid in (b"", b"\x00\x01\x00", b"\x01\xff\x01\x00",
                example + b"\x00", example[:-1]):
    try:
        decode_record(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("malformed record accepted")
for bad in (-1, 65536, True, 1.5):
    try:
        encode_record("item", bad)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid count accepted")
~~~

## Correctness and complexity

The encoder first rejects wrong input types and out-of-range values. It encodes the label to UTF-8, checks the *byte length* and stores the unsigned integer with exactly two bytes. The decoder checks the exact total length, decodes the designated UTF-8 region strictly and interprets the final two bytes using the same endian rule. For any valid label and count, each component has an unambiguous inverse: length identifies the text region, UTF-8 restores the string and the integer conversion restores the exact value.

Let L be the number of UTF-8 bytes in the label. Encoding and decoding each require O(L) byte operations and O(L) output storage for the label or record; the final integer field remains constant-sized. Validation bounds L by 255 in this particular format, but the variable L still explains where the work occurs. A robust decoder never relies on a caller to have allocated a correctly sized buffer.

## Counterexamples and design trade-offs

Converting 65536 modulo 65536 would turn an out-of-range positive quantity into zero. Counting Unicode code points instead of encoded bytes would reject or misparse valid international text. Reading a record without validating its declared length could accidentally merge two messages. Treating invalid UTF-8 as replacement characters might be acceptable for display, but it is not suitable for a format whose round-trip guarantee requires unchanged labels.

The exact layout used here favors simplicity over extensibility. Variable-length integers could reduce small-number storage; an explicit version could support evolution; a checksum could detect accidental corruption. Those mechanisms are not prerequisites for understanding types, bounds and representations. First make the representation invariant clear and test it thoroughly.

## Exercises and verification

1. Derive the signed and unsigned ranges for 8-, 16- and 32-bit integers. Explain which assumptions change when arithmetic uses Python int.
2. Predict and inspect `0.1 + 0.2 == 0.3`. Then perform decimal arithmetic with values constructed from strings [2].
3. Encode labels containing an accented letter and a combining sequence. Count code points, UTF-8 bytes and user-perceived characters separately.
4. Write a decoder that rejects truncated records, oversized records, invalid UTF-8 and a zero-length label. Explain why each rejection is a contract requirement.
5. Change the count field to big-endian and demonstrate a concrete record that the original decoder reads incorrectly.
6. Specify the input contract of a function accepting a number of passengers. Explain why accepting True as quantity one may be a semantic defect.

Continue with [programming semantics](/en/topics/programming-semantics-contracts/), [arrays and strings](/en/topics/arrays-and-strings/) and [machine representation](/en/topics/machine-representation-isa-cache/).