---
id: discrete-relations-orders
title: "Binary Relations, Equivalence Classes and Partial Orders"
description: "Derive equivalence partitions, partial orders, reachability closure and topological dependencies with executable counterexamples."
category: foundations
difficulty: foundational
updated: 2026-10-11
prerequisites: [logic-proofs-invariants, discrete-counting-probability]
sources:
  - {title: "MIT 6.042J — Lecture 11: Relations, Partial Orders, and Scheduling", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-fall-2010/resources/lecture-11-relations-partial-orders-and-scheduling/", kind: "university lecture"}
  - {title: "MIT 6.042J — Chapter 7: Relations and Partial Orders", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-fall-2010/resources/mit6_042jf10_chap07/", kind: "university open textbook"}
---
Relations are the mathematical link between sets and algorithms that group, constrain or order objects. A disjoint-set data structure maintains an **equivalence relation**; a dependency graph represents ordering constraints; a database join tests whether tuples satisfy a relation. These are different contracts even when all use pairs. This chapter develops the underlying properties before considering their implementations. MIT 6.042J introduces these definitions together with scheduling and topological orders [1][2].

The finite examples use a universe of integers `U = {0, ..., n-1}`, with `n >= 0`, and an explicitly enumerated set of ordered pairs. Results about these models do not automatically extend to arbitrary infinite sets or to a live database.

## Binary relations are sets of ordered pairs

A binary relation `R` **on** `U` is a subset of `U × U`. The notation `a R b` means the ordered pair `(a,b)` belongs to `R`. Direction matters: `(a,b)` and `(b,a)` need not occur together. A relation from `A` to `B` instead lies in `A × B`; its properties must be stated with the correct domain and codomain.

For `U={0,1,2}`, the relation `R={(0,0),(1,1),(2,2),(0,1)}` contains all identity pairs and one directed edge. The identity relation has only the three self-pairs. The **universal relation** contains all nine pairs. The empty relation on a nonempty universe contains none; it is symmetric and transitive but not reflexive. For the empty universe, universal quantification is vacuously true, so even the empty relation is reflexive.

Treating a directed edge set as a relation avoids hidden assumptions such as "if A depends on B, B depends on A." The same edge can model a prerequisite, connectivity, permission or comparison, but its mathematical properties depend on the intended meaning.

## The four properties and minimal counterexamples

`R` is **reflexive** if every `a` satisfies `a R a`; **symmetric** if `a R b` implies `b R a`; **antisymmetric** if both directions imply `a=b`; and **transitive** if `a R b` and `b R c` imply `a R c` [1][2].

Symmetry and antisymmetry are **not** logical opposites. Equality is simultaneously symmetric and antisymmetric. A relation with two different objects connected in both directions violates antisymmetry, even if all self-pairs are present. A missing reverse pair violates symmetry but does not violate antisymmetry.

For `U={0,1,2}`, define `a R b` when `|a-b| <= 1`. It is reflexive and symmetric. However `0 R 1` and `1 R 2` while `0 R 2` is false, so it is **not transitive**. This counterexample invalidates the tempting claim that "similarity" always partitions objects into coherent groups.

## Equivalence relations and partitions

An **equivalence relation** is reflexive, symmetric and transitive. For each `a`, its class is `[a] = {b in U : a R b}`. Reflexivity ensures the class is nonempty; symmetry and transitivity imply that any two classes are either disjoint or exactly the same. To see this, suppose `x` belongs to both `[a]` and `[b]`. Symmetry yields `x R a` and transitivity with `b R x` yields `b R a`. Repeating the argument shows that every member of `[a]` is in `[b]`, and conversely.

Thus the distinct classes form a **partition**: nonempty, pairwise disjoint subsets whose union is the universe. Conversely, any partition defines an equivalence relation by declaring two elements related precisely when they occur in the same block. This is a bijective correspondence between equivalence relations and partitions of a fixed finite universe [2].

For integers `0..5`, congruence modulo 2 gives the blocks `{0,2,4}` and `{1,3,5}`. [Disjoint-set union](/en/topics/disjoint-set-union/) supports merging these blocks efficiently when equivalences are added monotonically. It does **not** support an arbitrary request to remove a relation edge while maintaining connectivity.

## Partial orders, incomparability and total orders

A **partial order** is reflexive, antisymmetric and transitive. It need not compare every distinct pair. The `<=` relation on integers is total; the "divides" relation on **positive** integers is a partial order but not a total order: both 2 and 3 divide 6, yet neither divides the other.

The positive-domain condition matters. On all nonzero signed integers, divisibility in both directions need not imply equality: 2 divides -2 and -2 divides 2, yet the numbers differ. Hence divisibility there is a **preorder** (reflexive and transitive), but not an antisymmetric order. Formal specifications must identify the domain.

A finite **total order** adds comparability: for all `a,b`, either `a R b` or `b R a`. A total order can extend a partial order by choosing a consistent position for incomparable items. The extension need not be unique; multiple valid build or study schedules can obey the same dependency constraints [1].

## Dependencies, Hasse diagrams and topological sorting

A dependency edge `a -> b` may mean "a must precede b." The raw graph normally omits self-edges and edges implied by longer paths. Therefore its edge set is not itself the reflexive, transitive partial order. Taking **reflexive transitive closure** produces the reachability relation, adding `(a,a)` and every pair connected by a directed path of zero or more edges.

If the original graph has a directed cycle through distinct vertices, the closure contains both `a R b` and `b R a` for distinct `a,b`; antisymmetry fails. A directed acyclic graph (DAG), however, induces a partial order by reachability. A **topological order** is a linear extension of the constraints. It is impossible on a graph with a directed cycle.

A Hasse diagram is a compact representation of a finite partial order: it omits self-relations and transitively implied relations. It is **not** synonymous with an arbitrary directed graph. For a prerequisite path `A -> B -> C`, `A -> C` is true in the reachability order even though an edge `A -> C` need not be drawn [1][2]. This distinction is important for package dependencies, project scheduling and build systems.

## Executable finite model and invariant

The following implementation rejects invalid vertices, booleans masquerading as integer IDs and malformed pairs. It tests properties over `n` elements, constructs classes **only after** equivalence is established, and calculates closure by allowing each intermediate vertex in turn.

The closure loop maintains the invariant: after processing vertex `k`, `reach[i][j]` is true exactly when a path exists from `i` to `j` whose internal vertices are among `0..k`. A path either avoids `k` or consists of a path to `k` followed by a path from `k`. This proves the update. At termination, all possible intermediate vertices are allowed.

~~~python
def normalized_relation(n, pairs):
    if type(n) is not int or n < 0:
        raise ValueError("n must be a nonnegative integer")
    relation = set()
    for pair in pairs:
        if (type(pair) is not tuple or len(pair) != 2
                or any(type(x) is not int or not 0 <= x < n for x in pair)):
            raise ValueError("pairs must contain valid (int, int) vertices")
        relation.add(pair)
    return relation

def relation_properties(n, pairs):
    r = normalized_relation(n, pairs)
    reflexive = all((i, i) in r for i in range(n))
    symmetric = all((b, a) in r for a, b in r)
    antisymmetric = all(a == b or (b, a) not in r for a, b in r)
    transitive = all(
        (a, c) in r
        for a in range(n) for b in range(n) for c in range(n)
        if (a, b) in r and (b, c) in r
    )
    return {
        "reflexive": reflexive,
        "symmetric": symmetric,
        "antisymmetric": antisymmetric,
        "transitive": transitive,
        "equivalence": reflexive and symmetric and transitive,
        "partial_order": reflexive and antisymmetric and transitive,
    }

def equivalence_classes(n, pairs):
    r = normalized_relation(n, pairs)
    if not relation_properties(n, r)["equivalence"]:
        raise ValueError("relation is not an equivalence")
    unseen = set(range(n))
    classes = []
    while unseen:
        representative = min(unseen)
        group = {j for j in unseen if (representative, j) in r}
        classes.append(tuple(sorted(group)))
        unseen.difference_update(group)
    return tuple(classes)

def reflexive_transitive_closure(n, edges):
    r = normalized_relation(n, edges)
    reach = [[i == j for j in range(n)] for i in range(n)]
    for a, b in r:
        reach[a][b] = True
    for k in range(n):
        for i in range(n):
            if reach[i][k]:
                for j in range(n):
                    if reach[k][j]:
                        reach[i][j] = True
    return {(i, j) for i in range(n) for j in range(n) if reach[i][j]}

parity = {(a, b) for a in range(6) for b in range(6) if a % 2 == b % 2}
assert relation_properties(6, parity)["equivalence"]
assert equivalence_classes(6, parity) == ((0, 2, 4), (1, 3, 5))
divides = {(a, b) for a in range(6) for b in range(6) if (b + 1) % (a + 1) == 0}
assert relation_properties(6, divides)["partial_order"]
assert not relation_properties(6, divides)["symmetric"]
near = {(a, b) for a in range(3) for b in range(3) if abs(a - b) <= 1}
assert relation_properties(3, near)["reflexive"]
assert relation_properties(3, near)["symmetric"]
assert not relation_properties(3, near)["transitive"]
assert reflexive_transitive_closure(3, {(0, 1), (1, 2)}) == {
    (0, 0), (1, 1), (2, 2), (0, 1), (1, 2), (0, 2)
}
assert relation_properties(0, set())["equivalence"]
~~~

For an enumerated relation, `relation_properties` costs `O(n³)` expected-time membership probes and up to `O(n²)` stored pairs. Class extraction uses at most `O(n²)` probes plus sorting. The closure uses `O(n³)` time and `O(n²)` extra memory. The estimates assume bounded-cost integer IDs and expected constant-time Python set membership; they are **not** bit-complexity guarantees for arbitrary-sized integers or adversarial hashing.

## Failure cases and engineering boundaries

A relation defined by "distance at most one" is not an equivalence relation. Grouping by connected components computes the **transitive closure of connectivity**, which changes the intended semantics: elements at distance two can end up in the same block. A ticketing system should not merge identities using a vague notion of similarity.

A prerequisite DAG supports topological sorting. It does not require assigning a unique absolute rank to every task; incomparable tasks can run concurrently. Likewise, a positive divisibility order has no meaningful requirement that 2 precede 3. Imposing arbitrary order on incomparable data can introduce unnecessary serialization.

The executable implementation is intentionally dense and finite. A production scheduler usually uses indegree-based topological sorting in `O(V+E)`, not cubic closure, when it only needs one valid sequence. A dynamic connectivity service might use DSU for additions but needs a different data structure or recomputation for deletions. Choose algorithms from the operations required, rather than from a diagram that looks similar.

## Exercises and verification

1. On `U={0,1,2}`, classify the relation `{(0,0),(1,1),(2,2),(0,1),(1,0)}`. **Check:** reflexive and symmetric, but not transitive: `1 R 0` and `0 R 1` do not cause trouble, while `0 R 1` and `1 R 0` only imply self-pairs; the relation **is transitive**. It is an equivalence with classes `{0,1}` and `{2}`; antisymmetry fails. Verify by running the program.
2. Add `(1,2)` without `(0,2)` to that relation. **Check:** transitivity fails through `0 R 1` and `1 R 2`; symmetry fails because `(2,1)` is missing.
3. Find the closure of `{(0,1),(1,2)}` on three vertices. **Check:** the six pairs asserted in code, including `(0,2)` and the three diagonal pairs.
4. For the positive divisibility order on `{1,2,3,6}`, give two linear extensions. **Check:** `1,2,3,6` and `1,3,2,6` are both valid; 2 and 3 remain incomparable.
5. **Independent challenge:** implement `O(V+E)` topological sorting without calling the closure function; on cycle detection return an explicit error. Verify against every DAG on four labeled vertices, including disconnected graphs.

Passing these finite checks establishes behavior for the tested inputs, not universal mathematical correctness or performance on larger systems.
