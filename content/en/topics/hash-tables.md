---
id: hash-tables
title: "Hash Tables, Collisions and Invariants"
description: "Understand hash functions, collision resolution, load factors and adversarial inputs, with a correct frequency-counting example and edge cases."
category: foundations
difficulty: foundational
updated: 2026-10-09
prerequisites: [complexity-analysis]
sources:
  - {title: 'MIT 6.006 — Introduction to Algorithms', url: 'https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/', kind: university course}
  - {title: 'Python documentation — Mapping Types: dict', url: 'https://docs.python.org/3/library/stdtypes.html#mapping-types-dict', kind: language documentation}
---
A hash table maps keys to values through a hash function and a bounded set of storage locations. It trades ordering and extra space for typically fast lookup, insertion and deletion. The useful invariant is that **equal keys have compatible hash values and can always be found again**, even after a collision or resize [1].

## Model and collision resolution
For capacity `m`, a simple bucket index is `h(key) mod m`. Since the space of possible keys is much larger than `m`, distinct keys must sometimes map to the same bucket: these are **collisions**, not necessarily defects in the hash function. A correct data structure must resolve them.

- **Separate chaining** stores several entries per bucket, commonly as lists or another local structure.
- **Open addressing** probes alternate slots using a repeatable sequence; deletion must not break subsequent searches.
- **Resizing** rebuilds placement when the table becomes crowded, because the capacity affects the bucket index.

The **load factor** `α = number_of_entries / capacity` helps predict average behavior under a suitable distribution assumption. Chaining may have `α > 1`; open addressing requires a free slot for successful insertion. In the worst case, pathological collisions can make operations linear in the number of stored entries [1].

## Equality, hashability and the retrieval invariant
A language must align hash and equality semantics. If `a == b`, it must not be possible for the hash table to route them to incompatible candidate locations. Hashing mutable objects based on changing fields is hazardous: after mutation, a key may no longer be located in the bucket where it was inserted.

Python dictionaries use hashable keys. Immutable strings and integers are common examples, but a tuple is hashable only if all its components are hashable. A Python dictionary is not generally a valid dictionary key [2].

## Worked example: first repeated value
Return the first value encountered for the **second** time. Maintain `seen`, the set of values in the prefix already processed.

```python
def first_repeat(items):
    seen = set()
    for item in items:
        if item in seen:
            return item
        seen.add(item)
    return None

assert first_repeat([7, 2, 7, 2]) == 7
assert first_repeat([1, 2, 3]) is None
assert first_repeat([]) is None
```

**Loop invariant:** before iteration `i`, `seen` contains exactly the distinct items in `items[:i]`. If the current item is already in `seen`, its second appearance occurs at or before `i`; because earlier positions were checked, this is the earliest second appearance. Otherwise insertion restores the invariant for the next iteration.

With `n` hashable items and expected constant-time set operations, expected time is `O(n)` and auxiliary space is `O(u)`, where `u ≤ n` is the number of distinct values. **Worst-case time is implementation- and collision-dependent**, so a claim of guaranteed `O(n)` would be unjustified.

## Alternatives and counterexamples
A sorted array plus binary search supports `O(log n)` lookup, but maintaining sort order can cost `O(n)` per insertion. A balanced search tree gives ordered iteration and worst-case logarithmic operations at the cost of pointers and more comparisons. Hash tables cannot efficiently answer arbitrary range queries on keys without additional indexing.

A duplicate-finding algorithm based on a set also assumes the input elements are hashable. If inputs are nested mutable structures, choose an explicit immutable key representation or another algorithm. Do not silently stringify complex objects: distinct values may stringify identically.

## Exercises and verification
1. What happens when all keys hash into one bucket? With naive chaining, unsuccessful lookup can inspect all `n` entries: `Θ(n)`.
2. Why can `α=0.9` be more troublesome for open addressing than for chaining? Probe sequences lengthen as free slots disappear.
3. Count distinct integers in `[4,4,5,6]`: iterate with a set and get `3`; test empty, repeated and negative inputs.

The important skill is identifying the maintained invariant and the collision model, not simply memorizing that a dictionary is "fast".
