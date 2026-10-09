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

## Exercises and verification

1. Check every parent-child pair of [1,4,3,9,8,7] and explain why the heap is valid although the array is not sorted.
2. For the stream [5,1,8,2] with k=2, the retained value sets progress as {5}, {1,5}, {5,8}, {5,8}.
3. Explain why equal keys require a sequence counter when priority queue payloads do not support comparisons.
4. Compare successive heapq.heappop results after heapify with sorted input, including repeated values.
