---
id: tries-prefix-search
title: "Tries, Prefix Search and String Keys"
description: "Derive trie invariants and prefix search, implement insert, contains and completion, and analyze key length and memory trade-offs."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [hash-tables, complexity-analysis]
sources:
  - {title: "Princeton Algorithms — Tries", url: "https://algs4.cs.princeton.edu/52trie/", kind: "university reference"}
  - {title: "Princeton Algorithms — TrieST implementation", url: "https://algs4.cs.princeton.edu/code/edu/princeton/cs/algs4/TrieST.java.html", kind: "university implementation"}
---
A **trie** (prefix tree) indexes a collection of strings by sharing common prefixes. Unlike a hash table, which primarily answers exact-key membership, a trie exposes the structure of the key one symbol at a time: every path from the root corresponds to a prefix. This supports autocomplete, prefix counts, word dictionaries and, with suitable adaptations, longest-prefix matching [1].

## Define the key model before choosing nodes

Choose what one edge means: a byte, a Unicode code point, a normalized character, or a bit. The decision changes memory use and correctness. In a byte-wise trie, the word "é" in UTF-8 occupies two edges; in a code-point trie it occupies one. Unicode normalization matters: a visually similar character can have more than one sequence of code points. Case-insensitive lookup requires a defined case-folding policy. None of these are automatically solved by using string keys.

Represent each node as a mapping from symbol to child, plus a **terminal flag** indicating that the path to that node is a complete stored key. The root represents the empty prefix. Not every existing prefix is a stored word. If "car" and "cart" are inserted, the node reached after "ca" exists but should not be terminal; the node for "car" is terminal despite having a child [1].

## Structural invariant and operations

For every stored key k, exactly one path from the root spells k, and the terminal flag is set on its endpoint. **Insertion** traverses or creates a child for each symbol and marks the last node terminal. **Membership** traverses the entire key and checks that flag. **Starts-with** traverses only the prefix; finding a node suffices if at least one key has been inserted along or below it. A deletion procedure must clear terminal status and optionally prune only nodes whose subtrees contain no other stored keys.

![Shared-prefix tree for car, cart and cat.](/diagrams/trie-prefix.svg)

## Working Python implementation

~~~python
class Trie:
    def __init__(self):
        self.root = {"end": False, "children": {}}

    def insert(self, word):
        node = self.root
        for symbol in word:
            node = node["children"].setdefault(
                symbol, {"end": False, "children": {}}
            )
        node["end"] = True

    def contains(self, word):
        node = self.root
        for symbol in word:
            if symbol not in node["children"]:
                return False
            node = node["children"][symbol]
        return node["end"]

    def complete(self, prefix, limit=None):
        if limit is not None and limit < 0:
            raise ValueError("negative limit")
        node = self.root
        for symbol in prefix:
            if symbol not in node["children"]:
                return []
            node = node["children"][symbol]
        output, stack = [], [(node, prefix)]
        while stack and (limit is None or len(output) < limit):
            current, text = stack.pop()
            if current["end"]:
                output.append(text)
            for symbol in sorted(current["children"], reverse=True):
                stack.append((current["children"][symbol], text + symbol))
        return output

trie = Trie()
for word in ["car", "cart", "cat", "dog"]:
    trie.insert(word)
assert trie.contains("car") and trie.contains("cart")
assert not trie.contains("ca")
assert trie.complete("ca") == ["car", "cart", "cat"]
assert trie.complete("xyz") == []
~~~

This demonstration uses Python dictionaries, dynamic allocation and string concatenation; it is not an optimized compact trie. It intentionally accepts the empty string as a key: inserting "" marks the root terminal. Empty prefixes can enumerate all stored keys. For a production API, decide whether empty-key and empty-prefix operations should be permitted and whether results must be lexicographically ordered or merely any order.

## Complexity with key length, not only key count

Let L be the number of symbols in the input key or prefix. With expected constant-time dictionary child access, insert and exact lookup use expected O(L) time. A prefix query that **enumerates** matches cannot be O(L) independent of its output: after reaching the prefix node, it must visit relevant subtree nodes and emit strings. If K results have combined output length Z, generating those output strings requires at least Ω(Z) work; the exact bound also depends on traversal and implementation.

Let S be the total number of symbols across all inserted keys. At most S+1 trie nodes are created; sharing reduces that count when prefixes overlap. Yet one dictionary object per node can cost more memory than keeping plain strings. A fixed R-way array of child pointers trades fast indexed access for O(R) child storage **per node**, often wasteful for sparse alphabets [2].

## Prefix counting, deletion and compression

A **subtree terminal count** can make the number of keys with a prefix available after O(L) traversal; insertions and deletions must update counts consistently along their paths. Deleting "car" should remove only its terminal marker if "cart" remains. Deleting "cart" afterward may permit pruning its leaf and ancestors, but never nodes needed by "cat". A **radix** or Patricia trie compresses one-child chains into edges labeled by substrings, reducing node overhead at the cost of more involved split/merge logic.

| Operation | Plain trie | Hash table |
| --- | --- | --- |
| Exact key lookup | O(L) expected | Expected O(L) hashing plus lookup assumptions |
| Prefix existence | O(L) expected | No intrinsic prefix index |
| Enumerate prefix matches | Traversal of matching subtree | Scan keys or use extra index |
| Range order | Can traverse alphabetically | No natural sorted order |

A hash table may be simpler and smaller for exact lookups with no prefix operations. A sorted array plus binary search can also find prefix ranges and might outperform pointer-heavy structures for static dictionaries.

## Correctness counterexamples and practical hazards

A common bug treats any reached node as a complete word: after inserting "cart", querying "car" incorrectly returns true. Another incorrectly deletes a shared node, causing unrelated words to vanish. Concurrent inserts are not safe merely because a dictionary offers individual atomic-looking operations; coordinate mutations when threads share the trie. Strings with surrogate or combining sequences require normalization policy consistent across insertion and lookup.

**Related reading:** [Hash-table collision models](/en/topics/hash-tables/) explains exact-key indexing; [binary search](/en/topics/binary-search/) provides an ordered-array alternative. These structures solve overlapping but nonidentical query contracts.

## Exercises and verification

1. Insert "an", "ant" and "and": prove that prefix "a" exists but exact word "a" does not. Deleting "an" must preserve both longer words.
2. What is the maximum number of created nodes after storing n strings of length L with no common nonempty prefix? Give a bound relative to nL.
3. Modify complete to reject an empty prefix and test that the policy is applied before traversal.
4. Implement prefix counts, update them on **new** insertions only, and test repeated insertion of the same word.
5. Compare output against a reference built with sorted(word for word in words if word.startswith(prefix)) on a small set of strings; discrepancies reveal traversal or terminal-flag errors.
