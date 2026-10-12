---
id: resizable-arrays-capacity-amortized-cost
title: "Dynamic arrays: capacity, shrinking and amortized analysis"
description: "Implement a resizable array with append, pop, reference clearing and quarter-full shrinking, then prove amortized costs."
category: algorithms
difficulty: foundational
updated: 2026-10-12
prerequisites: [arrays-and-strings, complexity-analysis, abstract-data-types-representation-invariants]
sources:
  - {title: "Open Data Structures — Array-Based Lists", url: "https://opendatastructures.org/ods-python/2_Array_Based_Lists.html", kind: "open computer science textbook"}
  - {title: "MIT 6.006 — Introduction to Algorithms", url: "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/", kind: "university course"}
  - {title: "Python Tutorial — Data Structures", url: "https://docs.python.org/3/tutorial/datastructures.html", kind: "official programming documentation"}
---
A fixed-size array reserves a known number of slots. A dynamic array distinguishes **logical length n** from **allocated capacity C**, providing growth without allocating a fresh buffer at every insertion. Introductory array material describes geometric growth; here we implement both expansion and contraction, prove correctness and analyze sequences of **mixed appends and removals**, rather than only consecutive appends [1][2].

## Representation and its invariants

The private buffer has C slots, with 0 <= n <= C and C >= 1. Only slots with indices 0 through n-1 belong to the logical sequence. Unused slots remain private and are cleared when an element is removed so that obsolete references are not retained.

A live element may itself be None. Consequently, finding None in a slot does not tell us if it is occupied: the explicit n field is authoritative. The data structure stores references to objects, not deep copies. Python's built-in list is also based on an extensible array of references, but its exact capacity policy is implementation-dependent [3].

Indexed access is Θ(1) under a unit-cost RAM model. Keeping C separate from n clarifies why allocated memory can exceed live elements, and why a snapshot of n elements costs Θ(n) to copy their references.

## Doubling capacity after filling the buffer

When n equals C, append first allocates 2C slots and copies all n references, then writes the new value. Otherwise, it writes only the next unused slot. A resizing append therefore has Θ(n) worst-case work even though an ordinary append uses constant work.

If the program expanded by only one slot per insertion, n insertions could copy 1+2+...+(n-1) = Θ(n²) references. Doubling capacity instead copies at sizes 1, 2, 4, 8 and so forth, totalling less than 2n moves over n consecutive appends. Counting the actual insertions, their aggregate work remains O(n): **O(1) amortized append**, not O(1) worst-case append [1][2].

This guarantee belongs to the particular resizing algorithm, not to all collections that call themselves arrays.

## Shrinking without repeated reallocations

Reducing capacity immediately whenever an array becomes half full can cause an adversarial sequence to oscillate around its resize boundary, paying for repeated copies. Here pop shrinks only when the new size satisfies 4n <= C and C > 1, cutting capacity to max(1,C/2). After shrinking, occupancy is approximately one half; another comparable resize needs a significant number of operations.

This gap between growth at full capacity and contraction at quarter capacity is **hysteresis**. Deletion saves the removed element, clears its old slot, updates n and only then checks the shrink condition. Removing from an empty sequence raises IndexError without mutation.

## Implement and inspect the state

~~~python
class ResizingArray:
    def __init__(self):
        self._slots = [None]
        self._size = 0
        self.moves = 0

    @property
    def capacity(self):
        return len(self._slots)

    def __len__(self):
        return self._size

    def _resize(self, capacity):
        if capacity < max(1, self._size):
            raise ValueError("capacity would lose elements")
        new_slots = [None] * capacity
        for i in range(self._size):
            new_slots[i] = self._slots[i]
            self.moves += 1
        self._slots = new_slots

    def append(self, value):
        if self._size == self.capacity:
            self._resize(2 * self.capacity)
        self._slots[self._size] = value
        self._size += 1

    def pop(self):
        if self._size == 0:
            raise IndexError("empty array")
        self._size -= 1
        value = self._slots[self._size]
        self._slots[self._size] = None
        if self.capacity > 1 and 4 * self._size <= self.capacity:
            self._resize(max(1, self.capacity // 2))
        return value

    def get(self, index):
        if type(index) is not int or not 0 <= index < self._size:
            raise IndexError("index out of range")
        return self._slots[index]

    def snapshot(self):
        return tuple(self._slots[:self._size])

a = ResizingArray()
for item in (None, 4, 8, 12, 16):
    a.append(item)
assert a.snapshot() == (None, 4, 8, 12, 16)
assert a.capacity == 8 and a.get(0) is None
for item in (16, 12, 8, 4, None):
    assert a.pop() == item
assert len(a) == 0 and a.capacity == 1
~~~

The moves field counts references copied during resizing; it is not a timing measurement. The snapshot creates a tuple containing the same object references, not a deep copy. This class does not provide thread synchronization.

## Prove correctness by induction

At construction, n=0 and C=1 satisfy the invariant. On append, an available slot is filled and n increases by one. If full, doubling capacity preserves the old n elements in the same order and creates at least one free slot.

On pop, n must be positive. The old last element is returned and cleared; the remaining prefix preserves every prior element except the one removed. Any shrink copies precisely that prefix. Because 4n <= C implies n <= C/4 <= C/2, contraction never allocates fewer than n slots. The minimum capacity one preserves the empty-state invariant.

Thus after every successful operation the logical sequence matches the sequence of appends and pops, 0 <= n <= C remains true, and None can be stored like any other element.

## Derive O(1) amortized updates

Define a nonnegative potential Phi(n,C) equal to **2n-C if n >= C/2**, and **C/2-n otherwise**. Charge one unit for the basic append or pop, plus one for every live reference copied. The amortized cost is actual cost plus the potential change.

For growth at n=C, copying C references and appending one costs C+1. The potential drops from C to 2 after capacity doubles, giving amortized cost (C+1)+(2-C)=3. For contraction at n=C/4 after a pop, copying n references is paid by the decrease from roughly C/4 units of accumulated potential to zero. For operations without resizing, changing n by one changes the potential by at most a constant.

Summing these amortized charges telescopes the potential changes. Since Phi stays nonnegative and begins at a constant, **any sequence of m append/pop operations starting from empty costs O(m) reference moves and writes**. There is no probability assumption. The bound would require a new proof if the shrink threshold or growth factor changed [2].

## Representation-driven trade-offs

Valid indexed reads are Θ(1). Individual resizing operations cost Θ(n) worst-case; append and end-pop are O(1) amortized. Inserting or removing an item near the beginning needs Θ(n) worst-case shifts, even without resizing. Snapshots cost Θ(n) in time and reference storage. The capacity after operations is O(max(1,n)) under this policy, although the referred-to Python objects can consume arbitrary additional memory.

This is a suitable structure when indexing and end operations dominate. A linked list or a specialized deque can be preferable when operations repeatedly affect other positions. A benchmarking result cannot replace the stated model, especially when garbage collection and actual allocator behavior vary.

## Verification and exercises

Compare this array against an independent ordinary Python list for adversarial and generated operation sequences. Include None, repeated values, sizes at powers of two, full draining and rejected empty pops. Verify the move counter remains linear over long mixed sequences.

1. Compute the capacity after nine consecutive appends.
2. Explain why clearing the unused final slot affects reference lifetime without changing logical order.
3. Give a counterexample to the claim that every append is Θ(1) worst case.
4. Show how the quarter-full policy avoids repeated growth/shrink at the same size.
5. Calculate Phi for (n,C) equal to (8,8), (9,16), (2,8) and (2,4).
6. Contrast end removal and arbitrary-position removal.

Further reading: [arrays](/en/topics/arrays-and-strings/), [ADT contracts](/en/topics/abstract-data-types-representation-invariants/) and [asymptotic analysis](/en/topics/complexity-analysis/).
