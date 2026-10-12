---
id: program-memory-references-lifetimes
title: "Programming memory: references, aliasing and object lifetimes"
description: "Understand name bindings, identity, mutable aliases, call frames and immutable snapshots through a reproducible memory model."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-semantics-contracts, data-types-bytes-and-representation]
sources:
  - {title: "Python language reference — Data model", url: "https://docs.python.org/3/reference/datamodel.html", kind: "official language reference"}
  - {title: "Python language reference — Execution model", url: "https://docs.python.org/3/reference/executionmodel.html", kind: "official language reference"}
  - {title: "Python standard library — Copy", url: "https://docs.python.org/3/library/copy.html", kind: "official library documentation"}
  - {title: "Python standard library — Garbage collector", url: "https://docs.python.org/3/library/gc.html", kind: "official library documentation"}
---
A variable name, an object and the memory holding it are related but **different concepts**. If a programmer assumes that assigning a list to another name creates a separate list, unexpected mutations follow. Before studying allocators, virtual memory or garbage collectors, the essential foundation is to understand which names and containers reference which objects [1][2].

## Names, identity and equality

In Python, assignment binds a name to an object. Giving the same object a second name does not duplicate it. The identity operator tests whether two expressions refer to the same object; equality asks whether their contents are equivalent according to the type. Two distinct lists can be equal, while two names for the same mutable list are identical. Mutating one alias affects every observer of that object [1].

A function parameter is a local name bound to its argument object. When a function appends to a list argument, the caller sees the mutation. When it assigns a new list to its local parameter name, the caller's own variable is not rebound. The popular descriptions “Python always copies an argument” and “Python passes a variable itself by reference” both obscure the actual binding semantics.

## Mutability, references and ownership

Integers and strings are immutable objects, whereas lists and dictionaries permit updates. A tuple cannot have its slots reassigned, but it may contain a mutable list. That contained list can still change. Consequently, placing an arbitrary object in a tuple is not a deep immutability guarantee. The property depends on **all reachable objects**, not only the outer container.

Ownership is a design contract: which component may mutate an object, and when? Python itself does not enforce exclusive ownership of an ordinary list. APIs can instead promise never to modify input, create copies on entry, or provide documented mutable views. Each option has a different memory and time cost. Unclear ownership is particularly dangerous when multiple functions share nested collections.

## Stack frames and object lifetimes

A call frame represents an active function invocation, including its local bindings and control state. Recursive calls produce multiple logical frames. Returning from a function makes its call frame inactive; it does not necessarily destroy objects that were created during the call. An object returned to another function can remain accessible long after its creator returns [2].

The terms stack and heap describe common implementation strategies. A stack supports nested activation records; heap allocation can support objects whose lifetime outlasts the creating call. However, the Python language does not require every local binding to correspond to a specific physical machine-stack slot. Different Python implementations and languages use different allocation and optimization strategies. A diagram of frames and references is a conceptual model, **not** a portable address map.

## Shallow copying and shared nested objects

A shallow copy creates a new outer container but retains references to elements. Copying a list of lists using list(original) makes a new outer list, while the inner row lists remain shared. A mutation to an inner list is therefore visible from both outer lists. Deep copying attempts to recursively duplicate components according to their copy policies, with different behavior for special and user-defined objects [3].

Neither deep copying nor shallow copying is always preferable. Deep copying an enormous immutable structure can waste work; shallow copying a mutable nested record can violate the expectation of independence. The correct choice follows a clear contract about which nested values can change and which changes must become visible elsewhere.

## Worked example: an immutable integer grid

A grid is represented as a sequence of rows. The input contract accepts an empty outer sequence or a nonempty rectangular grid of exact integers. It rejects rows with inconsistent widths, noninteger cells and nonempty grids with zero columns. The freeze operation creates tuples of row tuples. Because all values are immutable integers, this particular representation provides recursively immutable snapshots.

A cell replacement produces a new outer tuple and a new tuple for the modified row, leaving every other row shared. This is elementary **copy-on-write**. A caller may continue changing the source list without altering the snapshot, because none of its nested mutable lists were retained. The code explicitly demonstrates where a shallow copy would be insufficient.

~~~python
def freeze_grid(rows):
    if not isinstance(rows, (list, tuple)):
        raise TypeError("sequence required")
    if not rows:
        return ()
    if any(not isinstance(row, (list, tuple)) for row in rows):
        raise ValueError("invalid row")
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        raise ValueError("nonrectangular grid")
    if any(type(cell) is not int for row in rows for cell in row):
        raise ValueError("integer cells required")
    return tuple(tuple(row) for row in rows)

def replace_cell(grid, row, col, value):
    if type(row) is not int or type(col) is not int:
        raise IndexError("invalid indices")
    if type(value) is not int:
        raise ValueError("invalid value")
    if row < 0 or row >= len(grid) or col < 0 or col >= len(grid[0]):
        raise IndexError("outside grid")
    return tuple(
        old[:col] + (value,) + old[col+1:] if index == row else old
        for index, old in enumerate(grid)
    )

source = [[1, 2], [3, 4]]
alias = source
shallow = list(source)
snapshot = freeze_grid(source)
assert alias is source and shallow is not source
assert shallow[0] is source[0]
source[0][0] = 99
assert shallow[0][0] == 99 and snapshot[0][0] == 1
new = replace_cell(snapshot, 0, 1, 7)
assert new == ((1, 7), (3, 4))
assert snapshot == ((1, 2), (3, 4))
assert new[1] is snapshot[1]
~~~

## Correctness and complexity

For R rows and C columns, freezing visits RC cells to validate the representation and constructs RC cell references in immutable tuples. Under constant-cost reference operations, time and additional storage are O(RC). Replacing one cell copies C references in its row and R references in the outer tuple, requiring O(R+C) time and auxiliary references. The remaining row tuples are shared safely because their contents are immutable.

The key invariant is that each row has the same width and every stored cell is an immutable integer. Freezing preserves input values in row-major order; a replacement changes exactly one position without modifying the earlier snapshot. If cells contained mutable lists, this argument would fail. The replacement also rejects negative indices by explicit API design, even though ordinary Python indexing accepts them.

## Garbage collection, finalization and counterexamples

An object remains reachable while a live path of references leads to it. Removing one name does not imply that the object is unreachable; another list or closure may retain it. Reference cycles complicate reclamation, and the exact timing of garbage collection is not a portable contract for closing files and sockets [4]. Resource lifetime should therefore be managed explicitly, for example with context managers.

Neither immutable snapshots nor Python reference semantics establish thread safety when two workers race to assign a shared variable. That is a separate synchronization problem. Similarly, this example does not demonstrate the operating-system memory layout or how a particular CPU implements a load instruction. Those are later abstractions, not prerequisites for understanding aliasing.

## Exercises and verification

1. Draw a reference diagram after assigning two names to one nested list. Distinguish mutation from rebinding.
2. Construct two different lists that compare equal but are not identical.
3. Build a tuple containing a mutable list and explain why nested mutation remains possible.
4. Compare the grid replacement against a full-copy reference for every cell in a 2-by-3 grid.
5. Derive the O(RC) cost of freezing and O(R+C) cost of a single-cell update.
6. Explain why returned objects can survive their creator's call and why garbage-collection timing cannot guarantee file closure [4].

Related foundations: [programming semantics](/en/topics/programming-semantics-contracts/), [recursion](/en/topics/recursion-call-stack/) and [virtual memory](/en/topics/processes-virtual-memory/).