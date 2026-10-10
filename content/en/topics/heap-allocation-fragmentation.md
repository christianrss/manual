---
id: heap-allocation-fragmentation
title: "Heap Allocation: Free Lists, Fragmentation and Coalescing"
description: "Model first-fit and best-fit heap allocation, contiguous free blocks, external and internal fragmentation, splitting and coalescing with independent tests."
category: operating-systems
difficulty: intermediate
updated: 2026-10-10
prerequisites: [processes-virtual-memory]
sources:
  - {title: "Operating Systems: Three Easy Pieces — Memory and Free-Space Management", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/", kind: "university textbook"}
  - {title: "Linux kernel — Physical Memory", url: "https://www.kernel.org/doc/html/latest/mm/physical_memory.html", kind: "official kernel documentation"}
  - {title: "Linux kernel — Memory Management APIs", url: "https://www.kernel.org/doc/html/latest/core-api/mm-api.html", kind: "official kernel API reference"}
---
Memory allocation has at least three different meanings in a systems program: an application asks a runtime or library for **object storage**; a process receives **virtual address ranges**; and the operating system assigns **physical pages** to back mappings. These layers are connected but must not be collapsed. A free-list allocator managing a contiguous arena does not directly implement a page table or decide which physical frame supplies a virtual page [1][2][3].

This chapter derives the policy and bookkeeping of one **fixed-size, byte-addressed arena**. It implements first-fit and best-fit allocation with splitting, deallocation with adjacent-block coalescing, and a separate size-rounding model. The program provides exact finite behavioral contracts and independently testable invariants; it is not a replacement for malloc, a Linux page allocator, or a thread-safe memory subsystem.

## What an allocator must track

Suppose an arena contains addresses `[0, N)`, with `N` positive. A live allocation is the **half-open interval** `[start, start+size)`: it includes `start` and excludes the end, so an allocation occupying `[4,8)` does not overlap another occupying `[8,11)`. A free interval is represented in the same way.

A **free list** records intervals available for future allocation. An **allocation table** associates an opaque handle with the interval held by a caller. This example uses short string labels to make the trace readable; actual pointer-based allocators must associate metadata with the returned address and validate usage under their own contracts [1].

Three conservation properties follow:

1. Every address in `[0,N)` belongs to **exactly one** free interval or live allocation.
2. Live allocation intervals cannot overlap each other; free intervals cannot overlap each other.
3. The union of free and allocated addresses has length `N`: `sum(free sizes)+sum(live sizes)=N`.

The implementation keeps free intervals **sorted by start address** and merges adjacent free neighbors after every release. Thus no two consecutive free records may overlap or even touch. That canonical representation makes fragmentation and correctness directly inspectable.

## Fragmentation: external is not internal

**External fragmentation** occurs when enough *total* unallocated space exists but no **single contiguous free region** satisfies a request. For example, free blocks `[0,4)` and `[8,12)` total eight units, but a request for five contiguous units must fail. A larger request cannot combine distant free fragments unless the allocator may relocate occupied objects, use noncontiguous backing, or change its address abstraction [1].

We expose an intentionally simple statistic `(total_free, largest_free, stranded)`, where `stranded=total_free-largest_free`. The third value quantifies *bytes outside the largest available hole*, not a standardized universal fragmentation score or bytes that can never be allocated. A request of size three may still fit into several small holes, so those units are not automatically wasted.

**Internal fragmentation** is different: the allocator reserves a block larger than the requested payload because of alignment, fixed size classes, pages, metadata or other constraints. A 13-unit payload rounded to a 16-unit reservation has three units of unused space *inside the reservation*. The free-list model below allocates precisely the requested units, ignores headers and alignment, and therefore deliberately has **zero modeled internal fragmentation**. We model reservation rounding separately rather than silently mix the two effects.

## First-fit and best-fit: policies over the same invariant

**First-fit** scans holes by increasing address and selects the *first* that is large enough. **Best-fit** scans all holes and selects the smallest adequate hole, breaking ties by the smallest address. Both policies split a larger free interval, returning its lowest-address prefix and preserving the residual suffix [1].

The two policies can choose different addresses for the same request. With holes of size seven at address zero and size five at address nine, a request for four units chooses address **0** under first-fit and address **9** under best-fit. This does **not** demonstrate that best-fit always wins: saving a large hole can help later requests, but repeatedly leaving tiny unusable remainders can hurt, and scanning all holes has cost. Neither policy makes a universal fragmentation guarantee.

The allocator returns an address or `None` if no contiguous hole fits, without changing state on failure. Invalid sizes or duplicate live handles raise `ValueError`; releasing a nonexistent handle raises `KeyError`. A handle becomes reusable after release. Python booleans are rejected as sizes to prevent `True` from silently becoming one byte.

## Executable contiguous arena with splitting and coalescing

~~~python
class ArenaAllocator:
    def __init__(self, capacity, policy="first"):
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        if policy not in ("first", "best"):
            raise ValueError("policy must be first or best")
        self.capacity = capacity
        self.policy = policy
        self.free_blocks = [(0, capacity)]
        self.allocated = {}

    def allocate(self, label, size):
        if (not isinstance(label, str) or not label.strip()
                or label != label.strip() or label in self.allocated):
            raise ValueError("invalid or duplicate label")
        if type(size) is not int or size <= 0:
            raise ValueError("size must be a positive integer")
        choice = None
        for index, (start, length) in enumerate(self.free_blocks):
            if length < size:
                continue
            if self.policy == "first":
                choice = index
                break
            if choice is None:
                choice = index
            else:
                old_start, old_length = self.free_blocks[choice]
                if (length, start) < (old_length, old_start):
                    choice = index
        if choice is None:
            return None
        start, length = self.free_blocks.pop(choice)
        if length > size:
            self.free_blocks.insert(choice, (start + size, length - size))
        self.allocated[label] = (start, size)
        return start

    def release(self, label):
        if label not in self.allocated:
            raise KeyError(label)
        block = self.allocated.pop(label)
        self.free_blocks.append(block)
        self.free_blocks.sort()
        merged = []
        for start, length in self.free_blocks:
            if merged and merged[-1][0] + merged[-1][1] == start:
                previous_start, previous_length = merged[-1]
                merged[-1] = (previous_start, previous_length + length)
            else:
                merged.append((start, length))
        self.free_blocks = merged

    def stats(self):
        total = sum(length for _, length in self.free_blocks)
        largest = max((length for _, length in self.free_blocks), default=0)
        return (total, largest, total - largest)

arena = ArenaAllocator(16)
assert [arena.allocate(k, 4) for k in "ABCD"] == [0, 4, 8, 12]
arena.release("A")
arena.release("C")
assert arena.free_blocks == [(0, 4), (8, 4)]
assert arena.stats() == (8, 4, 4)
assert arena.allocate("E", 5) is None  # 8 free units; no 5-unit span
arena.release("B")
assert arena.free_blocks == [(0, 12)]
assert arena.allocate("E", 8) == 0
assert arena.stats() == (4, 4, 0)

def policy_example(policy):
    a = ArenaAllocator(20, policy)
    for label, size in (("A", 7), ("B", 2), ("C", 5), ("D", 2), ("E", 4)):
        a.allocate(label, size)
    a.release("A")
    a.release("C")
    return a.allocate("F", 4)

assert policy_example("first") == 0
assert policy_example("best") == 9
~~~

The 16-unit trace starts fully allocated. Releasing A and C creates two disconnected holes of four units. The failed five-unit request leaves both unchanged. Releasing B merges the neighboring holes `[0,4)`, `[4,8)` and `[8,12)` into `[0,12)`, enabling the next eight-unit allocation. Coalescing does not **move** any live allocation, so it can only join *adjacent free space*. A compactor that relocates live objects requires an entirely different contract about pointers and references [1].

The most important correctness detail is update order: allocation validates before mutating, identifies a usable hole before changing lists, removes that hole, optionally inserts the suffix, and finally registers the live allocation. Release first verifies the handle, then adds its returned range, sorts and merges intervals. Because each release returns a range from the live table, this model has no separate double-free path that can duplicate free space: a second release raises `KeyError`. This is not protection against corrupted memory or arbitrary pointers in a native allocator.

## Memory conservation and complexity

Let `h` be the number of free intervals and `a` the number of live allocations.

- **Allocation with first-fit:** scanning at most `h` holes is `O(h)` worst-case; an early hit may stop sooner. Finding a hole is not `O(1)` just because the list is in memory. Python's list insert/pop can shift up to `h` entries, so worst-case remains `O(h)`.
- **Allocation with best-fit:** scans all `h` free intervals and uses `O(h)` time with a bounded-cost comparison model. It has no proven universal quality advantage.
- **Release:** appends and sorts at most `h+1` intervals then performs a single linear coalescing scan, so `O(h log h)` time for this simple implementation.
- **Storage:** `O(h+a)` metadata. The model does not actually reserve `N` bytes of physical memory: `capacity` is a logical address range, not a `bytearray` backing store.

These bounds describe the **simulation implementation** under constant-size identifiers and conventional dictionary lookup assumptions. Production allocators may use balanced trees, bins, segregated lists, slab caches, buddy allocation or per-thread/per-CPU data structures to optimize different workloads [2][3]. They also account for synchronization, memory pressure, memory reclamation, security hardening and allocator metadata, which the simple program omits.

## Rounding and internal fragmentation in a separate model

A fixed reservation granularity `g` rounds a payload of `x` units up to `g × ceil(x/g)`. The difference is unused capacity inside the reserved region. Such rounding may arise with size classes or page-granular reservations, although it should **not** be mistaken for a complete description of how a particular `malloc` implementation rounds or aligns memory [3].

~~~python
def rounded_reservation(payload, granularity):
    if (type(payload) is not int or payload <= 0
            or type(granularity) is not int or granularity <= 0):
        raise ValueError("positive integer sizes required")
    reserved = ((payload + granularity - 1) // granularity) * granularity
    return (reserved, reserved - payload)

assert rounded_reservation(13, 8) == (16, 3)
assert rounded_reservation(4096, 4096) == (4096, 0)
assert rounded_reservation(4097, 4096) == (8192, 4095)
~~~

For a 4097-unit payload reserved in 4096-unit chunks, the model reserves 8192 units with 4095 units internal slack. Importantly, multiple virtual pages can be backed by **nonadjacent physical frames**, so the requirement for two pages does not imply an 8192-byte physically contiguous frame allocation. The [virtual-memory chapter](/en/topics/processes-virtual-memory/) develops address translation and page permissions separately.

## Buddy systems, slab allocation and real Linux boundaries

A Linux physical-page allocator organizes free page blocks by **power-of-two orders** and splits larger blocks when a smaller order is required. Free matching buddy blocks may coalesce into a larger order. Its actual allocation decisions also depend on zones, migratetypes, reclaim and other kernel mechanisms [2]. The `/proc/buddyinfo` interface can help diagnose lack of higher-order page blocks, but a teaching arena of arbitrary lengths is **not** a buddy allocator.

For kernel object allocation, APIs such as `kmalloc`, `vmalloc` and `kvmalloc` have different contracts about contiguity and allocation context. In particular, `vmalloc` may provide **virtually contiguous** storage without physically contiguous pages; `kvmalloc` can use alternative backing paths [3]. Physical fragmentation, heap free-list fragmentation, and the unused tail of a page-rounded reservation are related resource-management concerns, not identical counters.

Memory safety also includes **lifetime**: access after free, double free, incorrect size calculations and pointer corruption are correctness or security problems rather than just fragmentation. Garbage-collected runtimes and moving compactors solve different parts of the lifecycle problem and may make relocation possible at the cost of metadata, runtime pauses or pointer-update machinery.

## Independent verification and model boundaries

The companion tests implement a **bitmap-based reference allocator** with one owner per address, deliberately **not** using the article's interval free list. They enumerate short operation histories under both policies, check all observable addresses, and reconstruct free spans from the bitmap after each action. The tests distinguish invalid requests, unsuccessful-but-valid requests, handles returned after free, adjacent coalescing and completely full/empty states.

Agreement across a finite domain provides evidence for the described model, not a proof against arbitrary integer inputs, race conditions, unbounded heaps, allocator corruption or hardware memory ordering. The simulator stores no payload data, does not expose real pointers, does not zero released memory and is not thread-safe. Never infer kernel page behavior or real latency directly from its unit-test results.

## Exercises and verification

1. Starting from a 16-unit arena, allocate four blocks of length four. Release A and C. Derive the free-list representation and prove why a request of size five fails despite eight units free.
2. Release B from that state. Show each coalescing step, compute `total_free`, `largest_free` and `stranded`, and confirm that occupied D never moves.
3. Construct an allocation history that leaves holes of sizes seven and five. Predict where first-fit and best-fit place a four-unit request; explain why one example does not establish general superiority.
4. Show the conservation equation after every allocation and deallocation. What extra invariant would be required to validate a native allocator returning pointers instead of labels?
5. Compute reservation and internal slack for payloads 1, 8, 9 and 16 with granularity eight. Explain why this cannot be added uncritically to external fragmentation.
6. Modify the design to enforce eight-unit alignment of returned addresses **without moving existing blocks**. What new prefix/suffix splitting rules and alignment-related slack appear?
7. Explain how the Linux buddy algorithm differs from first-fit in block sizes, search and merging, and why `vmalloc` changes the physical-contiguity requirement.
8. Design a property test that injects invalid labels and sizes. Prove that rejected operations cannot change the free-list representation or the live allocation table.

**Next:** [File descriptors, buffering and fsync](/en/topics/file-descriptors-buffering-fsync/) now distinguishes kernel open-file descriptions, shared offsets, visibility and durability. For another storage layer, [write-ahead logging](/en/topics/database-storage-wal/) develops database recovery semantics [1][2][3].
