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

## From the hash function to the table index

A hash table maps a key `k` through a function `h(k)` to one of `m` buckets, usually after a reduction such as `h(k) mod m`. It must resolve **collisions** because the key universe is larger than the finite set of buckets. A hash function that always produces the same bucket remains correct if collisions are handled, but performance degenerates. A good empirical distribution is not a proof that adversarial inputs are safe [1].

Let `n` be stored entries and `α=n/m` the **load factor**. Under uniform hashing assumptions, separate chaining has expected unsuccessful-search cost `Θ(1+α)` because a bucket holds approximately `α` entries on average. Under worst-case collisions, search is `Θ(n)`. The expectation refers to a model of key dispersion; no universal constant-time guarantee follows merely from using a dictionary [2].

## Chaining versus open addressing

**Separate chaining** places multiple entries in a bucket, often in a list or another collection. Deletion removes the matching entry without disturbing other buckets. **Open addressing** stores keys in table slots and probes a sequence until it finds the key or an eligible empty slot. Linear probing is cache-friendly but can create clusters; quadratic probing and double hashing change the probe sequence and must be configured to reach slots correctly. Open-addressed deletion may require a tombstone: clearing a slot to 'never used' could terminate a search before reaching a key inserted later along the same probe chain.

| Property | Chaining | Open addressing |
| --- | --- | --- |
| Storage | Bucket heads plus entries | Preallocated slots |
| Load factor | May exceed one | Must stay below one to admit new keys |
| Deletion | Remove matching entry | Tombstones or probe-preserving repair |
| Worst-case lookup | Linear | Linear |

## Resizing and equality correctness

When load exceeds a chosen threshold, allocating a larger table and **rehashing** entries often preserves expected constant-time operations over a long sequence. The resize itself is linear, so the claim is amortized rather than a per-operation worst-case bound. For mutable keys, a crucial invariant is: **keys considered equal must hash equally while stored**. Changing fields that determine a key's hash after insertion may make it unreachable under the new hash. Hash function choice, equality semantics and normalization must agree; for text keys, specify Unicode normalization and case sensitivity.

## Security, trade-offs and reproducible checks

Attackers may intentionally generate many colliding keys if hashing is predictable, causing CPU exhaustion. Runtime-specific collision hardening mitigates some attacks but does not eliminate the need to bound request sizes and distinct keys. Tables work well for exact membership and key lookup; they are not an ordered range index. A balanced tree may be preferable for predecessor/successor queries or deterministic logarithmic worst-case bounds.

**Worked reasoning:** put `n=24` keys into `m=8` buckets. Here `α=3`; under a uniform assumption, an unsuccessful chained search visits about three entries on average, plus bucket access. If all 24 keys collide, it may examine 24. For verification, deliberately substitute a constant hash, insert keys with distinct values, then test updates and deletions. Correct results must survive; runtime may increase sharply.

## Exercises and verification
1. What happens when all keys hash into one bucket? With naive chaining, unsuccessful lookup can inspect all `n` entries: `Θ(n)`.
2. Why can `α=0.9` be more troublesome for open addressing than for chaining? Probe sequences lengthen as free slots disappear.
3. Count distinct integers in `[4,4,5,6]`: iterate with a set and get `3`; test empty, repeated and negative inputs.

The important skill is identifying the maintained invariant and the collision model, not simply memorizing that a dictionary is "fast".
