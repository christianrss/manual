---
id: shortest-paths
title: "Shortest Paths: Dijkstra, Bellman–Ford and Negative Cycles"
description: "Prove shortest-path relaxation, implement Dijkstra with a heap, compare Bellman–Ford and analyze negative cycles and weighted graphs."
category: algorithms
difficulty: advanced
updated: 2026-10-09
prerequisites: [graph-traversal, heaps-priority-queues, complexity-analysis]
sources:
  - {title: "Dijkstra — CP-Algorithms", url: "https://cp-algorithms.com/graph/dijkstra.html", kind: "technical reference"}
  - {title: "Bellman–Ford — CP-Algorithms", url: "https://cp-algorithms.com/graph/bellman_ford.html", kind: "technical reference"}
---
An unweighted graph can be searched with BFS to minimize the number of edges; a **weighted** graph instead assigns a numerical cost to each edge. The objective is the minimum sum of weights along a path, not the path containing the fewest edges. Choosing the algorithm requires inspecting weight signs, graph direction, and whether reachable negative cycles exist [1][2].

## Formal problem and assumptions

For a directed graph G=(V,E), define a path P from source s to vertex v as a sequence of adjacent vertices. Its cost is the sum of edge weights w(e), and the shortest-path distance δ(s,v) is the infimum of costs among such paths. For an unreachable vertex, distance is infinity. If a **negative-weight cycle** reachable from s can lead to v, one may loop arbitrarily often and make path cost arbitrarily negative; then no finite shortest distance exists for that v. An undirected negative edge creates a negative closed walk when traversable in both directions, so Dijkstra's nonnegative assumption matters even more [2].

## Relaxation as the common primitive

Keep a tentative estimate d[v], initialized d[s]=0 and d[other]=infinity. For edge u→v with weight w, **relax** if d[u]+w<d[v], setting d[v]=d[u]+w and parent[v]=u. Each finite estimate corresponds to a concrete path already found, hence is never **smaller** than a true finite optimum. Relaxation can only decrease estimates. The central challenge is knowing when an estimate has become final [1].

![Weighted graph: a longer route by edges can have a lower total cost.](/diagrams/weighted-shortest-path.svg)

## Dijkstra's greedy invariant

When every reachable edge weight is nonnegative, pick the unsettled vertex with smallest tentative distance. That vertex cannot later receive a shorter path through other unsettled nodes: any such path would first enter the unsettled region from a settled vertex, and nonnegative remaining edges cannot undercut the current minimum. Mark it settled, then relax its outgoing edges. This is the greedy proof; merely observing that a heap returns the smallest candidate is insufficient [1].

~~~python
from heapq import heappush, heappop

def dijkstra(graph, source):
    for edges in graph.values():
        for _, weight in edges:
            if weight < 0: raise ValueError("negative edge")
    distances = {source: 0}
    parents = {source: None}
    heap = [(0, source)]
    while heap:
        distance, u = heappop(heap)
        if distance != distances[u]:
            continue                 # obsolete heap entry
        for v, w in graph.get(u, []):
            candidate = distance + w
            if candidate < distances.get(v, float("inf")):
                distances[v] = candidate
                parents[v] = u
                heappush(heap, (candidate, v))
    return distances, parents

g = {"s":[("a",4),("b",1)], "b":[("a",2),("t",7)], "a":[("t",1)]}
d, parent = dijkstra(g,"s")
assert d["t"] == 4 and parent["t"] == "a"
assert d["a"] == 3 and "missing" not in d
~~~

The dictionary stores only reachable nodes. With binary heap and lazy duplicate entries, time is O((V+E) log(V+E)) in this implementation, with O(V+E) auxiliary heap entries in a worst-case bound. Specialized decrease-key structures can attain other bounds; do not silently claim this code has O(V) heap space. Keys must be mutually orderable when equal distances cause heap tuple comparison: in production, use a stable integer tie-breaker if vertex objects are incomparable.

## A worked shortest-path trace

For s→a cost 4, s→b cost 1, b→a cost 2, a→t cost 1, b→t cost 7: settle s (distance 0); discover a:4 and b:1. Settle b next and reduce a from 4 to 3, while t becomes 8. Settle a at 3 and reduce t to 4. Pop the obsolete a:4 entry but ignore it; then settle t at 4. The resulting route s→b→a→t costs 1+2+1=4. The direct edge s→a had fewer hops than s→b→a, yet was more expensive.

## Bellman–Ford and its proof boundary

Bellman–Ford relaxes all edges for up to |V|-1 passes. A shortest simple path in a graph without a reachable negative cycle uses at most |V|-1 edges, because repeated vertices could be removed without worsening the cost. After k passes, every path of at most k edges has been accounted for in the distance upper bounds. Thus |V|-1 passes suffice for finite optima; an additional successful relaxation indicates a reachable negative cycle can improve at least one distance [2].

Time is O(VE) and space O(V) for an edge list representation. Terminating early after a pass without changes is valid, but only under the same input and arithmetic assumptions. If a reachable negative cycle exists, distances of vertices reachable from that cycle are not well-defined finite shortest-path values. An unreachable negative cycle need not affect distances from s.

## Selection matrix and failure cases

| Situation | Starting algorithm | Limitation |
| --- | --- | --- |
| Equal unit edge weights | BFS | Minimizes hops |
| Nonnegative weighted edges | Dijkstra | Cannot handle negative edges |
| Negative edges, detect cycles | Bellman–Ford | O(VE) cost |
| Directed acyclic graph | Topological relaxation | Requires a DAG |
| All-pairs shortest paths | Floyd–Warshall or repeated single-source | Different complexity/space needs |

Do not mark a vertex as settled merely when enqueued in a weighted graph. A candidate path through another vertex might still improve it. Floating-point weights require numerical policies for infinities and precision. Negative cycles destroy the finite optimum, not just the usefulness of a particular implementation. For paths rather than distances, store parents and reverse the chain from target to s, rejecting unreachable targets.

**Prerequisite connections:** [Graph traversal](/en/topics/graph-traversal/) explains BFS layers and unreachable vertices. [Binary heaps](/en/topics/heaps-priority-queues/) explains why the priority queue can efficiently extract the current smallest estimate.

## Exercises and verification

1. On s→a weight 8, s→b weight 2 and b→a weight 1, the minimum distance to a is 3, not 8. Walk through the heap entries.
2. Add a negative edge a→t weight -5 to the sample. Dijkstra must reject it under its contract; Bellman–Ford can process it if no reachable negative cycle occurs.
3. Show why a negative cycle *unreachable from s* does not invalidate a reachable vertex's finite distance.
4. Compare Dijkstra to Bellman–Ford on small random graphs with only nonnegative weights and no self-loops; differences reveal a bug.
5. For every recovered path, verify that the sum of stored edge costs equals the reported distance and each predecessor edge actually exists.
