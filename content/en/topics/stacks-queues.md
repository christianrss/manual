---
id: stacks-queues
title: "Stacks and Queues: LIFO, FIFO, Deques and Invariants"
description: "Distinguish stack and queue contracts, derive their invariants, implement balanced-delimiter scanning and BFS-compatible queues."
category: algorithms
difficulty: beginner
updated: 2026-10-09
prerequisites: [arrays-and-strings, linked-lists]
sources:
  - {title: "Princeton Algorithms — Bags, Queues, and Stacks", url: "https://algs4.cs.princeton.edu/13stacks/", kind: "university textbook"}
  - {title: "Python Documentation — collections.deque", url: "https://docs.python.org/3/library/collections.html#collections.deque", kind: "official language documentation"}
  - {title: "Python Documentation — Data Structures", url: "https://docs.python.org/3/tutorial/datastructures.html", kind: "official language documentation"}
---
A **stack** and a **queue** can store the same values yet implement fundamentally different retrieval contracts. A stack removes the **last** inserted element first (LIFO). A queue removes the **first** inserted element first (FIFO). Both are abstract data types: their contracts determine behavior, while arrays, linked lists and ring buffers are possible implementations. Confusing interface with representation leads to avoidable complexity mistakes [1].

## Contract of a stack

A stack supports push(x), pop(), peek() and empty(). After push(A), push(B), push(C), pop must return C and the remaining top is B. The invariant is that a pop returns the most recent push not yet matched by an earlier pop. With a dynamic array backed by a Python list, append and pop at the **end** are efficient amortized constant-time operations, under the usual resizing-array cost model [3].

A linked-list stack can insert and remove at its head in O(1), but node allocation and pointer locality change practical costs. For both representations, peeking at the top takes O(1) when it exists. Define the empty-stack policy: returning a sentinel is dangerous if that sentinel is a legitimate value; an explicit exception or optional result is clearer.

![A stack removes from one end while a queue removes from the opposite end.](/diagrams/stack-queue-operations.svg)

## Contract of a queue

A FIFO queue offers enqueue(x), dequeue(), front() and empty(). After enqueue(A), enqueue(B), enqueue(C), dequeue returns A; the next item is B. A singly linked list with head and tail pointers supports enqueue at tail and dequeue at head in O(1). Without a maintained tail, enqueue might scan n nodes and cost O(n). An array-backed **circular buffer** tracks head index and count, wrapping through fixed capacity with modulo arithmetic.

Using Python list.pop(0) is not the right general-purpose implementation: deleting index zero shifts all later references, O(n) worst-case for n elements. Python's collections.deque provides efficient appends and removals at either end, with approximately O(1) performance, and is the standard choice for FIFO queues in ordinary single-process Python algorithms [2].

## Balanced delimiters: a worked stack invariant

Consider checking that braces, brackets and parentheses are properly nested. Read characters left to right. On an opening delimiter, push its type. On a closing delimiter, the **top must be the matching opener**; if no opener exists or types differ, reject. At end, accept only when the stack is empty. The invariant is that after processing the first i characters, the stack contains exactly the opening delimiters that have not yet been matched, in nesting order.

~~~python
def balanced(text):
    opening = set("([{")
    matches = {")":"(", "]":"[", "}":"{"}
    stack = []
    for character in text:
        if character in opening:
            stack.append(character)
        elif character in matches:
            if not stack or stack.pop() != matches[character]:
                return False
    return not stack

assert balanced("{a:[b,(c)]}")
assert balanced("")
assert not balanced("([)]")
assert not balanced("(()")
assert not balanced(")")
~~~

For n characters, scanning costs O(n) time. The stack uses O(d) space, where d is the maximum number of simultaneously open delimiters, bounded by n. The code ignores all non-delimiter characters by contract; a language parser must additionally handle strings, comments and escapes because punctuation inside them might not act as syntax.

## Queue as the engine of breadth-first search

BFS relies on FIFO order to discover vertices in nondecreasing distance measured in **unweighted edges**. Initially enqueue the source and mark it discovered. Repeatedly remove the front vertex and enqueue each previously undiscovered neighbor. Since items inserted from a vertex at distance k are at distance k+1 and existing queue entries are at distance k or k+1, the first discovery of any vertex has minimum hop count.

~~~python
from collections import deque

def distances(graph, origin):
    distance = {origin: 0}
    queue = deque([origin])
    while queue:
        node = queue.popleft()
        for neighbor in graph.get(node, ()):
            if neighbor not in distance:
                distance[neighbor] = distance[node] + 1
                queue.append(neighbor)
    return distance

graph = {"s":["a","b"], "a":["t"], "b":["t"], "t":[]}
assert distances(graph,"s") == {"s":0,"a":1,"b":1,"t":2}
assert distances({},"missing") == {"missing":0}
~~~

Using a stack here would instead implement a depth-first traversal, whose first-found route need not be the shortest. BFS on an adjacency list costs O(V+E) when considering all reachable vertices and edges; the queue can hold O(V) entries. For weighted graphs, shortest paths require an appropriate algorithm such as Dijkstra, not ordinary FIFO traversal.

## Double-ended queues and monotonic variants

A **deque** permits insertion and removal at both the front and back. It can serve as a stack or queue depending on chosen operations. A **monotonic deque** additionally maintains values or indexes in nonincreasing/nondecreasing order by removing dominated entries from the tail. This supports sliding-window maximum with O(n) total deque operations, because each index enters and leaves at most once.

A **priority queue** is different: it removes an item by priority rather than FIFO arrival or LIFO recency. Binary heaps are a common priority-queue implementation and support O(log n) insertion/removal under ordinary comparison assumptions. Do not call a heap a FIFO queue just because both return 'the next' item; the next-item ordering contract differs.

## Memory and cost matrix

| Implementation | Push/enqueue | Pop/dequeue | Random access |
| --- | --- | --- | --- |
| Python list as stack at end | O(1) amortized | O(1) at end | O(1) indexing |
| Python list as queue at front | O(1) append amortized | O(n) shift | O(1) indexing |
| Deque as FIFO | Approximately O(1) both ends | Approximately O(1) both ends | O(n) middle access |
| Linked list with head/tail | O(1) at boundaries | O(1) at head | O(n) |

The distinctions are asymptotic and representation-dependent. A deque's middle indexed access may be linear; it is not an array replacement for arbitrary random access. A ring buffer with **fixed capacity** must specify behavior on full: reject, block, overwrite or resize; silent overwriting can lose work.

## When abstractions are insufficient

A local deque in one Python process does **not** provide durable distributed messaging. A queue used by multiple producers and consumers needs thread synchronization or an appropriate concurrent queue. A stack for parsing untrusted input should impose input-size or nesting-depth limits to protect memory. Infinite producer throughput into an unbounded queue causes backlog; capacity and admission policy are part of a robust API.

## Exercises and verification

1. Trace push(1), push(2), pop(), push(3), pop(): outputs are 2 and 3. Explain LIFO.
2. Trace enqueue(1), enqueue(2), dequeue(), enqueue(3), dequeue(): outputs are 1 and 2. Explain FIFO.
3. Prove the balanced delimiter invariant by induction on the scanned prefix.
4. Replace deque with list.pop(0) in BFS and identify why worst-case complexity can increase on a broad graph.
5. Explain why priority scheduling and FIFO scheduling are not interchangeable even if both use a structure called 'queue'.

**Related reading:** [Arrays](/en/topics/arrays-and-strings/) explain amortized growth; [linked lists](/en/topics/linked-lists/) provide node-based implementations; [graph traversal](/en/topics/graph-traversal/) develops BFS/DFS.
