---
id: disjoint-set-union
title: "Disjoint Set Union: Connectivity, Compression and Kruskal"
description: "Derive union-find invariants, path compression, union by size, amortized bounds and minimum spanning tree use with verified Python code."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis, graph-traversal]
sources:
  - {title: "Disjoint Set Union — CP-Algorithms", url: "https://cp-algorithms.com/data_structures/disjoint_set_union.html", kind: "technical reference"}
  - {title: "Minimum Spanning Tree — Kruskal — CP-Algorithms", url: "https://cp-algorithms.com/graph/mst_kruskal_with_dsu.html", kind: "technical reference"}
---
A disjoint-set union structure (DSU, also called union-find) maintains a **partition** of a fixed universe into pairwise disjoint sets. It answers whether two elements currently belong to the same component and merges two components. This is the right abstraction when relationships only **add** connectivity, such as undirected edges inserted over time; it does not maintain a graph's complete topology [1].

## Mathematical model and precise contract

Let the universe be integers from 0 through n-1. Initially every element is alone. The equivalence relation 'belongs to the same component' is reflexive, symmetric and transitive. The operation find(x) returns an arbitrary **representative** of x's component; union(a,b) merges their components and returns whether a merge actually occurred. Representatives are internal implementation details: clients must not rely on a particular vertex remaining the leader. Out-of-range element IDs violate the contract.

![A collection of disjoint components is represented by parent pointers.](/diagrams/dsu-forest.svg)

## Forest invariant and union by size

Represent each set by a rooted tree. The array parent[x] points toward the root, and a root satisfies parent[root]=root. The invariant is that following parents terminates at exactly one root and never creates a directed cycle of length greater than one. Union must therefore attach **roots**, not arbitrary nodes. Otherwise the forest can break or a component may be silently split.

Without a rule for choosing the parent, repeated unions can form a chain of length n-1, so find may take linear time. With **union by size**, attach the smaller root underneath the larger one. Every time the depth of an element increases, its component size at least doubles. An element can therefore increase depth at most floor(log₂ n) times before the component reaches size n. This proves logarithmic height without path compression [1].

## Path compression and executable implementation

A find traverses a path to the root. **Path compression** rewires visited nodes to point directly at that root. This keeps the same partition: only parent pointers inside a component change. Coupled with union by size, the amortized cost of an operation is O(α(n)), where α denotes the inverse Ackermann function. This is a sophisticated *sequence* bound, not a claim that every individual call is constant-time or that the bound was proved by the simple doubling argument [1].

~~~python
class DSU:
    def __init__(self, n):
        if n < 0: raise ValueError("n must be nonnegative")
        self.parent = list(range(n))
        self.size = [1] * n
        self.components = n

    def find(self, x):
        if not 0 <= x < len(self.parent): raise IndexError(x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a == b: return False
        if self.size[a] < self.size[b]: a, b = b, a
        self.parent[b] = a
        self.size[a] += self.size[b]
        self.components -= 1
        return True

d = DSU(5)
assert d.components == 5
assert d.union(0, 1) and d.union(1, 2)
assert d.find(0) == d.find(2)
assert not d.union(0, 2)
assert d.components == 3
~~~

This version uses **path halving**, a safe iterative compression variant that avoids recursive call depth. It consumes O(n) memory; construction is O(n). Sizes are meaningful only at roots. After attaching a root, its stored size may be stale, but never consult it as an authority while it is not a root.

## Worked example: detecting an undirected cycle

Process undirected edges (0,1), (1,2), (3,4), (2,0). The first two form component {0,1,2}; the third forms {3,4}. For edge (2,0), find returns the same representative at both endpoints. Adding this edge would create a cycle because a path between those vertices already exists. This reasoning assumes an **undirected** graph; the same criterion is not valid for detecting cycles in directed graphs.

For dynamic insertion, each edge costs an almost-constant amortized amount, so m additions take O(m α(n)) after initialization. Note that DSU answers connectivity, not which path connects vertices, and does not support removal of arbitrary edges without special offline techniques or a different dynamic-connectivity structure.

## Kruskal and minimum spanning forests

Kruskal sorts weighted undirected edges by nondecreasing weight, then adds an edge only when its endpoints are in different DSU components. The **cut property** justifies selecting a minimum-weight crossing edge: it is safe for at least one minimum spanning tree. Sorting costs O(E log E); DSU work O(E α(V)) is typically smaller. For a disconnected graph, the result is a **minimum spanning forest**, not a single spanning tree [2].

| Question | DSU answers? | Reason |
| --- | --- | --- |
| Are u and v connected after additions? | Yes | Compare representatives |
| Does a new undirected edge create a cycle? | Yes | Endpoints already connected |
| What is the shortest path from u to v? | No | Path weights and predecessor edges are absent |
| What happens when an old edge is deleted? | Not directly | Ordinary DSU only merges |

## Counterexamples, correctness and alternatives

Consider union(0,1), union(1,2), then removing (1,2). The ordinary DSU still reports 0 and 2 connected, even if no alternate edge exists; **deletions** violate its supported operation model. Another mistake is to combine parent[a]=b for raw endpoints without finding roots; this can destroy representational invariants. For concurrency, independent unsynchronized finds and unions race on parent and size; thread safety requires a deliberately designed concurrent structure.

## Exercises and verification

1. Perform four unions on six isolated elements and track the component count. It decreases only when roots differed; redundant union does not decrement it.
2. Prove the logarithmic height bound under union by size by counting how often a fixed element's component size doubles.
3. Extend the implementation to report each component's size using size[find(x)], and test nodes whose stored local size is stale.
4. On edges (0,1,2), (1,2,5), (0,2,1), Kruskal picks weights 1 and 2 for a total of 3. Explain why weight 5 would create a cycle if added afterward.
5. Compare DSU answers to DFS reachability in a small randomly generated **undirected insertion-only** graph; this independent oracle catches incorrect unions.
