---
id: maximum-flow-matching
title: "Maximum Flow, Minimum Cuts and Bipartite Matching"
description: "Derive flow conservation, residual networks, augmenting paths, the max-flow min-cut theorem and bipartite matching reduction with tested code."
category: algorithms
difficulty: advanced
updated: 2026-10-09
prerequisites: [graph-traversal, disjoint-set-union, complexity-analysis]
sources:
  - {title: "Maximum flow — Edmonds–Karp", url: "https://cp-algorithms.com/graph/edmonds_karp.html", kind: "algorithmic reference"}
  - {title: "Kuhn's algorithm — Maximum bipartite matching", url: "https://cp-algorithms.com/graph/kuhn_maximum_bipartite_matching.html", kind: "algorithmic reference"}
---
A network with directed edges and nonnegative capacities models how much material, information or work may be transported from a source to a sink. **Maximum flow** asks for the greatest feasible source-to-sink throughput. Its central invariant is conservation: intermediate vertices cannot create or destroy units. Unlike a shortest path, finding one good route is not enough; multiple routes may share bottlenecks and an early choice might need to be undone [1].

## Define feasibility before optimizing

For directed graph G=(V,E), source s distinct from sink t, capacity c(u,v)≥0 and flow f(u,v), require 0≤f(u,v)≤c(u,v) for each original edge. At every vertex other than s and t, total incoming flow equals total outgoing flow. The **flow value** is the net outgoing flow at s (equivalently net incoming at t). In an implementation, represent a reverse residual edge to express that a previous assignment may be reduced, without inventing a negative physical flow on an original edge.

Capacities can model independent links, but they need a consistent **unit** (requests/s, vehicles/hour or abstract integer units) and direction. A capacity does not guarantee that all independent links can simultaneously sustain it if they share a real-world bottleneck. The graph is a model whose assumptions must be stated explicitly.

## Residual graphs and augmentation

For an edge with capacity c and current flow f, the **forward residual capacity** is c−f: extra throughput still available. The **reverse residual capacity** is f: throughput that can be cancelled and reassigned to a different path. These two residual possibilities explain why a greedy algorithm that only adds flow forward can become stuck before the optimum. An **augmenting path** consists of positive-residual-capacity edges from s to t. Its bottleneck is the minimum residual capacity on that path; augmenting that amount preserves conservation and all capacity constraints [1].

![Residual capacity, augmenting paths and source-to-sink flow.](/diagrams/maxflow-residual.svg)

Repeatedly searching augmenting paths is the Ford–Fulkerson method. With integer capacities, each positive augmentation increases integral flow and the process terminates, but the number of augmentations may depend on the numeric maximum flow. With arbitrary real capacities, careless path selection has different termination considerations. **Edmonds–Karp** chooses a shortest augmenting path in *number of residual edges* using BFS; it is a concrete polynomial-time specialization [1].

## An executable Edmonds–Karp implementation

The following implementation accepts vertices numbered 0 through n−1 and triples (u,v,capacity), including parallel edges. It maintains one aggregate residual capacity per ordered pair. When both directions are original edges, their contributions combine correctly in the residual representation.

~~~python
from collections import deque

def max_flow(n, edges, source, sink):
    if n < 2 or not 0 <= source < n or not 0 <= sink < n or source == sink:
        raise ValueError("invalid graph or endpoints")
    neighbors = [set() for _ in range(n)]
    residual = {}
    for u, v, capacity in edges:
        if not 0 <= u < n or not 0 <= v < n or capacity < 0:
            raise ValueError("invalid edge")
        if u == v:
            continue
        neighbors[u].add(v)
        neighbors[v].add(u)
        residual[(u,v)] = residual.get((u,v), 0) + capacity
        residual.setdefault((v,u), 0)

    total = 0
    while True:
        parent = {source: None}
        queue = deque([source])
        while queue and sink not in parent:
            u = queue.popleft()
            for v in neighbors[u]:
                if v not in parent and residual.get((u,v), 0) > 0:
                    parent[v] = u
                    queue.append(v)
        if sink not in parent:
            return total
        path_capacity = float("inf")
        v = sink
        while v != source:
            u = parent[v]
            path_capacity = min(path_capacity, residual[(u,v)])
            v = u
        v = sink
        while v != source:
            u = parent[v]
            residual[(u,v)] -= path_capacity
            residual[(v,u)] = residual.get((v,u), 0) + path_capacity
            v = u
        total += path_capacity

network = [(0,1,3),(0,2,2),(1,2,1),(1,3,2),(2,3,3)]
assert max_flow(4, network, 0, 3) == 5
assert max_flow(3, [(0,1,2),(0,1,4),(1,2,6)], 0, 2) == 6
assert max_flow(3, [(0,1,2)], 0, 2) == 0
~~~

A missing edge has zero residual capacity. The finite integer-capacity tests are illustrative; the function also accepts nonnegative floating capacities, though floating-point roundoff may complicate positivity tests. For very large graphs use compact indexed edge records rather than a dictionary of tuples and sets.

## Why Edmonds–Karp has a polynomial bound

Each BFS examines a residual graph with O(E) edges under adjacency lists, where E counts original directed edges (and reverse residual edges differ only by a constant factor). A shortest augmenting path's edge distances from s never decrease during the algorithm. When an edge becomes saturated and later reappears as a useful forward residual edge, relevant distance labels have advanced. This can happen only O(V) times per edge. Hence there are O(VE) augmentations, with O(E) search work each, giving **O(VE²)** worst-case time [1]. This does **not** mean the flow value itself is O(VE), nor that a flow's numeric capacity determines the bound.

Space is O(V+E) for adjacency and residual records (apart from Python object overhead). The code reuses one BFS tree per augmentation and records only one parent per discovered vertex. A BFS search fails to find an augmenting path exactly when the source cannot reach the sink in the remaining positive-capacity residual network.

## Minimum cuts and the optimality certificate

A cut partitions vertices into S and T with s∈S, t∈T. Its capacity sums **original forward edge capacities** crossing S→T; subtracting edges T→S is not part of the cut capacity. Any feasible flow is bounded above by every such cut, because conservation makes net flow across the partition equal the flow value and backward flow cannot increase that bound. When no augmenting path remains, choose S as the vertices reachable from s in the residual graph. Every original crossing edge S→T must then be saturated, and reverse net flow across the cut must be zero. Therefore flow value equals cut capacity. This proves the **max-flow min-cut theorem** and gives an optimality certificate [1].

For the worked network, the source's two outgoing edges have capacities 3 and 2, so the cut {0} has capacity 5. The algorithm finds flow 5; the upper bound matches the feasible construction. Consequently 5 is optimal, independently of the order in which BFS explores equal-length paths.

## Bipartite matching as unit-capacity flow

A bipartite graph splits vertices into left L and right R with edges only between sides. A matching selects edges so that no vertex appears more than once. Construct a flow network: a super-source connects to each left vertex with capacity 1; each allowed left→right edge has capacity 1; each right vertex connects to a super-sink with capacity 1. Integral maximum flow corresponds to a maximum-cardinality matching: each unit of flow chooses one left-right pair and no endpoint can be reused [2].

| Question | Correct approach | Important assumption |
| --- | --- | --- |
| Total throughput | Max flow | Directed edges with capacities |
| Limiting bottleneck partition | Min cut | Same capacity model |
| Maximum one-to-one assignment | Bipartite matching | Disjoint sides and unit endpoint capacity |
| Minimum-cost assignment | Min-cost flow or assignment algorithm | Edge costs require a different objective |
| Shortest route | BFS/Dijkstra | Distance, not throughput |

An arbitrary matching can be **maximal** (no immediate edge can be added) without being **maximum**. Alternating augmenting paths can move previously selected partners to free capacity; this is the matching analogue of flow residual reversals [2].

## Counterexamples and exercises

Do not confuse a graph edge with a unique undirected connection: for directed flow, capacity u→v is independent of v→u. A greedy choice that assigns the only worker capable of job B to job A can produce matching size 1 where reassigning job A to another worker permits 2 matches. An ordinary DSU does not capture directed capacities. Be careful when interpreting self-loops: they cannot increase source-to-sink flow, so the demonstration ignores them.

1. For the worked network, exhibit a cut of capacity five and explain why no feasible flow can exceed it.
2. Derive the residual reverse capacity after sending two units through an edge of capacity five: forward residual three, reverse residual two.
3. Build the bipartite reduction for two workers and two tasks where one worker can do both tasks and the other only the first.
4. Why does an augmenting path improve value rather than simply redistribute it?
5. Compare results for a small network against brute-force integer flow assignments and verify capacity and conservation, rather than trusting two implementations of the same augmenting-path heuristic.

**Related reading:** [Graph traversal](/en/topics/graph-traversal/) supplies BFS; [Union-Find](/en/topics/disjoint-set-union/) handles a different undirected connectivity abstraction; [shortest paths](/en/topics/shortest-paths/) optimizes path costs rather than total throughput.
