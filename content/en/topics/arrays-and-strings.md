---
id: arrays-and-strings
title: "Arrays and Strings: Representation, Costs and Correct Iteration"
description: "Understand contiguous arrays, dynamic growth, indexing, slices, Unicode strings and boundary invariants with tested examples."
category: foundations
difficulty: beginner
updated: 2026-10-09
prerequisites: [complexity-analysis]
sources:
  - {title: "Python Tutorial — Data Structures", url: "https://docs.python.org/3/tutorial/datastructures.html", kind: "official language documentation"}
  - {title: "Python Standard Library — Unicode HOWTO", url: "https://docs.python.org/3/howto/unicode.html", kind: "official language documentation"}
  - {title: "Princeton Algorithms — Bags, Queues and Stacks", url: "https://algs4.cs.princeton.edu/13stacks/", kind: "university textbook"}
---
Arrays and strings are the foundation of many coding problems because they define how an ordered sequence is represented, indexed, copied and modified. An interview solution can be logically sound and still be inefficient if it repeatedly shifts an array or concatenates large immutable strings. The first question is always **what representation and operations does the language actually provide?** Python's list and str make a useful concrete case, while the underlying ideas transfer to Java, C++ and other languages [1].

## Fixed arrays, dynamic arrays and Python lists

A conventional fixed array stores n elements in consecutive slots of equal size. Given base address B and element width w, element i is conceptually located at B+i×w, so address calculation takes O(1) time. A dynamically sized array adds a logical length n and a capacity C. When n=C, growing may allocate a larger buffer and copy or move existing elements. Python lists are dynamic arrays of **references** to objects; the referenced Python objects themselves need not be contiguous or have uniform byte widths [1].

For example, an array [6,2,9] has indices 0,1,2. Inserting 4 at position 1 produces [6,4,2,9] and requires shifting two later references. Removing index 0 shifts the remaining references left. Index lookup is O(1), insertion/deletion near the beginning O(n), and iteration over every element O(n), where n denotes element count.

## Why appending is amortized constant time

Suppose capacity doubles whenever the buffer fills. Appending n elements performs n ordinary placements. Copies during resizing sum to less than 1+2+4+...+2^k, with the last power below n; this geometric sum is O(n). Thus n appends take O(n) aggregate work and **O(1) amortized** time each, despite an individual append sometimes costing O(n). This does not mean a language promises capacity exactly doubles or that reallocation is always available. The proof applies to the described growth policy, not blindly to every dynamic container [3].

Repeatedly inserting at index zero is different: each insertion shifts all existing elements. Inserting n elements one by one at the front can cost Θ(n²) total work. A queue that removes from the front of a Python list also shifts elements; choose a deque when operations at both ends dominate.

## Iteration invariants and boundary cases

A common loop maintains a half-open interval [lo,hi): lo is included and hi excluded. Its length is hi−lo, and an empty interval satisfies lo=hi. The contract must ensure 0≤lo≤hi≤n before indexing. Empty arrays require special care: accessing index zero is invalid, but summing zero elements is well-defined as zero.

![Half-open array intervals and index boundaries.](/diagrams/array-half-open.svg)

~~~python
def range_sum(values, lo, hi):
    if not 0 <= lo <= hi <= len(values):
        raise ValueError("invalid half-open interval")
    total = 0
    for i in range(lo, hi):
        total += values[i]
    return total

assert range_sum([3,-2,7,4], 1, 3) == 5
assert range_sum([], 0, 0) == 0
assert range_sum([8], 0, 1) == 8
try:
    range_sum([8], 0, 2)
    assert False
except ValueError:
    pass
~~~

The function runs in O(hi−lo) time and O(1) auxiliary space under constant-time addition and indexing. With arbitrarily large integers, arithmetic itself may not be constant cost; complexity claims in elementary problems normally use a fixed-word arithmetic model unless stated otherwise.

## Strings are sequences, but character models matter

Python strings are immutable sequences of Unicode code points [2]. A string is not necessarily a byte array or a sequence of user-perceived letters. UTF-8 encodes different code points into different numbers of bytes. The character "é" can appear as one precomposed code point or as "e" followed by a combining accent; the resulting strings can look identical yet compare unequal without normalization.

A grapheme cluster—the user's perceived character—may contain several code points, and emoji sequences can contain multiple code points joined together. Therefore 'reverse the string' is ambiguous until the task specifies whether it means bytes, code points or grapheme clusters. Code-point indexing is not the same as visual-character indexing.

## Costs of copying, slicing and concatenation

Because Python strings are immutable, operations building new strings must allocate output. A slice of length k generally costs O(k) time and output memory; repeatedly concatenating increasingly long strings may copy prefixes over and over. When constructing an output from many fragments, collect pieces then join once, subject to the language runtime's actual behavior [1].

~~~python
import unicodedata

def canonical_equal(left, right):
    return unicodedata.normalize("NFC", left) == unicodedata.normalize("NFC", right)

assert "é" != "é"
assert canonical_equal("é", "é")
assert len("é") == 2

def filtered_ascii_letters(text):
    parts = []
    for char in text:
        if "a" <= char.lower() <= "z":
            parts.append(char.lower())
    return "".join(parts)

assert filtered_ascii_letters("A-1 b!") == "ab"
~~~

The last function deliberately handles **ASCII Latin letters only**; it is not a Unicode-aware identifier normalizer. Calling lower() on certain Unicode symbols can yield multi-code-point results, so production normalization must define its accepted alphabet. Security-sensitive comparisons also need policy for confusable characters and locale-independent matching.

## Representation-driven algorithm choices

| Operation | Dynamic array/list | Immutable string |
| --- | --- | --- |
| Read index i | O(1) typical | O(1) for Python code-point index under implementation model |
| Append at end | O(1) amortized | Creates new string |
| Insert near beginning | O(n) shifting | Creates new string |
| Slice k elements | O(k) for Python list slice | O(k) output copying |
| Full iteration | O(n) | O(number of code points) |

The exact runtime complexities depend on representation, which is why a Python solution and a C++ fixed-char-buffer solution should not silently share every memory claim. Hashing a string generally inspects its contents when the hash is first computed, even if later caching changes repeated cost. An input that is already sorted can enable techniques such as two pointers and binary search; verify the ordering prerequisite first.

## When the structure is unsuitable

Arrays perform poorly for frequent arbitrary front insertions, while linked lists trade indexing for pointer changes. A large number of tiny copied slices can dominate memory bandwidth even if the high-level algorithm performs few loop iterations. Immutable strings are convenient for reasoning, but a naïve repeated-concatenation algorithm may be quadratic. A byte-oriented algorithm applied to Unicode text can split an encoded symbol and produce invalid data.

## Exercises and verification

1. For [7,4,9,2], calculate the references shifted when inserting at index 1, then when removing index 0.
2. Derive the geometric bound for copying under doubling capacity and explain why the worst individual append remains O(n).
3. Prove the invariant 0≤lo≤hi≤n before and after a loop scanning [lo,hi).
4. Explain why "é" and "e" followed by a combining accent can have different lengths under Python code-point indexing.
5. Implement range_sum using Python's built-in sum over a slice and compare correctness; explain why creating the slice changes space complexity.

**Next reading:** [Linked lists](/en/topics/linked-lists/) and [stacks and queues](/en/topics/stacks-queues/) compare representations; [binary search](/en/topics/binary-search/) relies on ordered index access.
