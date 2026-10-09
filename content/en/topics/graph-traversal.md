---
id: graph-traversal
title: "Graph Traversal with BFS and DFS"
description: "Derive breadth-first and depth-first search, shortest paths in unweighted graphs, visited-state invariants and O(V+E) complexity."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis, hash-tables]
sources:
  - {title: 'CP-Algorithms — Breadth First Search', url: 'https://cp-algorithms.com/graph/breadth-first-search.html', kind: technical reference}
  - {title: 'MIT 6.006 — Introduction to Algorithms', url: 'https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/', kind: university course}
---
A graph is `G=(V,E)`: `V` is a collection of vertices and `E` contains directed or undirected edges. Problems such as reachability, dependency analysis and unweighted shortest paths can often be solved without comparing every possible pair of vertices. The essential representation is an **adjacency list** that lists neighbors of each vertex [1].

## Representation and assumptions
For an undirected edge between `A` and `B`, place each endpoint in the other's adjacency list. For directed edges, only include the specified direction. A graph need not be connected; a search started at one vertex reaches only its connected/reachable component. Complexity will use `V = number of vertices` and `E = number of edges` [2].

![Breadth-first search explores one hop at a time in an unweighted graph.](/diagrams/bfs-graph.svg)

## Breadth-first search: the queue invariant
**BFS** explores vertices in nondecreasing distance measured in edge count. Start with the source at distance zero. Place it in a FIFO queue. Repeatedly remove one vertex, and enqueue each previously unseen neighbor at distance `current_distance + 1`.

```python
from collections import deque

def shortest_hops(graph, source):
    distance = {source: 0}
    queue = deque([source])
    while queue:
        vertex = queue.popleft()
        for neighbor in graph.get(vertex, []):
            if neighbor not in distance:
                distance[neighbor] = distance[vertex] + 1
                queue.append(neighbor)
    return distance

sample = {'A':['B','C'], 'B':['A','D'], 'C':['A','E'],
          'D':['B','F'], 'E':['C','F'], 'F':['D','E']}
assert shortest_hops(sample, 'A')['F'] == 3
assert shortest_hops(sample, 'A')['C'] == 1
```

**Proof idea:** the queue contains discovered vertices in nondecreasing distance order. A first discovery through a vertex at distance `d` sets distance `d+1`. If a shorter path to that neighbor existed, its predecessor would have been processed at an earlier layer. Thus the first assigned distance is optimal for **unit-weight edges** [1].

Every vertex is enqueued at most once and every adjacency entry is inspected at most once. With adjacency lists, time is `Θ(V_reachable + E_reachable)` and storage for the visited set, distances and queue is `O(V_reachable)`. Traversing every component yields `O(V+E)`.

## Depth-first search: stack and finishing order
**DFS** explores one path as deeply as possible before backtracking. It can use recursion or an explicit stack. A visited set prevents infinite loops in cyclic graphs. DFS is useful for component discovery, cycle detection, topological ordering on DAGs and many graph decompositions; its traversal tree is generally **not** a shortest-path tree [2].

```python
def dfs_iterative(graph, source):
    seen = set()
    stack = [source]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph.get(node, []))
    return seen
```

Because neighbors can be placed on the stack before a vertex is marked visited, this variant may hold duplicate entries; complexity remains bounded by adjacency pushes, `O(V+E)`. Marking on push avoids those duplicates but may change traversal order.

## Selection and failure modes
| Goal | Appropriate starting point | Caveat |
| --- | --- | --- |
| Fewest edges from a source | BFS | Only for uniform/unit edge weights |
| Reachability | BFS or DFS | Respect edge direction |
| Explore dependency graph | DFS | Cycles must be detected separately |
| Lowest weighted cost | Dijkstra or Bellman–Ford | BFS is insufficient when edge costs vary |

## Exercises and verification
1. Add an isolated vertex `Z` to the sample graph. It must be absent from distances starting at `A`.
2. Replace edge `A→B` weight 1 with weight 100 and add a two-edge route of total weight 2. BFS minimizes **hops**, not weighted cost.
3. For `V=1` and `E=0`, BFS must return `{source: 0}` even if the adjacency map is empty.

Explain whether your input is a directed graph, how missing vertices are represented and which meaning of "shortest" your algorithm actually guarantees.
