---
id: heaps-priority-queues
title: "Binary Heaps and Priority Queues"
description: "Explain heap shape and order invariants, derive logarithmic updates and linear heapify, and solve top-k with executable examples."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis]
sources:
  - {title: "Python Documentation — heapq", url: "https://docs.python.org/3/library/heapq.html", kind: "official language documentation"}
  - {title: "Python Documentation — queue", url: "https://docs.python.org/3/library/queue.html", kind: "official language documentation"}
---
A **priority queue** selects an item based on priority instead of arrival order. A binary heap is one implementation: it maintains quick access to an extreme key without fully sorting all elements. A **min-heap** returns the smallest key first, following the convention of Python heapq [1].

## Two invariants, not one

The **shape invariant** requires a complete binary tree filled left-to-right at every level. The **order invariant** requires each parent key to be no greater than its child keys. Siblings need not be ordered. In a zero-based array, children of index i are 2i+1 and 2i+2; a nonroot element has parent (i-1)//2 [1].

Array [1,4,3,9,8,7] is a valid min-heap despite 4 being greater than 3. Each parent is no larger than its own children, so transitivity along all root-to-leaf paths makes the root the global minimum. Array [1,7,3,2] is not a heap, because 7 is the parent of 2 but exceeds it.

## Insertion, removal and building

To insert, append the new item, preserving the complete-tree shape, and swap it upwards while it is smaller than the parent. To remove the minimum, save the root, move the last item to index zero and swap downwards with the smaller child until order is restored. Only a single path can be out of order. With n entries, the height is floor(log2 n), so insertion and removal take O(log n), while inspecting the root takes O(1) [1].

Repeated insertion builds a heap in O(n log n). **Bottom-up heapify** works in O(n): half the nodes are leaves, about one quarter have height at least one, and the weighted sum of heights of internal nodes is linear in n. This distinction matters when all elements are available at once.

## Worked example: largest k elements

Keep a min-heap containing the k largest values seen so far. The root is the smallest of the retained values; if a newly arriving value exceeds the root, replace it.

~~~python
from heapq import heappush, heapreplace

def largest_k(values, k):
    if k < 0:
        raise ValueError('negative k')
    heap = []
    for value in values:
        if len(heap) < k:
            heappush(heap, value)
        elif k and value > heap[0]:
            heapreplace(heap, value)
    return sorted(heap, reverse=True)

assert largest_k([5, 1, 8, 2, 8, 3], 3) == [8, 8, 5]
assert largest_k([7, 2], 5) == [7, 2]
assert largest_k([7, 2], 0) == []
~~~

**Invariant:** after processing each prefix, the heap retains the largest min(k, prefix length) values. Each candidate replaces the current retained minimum only if it is larger. For n input values and k at least one, runtime including final sorting is O(n log k + k log k), with O(k) additional storage. This formulation scans all n items even when k equals zero.

## Comparison and suitability

| Operation | Unsorted array | Sorted array | Binary heap |
| --- | ---: | ---: | ---: |
| Read minimum | O(n) | O(1) at front | O(1) |
| Insert | O(1) amortized append | O(n) shifting | O(log n) |
| Remove minimum | O(n) search | O(n) shift | O(log n) |
| Search arbitrary key | O(n) | O(log n) | O(n) |

A heap is **not** a general-purpose key index. Efficiently changing priority for an arbitrary known item needs an index map or a lazy invalidation policy. Equal priorities need a stable tie-breaker such as an increasing sequence counter; otherwise incomparable payload objects may raise errors. Unbounded queues can consume memory, and priority-based service can starve low-priority tasks. heapq itself is not a concurrent task queue; queue.PriorityQueue provides locking semantics [2].

## Derive height and heap construction cost

In an array-backed complete binary tree, level `d` contains at most `2^d` nodes. Therefore the tree height is `⌊log₂ n⌋`, and a single sift-up or sift-down traverses at most that many edges. This establishes `O(log n)` for insertion and root removal, independently of comparisons between unrelated siblings. A heap never promises its array is sorted: only every parent is ordered relative to its own children [1].

Why is bottom-up construction `O(n)` rather than `O(n log n)`? A node of height `h` may need `O(h)` swaps, but there are at most approximately `n/2^(h+1)` such nodes. Summing `n Σ(h≥0) h/2^(h+1)` yields `O(n)` because the weighted geometric series converges. Treating all nodes as height `log n` ignores the fact that most are leaves. This reasoning is essential when comparing construction with `n` independent pushes [1].

## Choosing the priority queue contract

Priorities may be smallest-first or largest-first; repeated keys may or may not need stable order. A binary heap excels at extracting extrema but not at searching for arbitrary keys. For Dijkstra, a common Python implementation inserts updated (priority,node) pairs and ignores obsolete entries when popped; without decrease-key, the heap can temporarily contain repeated nodes. For a job scheduler, fairness and starvation policy matter: low-priority jobs can wait forever if high-priority work never stops.

**Worked trace:** insert `8,3,5,1` into a min-heap. After inserting 8: `[8]`; insert 3 and sift up: `[3,8]`; insert 5: `[3,8,5]`; insert 1 and sift twice: `[1,3,5,8]`. Removing the minimum moves 8 to the root, compares children 3 and 5, and sifts to obtain `[3,8,5]`. Note that `[3,8,5]` is a heap although it is not sorted.

## Verify the invariants by testing

```python
import heapq

def heap_is_valid(items):
    return all(items[(i-1)//2] <= items[i] for i in range(1,len(items)))

numbers = [9, 1, 4, 8, 2, 7]
heapq.heapify(numbers)
assert heap_is_valid(numbers)
removed = [heapq.heappop(numbers) for _ in range(len(numbers))]
assert removed == sorted([9, 1, 4, 8, 2, 7])
```

A useful property-based test generates arrays including duplicates, negatives and empty inputs, heapifies them, then verifies both the parent-child invariant and sorted pop order. Beware of mutating objects whose priority participates in comparisons after insertion: their relative order may no longer be represented correctly. For concurrent producers and consumers, `heapq` alone is not a synchronization primitive; use a thread-safe queue or explicit locking [2].

## Costs that do not appear in Big O

A comparator may execute arbitrary application code, allocate memory or raise exceptions. Large objects stored as heap entries may increase memory traffic; adding a stable monotonic counter increases tuple width. For `top-k` over a stream, choose heap size `k`; if `k=0`, the optimal implementation should short-circuit rather than scan needlessly, unless the contract requires consuming the iterator. State whether input is finite and whether output must be sorted, because sorting retained values adds `O(k log k)`.

## Exercises and verification

1. Check every parent-child pair of [1,4,3,9,8,7] and explain why the heap is valid although the array is not sorted.
2. For the stream [5,1,8,2] with k=2, the retained value sets progress as {5}, {1,5}, {5,8}, {5,8}.
3. Explain why equal keys require a sequence counter when priority queue payloads do not support comparisons.
4. Compare successive heapq.heappop results after heapify with sorted input, including repeated values.
