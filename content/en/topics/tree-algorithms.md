---
id: tree-algorithms
title: "Tree Algorithms: Level Order, LCA, Diameter and BST Validation"
description: "Derive breadth-first levels, lowest common ancestor, tree diameter and inherited BST ordering with iterative implementations."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [binary-trees-bst, stacks-queues, recursion-call-stack]
sources:
  - {title: "Princeton Algorithms — Binary Search Trees", url: "https://algs4.cs.princeton.edu/32bst/", kind: "university textbook"}
---
Binary trees are a recurring setting for algorithmic reasoning because the same collection of nodes admits several questions: visit by level, compare whole subtrees, find the lowest common ancestor, calculate the longest path, or verify ordering constraints. Different tasks require different **invariants**. A binary tree is not automatically a binary search tree, and a search tree is not automatically balanced [1].

## A precise node and input model

Assume a rooted binary tree with n distinct **node objects**, each containing a value and at most two child references. The structure has no cycles, and no child is reachable by two different parent paths. The empty tree has zero nodes. Node identity is separate from node value: two different nodes may both store 7, but they are not the same vertex.

The number of edges on the longest downward root-to-leaf path is the tree height. A balanced binary tree has height O(log n), whereas a chain of n nodes has height n−1. These properties matter for recursive stack depth, but a full traversal visits every node regardless of balance and therefore takes Θ(n) time under constant-time node processing.

## Level-order traversal using FIFO

Breadth-first traversal keeps a queue of nodes whose parents have already been processed. At each iteration, record the queue's current length; these entries form exactly one depth level. Remove those nodes and append their children to the end, ensuring that a complete next level appears only after the current one.

![Breadth-first levels, ancestor relationships and a longest path in a sample tree.](/diagrams/tree-levels-lca.svg)

~~~python
from collections import deque

class Node:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right

def levels(root):
    if root is None:
        return []
    q = deque([root])
    answer = []
    while q:
        level = []
        for _ in range(len(q)):
            node = q.popleft()
            level.append(node.value)
            if node.left is not None:
                q.append(node.left)
            if node.right is not None:
                q.append(node.right)
        answer.append(level)
    return answer

n4, n5, n3 = Node(4), Node(5), Node(3)
n2 = Node(2, n4, n5)
root = Node(1, n2, n3)
assert levels(root) == [[1], [2, 3], [4, 5]]
assert levels(None) == []
~~~

Every node enters and leaves the deque once: Θ(n) time. The queue holds at most O(w) nodes at a time, where w is the maximum breadth of a level plus the next level being constructed; formally its upper bound is O(n). The nested output itself stores all n values. Unlike DFS, BFS's memory depends on width rather than height.

## Lowest common ancestor: identity matters

The **lowest common ancestor (LCA)** of nodes a and b is their deepest shared ancestor, allowing a node to be its own ancestor. For nodes 4 and 5 in the sample, the answer is node 2. For 4 and 3, the answer is the root 1. A routine that compares only values breaks when values repeat; an LCA query is about node identity unless the API specifically imposes unique keys.

For a general binary tree without parent pointers, build a parent map by traversal until both targets are discovered. Then place all ancestors of a into a set and walk upward from b until the first common ancestor is found. This is O(n) time and O(n) memory in the worst case. In a BST with both values known present, ordering can offer a faster O(h) descent, but that shortcut is invalid for ordinary binary trees.

~~~python
def lowest_common_ancestor(root, a, b):
    if root is None or a is None or b is None:
        return None
    parents = {root: None}
    stack = [root]
    while stack and (a not in parents or b not in parents):
        node = stack.pop()
        for child in (node.left, node.right):
            if child is not None and child not in parents:
                parents[child] = node
                stack.append(child)
    if a not in parents or b not in parents:
        return None
    ancestors = set()
    while a is not None:
        ancestors.add(a)
        a = parents[a]
    while b not in ancestors:
        b = parents[b]
    return b

assert lowest_common_ancestor(root, n4, n5) is n2
assert lowest_common_ancestor(root, n4, n3) is root
assert lowest_common_ancestor(root, n2, n2) is n2
assert lowest_common_ancestor(root, n4, Node(4)) is None
~~~

The last assertion tests the absent-node case: another object storing 4 is **not** the queried node. This implementation assumes ordinary identity-hashable Python Node objects, no concurrent structural mutation during traversal, and no cycles. A version supporting arbitrary unhashable nodes should map by explicit stable identities.

## Tree diameter using postorder dynamic programming

The **diameter** of a tree is the maximum number of edges along a simple path between any two nodes; the path does **not** have to pass through the root. At each node, the longest path that passes through it combines the heights of its left and right subtrees. With the empty-child height convention −1, its length in edges is left_height + right_height + 2.

A postorder traversal computes child heights before their parent, storing one result per node. The global maximum of all candidate crossing paths is the diameter. This is dynamic programming on a tree: each subtree height is evaluated once and reused exactly where needed.

~~~python
def diameter_edges(root):
    if root is None:
        return 0
    stack = [(root, False)]
    heights = {}
    answer = 0
    while stack:
        node, visited = stack.pop()
        if not visited:
            stack.append((node, True))
            if node.right is not None:
                stack.append((node.right, False))
            if node.left is not None:
                stack.append((node.left, False))
        else:
            left = heights.get(node.left, -1)
            right = heights.get(node.right, -1)
            answer = max(answer, left + right + 2)
            heights[node] = max(left, right) + 1
    return answer

assert diameter_edges(root) == 3
assert diameter_edges(Node(9)) == 0
assert diameter_edges(None) == 0
~~~

The sample's longest path is 4→2→1→3, of length three edges. A tempting but incorrect approach is to compute only left_height(root)+right_height(root)+2: the longest path might lie entirely within one deeply branched subtree and never cross the root. Maximizing the crossing candidate at **every node** avoids this error.

The iterative implementation avoids Python recursion-depth limits. It takes Θ(n) time and O(n) extra memory for the height map and explicit stack. A recursive height function can achieve O(h) call-stack space when it returns local subtree heights and tracks a global diameter, but it risks stack overflow on a deep chain.

## Validate a BST with ancestor bounds

A **binary search tree** has the stronger invariant: all values in a node's left subtree are strictly smaller, and all in its right subtree strictly greater, assuming duplicates are forbidden. Checking each node against its immediate children is insufficient. Root 10, right child 15, and that child's left child 8 looks locally ordered under node 15, but 8 violates the root's inherited lower bound of 10.

Maintain an allowed open interval (low,high) for each node. As traversal enters a left subtree, high becomes the parent's value; on the right, low becomes the parent's value. If any value lies on or outside its inherited interval, reject. This tests all ancestor constraints in Θ(n) time and O(h) stack space for a well-behaved DFS, though an unbalanced tree makes h=Θ(n).

~~~python
def valid_bst(root):
    pending = [(root, None, None)]
    while pending:
        node, low, high = pending.pop()
        if node is None:
            continue
        if (low is not None and node.value <= low) or (
            high is not None and node.value >= high
        ):
            return False
        pending.append((node.left, low, node.value))
        pending.append((node.right, node.value, high))
    return True

assert valid_bst(Node(10, Node(5), Node(15, Node(12), Node(20))))
assert not valid_bst(Node(10, Node(5), Node(15, Node(8))))
assert not valid_bst(Node(2, Node(2), Node(3)))
assert valid_bst(None)
~~~

This code assumes comparable numeric values and uses None as an absent bound; adapt it if None is a legitimate key. For massive or persistent trees, structural sharing, external storage and concurrent mutation create additional correctness constraints outside the scope of these in-memory methods.

## Choose the right tree technique

| Task | Structural principle | Typical cost |
| --- | --- | --- |
| Traverse by depth | FIFO frontier | Θ(n) time, up to O(n) space |
| LCA in ordinary tree | Parent map or recursion | O(n) time |
| Diameter | Child heights and postorder | Θ(n) time |
| Validate BST | Inherited lower/upper bounds | Θ(n) time |
| Search balanced BST | Ordered descent | O(log n) time |
| Search unbalanced BST | Ordered descent | O(h), worst Θ(n) |

Do not apply BST ordering to arbitrary binary trees. Do not use node values as identities without a uniqueness contract. Do not confuse *height* (root-to-leaf) with *diameter* (any two vertices). These are common sources of seemingly reasonable but incorrect interview solutions.

## Exercises and verification

1. Trace the FIFO queue for each level in the provided five-node tree and show its grouped output.
2. Prove that the parent-map LCA routine returns the **lowest**, not merely any shared ancestor.
3. Derive the candidate diameter formula with empty-child height −1 and validate the three-edge sample.
4. Construct a tree whose diameter lies wholly inside its left subtree, not through the root.
5. Explain why immediate child comparisons miss the invalid value 8 under root 10, and trace its inherited bounds.

**Related chapters:** [Binary trees and BST](/en/topics/binary-trees-bst/) define shape and ordering; [queues](/en/topics/stacks-queues/) support BFS; [recursion](/en/topics/recursion-call-stack/) explains recursive subtree decomposition [1].
