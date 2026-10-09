---
id: backtracking-search
title: "Backtracking: State Spaces, Pruning and Correctness"
description: "Derive backtracking search trees, pruning safety, N-Queens constraints, complexity bounds and verifiable recursive implementations."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis, graph-traversal]
sources:
  - {title: "MIT 6.006 — Introduction to Algorithms", url: "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/", kind: "university course"}
  - {title: "Python Standard Library — itertools combinatoric iterators", url: "https://docs.python.org/3/library/itertools.html", kind: "official documentation"}
---
**Backtracking** explores a space of partial decisions and reverses a decision when its extension cannot lead to an admissible solution. It is a **search strategy**, not a particular data structure or a promise of polynomial runtime. A good solution states the set of possible states, the order of decisions, the constraints that must remain true and a pruning rule proven not to discard any valid completion [1].

## Model the state-space tree

Consider building a sequence of n symbols, one choice per depth. The root is the empty sequence; an edge adds a choice, and a leaf represents a complete candidate. If each decision has b options, an unpruned tree may have 1+b+...+b^n nodes, which is O(b^n) for b>1. This is a *bound on generated states*, not a bound on the cost of evaluating an individual state. A procedure that copies an O(n)-length partial solution at every node may add another factor n.

The distinction between **permutations**, **combinations** and **subsets** changes the search space. There are n! full permutations of n distinct items, C(n,k) k-element subsets and 2^n total subsets. Python's itertools provides independent enumeration utilities useful for testing small cases [2].

## Invariants and valid pruning

A recursive procedure search(state) should maintain that state satisfies every constraint already decidable from the partial choices. A pruning predicate is **sound** only when failure implies no completion can satisfy the full problem. In N-Queens, if two already placed queens attack each other, adding future queens will never remove that attack. Therefore prune that branch immediately. But pruning whenever two choices temporarily produce a score below a target can be wrong if future choices may increase the score.

State restoration is equally important. When a mutable set or list is extended before recursion, it must be restored afterward even when deeper search returns early or raises an error. An alternative uses immutable copied states at the cost of more allocation.

## Worked N-Queens representation

Place one queen per row on an n×n board. Represent an assignment as the column chosen for each row. Any two queens conflict if they share a column or diagonal; diagonal identities are row-col and row+col. Because we place exactly one queen per row, a row conflict is impossible by construction.

![N-Queens backtracking: a decision tree with a rejected conflicting branch.](/diagrams/backtracking-tree.svg)

~~~python
def queens(n):
    if n < 0: raise ValueError("n must be nonnegative")
    solutions = []
    cols, diag_down, diag_up = set(), set(), set()
    chosen = []

    def search(row):
        if row == n:
            solutions.append(tuple(chosen))
            return
        for col in range(n):
            d1, d2 = row-col, row+col
            if col in cols or d1 in diag_down or d2 in diag_up:
                continue
            cols.add(col); diag_down.add(d1); diag_up.add(d2)
            chosen.append(col)
            search(row+1)
            chosen.pop()
            cols.remove(col); diag_down.remove(d1); diag_up.remove(d2)

    search(0)
    return solutions

assert queens(0) == [()]
assert len(queens(1)) == 1
assert queens(2) == [] and queens(3) == []
assert len(queens(4)) == 2
~~~

The count for n=0 deliberately follows the mathematical convention that there is one empty assignment. A product contract could reject n=0 instead; this choice must be documented. For large n, storing every solution can exhaust memory, even if searching for only the **number** of solutions could be streamed.

## Proof of completeness and nonduplication

Prove by induction on row. At the root, the empty assignment is valid. Assume every valid arrangement of the first r rows is representable by one recursive path. For a complete valid board, the queen in row r occupies one column c; because the complete board is valid, c conflicts with none of the previously placed queens, so search does not prune that child. By induction, every complete solution is reached. Each row tries each column once, so a complete column sequence is generated at most once. Therefore the algorithm is **complete and duplicate-free** under this state representation.

## Time, space and practical branching

At depth r at most n-r columns remain unused, even without diagonal pruning. Hence the number of complete candidates is at most n!, and a loose search-time bound with O(1) set membership per attempted column and up to n trials per visited node is O(n·n!), rather than automatically O(n!) for this exact implementation. The actual number of explored nodes is typically much lower because diagonal conflicts prune early, but no polynomial guarantee follows. The recursion and three constraint sets use O(n) auxiliary space excluding stored output; storing S solutions of length n uses Θ(Sn).

In other problems, **constraint propagation** can reduce branching before recursion, while **branch and bound** prunes states whose best possible objective value cannot improve an incumbent solution. Both require valid bounds: a heuristic estimate alone is not necessarily an admissible pruning certificate. Memoization helps only when different paths reach genuinely identical future subproblems; otherwise it may waste memory.

## Counterexamples and alternatives

A greedy algorithm commits to one locally attractive choice and never revisits it; backtracking can revise choices but may explore exponentially many. Dynamic programming compresses repeated subproblems when a sufficient state is available. Backtracking is more natural for feasibility with combinatorial constraints and modest search spaces; a SAT/constraint solver can be preferable for large structured instances. Do not call a global cache over only 'depth' a valid memoization for N-Queens: occupied columns and diagonals change the future.

## Exercises and verification

1. For n=4, verify the two solutions (1,3,0,2) and (2,0,3,1), and explain why (0,1,2,3) is rejected.
2. Count all full permutations of four distinct items: 4!=24. Compare a simple permutation generator to itertools.permutations as an oracle [2].
3. Write a pruning rule for finding subsets with sum exactly T **when all remaining numbers are nonnegative**, then show why negative numbers invalidate pruning on current_sum>T.
4. Modify queens to yield solutions instead of storing them and state how space and API behavior change.
5. Deliberately omit chosen.pop() and explain which invariant fails on the next sibling branch.
