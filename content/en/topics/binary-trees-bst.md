---
id: binary-trees-bst
title: "Binary Trees and BSTs: Traversals, Ordering and Height"
description: "Explain binary-tree structure, DFS/BFS traversals, BST ordering and height-dependent complexity with an iterative tested implementation."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [arrays-and-strings, stacks-queues, complexity-analysis]
sources:
  - {title: "Princeton Algorithms — Binary Search Trees", url: "https://algs4.cs.princeton.edu/32bst/", kind: "university textbook"}
  - {title: "Princeton Algorithms — Balanced Search Trees", url: "https://algs4.cs.princeton.edu/33balanced/", kind: "university textbook"}
---
A **tree** is a graph without cycles when viewed as an undirected connected structure. A **rooted tree** adds a chosen root and parent-child orientation. A **binary tree** restricts each node to at most two children, named left and right; it does not imply sorted values. A **binary search tree (BST)** adds an ordering invariant: each node's left subtree contains smaller keys, and its right subtree larger keys, under a defined comparison policy [1].

## Shape, depth and height

A leaf has no children. The depth of a node is its edge distance from the root; the root has depth zero. The height of a nonempty tree is the maximum root-to-leaf edge count. Some texts define height of empty tree as −1, others zero; state the convention when using height recurrences. A perfectly balanced binary tree with n nodes has height Θ(log n). A chain of n nodes satisfies the binary-tree definition but has height n−1. **Binary** does not imply **balanced**.

The number of possible nodes on level d is at most 2^d. Summing levels 0 through h yields at most 2^(h+1)−1 nodes. Therefore a tree with n nodes has height at least logarithmic in n when all levels are filled near capacity, but this bound does not prevent much larger height in an unbalanced BST.

## DFS traversals and invariants

Tree traversals must define **visit order**. Preorder visits node, then left subtree, then right. Inorder visits left, node, right. Postorder visits left, right, node. In a valid BST with distinct keys, inorder yields strictly increasing order. Breadth-first traversal visits levels in FIFO order. These traversals are O(n) because every node is visited once, with memory O(h) for DFS stack and O(w) for BFS queue where h is height and w maximum level width.

![A binary search tree and its inorder ascending traversal.](/diagrams/bst-inorder.svg)

For example, a root 8 with left child 3 and right child 10 has inorder sequence 3,8,10; preorder 8,3,10; postorder 3,10,8. An inorder traversal being sorted is a consequence of the BST invariant, not proof that **every** binary tree has a sorted traversal.

## Iterative BST insert and inorder traversal

The example rejects duplicate keys and assumes keys are mutually comparable under < and >. It is a **plain unbalanced BST**, not AVL or red-black. An iterative traversal avoids Python recursion limits on a degenerate chain.

~~~python
class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None

def insert(root, key):
    if root is None:
        return Node(key)
    current = root
    while True:
        if key == current.key:
            return root
        if key < current.key:
            if current.left is None:
                current.left = Node(key)
                return root
            current = current.left
        else:
            if current.right is None:
                current.right = Node(key)
                return root
            current = current.right

def inorder(root):
    result, stack = [], []
    current = root
    while current is not None or stack:
        while current is not None:
            stack.append(current)
            current = current.left
        current = stack.pop()
        result.append(current.key)
        current = current.right
    return result

root = None
for key in [8,3,10,1,6,14,4,7,13]:
    root = insert(root,key)
assert inorder(root) == [1,3,4,6,7,8,10,13,14]
assert inorder(insert(root,6)) == [1,3,4,6,7,8,10,13,14]
assert inorder(None) == []
~~~

After each insert, every key in each left subtree remains less than its ancestor key and every key in a right subtree remains greater. The loop follows exactly one search path until finding a missing child; attaching the new node there preserves the invariant. Inorder correctness follows inductively: sorted(left), root key, sorted(right) is sorted under that invariant.

## Search depends on height, not merely node count

BST lookup compares the desired key with the current key and follows left if smaller, right if larger. Each step descends one level, so the number of comparisons is O(h+1), where h is tree height. Balanced search trees keep h=O(log n), while a plain BST built by inserting sorted keys may become a chain and take Θ(n) per lookup [1][2].

For n=7 inserted in ascending order, the root has a right-only chain of seven nodes. The worst search takes seven comparisons. In contrast, constructing a balanced tree of seven distinct sorted keys with median as root gives height two (at most three node comparisons). The keys are identical; **insertion order and balancing policy** explain the difference.

## A completeness and correctness argument

Proof of insert preservation uses cases. When key equals a stored key, the tree is unchanged. When key is smaller than current, any valid insertion position must lie in the left subtree; otherwise inserting it to the right would violate the current node's ordering. The same reasoning applies symmetrically for larger keys. At the first missing pointer, attach the key. All ancestors on the path already constrained the valid interval, so the new key satisfies each constraint. By induction the whole tree remains a BST.

A tree validator must check **ranges inherited from all ancestors**, not merely each node against its immediate children. A root 10 with right child 15 whose left child is 8 violates BST even though 8<15 locally: node 8 is in root 10's right subtree and must be greater than 10.

## Binary trees versus heaps and tries

A binary **heap** maintains parent-child priority order plus a shape invariant (complete tree) and is often stored in an array. It does not support sorted inorder traversal or efficient arbitrary-key search. A **trie** branches on symbols in a key prefix and is not necessarily binary. A BST branches using whole-key comparisons. Balanced BSTs support ordered iteration and predecessor/successor queries; hash tables generally provide expected efficient exact-key lookup but no inherent ordering.

| Operation | Plain BST | Balanced BST |
| --- | --- | --- |
| Search | O(h), worst Θ(n) | O(log n) |
| Insert | O(h), worst Θ(n) | O(log n) |
| Sorted traversal | O(n) | O(n) |
| Extra links | 2 child references per node | Additional balance metadata often required |

## Limitations and counterexamples

Without balancing, worst-case linear lookup remains possible even when inputs fit in memory. The exercises below verify the core invariant and failure cases.

## Exercises and verification

Do not use a plain BST expecting worst-case O(log n) without balancing. Recursive traversal on an extremely deep chain may overflow the language call stack; the iterative implementation avoids this. Deletion is subtler than insertion: a node with two children is usually replaced by a predecessor or successor while maintaining ordering and preserving all descendants. Concurrent updates need synchronization; an ordinary Node class is not a concurrent index.

1. Insert [5,2,8,1,3] into an empty BST and write its inorder, preorder and postorder traversals.
2. Construct a counterexample where every node is larger than its immediate left child but an ancestor range rule is violated.
3. Compare search comparisons for sorted insertion versus median-first insertion of seven keys.
4. Demonstrate by induction that inorder of a valid BST with distinct keys is strictly increasing.
5. Explain why a binary heap's root is its minimum (for min-heap), but its left subtree need not contain all keys smaller than its right subtree.

**Related reading:** [Stacks and queues](/en/topics/stacks-queues/) implement traversal frontiers; [heaps](/en/topics/heaps-priority-queues/) use different invariants; [graph traversal](/en/topics/graph-traversal/) extends tree search to graphs with cycles.
