---
id: strongly-connected-components
title: "Strongly Connected Components and Condensation Graphs"
description: "Derive strongly connected components, prove why condensation is a DAG and implement iterative Kosaraju with complexity and edge-case checks."
category: algorithms
difficulty: advanced
updated: 2026-10-09
prerequisites: [graph-traversal, complexity-analysis]
sources:
  - {title: "Strongly Connected Components and Condensation Graph — CP-Algorithms", url: "https://cp-algorithms.com/graph/strongly-connected-components.html", kind: "technical reference"}
  - {title: "Princeton Algorithms — Directed Graphs", url: "https://algs4.cs.princeton.edu/42digraph/", kind: "university course"}
---
A directed graph may contain a group of vertices from which every member can reach every other member. Those maximal groups are **strongly connected components** (SCCs). They are not merely connected components of the undirected version: direction determines whether return paths exist. Identifying SCCs lets us simplify dependency cycles, group mutually reachable states, and reason about the acyclic structure between groups [1].

## Definition, maximality and partition

Let G=(V,E) be a directed graph. Vertices u and v are mutually reachable when there is a directed path from u to v and another from v to u. Mutual reachability is an equivalence relation: it is reflexive through the length-zero path, symmetric by definition, and transitive by concatenating paths. Therefore V is partitioned into disjoint equivalence classes. Each class is maximal: adding a vertex outside it would violate mutual reachability. A lone vertex forms an SCC even without a self-loop; a self-loop is not required.

Do not confuse SCCs with the connected components of an undirected graph. If edges are A→B and B→C only, ignoring directions yields one undirected component, but the directed SCCs are three singleton sets. Conversely, if A→B→C→A, all three form one SCC.

## Condensation and the key acyclicity proof

Replace each SCC with one vertex. Add a directed edge X→Y between two different component vertices if any original edge connects a member of X to a member of Y. The result is the **condensation graph**. It cannot contain a directed cycle with two or more components: if such a cycle existed, every component on that cycle would reach the others and return, so all their members would form one larger SCC. This contradicts maximality. The condensation graph is therefore a directed acyclic graph (DAG) [1].

![Three strongly connected components collapse into a directed acyclic condensation graph.](/diagrams/scc-condensation.svg)

This proof matters operationally. A dependency scheduler cannot topologically order individual packages participating in a directed cycle, but it can topologically order the *groups* of mutually dependent packages. Resolving cycles inside each group remains a separate problem; condensation does not magically remove semantic dependencies.

## Why two DFS passes work

Kosaraju–Sharir's algorithm runs DFS over the original graph to record vertices by finishing time, then runs DFS on the **transpose graph**, whose edges point in the reverse direction, considering vertices from the latest finishing time backward. The second DFS discovers one SCC at a time. The decisive property is that an edge between different components in the original condensation imposes a finishing-time ordering; reversing the edges prevents the second pass from escaping the appropriate source component in the remaining graph [1][2].

The first pass must run across **every vertex**, not just vertices reachable from one preferred source. Record a vertex upon completion of exploring its descendants, not on initial discovery. The second pass must iterate in **reverse finishing order**. Swapping either order can merge distinct components incorrectly. Transposition changes edge direction but preserves the equivalence classes of mutual reachability.

## Iterative implementation that avoids recursion depth

~~~python
def strongly_connected(graph):
    vertices = set(graph)
    for neighbors in graph.values():
        vertices.update(neighbors)
    seen, finish = set(), []
    for start in vertices:
        if start in seen:
            continue
        seen.add(start)
        stack = [(start, iter(graph.get(start, ())))]
        while stack:
            node, edges = stack[-1]
            nxt = next(edges, None)
            if nxt is None:
                finish.append(node)
                stack.pop()
            elif nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, iter(graph.get(nxt, ()))))
    reverse = {v: [] for v in vertices}
    for u, neighbors in graph.items():
        for v in neighbors:
            reverse[v].append(u)
    seen.clear()
    components = []
    for start in reversed(finish):
        if start in seen:
            continue
        group, pending = set(), [start]
        seen.add(start)
        while pending:
            u = pending.pop()
            group.add(u)
            for v in reverse[u]:
                if v not in seen:
                    seen.add(v)
                    pending.append(v)
        components.append(group)
    return components

graph = {0:[1], 1:[0,2], 2:[3], 3:[2,4], 4:[]}
parts = strongly_connected(graph)
assert {frozenset(c) for c in parts} == {
    frozenset({0,1}), frozenset({2,3}), frozenset({4})
}
assert strongly_connected({}) == []
assert {frozenset(c) for c in strongly_connected({7:[7]})} == {frozenset({7})}
~~~

This code uses None as an end-of-iterator sentinel; accordingly it assumes **vertex labels are not None**. Labels must be hashable, and the example uses integers. A general-purpose library should use a fresh sentinel object instead and verify its input domain. The algorithm returns sets in an order that can vary because the initial vertex set is unordered; SCC membership, rather than presentation order, is its contract.

## A worked trace on a graph with two cycles

Take edges 0→1, 1→0, 1→2, 2→3, 3→2, and 3→4. Mutual reachability gives groups A={0,1}, B={2,3}, C={4}. The group A can reach B, but B cannot reach A. B reaches C, but C has no return edge. The condensation is A→B→C. One topological order is A,B,C, but internal numbering of representatives does not define an intrinsic order.

To construct this condensation programmatically, assign each vertex its returned component ID, scan every original edge u→v, and insert component(u)→component(v) whenever IDs differ. Using a set of pairs removes duplicate component edges. Construction visits O(V+E) entries. You can then run a standard topological sort on the condensed DAG without worrying about directed cycles between SCCs.

## Cost model and implementation limits

With adjacency lists, the first DFS, transposition and second DFS each inspect at most O(V+E) entries. Total **time is O(V+E)**, and lists, reverse adjacency and traversal stacks occupy **O(V+E)** space. Iterative DFS avoids Python recursion-limit failures on deep graphs, but its iterator and stack objects still have memory overhead. If input edges are streamed and cannot be revisited, obtaining a transpose requires retaining edge information or another external-memory strategy.

For a huge dependency graph with millions of edges, memory layout and locality may matter more than minor Python-level optimizations. Tarjan's algorithm can find SCCs in one traversal using discovery indices and low-link values, but its correctness relies on a different stack invariant; merely counting traversals does not guarantee that it is faster in practice [1].

## Unsuitable methods and counterexamples

Union-Find cannot simply replace SCC algorithms: DSU records undirected connectivity under merges, while strong connectivity requires directed paths **both ways**. Ordinary BFS from one source also fails to partition a graph containing unreachable vertices. A directed edge from A to B is not evidence that A and B belong to the same SCC. Marking nodes as visited on only the first pass and reusing that set without clearing it is another implementation bug.

## Exercises and verification

1. List SCCs of the chain 0→1→2 with no reverse edges. Answer: three singleton components.
2. Add the edge 2→0. Prove that the three vertices now form one SCC by constructing return paths.
3. On the example graph above, show that the condensed graph is a DAG and compute one topological order.
4. Implement condensation-edge generation and verify that no edge has identical source and destination component IDs.
5. Compare the result on small random directed graphs with a slow oracle: for every pair of vertices, test reachability in both directions. This oracle is slower but independent from Kosaraju's finishing-time argument.
