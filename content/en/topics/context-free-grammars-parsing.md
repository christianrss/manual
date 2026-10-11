---
id: context-free-grammars-parsing
title: "Context-Free Grammars, Pushdown Automata and Syntax Analysis"
description: "Derive context-free recognition, implement a pushdown recognizer and syntax tree, and test an Earley-style chart parser with independent oracles."
category: foundations
difficulty: intermediate
updated: 2026-10-11
prerequisites: [formal-languages-finite-automata, recursion-call-stack]
sources:
  - {title: "MIT OpenCourseWare — Automata, Computability and Complexity: Lecture Notes", url: "https://ocw.mit.edu/courses/6-045j-automata-computability-and-complexity-spring-2011/pages/lecture-notes/", kind: "university lecture notes"}
  - {title: "Cornell CS 4120 — Recursive-Descent Parsing and Predictive Parsing", url: "https://www.cs.cornell.edu/courses/cs4120/2023sp/notes.html?id=topdown", kind: "university compiler notes"}
  - {title: "Cornell CS 4120 — Bottom-Up and Earley Parsing", url: "https://www.cs.cornell.edu/courses/cs4120/2023sp/notes.html?id=bottomup", kind: "university compiler notes"}
  - {title: "Jay Earley — An Efficient Context-Free Parsing Algorithm (1970)", url: "https://doi.org/10.1145/362007.362035", kind: "original peer-reviewed algorithm"}
---
The previous [finite automata chapter](/en/topics/formal-languages-finite-automata/) proved why finite-state recognition cannot handle arbitrary matching counts. The natural next model adds **recursive grammatical structure and unbounded stack memory**. This chapter separates three deliverables that are easily confused: membership in a context-free language, an explicit pushdown-machine implementation, and a **syntax tree** representing a recognized program fragment. A general chart recognizer is also implemented and independently tested; it is not presented as a production compiler front end [1][3].

## Define the grammar before writing parsing code

A **context-free grammar** is G = (V, Sigma, P, S): a finite set V of nonterminal symbols, a disjoint set Sigma of terminals, a finite set P of productions A -> alpha with A in V and alpha a finite string from (V union Sigma), and a start symbol S in V. A production may have an empty right-hand side, denoted epsilon. A **derivation** replaces one nonterminal occurrence with its production's right-hand side. A word belongs to L(G) if S can derive exactly that terminal word, without leftover nonterminals [1].

For balanced parentheses of one type, use **S -> '(' S ')' S | epsilon**. The first S describes what is inside the first pair; the final S describes the balanced suffix that follows it. For example, `(()())` derives an opening pair whose interior is `()()`, followed by an empty suffix. This grammar accepts epsilon, `()`, `(())`, and `()()`, but rejects `)(`, `(()`, and `())`. It is unambiguous: the closing parenthesis matching the first opening parenthesis fixes the decomposition into the inner segment and the remaining suffix.

A **parse tree** makes the production choices explicit. In contrast, a membership **recognizer** returns only true or false. A compiler eventually needs an AST carrying operators, literal values, source spans and semantic relationships. A parse tree may retain punctuation and grammar-specific nonterminals that an AST omits. Neither the grammar nor a successful boolean recognition alone constructs semantic meaning [2].

## From finite automata to a pushdown automaton

A pushdown automaton (PDA) extends finite control with a **last-in, first-out stack**. A general PDA transition may inspect the current control state, input symbol (or epsilon) and stack top, then change state and push or pop stack symbols. Its formal description includes finite control states, an input alphabet, a stack alphabet, a transition relation, an initial state/stack marker and an acceptance convention. Nondeterministic PDAs characterize the context-free languages; deterministic PDAs recognize a proper subclass [1].

For one kind of parenthesis, use a deterministic procedure: push an opening marker on `(`, pop it on `)`, reject a closing symbol if the stack is empty, and accept at end of input only when the stack is empty. An integer **depth** is equivalent to the stack height for this one-symbol stack alphabet, but it does not generally replace a real stack. If there are two types of brackets, the sequence `([)]` has equal opening and closing counts yet is invalid: the closing parenthesis attempts to remove an opening square bracket.

Our executable `pushdown_accepts` therefore stores the actual opening symbols for `()[]`. A valid mixed example is `([][()])`. With n input symbols, each is pushed or popped at most once; this recognizer uses O(n) worst-case time and O(n) worst-case stack memory under constant-cost single-character operations. It does **not** recognize arbitrary CFGs: this is the explicit deterministic machine for the chosen bracket language, not a replacement for the general recognizer.

## From grammar to recursive-descent syntax tree

The same grammar `S -> '(' S ')' S | epsilon` permits a recursive-descent parser because an opening parenthesis uniquely selects the first production; a closing parenthesis or end-of-input selects epsilon. Define `parse_sequence(position)`: if the next symbol is `)` or the word ends, return an empty tree and the unchanged position. Otherwise require `(`, recursively parse its inside sequence, require its matching `)`, and recursively parse the trailing sequence. A top-level call must consume **all** input, otherwise an unmatched `)` could be silently ignored.

The published `parse_balanced(word)` returns `None` for epsilon and a pair `(inner, tail)` for one parenthesized group plus its remaining sequence. This is an actual **structural parse tree**, not a verdict. For `()()`, the tree consists of one empty inner group with a tail containing one more empty inner group. Rendering that recursive structure by inserting `(`, `)` and the tail reconstructs exactly the original source. It demonstrates a precise round-trip property without claiming that semantic ASTs necessarily preserve every source character.

For length n, each successful input character participates in a constant amount of parser work, giving O(n) time and O(n) tree nodes for this grammar. The recursive implementation uses O(n) call-stack depth in the worst case, so Python can raise `RecursionError` on deeply nested or long sequential inputs before any mathematical language limit is reached. Production compilers may use table-driven stacks or bounded nesting rather than relying on unrestricted recursion [2].

## Why left recursion defeats naive descent but not chart recognition

Consider the grammar **S -> S a | epsilon**, which generates zero or more `a` characters. A naive top-down function that immediately implements the first production calls itself again **without consuming input**, potentially recursing forever. Even ambiguity without left recursion complicates choosing one branch. Rewriting a left-recursive grammar may make it suitable for a predictive LL parser, but any changes to associativity or parse-tree shape must be reviewed. An arbitrary CFG cannot be assumed LL(1) merely because it has valid productions [2][3].

The chart-based recognizer in the codebase uses **dotted items**. An item `[A -> alpha • beta, j]` stored at input position i records progress through a production, with origin j indicating where recognition of that A began. Three operations are required: **predict** each production when the next symbol after the dot is a nonterminal; **scan** one matching terminal to the next chart column; **complete** a finished item by advancing origin items that were waiting for its left-hand nonterminal [3][4].

For example, at the beginning of `()` under the balanced grammar, the chart predicts the `S` productions. Scanning `(` enters the next column with the item expecting the inner `S`. The epsilon rule can complete an empty inner S **at the same input position**. That completion advances the item so `)` can be scanned; a final epsilon S completes the trailing suffix. Without closure to a fixed point, a nullable production can be added **after** an item was already visited, causing an incorrect rejection.

## A finite chart recognizer with explicit limitations

The function `earley_accepts(grammar, start, word)` stores one set of dotted items for each input boundary. It accepts finite grammars supplied as a mapping from nonterminal names to lists or tuples of right-hand-side symbol sequences. An empty sequence means epsilon. Symbols that are dictionary keys are nonterminals; other symbols must be single-character terminals. For simplicity the model is character-based, not token-based, and unknown one-character names are interpreted as terminals. This is a deliberate input convention, not a robust general grammar-file parser.

At each position the implementation repeats predictions and completions **until the chart stops changing**, then scans matching characters into the next column. Set deduplication makes this terminate even with nullable cycles such as `S -> S | epsilon`. The accept condition is the completed, synthetic start production at the final input boundary, whose origin is zero. It rejects malformed grammar structures with `ValueError`; unlike `parse_balanced`, a syntactically invalid but correctly formed input string simply yields `False`.

The construction's **soundness** follows because each predicted item belongs to a real production, each scan consumes a matching terminal, and completion connects a completed nonterminal to a waiting constituent from the correct origin. For **completeness**, follow a finite derivation tree: its child constituents are predicted, scanned or completed recursively; fixed-point closure ensures nullable children are also completed, even when no input advances. By structural induction, an accepting derivation eventually yields a completed synthetic start item. This reasoning applies to recognition, not to an absent parse-forest implementation [3][4].

## Execute the two parsing models

The committed [Python module](https://github.com/christianrss/manual/blob/main/examples/python/context_free_parser.py) contains all three public functions and two grammars. The following assertions execute in both language builds:

~~~python
from examples.python.context_free_parser import (
    earley_accepts, parse_balanced, pushdown_accepts,
    BALANCED_GRAMMAR, ANBN_GRAMMAR,
)

assert earley_accepts(BALANCED_GRAMMAR, "S", "(()())")
assert not earley_accepts(BALANCED_GRAMMAR, "S", "([)]")
assert earley_accepts(ANBN_GRAMMAR, "S", "aaabbb")
assert not earley_accepts(ANBN_GRAMMAR, "S", "aabbb")
assert earley_accepts({"S": (("S", "a"), ())}, "S", "aaaa")
assert parse_balanced("()") == (None, None)
assert pushdown_accepts("([][()])")
assert not pushdown_accepts("([)]")
~~~

The grammar for `a^n b^n`, with n at least zero, is `S -> a S b | epsilon`: each recursive step introduces exactly one `a` before and one `b` after the inside derivation. No finite-state recognizer can store the unbounded matching count; the recursion or PDA stack provides the additional memory. Note that `aabbb` violates equal counts, even though the symbols occur in the expected order.

## Complexity, ambiguity and what the implementation does not claim

Let n be the word length and d the number of **dotted production positions** across the grammar, including an augmented start production. Each chart column may contain O((n+1)d) items indexed by their origin, so across n+1 columns there are O((n+1)^2 d) distinct chart items. This is an **entry-count bound**, excluding Python object overhead, hashing of production tuples and grammar input storage. Because the educational code rescans every column to saturation instead of maintaining optimized work queues and completion indexes, it is **not** an implementation for which we claim the classical O(n³) Earley bound.

Earley's original algorithm has an O(n³) worst-case bound under its algorithmic assumptions, improving on certain grammar classes [4]. That result must not be silently transferred to this simpler repeated-sweep implementation. For practical parsing, indexing completed items, handling nullable symbols carefully, detecting ambiguity, collecting a packed parse forest, and defining resource budgets matter. A recognizer reporting `True` does **not** count parse trees or select which AST a compiler should use.

For example, `S -> S S | a | epsilon` is ambiguous: several derivations can generate the same sequence of `a` symbols. Set-based membership checks only whether at least one derivation exists. An expression grammar without operator precedence may similarly accept `a+a*a` while leaving interpretation unresolved. An AST-producing compiler must separately specify precedence, associativity, disambiguation and error handling. This chapter proves no general solution to semantic analysis or type checking [2][3].

## Exercises and verification

1. Trace `()()` using `S -> (S)S | epsilon`. Identify which nonterminal corresponds to the first interior and which to the remaining suffix. **Check:** the first interior is empty; the suffix derives the second `()`.
2. Give a PDA trace for `([)]`. **Check:** the third symbol `)` tries to close `[` at the top of the stack; reject immediately, despite equal total opening/closing counts.
3. Explain why a completed epsilon production can advance another chart item without scanning input. **Check:** a nullable constituent spans zero characters and has identical start/end offsets.
4. Compare `S -> S a | epsilon` with `S -> a S | epsilon`. Do they recognize the same words? **Yes,** both recognize `a*`; naive recursive-descent control flow differs.
5. Construct a rejection example for `S -> a S b | epsilon` and verify both terminal order and count. **Check:** `aabb` accepts, `abab` and `aab` reject.
6. Separate three contracts: membership, syntax-tree construction and semantic/type checking. Why can a syntactically valid expression still be ill-typed?

The independent tests use a separate explicit-stack oracle, deletion of adjacent matched pairs for mixed brackets, and exhaustive comparisons for `a^n b^n` and generated left-recursive/ambiguous grammars. They establish **bounded agreement**, not a universal proof or industrial compiler performance. Next steps in the curriculum are syntax-directed evaluation, tokenization and a small compiler/type-checker; Turing computability and complexity classes remain separate foundations.
