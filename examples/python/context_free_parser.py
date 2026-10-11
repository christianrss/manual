"""Finite educational CFG recognition and a balanced-parenthesis tree parser.

General Earley-style chart reachability uses a deliberately simple fixed-point
closure, not the indexed O(n^3) implementation in the literature.
"""


def earley_accepts(grammar, start, word):
    """Test word membership for a finite CFG with single-character terminals.

    grammar: nonempty dict[str, tuple[tuple[str, ...], ...]].
    Nonterminals are dictionary keys; all other symbols must be one character.
    Empty RHS tuple represents epsilon. Duplicate productions are allowed.
    """
    if (type(word) is not str or type(grammar) is not dict or not grammar
            or type(start) is not str or start not in grammar):
        raise ValueError("invalid CFG or input word")
    rules = {}
    for lhs, productions in grammar.items():
        if type(lhs) is not str or not lhs or type(productions) not in (tuple, list):
            raise ValueError("invalid CFG nonterminal or production list")
        if not productions:
            raise ValueError("each nonterminal must have a production")
        rhs_list = []
        for rhs in productions:
            if type(rhs) not in (tuple, list):
                raise ValueError("RHS must be a tuple or list of symbols")
            symbols = tuple(rhs)
            if any(type(s) is not str or not s or
                   (s not in grammar and len(s) != 1) for s in symbols):
                raise ValueError("invalid CFG symbol")
            rhs_list.append(symbols)
        rules[lhs] = tuple(rhs_list)
    synthetic = "@START"
    while synthetic in rules:
        synthetic = "@" + synthetic
    n = len(word)
    chart = [set() for _ in range(n + 1)]
    accepted_item = (synthetic, (start,), 1, 0)
    chart[0].add((synthetic, (start,), 0, 0))
    for i in range(n + 1):
        changed = True
        while changed:
            changed = False
            for lhs, rhs, dot, origin in tuple(chart[i]):
                if dot == len(rhs):
                    # Completion: advance each origin item awaiting lhs.
                    for old_lhs, old_rhs, old_dot, old_origin in tuple(chart[origin]):
                        if old_dot < len(old_rhs) and old_rhs[old_dot] == lhs:
                            advanced = (old_lhs, old_rhs, old_dot + 1, old_origin)
                            if advanced not in chart[i]:
                                chart[i].add(advanced)
                                changed = True
                else:
                    nxt = rhs[dot]
                    if nxt in rules:
                        for production in rules[nxt]:
                            prediction = (nxt, production, 0, i)
                            if prediction not in chart[i]:
                                chart[i].add(prediction)
                                changed = True
                    elif i < n and word[i] == nxt:
                        chart[i + 1].add((lhs, rhs, dot + 1, origin))
    return accepted_item in chart[n]


def pushdown_accepts(word):
    """Deterministic stack recognizer for two balanced bracket types.

    A valid empty word is accepted. Characters outside ()[] raise ValueError.
    """
    if type(word) is not str or any(c not in "()[]" for c in word):
        raise ValueError("word must use the ()[] alphabet")
    opened = []
    closing = {")": "(", "]": "["}
    for symbol in word:
        if symbol in "([":
            opened.append(symbol)
        elif not opened or opened.pop() != closing[symbol]:
            return False
    return not opened


def parse_balanced(word):
    """Return a structural tree for S -> '(' S ')' S | epsilon.

    None denotes epsilon; (inner, tail) denotes one balanced group plus rest.
    Raises ValueError for invalid words, RecursionError if nesting is too deep.
    """
    if type(word) is not str or any(c not in "()" for c in word):
        raise ValueError("only '(' and ')' are permitted")

    def sequence(offset):
        if offset == len(word) or word[offset] == ")":
            return None, offset
        inner, j = sequence(offset + 1)
        if j == len(word) or word[j] != ")":
            raise ValueError("opening parenthesis has no close")
        tail, k = sequence(j + 1)
        return (inner, tail), k

    tree, consumed = sequence(0)
    if consumed != len(word):
        raise ValueError("unmatched closing parenthesis")
    return tree


BALANCED_GRAMMAR = {"S": (("(", "S", ")", "S"), ())}
ANBN_GRAMMAR = {"S": (("a", "S", "b"), ())}

if __name__ == "__main__":
    for word in ("", "()", "(())", "()()", "(()())"):
        assert earley_accepts(BALANCED_GRAMMAR, "S", word)
        parse_balanced(word)
    for word in (")(", "(()", "())", "(()))("):
        assert not earley_accepts(BALANCED_GRAMMAR, "S", word)
        try:
            parse_balanced(word)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid parentheses accepted")
