---
id: integrated-vm-mark-sweep-gc
title: "Garbage Collection Inside the Slot VM: Roots, Closures and Recursive Cycles"
description: "Integrate explicit-root mark-and-sweep with the verified slot VM, preserving mutable closures and reclaiming unreachable recursive cycles."
category: foundations
difficulty: advanced
updated: 2026-10-12
prerequisites: [versioned-bytecode-serialization, tracing-garbage-collection-reachability]
sources:
  - {title: "Hans-J. Boehm — Description of a Garbage Collector", url: "https://www.hboehm.info/gc/gcdescr.html", kind: "original collector implementation documentation"}
  - {title: "Robert Nystrom — Crafting Interpreters: Closures", url: "https://craftinginterpreters.com/closures.html", kind: "original engineering textbook"}
  - {title: "Python documentation — gc, Garbage Collector interface", url: "https://docs.python.org/3/library/gc.html", kind: "official standard library documentation"}
  - {title: "Java Virtual Machine Specification — Verification of Class Files", url: "https://docs.oracle.com/javase/specs/jvms/se25/html/jvms-4.html#jvms-4.10", kind: "official virtual machine specification"}
---
The earlier [heap reachability](/en/topics/tracing-garbage-collection-reachability/) chapter built a stand-alone object graph and a mark-and-sweep collector. The [versioned bytecode](/en/topics/versioned-bytecode-serialization/) chapter established a verified instruction representation. These techniques become a runtime design only when the evaluator itself knows **which values are roots**, which objects point to other objects, and when collection can occur without losing a value temporarily removed from a stack.

This chapter integrates the previous graph model with a **third execution path** for the existing typed slot VM. The original name-based VM and indexed slot VM remain unchanged and are used as independent runtime checks. The managed VM runs the same statically verified `SlotCode` but stores mutable cells and closures under heap identifiers. It is a bounded **pedagogical memory model implemented in Python**, not a replacement for Python's actual allocator or garbage collector [1][3].

## Object identities, values and the managed heap

The VM distinguishes **immediate** results from **managed** objects. Integers and exact rational results remain `Fraction` values; Booleans remain `bool` values. A cell or closure is allocated in an explicit `HeapModel` graph and represented within VM stacks and scopes by an immutable `ManagedRef(object_id)`. Identifiers increase monotonically and are not reused within one run, so a reclaimed object ID is not silently redirected to another allocation.

Two payload forms are important. A `ManagedCell` stores a current value, a write-permission bit and an initialized bit. A `ManagedClosure` stores compiled code and a snapshot of its lexical scope **lists**. Those lists contain values or managed references, not copies of managed objects. Thus a copied lexical scope can still point to the exact same writable cell as another closure [2].

The managed heap graph records outgoing edges. A cell containing a reference to a closure has an edge to that closure's ID; a closure has edges to every managed reference retained by its captured environment. When a mutable cell changes value through `STORE_SLOT`, its outgoing edge set is updated **at the same time**. When `INIT_REC_SLOT` fills a recursive placeholder, it adds an edge from the placeholder cell to the closure. Missing these updates is a genuine collector defect: the tracer could reclaim an object that source-level code can still reach.

The graph's objects are not real memory blocks and the object IDs are not machine addresses. Python objects still hold the payloads. Keeping this distinction explicit prevents a successful reachability test from being presented as evidence of native heap isolation, address safety or allocator performance.

## Root sets across activation records

A root is a live reference held **outside the managed heap graph**. In this VM, roots come from every active activation frame: all values in every operand stack and every slot in every lexical scope. The collector scans **all frames**, not just the frame at the top of the call stack. Otherwise a closure referenced by a suspended caller could be reclaimed while a callee is executing.

The root-discovery algorithm visits each stack and scope entry and selects only `ManagedRef` values. It then invokes the existing heap mark phase, which follows all outgoing managed-object edges transitively. The sweep phase deletes objects not reached from that starting set. The runtime also discards corresponding payload records so that the graph and payload table contain the same live IDs after each collection.

A returned top-level closure presents a special case. At the instant `RETURN` completes, there is no remaining VM call frame that can root the result. The VM therefore treats the returned reference as a **temporary external root for the final collection**. Numeric results are immediate and require no such heap root, so all otherwise-unreachable managed objects can be reclaimed. The resulting managed function handle is deliberately **opaque and cannot be invoked through a public external-call API** in this chapter. Its survival demonstrates reachability, not a new calling convention.

## Safe points, temporary roots and allocation budgets

A mark-and-sweep collector must not run while the mutator's reference graph is inconsistent. The implementation triggers periodic collections **between completed bytecode instructions**. The interval is an explicit positive integer, `gc_interval`, representing dispatched instructions. For example, `gc_interval=1` requests a collection after every completed instruction; it is useful for correctness stress tests, not normal throughput.

Allocation introduces a less obvious temporary-root case. The VM's `BIND_SLOT` first pops the initializer value from the operand stack and then allocates its managed cell. If the heap has reached capacity and the allocator collects before adding the cell, that popped value is no longer a normal stack root. When it is a managed closure reference, the allocator must explicitly preserve it as a **temporary allocation root**. The managed runtime passes such transient references to its collection call. This closes a window in which aggressive collection could destroy a live initializer.

The heap has an explicit maximum number of objects. An allocation at capacity triggers a collection using active frames and temporary references; if no sufficient space becomes available, allocation raises `MemoryError`. The VM continues to enforce instruction and call-frame budgets. This is **not** comprehensive resource containment: a single operation on arbitrarily large `Fraction` operands could consume considerable host CPU and memory before the next collection.

## Cyclic recursive closures and their lifetimes

The earlier compiler's `let rec` creates a placeholder cell before building a closure. The closure captures a reference to the cell. Initialization then stores the closure in that same cell, forming a reachable cycle: **cell → closure → cell**. Reference counting alone would not necessarily reclaim a cycle after it loses all external references. Tracing collection can: if no stack, lexical scope or retained result refers to either object, neither is marked, and both are swept [1].

While the recursive function is running, however, its own call frames and captured scopes root the placeholder cell. The collector must **not** reclaim the cycle during a nested call. This gives a strong test: execute a recursive factorial with collection after every instruction, then check both its exact result and the final absence of reachable managed objects. The final collection should reclaim the recursive cell and closure once the computation has returned a numeric result.

A separate case returns a closure that captures a mutable counter. That closure outlives its creator's frame, but its reference remains rooted by the caller's local slot. It must survive repeated collections and preserve its counter across calls. Changing the collector frequency must **not change the program's value**. This is a semantic invariant, not a speed benchmark.

## Executable implementation and observation

The [managed VM implementation](https://github.com/christianrss/manual/blob/main/examples/python/managed_slot_vm.py) exposes `run_managed` and `evaluate_managed`. It always calls the earlier bytecode verifier before running; `ManagedResult` reports the result, number of collections, reclaimed count, peak managed objects and remaining objects. The following block is identical in the English and Portuguese chapters.

~~~python
from fractions import Fraction
from examples.python.lexical_slot_verifier import compile_slots, run_slots
from examples.python.managed_slot_vm import (
    run_managed, evaluate_managed, ManagedRef,
)

source = ("var x:Int=1 in "
          "let inc:Fn()->Int=fn()->Int=>set x=x+1 in "
          "inc()+inc()")
program = compile_slots(source)
managed = run_managed(program, gc_interval=1)
assert managed.value == run_slots(program) == Fraction(5)
assert managed.reclaimed == managed.allocated_objects
assert managed.live_objects == 0

recursive = ("let rec fact:Fn(Int)->Int="
             "fn(n:Int)->Int=>if n<2 then 1 else n*fact(n-1) "
             "in fact(5)")
typ, collected = evaluate_managed(recursive, gc_interval=1)
assert typ == "Int" and collected.value == Fraction(120)
assert collected.live_objects == 0

closure = run_managed(compile_slots("fn(x:Int)->Int=>x+1"))
assert isinstance(closure.value, ManagedRef)
assert closure.live_objects == 1
~~~

In the [new contract suite](https://github.com/christianrss/manual/blob/main/tests/test_integrated_vm_gc_contracts.py), output is compared against both the earlier slot VM and a separately written direct AST interpreter. Additional seeded tests cover mutation, lexical shadowing, factorial and varying collection frequencies. Negative tests check invalid bytecode, impossible execution budgets and full-heap allocation failures. These finite experiments show the implementation satisfies the stated cases, not that arbitrary VM programs are formally memory-safe.

## Complexity, correctness boundaries and extensions

Let V be the number of currently allocated managed objects and E the number of graph edges between them. Each full mark-and-sweep collection visits reachable vertices and edges and examines allocated objects during sweep, giving **O(V + E)** time and O(V) auxiliary marking space under the model's bounded graph representation. Discovering roots additionally costs O(R), where R is the number of live values across all frame stacks and lexical scopes. A program requesting collection after every instruction can therefore incur O(I(V+E+R)) overhead across I instructions in the worst case; this interval is intended for debugging invariants.

The allocation counter, peak managed-object count and collection count are **model statistics**, not measurements of Python's real heap, resident memory or allocation latency. The collector is stop-the-world, single-threaded and non-generational. It does not relocate objects, compact memory, scan arbitrary machine stacks, implement weak references, finalizers, write barriers for concurrent collection or incremental pauses. The VM's runtime still depends on Python's own allocation and lifetime mechanisms, and its instruction verifier remains limited to the published in-memory bytecode subset [3][4].

The integration proves a specific engineering distinction: **a root must be present at every collection safe point, and every managed reference mutation must be reflected in the graph**. A later implementation could add typed heap-object layouts, incremental marking, remembered sets or a native allocator, but each would require independent invariants and tests.

## Exercises and verification

1. Identify the roots while a callee executes and its caller is suspended. **Check:** values in both frames' stacks and lexical scopes must be scanned.
2. Explain why a closure popped just before allocating a mutable cell requires a temporary root. **Check:** a full-heap collection at that point must preserve the initializer's managed reference.
3. Draw the recursive reference cycle formed by `let rec`. **Check:** the cell references the closure and the closure's captured slots reference the cell.
4. Predict the effect of changing `gc_interval` from 1 to 100 on a valid counter program. **Check:** collection statistics may change, but the exact numeric result must not.
5. State when `MemoryError` is raised. **Check:** the heap is at capacity, collection cannot free enough objects, and another allocation is requested.
6. Distinguish this model from a production collector. **Check:** graph identities and object counts are simulated; neither host memory isolation nor concurrent garbage collection is provided.
