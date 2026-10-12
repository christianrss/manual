---
id: tracing-garbage-collection-reachability
title: "Heap Reachability, Object Lifetimes and Stop-the-World Mark-and-Sweep"
description: "Derive object reachability and a bounded mark-and-sweep collector with shared closure cells, cycles, explicit roots and independent tests."
category: foundations
difficulty: advanced
updated: 2026-10-11
prerequisites: [mutable-cells-recursive-functions]
sources:
  - {title: "Hans-J. Boehm — A garbage collector for C and C++", url: "https://www.hboehm.info/gc/", kind: "original collector author and project"}
  - {title: "Hans-J. Boehm — Description of a Garbage Collector", url: "https://www.hboehm.info/gc/gcdescr.html", kind: "original implementation documentation"}
  - {title: "Python Data Model — Objects, values and types", url: "https://docs.python.org/3/reference/datamodel.html", kind: "official language reference"}
  - {title: "Robert Nystrom — Crafting Interpreters: Closures", url: "https://craftinginterpreters.com/closures.html", kind: "original compiler engineering textbook"}
---
A call frame can return while a closure continues to reference a variable created inside that frame. In the [mutable-cell compiler](/en/topics/mutable-cells-recursive-functions/), Python's runtime retains the captured cell automatically. That observation raises two independent questions: **which objects must remain alive**, and **which objects can safely be reclaimed?** This chapter derives the graph model behind tracing garbage collection and implements a bounded, stop-the-world **mark-and-sweep teaching heap** [1][2].

The collector in this chapter is **not installed inside the bytecode VM**. It is an explicit graph simulation with stable integer object identifiers. Making this boundary clear is more important than presenting an algorithm as a working production memory manager without handling pointers, native stacks, allocator metadata, synchronization, or runtime object layout.

## Objects, references and the root set

Represent the heap as a directed graph G=(V,E). Every vertex corresponds to a heap-allocated object and each directed edge represents a **strong reference** from one object to another. In the example implementation, object kinds are `closure`, `environment`, `cell`, `value` and `pair`. These tags are illustrative; a production runtime would need real object headers, field layouts and pointer maps. An integer identifier distinguishes object identity from the value it represents.

The **root set R** contains addresses directly held by program state outside the heap traversal: for instance, live activation-frame slots, global variables or VM registers. The example takes roots as an explicit argument to `collect(roots)`. It does not automatically inspect the Python call stack or registers. Requiring roots explicitly avoids pretending that Python local variables can be interpreted as pointers in another language's heap.

Define Reach(R) as the smallest set containing R and closed under outgoing references: if u is reachable and u points to v, then v is reachable. The central collector invariant is **never reclaim a reachable vertex**. Conversely, with complete and accurate roots and edges, all vertices outside Reach(R) are reclaimable in this closed graph model. Missing a root is not a minor bookkeeping error: it can cause the collector to free an object the program will still use.

## Worked closure lifetime example

Consider a function that creates a mutable counter cell and returns a closure that reads or modifies that cell. The object graph includes three vertices: a `closure` that points to an `environment`, which points to a `cell`. The function's finished activation frame is no longer a root. The returned closure, however, remains referenced by the caller, so the closure is a root. Graph traversal gives:

`root closure -> environment -> cell`

All three remain reachable. If an unrelated temporary `pair` object has no path from any root, it is reclaimed during collection. When the caller later removes its last reference to the closure and the root set becomes empty, the closure, environment and cell are all unreachable and can be reclaimed together. The lifetime of an object is therefore determined by **reachability**, not simply by the order in which functions return [3][4].

This also explains aliasing: two closures may refer to the same environment and the same mutable cell. Dropping one closure does not free the cell while the second remains rooted. A correct collector must follow the complete object graph, not count how many distinct lexical names are present in source code.

## The mark phase and the sweep phase

Mark-and-sweep is usually described as two conceptual phases. **Mark:** begin from every root and follow references until all reachable objects have been visited. A visited set prevents repeated work and infinite traversal around cycles. **Sweep:** iterate across allocated heap objects, reclaim those not in the marked set, and retain all marked objects [1][2].

The implementation uses an explicit `deque` for traversal instead of recursively walking Python function calls, so a long reference chain does not consume one Python stack frame per edge. Its `HeapModel.mark` returns sorted reachable identifiers. `HeapModel.collect` computes that set, removes every other vertex from its owned dictionary and returns a `Collection` containing the reachable identifiers, reclaimed identifiers and remaining object count. Object IDs increase monotonically and are **not reused**. This makes stale-ID tests unambiguous.

The model's collector is **stop-the-world** by contract: the graph does not mutate during one collection. It has no write barrier, concurrent marker, incremental snapshot or generational remembered set. Calling it concurrently with graph mutations would invalidate the assumptions of the reachability walk. Real concurrent and incremental collectors need additional synchronization and tri-color or barrier invariants, which are beyond this example [2].

## Why cycles matter

Suppose two `pair` objects A and B point to each other, while neither is reachable from any root. They form a directed cycle, but **cycles do not imply liveness**. A reference-counting system that only decrements counts when references are removed may fail to reclaim A and B, since each retains an incoming reference from the other. A tracing collector has no such problem: neither vertex appears during marking from the roots, so both are swept.

Conversely, if A is a root, the edge A→B makes B reachable, and B→A changes nothing about that result. The visited set guarantees termination even though the graph contains a cycle. This is why root reachability is a more useful correctness criterion for tracing collection than raw incoming-reference counts.

The demonstration also distinguishes an ordinary object reference from a borrowed or weak reference. **Only strong edges** are modeled; weak references, finalizers, resurrection and reference queues are not present. Adding these would change what can be reclaimed and when, so they cannot be inferred from the current implementation.

## Runnable graph lab and independent oracle

The [heap simulation](https://github.com/christianrss/manual/blob/main/examples/python/mark_sweep_heap.py) supports `allocate`, `set_references`, `mark`, `collect` and `get`, plus two complete worked scenarios. The first demonstrates a returned closure retaining a cell; the second demonstrates reclamation of a cycle:

~~~python
from examples.python.mark_sweep_heap import (
    HeapModel, closure_lifetime_example, cyclic_collection_example,
)

first, last = closure_lifetime_example()
assert len(first.reachable) == 3
assert len(first.reclaimed) == 1
assert last.remaining == 0

cycle = cyclic_collection_example()
assert len(cycle.reclaimed) == 2

heap = HeapModel()
cell = heap.allocate("cell")
env = heap.allocate("environment", (cell,))
closure = heap.allocate("closure", (env,))
assert heap.collect((closure,)).reclaimed == ()
assert heap.collect(()).reclaimed == (cell, env, closure)
~~~

The [independent contract suite](https://github.com/christianrss/manual/blob/main/tests/test_mark_sweep_heap_contracts.py) generates random small object graphs with a fixed seed. Rather than using the collector's deque traversal, its **separate fixed-point oracle** repeatedly expands a set until no more referenced vertices can be added. It compares this independently calculated Reach(R) with the mark and sweep results. Other cases test cycles, shared cells, changes in outgoing references, nonexistent roots, invalid object IDs, repeated collection and allocation capacity failures.

## Complexity and explicit failure boundaries

Let V be the number of allocated objects, E the total number of stored reference edges and R the number of roots. With ordinary set/dictionary operations treated as expected constant time, marking is **O(V_reachable + E_reachable + R)** in expected time, while sweeping scans O(V) allocated objects. The combined expected time is O(V+E+R), and the visited set and worklist need O(V_reachable+R) auxiliary space. These expressions describe **graph operations**, not actual allocator byte overhead or worst-case adversarial hash collisions.

The toy heap caps live objects at **8,192** and limits outgoing-reference list sizes. Allocation fails explicitly when full; collection does not run automatically on allocation. The graph stores immutable `HeapObject` records in a Python dictionary, and its own memory allocation is handled by Python. It does not use the bytecode VM's actual closure objects and thus **does not reclaim VM memory**. A real VM integration would need to identify every pointer-bearing operand stack, call frame, captured cell, constant table and global root. It would also need a strategy for object layouts, synchronization, fragmentation and potential cycles in metadata.

## Exercises and verification

1. Draw a graph with a returned closure, environment and counter cell. **Check:** if the closure is rooted, all three are reachable after the defining call returns.
2. Add a second closure referring to the same environment. Remove the first root. **Check:** the shared environment and cell remain live through the second root.
3. Create A→B and B→A with no roots. **Check:** both are reclaimed; a cycle does not generate a root.
4. Pass a nonexistent object ID as a root. **Check:** the model rejects the root rather than silently pretending it points to an empty object.
5. Show why the collector is incorrect if the mutator changes edges concurrently. **Check:** an object could become newly reachable after the marker passes its old parent without being traced.
6. Compare the algorithm with reference counting. **Check:** tracing handles unreachable cycles, while simple reference counting may leave them allocated.

Further work must connect real VM frames and runtime objects to a heap, define root enumeration and lifetime invariants, and eventually address fragmentation, generational policies and concurrent barriers. The graph simulation establishes the reachability model but **not** a production garbage collector.
