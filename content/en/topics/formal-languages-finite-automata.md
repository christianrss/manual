---
id: formal-languages-finite-automata
title: "Formal Languages and Finite Automata: DFA, NFA, Epsilon Closure and Determinization"
description: "Build the computational model behind lexical analysis: define languages, derive DFA/NFA equivalence, implement epsilon-closure determinization, and test it independently."
category: foundations
difficulty: intermediate
updated: 2026-10-11
prerequisites: [logic-proofs-invariants, discrete-relations-orders, graph-traversal]
sources:
  - {title: "MIT OpenCourseWare — 6.045J Automata, Computability, and Complexity, Lecture Notes", url: "https://ocw.mit.edu/courses/6-045j-automata-computability-and-complexity-spring-2011/pages/lecture-notes/", kind: "university lecture notes"}
  - {title: "Stanford CS103 — Guide to the Subset Construction", url: "https://web.stanford.edu/class/archive/cs/cs103/cs103.1244/guide_to_the_subset_construction", kind: "university teaching guide"}
  - {title: "MIT 6.045 (2019) — Finite Automata, Regular Expressions and Minimization", url: "https://people.csail.mit.edu/rrw/6.045-2019/", kind: "original university course outline"}
---
An algorithm can recognize a fixed input string, but a **language recognizer** decides whether *every possible finite string* belongs to a specified set. Finite automata make that distinction precise. They are the first model in the progression from regular languages to grammars, parsing, computability and complexity theory. They also provide the mathematical basis for many lexical recognizers. This chapter constructs an executable deterministic machine from a nondeterministic machine rather than treating a regular expression as unexplained syntax [1][3].

## Alphabet, words, languages and recognition

An **alphabet** Sigma is a finite set of symbols; this chapter fixes Sigma = {0,1}. A **word** is a finite sequence of symbols from Sigma. The empty word is epsilon and has length zero. Sigma-star denotes all finite words over Sigma, including epsilon. A **language** is any subset of Sigma-star. The language L of binary words ending with 01 includes 01, 001, 101 and 0101, but not the empty word, 0, 10 or 011. Recognition is a yes/no decision for *membership* of an entire input word; finding a substring inside longer text is a different contract.

A compiler's lexer usually classifies tokens within a longer input stream, so it requires boundary rules such as longest match, priority and handling invalid characters in addition to simple whole-word recognition. Keep those concerns separate: an automaton is a mathematical recognizer, not a complete lexer with diagnostics, Unicode policy, lookahead and source locations. Likewise, a programming-language regex engine offering backreferences can describe some nonregular patterns; such engines are not interchangeable with the formal regular-expression model [3].

## Deterministic automata and total transitions

A deterministic finite automaton (DFA) is a five-part model (Q, Sigma, delta, q0, F): a finite set of states Q, finite alphabet Sigma, **total** transition function delta: Q × Sigma -> Q, initial state q0 in Q, and accepting states F contained in Q. For a word a1...ak, start at q0 and repeatedly follow delta. Accept exactly when the final state belongs to F. Acceptance of the empty word depends only on whether q0 is in F.

For L = all strings ending in 01, choose states S (no relevant suffix), Z (last symbol is 0) and A (current suffix is 01). The transitions are S --0--> Z, S --1--> S; Z --0--> Z, Z --1--> A; A --0--> Z, A --1--> S. Only A accepts. A does **not** stop consuming after reaching an accepting state: reading another 1 from A returns to S, so 011 is rejected. This is a full-word recognizer; calling A a terminal accept node would be incorrect.

A partial transition table can be converted into a total DFA by adding a rejecting sink with self-loops. In the construction below, the **empty subset of NFA states** plays the same role automatically. Rejecting an unsupported input symbol is instead an input-contract error; it is not the same as a valid word that the language rejects.

## Nondeterminism, epsilon edges and path semantics

A nondeterministic finite automaton (NFA) allows a set of destinations for each state and symbol. It may also contain **epsilon transitions**, which consume no input. An NFA accepts a word when **at least one** path consumes the entire word and ends in an accepting state, possibly taking epsilon transitions before, between or after consumed symbols. Nondeterminism is an existential path condition; it is not a claim about randomness, parallel processors or guessing at runtime [1].

An **epsilon closure** E(S) is the set of all states reachable from any state in S through zero or more epsilon edges. It includes S itself and must terminate even with epsilon cycles. To advance a current state set S over symbol a, first collect all a-labeled outgoing destinations, then apply epsilon closure to that result. The NFA's effective state is therefore a **set of possible states**, not one arbitrarily chosen state.

For the worked example, states are 0, 1, 2 and 3. State 3 is initial and takes epsilon to 0. State 0 loops on both symbols and may additionally take 0 to state 1. State 1 consumes 1 to reach accepting state 2. A successful path guesses which zero begins the **final** 01. NFA state 2 has no outgoing edges, so accepting that path requires the input to end there.

## Subset construction: derive a DFA, do not guess states

The subset construction defines each DFA state as a subset of NFA states. Its start state is E({q0}). For a subset S and symbol a, the deterministic transition is E(union of all NFA destinations on a from members of S). A subset accepts if it intersects the NFA's accepting set. The reachable-subset construction starts at the initial subset and explores each discovered subset exactly once [2].

The example begins in {0,3}. Reading 0 gives {0,1}; reading 1 from {0,1} gives {0,2}, an accepting subset. Reading another 1 gives {0}, a rejecting subset. Only four distinct subsets are reachable in this example, although a four-state NFA has at most 2^4 = 16 potential subsets. The empty subset, when reachable, must transition back to itself on all alphabet symbols. The construction neither requires nor necessarily reaches all subsets.

**Correctness invariant:** after reading any prefix w, the DFA subset equals exactly the set of NFA states reachable from the NFA start after consuming w, including any permitted epsilon moves. The base case w=epsilon follows from the initial closure. If it holds for w, applying the move-and-closure rule proves it for wa. Consequently the DFA's intersection with accepting states is nonempty exactly when an accepting NFA path exists. This induction establishes language equivalence for **all finite words**, not just tested examples [1][2].

## Executable epsilon closure and determinization

The Python code below is deliberately self-contained, fixes a binary alphabet, validates graph endpoints and converts reachable subsets into integer DFA state IDs. The graph is an author-controlled exercise input; the implementation is not a hardened parser for arbitrary attacker-supplied Python objects. An absent NFA transition means no destination; a compiled DFA always has both binary transitions for every reachable state.

~~~python
from collections import deque

ALPHABET = ("0", "1")

def epsilon_closure(seed, edges):
    """States reachable with zero or more epsilon (None) transitions."""
    found = set(seed)
    stack = list(seed)
    while stack:
        state = stack.pop()
        for target in edges.get((state, None), ()):
            if target not in found:
                found.add(target)
                stack.append(target)
    return frozenset(found)

def determinize(states, start, accepting, edges):
    """Compile a binary epsilon-NFA into a total DFA with integer state IDs.

    edges maps (state, symbol) to sets of destinations; None is epsilon.
    Returns (start_id, final_ids, dfa_edges, id_to_subset).
    """
    states = frozenset(states)
    accepting = frozenset(accepting)
    if not states or start not in states or not accepting <= states:
        raise ValueError("invalid state set or start/final state")
    for (source, symbol), targets in edges.items():
        if (source not in states or symbol not in (None, *ALPHABET)
                or not set(targets) <= states):
            raise ValueError("invalid NFA transition")
    initial = epsilon_closure({start}, edges)
    names = {initial: 0}
    pending = deque([initial])
    finals = set()
    dfa_edges = {}
    while pending:
        subset = pending.popleft()
        source_id = names[subset]
        if subset & accepting:
            finals.add(source_id)
        for symbol in ALPHABET:
            moved = {target for source in subset
                     for target in edges.get((source, symbol), ())}
            destination = epsilon_closure(moved, edges)
            if destination not in names:
                names[destination] = len(names)
                pending.append(destination)
            dfa_edges[(source_id, symbol)] = names[destination]
    return 0, frozenset(finals), dfa_edges, tuple(names)

def accepts_dfa(word, dfa):
    if type(word) is not str or any(ch not in ALPHABET for ch in word):
        raise ValueError("word must use the binary alphabet")
    state, finals, transitions, subsets = dfa
    for symbol in word:
        state = transitions[(state, symbol)]
    return state in finals

# A binary string ends in 01: the initial epsilon edge is intentional.
states = {0, 1, 2, 3}
edges = {(3, None): {0}, (0, "0"): {0, 1},
         (0, "1"): {0}, (1, "1"): {2}}
dfa = determinize(states, 3, {2}, edges)
assert len(dfa[3]) == 4
assert dfa[3][0] == frozenset({0, 3})
for word, expected in (("", False), ("01", True), ("101", True),
                       ("0101", True), ("010", False), ("11", False)):
    assert accepts_dfa(word, dfa) is expected
try:
    accepts_dfa("012", dfa)
    assert False
except ValueError:
    pass
~~~

The queue terminates because there are finitely many subsets, and the closure search marks each state before revisiting it. The returned subset-to-ID trace exposes the generated states for inspection; integer IDs avoid representing every runtime input symbol as a new set. This is an **automaton compiler**, not a compiler for a general programming language.

## Complexity, explosion and boundaries

Let m be the number of NFA states, t the total number of stored NFA transition edges and k the alphabet size (k=2 here). A closure traversal costs O(m+t) in a straightforward adjacency representation; processing one discovered subset for all symbols costs at most O(k(m+t)) under the unit-cost hash-container model. At most 2^m subsets are discovered, giving a conservative upper bound O(2^m × k × (m+t)) for constructing a DFA and O(2^m × (m+k)) for state identifiers, subset records and the transition table, plus input edge storage. These are **worst-case bounds**, not claims that the worked example allocates 16 states.

Once compiled to integer state identifiers and a fixed alphabet, DFA recognition of a word of length n takes O(n) expected dictionary operations and O(1) additional working memory, apart from the prebuilt automaton and the input word. An NFA can instead be simulated without determinizing, maintaining reachable states while reading the word. That can avoid exponential compilation but incurs state-set work per symbol. Which representation is better depends on how many input words reuse the automaton and on memory limits.

Finite automata cannot recognize every computable language. Consider L_equal = {0^n 1^n : n >= 0}. If it were regular, a pumping length p would exist. For the word 0^p1^p, every valid decomposition xyz with |xy|<=p and |y|>0 places y entirely in the zeros. Pumping y down changes only the zero count, producing a word outside L_equal; contradiction. This **disproves regularity**. The pumping lemma is a necessary property of regular languages; satisfying a few pumping instances does not prove regularity. Actual nested syntax may require a pushdown model or a parser with an explicit stack [3].

## Independent verification and counterexamples

The published example checks six familiar strings, which is insufficient evidence of equivalence. An **independent oracle** can explore configurations (input position, NFA state) directly: epsilon edges keep the position unchanged; consuming edges advance it by one. A visited set prevents infinite loops. Compare this graph-search oracle against the compiled DFA on every binary word up to a finite length, including empty words. Unlike the subset algorithm, this oracle never constructs epsilon closures or DFA states and therefore can detect certain shared-implementation mistakes.

Tests should also cover accepting starts, empty-language NFAs, missing transitions that yield the empty-subset sink, epsilon cycles, unreachable states, and alternate nondeterministic paths. Validate malformed edges rather than silently treating unknown states as valid. Finite exhaustive and generated tests increase confidence, but they do not **replace** the induction proof: no fixed maximum word length can establish equivalence over an infinite language.

## Exercises and verification

1. Trace prefixes epsilon, 0, 01 and 011 through the worked NFA and its subset DFA. **Check:** {0,3}, {0,1}, {0,2}, {0}; only the third prefix is accepted.
2. Modify the NFA so the start state's epsilon closure already includes an accepting state. Does it accept the empty word? **Yes**, because the initial DFA subset intersects F.
3. Remove all transitions labeled 1 from the start's closure. Describe the resulting DFA transition and all its successors. **Check:** it goes to the empty-subset sink and stays there.
4. Prove with an induction on input length that the subset transition preserves the reachable-state invariant, including epsilon moves **after** the final consumed symbol.
5. Explain why simply choosing one NFA branch cannot simulate nondeterminism. Construct a word accepted only by another branch.
6. Determine whether a regex with a backreference necessarily denotes a regular language. **No**: formal regular expressions and extended engine features have different expressive limits.

This chapter establishes finite-state recognition and determinization. Subsequent chapters must address context-free grammars and parsing, Turing machines and undecidability, complexity classes, compiler pipelines and type systems separately; none is implied to be covered by the present finite-state model.
