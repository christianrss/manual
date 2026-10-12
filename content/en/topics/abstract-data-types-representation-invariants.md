---
id: abstract-data-types-representation-invariants
title: "Abstract data types: interfaces, representation invariants and costs"
description: "Separate an ADT contract from storage, derive a bounded circular queue and verify FIFO, wraparound and complexity."
category: algorithms
difficulty: foundational
updated: 2026-10-12
prerequisites: [data-types-bytes-and-representation, arrays-and-strings, complexity-analysis]
sources:
  - {title: "Open Data Structures — Interfaces", url: "https://opendatastructures.org/ods-python/1_2_Interfaces.html", kind: "university-level open textbook"}
  - {title: "Open Data Structures — Array-Based Lists", url: "https://opendatastructures.org/ods-python/2_Array_Based_Lists.html", kind: "university-level open textbook"}
  - {title: "Python standard library — collections.deque", url: "https://docs.python.org/3/library/collections.html#collections.deque", kind: "official language documentation"}
---
A **data structure** arranges information in memory; an **abstract data type (ADT)** specifies which operations clients may perform and the observable results. A queue may use an array, linked nodes or a library deque without changing its FIFO contract. Choosing a representation before specifying its required operations confuses interface with implementation [1]. The fundamental skill is to derive storage rules from observable behavior rather than memorize one implementation.

## Contracts before classes and containers

A stack removes the most recently inserted value (LIFO); a queue removes the earliest still present (FIFO). A set records membership without independent duplicate occurrences. A map associates keys with values. A list supports indexed access and positional updates. These are distinct contracts even when several representations share the same physical array [1].

For a bounded queue, define a positive integer capacity C, an insertion operation that fails if the queue is full, and a removal operation that fails if it is empty. Peeking reads the oldest value without removing it; size returns the number of live elements. The queue accepts any Python object, including None. Therefore using None alone to indicate emptiness is invalid; an empty state must be represented separately from element contents.

## Derive the circular array representation

Allocate C slots, keep an index h for the oldest element and a logical size n. Require the numerical invariant 0 ≤ n ≤ C and 0 ≤ h < C. The element at abstract position i, for 0 ≤ i < n, is physically stored at index (h + i) mod C. This is a **representation invariant**: it relates the public logical sequence to the private buffer.

For C=4, h=2 and n=3, the occupied physical positions are 2, 3 and 0. The next insertion writes to index (2+3) mod 4 = 1. No values need to shift. In contrast, deleting the first element of a Python list generally shifts references for later positions. Circular indexing is a way to obtain constant-time FIFO operations from a fixed array, not a new abstract behavior [2].

Physical empty slots can contain None, just as an occupied slot can contain the explicitly inserted value None. The size and head establish which slots are logically occupied. This distinction prevents the sentinel bug in which a legitimate element is mistaken for an empty cell.

## Construct each operation from the invariant

On enqueue, reject when n=C; otherwise write at tail (h+n) mod C and increment n. Existing logical positions remain unchanged while one new element appears at the end. On dequeue, reject when n=0; otherwise read the value at h, clear the reference, advance h to (h+1) mod C and decrement n. The first logical element disappears; all others retain their relative order.

Clearing the removed reference can reduce accidental retention of objects in a garbage-collected runtime. It is not what establishes correctness of FIFO order, because occupancy comes from the count. For C=1 the index always remains zero, yet the size distinguishes full and empty. This edge case is particularly effective for detecting incorrect head/tail arithmetic.

~~~python
class BoundedQueue:
    def __init__(self, capacity):
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("invalid capacity")
        self._slots = [None] * capacity
        self._head = 0
        self._size = 0

    def __len__(self):
        return self._size

    def enqueue(self, value):
        if self._size == len(self._slots):
            raise OverflowError("queue full")
        tail = (self._head + self._size) % len(self._slots)
        self._slots[tail] = value
        self._size += 1

    def dequeue(self):
        if not self._size:
            raise IndexError("queue empty")
        value = self._slots[self._head]
        self._slots[self._head] = None
        self._head = (self._head + 1) % len(self._slots)
        self._size -= 1
        return value

    def peek(self):
        if not self._size:
            raise IndexError("queue empty")
        return self._slots[self._head]

    def snapshot(self):
        capacity = len(self._slots)
        return tuple(self._slots[(self._head + i) % capacity]
                     for i in range(self._size))

q = BoundedQueue(2)
q.enqueue("A")
q.enqueue(None)
assert q.snapshot() == ("A", None)
assert q.dequeue() == "A"
q.enqueue("B")
assert q.snapshot() == (None, "B")
assert q.peek() is None
assert q.dequeue() is None and q.dequeue() == "B"
assert len(q) == 0
try:
    q.dequeue()
except IndexError:
    pass
else:
    raise AssertionError("empty dequeue succeeded")
~~~

## Prove the implementation preserves its contract

Initially n=0 and h=0, so the bounds hold and the abstract sequence is empty. Assume the invariant before a successful enqueue. Since n<C, the tail is the first slot following all n live logical positions. Writing to it and increasing n preserves the earlier sequence and appends the new value. A successful dequeue requires n>0. Advancing the head maps every old logical position i+1 to new position i, proving that exactly the oldest element was removed.

Peek and size do not mutate state. On an unsuccessful operation, the exception is raised **before** modifying the array, head or count. Induction over operation sequences therefore proves correspondence with an abstract FIFO list, provided callers do not directly corrupt the internal attributes. Python underscores express a convention, not enforced privacy.

## Analyze costs and compare representations

Enqueue, dequeue, peek and length use a fixed number of arithmetic and reference operations, hence O(1) time under the ordinary RAM model. Creating a snapshot of n elements takes O(n) time and O(n) additional references. Storage reserves O(C) slots even when the queue is empty. This implementation does **not** grow automatically; an insertion into a full queue is an error.

A dynamic array may support amortized O(1) append but incur O(n) work during resizing. A linked-node queue with head and tail pointers supports O(1) endpoint operations but requires one allocation per node. Python collections.deque already offers efficient endpoint behavior and is normally preferable in everyday code [3]. The bounded circular implementation remains valuable for teaching representation and a hard capacity contract.

| Client needs | Candidate | Key cost |
| --- | --- | --- |
| FIFO and fixed capacity | Circular buffer | O(C) reserved slots |
| FIFO and flexible capacity | Deque or linked queue | Growth or node overhead |
| Index by position | Dynamic array | O(1) index, shifts on insertion |
| Lookup by key | Hash table | Expected constant-time under assumptions |
| Highest priority first | Heap | Logarithmic update, not FIFO |

Complexity describes an operation under assumptions, not a universal ranking. Actual memory usage also depends on object references, allocator behavior, cache locality and element size.

## Independent verification and counterexamples

A list can serve as a simple reference model: append inserts at the end, and pop(0) removes the oldest. Although its removal costs O(n), it is an understandable oracle for short tests. Enumerate all short sequences of operations against both implementations; after every operation compare output, error type, size and logical contents. Include wraparound, None, repeated errors, and capacity one.

The queue is unsuitable if an unbounded workload must never reject inserts; a capacity policy is part of the ADT. The proof also does not establish thread safety: concurrent read-modify-write operations may race. Nor does FIFO guarantee persistence, network delivery or priority ordering. These are different contracts. A shallow snapshot copies element references rather than deeply cloning mutable elements, so aliasing remains a separate concern.

## Exercises and verification

1. Trace head, count, slots and logical sequence for enqueue(A), enqueue(B), dequeue(), enqueue(C) with C=2.
2. Reimplement the same interface using collections.deque, retaining the same bounded-capacity errors [3].
3. Compare a list reference model against the circular queue for every operation sequence of length at most six at capacities 1, 2 and 3.
4. Demonstrate why a test based on the head slot being None fails when None is valid input.
5. Prove by induction that dequeue preserves FIFO and both numeric bounds.
6. Modify the design to overwrite the oldest value when full. Explain why this changes the public contract rather than merely its performance.

Related: [arrays](/en/topics/arrays-and-strings/), [linked lists](/en/topics/linked-lists/), [stacks and queues](/en/topics/stacks-queues/) and [complexity](/en/topics/complexity-analysis/).