---
id: linked-lists
title: "Linked Lists: Nodes, Reversal, Cycles and Ownership"
description: "Implement and prove singly linked-list reversal and Floyd cycle detection; compare pointer operations with dynamic-array costs."
category: algorithms
difficulty: beginner
updated: 2026-10-09
prerequisites: [arrays-and-strings]
sources:
  - {title: "Princeton Algorithms — Linked Lists", url: "https://algs4.cs.princeton.edu/13stacks/", kind: "university textbook"}
---
A **singly linked list** is an ordered sequence of nodes. Each node stores a value and a reference to the next node, or a null reference marking the end. Unlike a dynamic array, nodes need not be placed in adjacent memory addresses. Insertion at a position for which we already possess the **preceding node** changes only a fixed number of links, but finding that position can still require scanning the entire list [1].

## Node invariant and the representation contract

Represent an empty list by head=None. A nonempty acyclic list starts at head and following next reaches each member exactly once before None. The list's order is defined by pointers, not address values. A tail reference, when present, must always refer to the last node whose next is None. A stored length, if present, must agree with the number of reachable nodes. These extra fields speed up specific operations but add maintenance obligations.

For [8,3,5], head points to a node containing 8, which points to 3, which points to 5, whose next is None. Prepending 4 means creating a new node with next=head then assigning head=new_node. Removing the first node sets head=head.next. Both update O(1) pointers, assuming object allocation and memory reclamation are accounted for separately.

## Why index access and deletion are different

To get the element at position i, start at head and follow i next links, so index lookup is O(i+1) and worst-case O(n). Adding after a **known** node is O(1), but adding at arbitrary index i requires locating its predecessor first, costing O(n) worst-case. Removing a **known successor** of a known predecessor can also be O(1), provided node ownership and references remain valid. Removing a node when only its value is given requires finding it.

A doubly linked list stores next and previous references. With a known node it can unlink a middle element in O(1), at the cost of an extra reference per node and stricter pointer invariants. Neither list provides O(1) arbitrary indexed access. In garbage-collected languages, removed nodes can remain allocated while other references still point to them; in C/C++, dangling pointers can lead to memory-unsafe behavior.

## Reverse a list by rewriting links

Reversal illustrates the central pointer invariant. Maintain prev as the already-reversed prefix, cur as the first unreversed node, and nxt as a temporary saved link. Each iteration redirects cur.next=prev, then advances prev and cur. The loop invariant is that prev heads a reversed prefix and cur heads the untouched suffix, with no original node lost. At the end cur=None and prev heads the fully reversed list.

![Reversing a linked list requires preserving the next pointer before rewiring.](/diagrams/linked-list-reversal.svg)

~~~python
class Node:
    def __init__(self, value, next=None):
        self.value = value
        self.next = next

def from_values(values):
    head = None
    for item in reversed(values):
        head = Node(item, head)
    return head

def to_values(head):
    result = []
    while head is not None:
        result.append(head.value)
        head = head.next
    return result

def reverse_list(head):
    prev = None
    current = head
    while current is not None:
        next_node = current.next
        current.next = prev
        prev = current
        current = next_node
    return prev

assert to_values(reverse_list(from_values([1,2,3]))) == [3,2,1]
assert reverse_list(None) is None
assert to_values(reverse_list(from_values([7]))) == [7]
~~~

The reversal uses O(n) time and O(1) extra auxiliary space, excluding the existing n nodes. The construction and conversion helpers each use O(n) work; do not include their allocation in the reversal's space claim. It mutates the input links; callers holding references to old nodes must understand that the old head becomes the new tail.

## Detect a cycle with two speeds

A list can accidentally contain a cycle: some node.next points to a node earlier in the sequence. Naively iterating until None then **never terminates**. Floyd's tortoise-and-hare algorithm moves one pointer one node at a time and another pointer two nodes at a time. If there is a cycle, once both enter it, their relative position around a cycle of length c advances by one modulo c each iteration, so they eventually meet. If there is no cycle, the fast pointer reaches None [1].

~~~python
def has_cycle(head):
    slow = fast = head
    while fast is not None and fast.next is not None:
        slow = slow.next
        fast = fast.next.next
        if slow is fast:
            return True
    return False

acyclic = from_values([1,2,3])
assert not has_cycle(acyclic)
cyclic = from_values([4,5,6])
cyclic.next.next.next = cyclic.next
assert has_cycle(cyclic)
assert not has_cycle(None)
~~~

Use **identity** rather than equality for meeting pointers: two nodes with equal values need not be the same node. The algorithm uses O(n) time until termination or meeting, O(1) memory, and it does not alter the links. This implementation only answers whether a cycle exists. Identifying its entry requires a second phase using the meeting point and list head.

## A worked pointer trace

Reverse 1→2→3. Initially prev=None, cur=1. Save nxt=2 and set 1.next=None; prev=1, cur=2. Save nxt=3 and set 2.next=1; prev=2, cur=3. Save nxt=None and set 3.next=2; prev=3, cur=None. The final list is 3→2→1. If we omitted saving nxt before changing cur.next, the remaining suffix could become unreachable.

For Floyd, consider 4→5→6→5. From 4, slow moves to 5 while fast moves to 6; then slow moves to 6 and fast moves around to 6 after two steps. Their identities match, proving a cycle. If values were repeated in an acyclic list, equality of values alone would give a false positive.

## Cost comparison and common traps

| Operation | Singly linked list | Dynamic array |
| --- | --- | --- |
| Access index i | O(i+1) | O(1) |
| Prepend | O(1) | O(n) shifting |
| Append | O(1) with maintained tail | O(1) amortized |
| Delete after known predecessor | O(1) | O(n) shifts worst case |
| Traverse every item | O(n) | O(n), often better locality |
| Extra per-item representation | Pointer field and allocation | References in compact buffer |

Linked lists are not automatically faster because their pointer changes are cheap. Node allocation, cache misses and inability to address by index can dominate. In array-based languages, pointer misuse raises ownership and lifetime questions. For many workloads a contiguous sequence beats a linked list despite asymptotic insert advantages.

## Cases where the technique is wrong

Never call reverse_list on a cyclic list without first handling cycles; it may loop indefinitely or corrupt the structure. A dummy/sentinel head can simplify edge cases but should not be mistaken for user data. Two logical lists sharing node objects can interfere: reversing one list changes links observed by the other. Concurrent mutation during traversal needs synchronization or a safe snapshot. A doubly linked list's prev pointer must be repaired on every insertion and deletion, including at head and tail.

## Exercises and verification

1. Draw three nodes before and after reversing, annotating prev, cur and saved next on every iteration.
2. Explain why removal at a known node is easy in a doubly linked list but may require a predecessor in a singly linked one.
3. Prove the two-speed pointers meet in a cycle by reasoning about their relative position modulo the cycle length.
4. Given two nodes with equal value 7 but different identity, explain why Floyd must compare `is`, not `==`.
5. Implement insertion after a known node, and test empty list, singleton and tail cases without losing reachability.

**Related reading:** [Arrays and strings](/en/topics/arrays-and-strings/) explains contiguous representation; [stacks and queues](/en/topics/stacks-queues/) shows linked and array implementations of abstract interfaces.
