---
id: lexing-parsing-expression-compiler
title: "An Expression Compiler: Lexing, Precedence Parsing, AST, Bytecode and Virtual Machine"
description: "Implement an auditable arithmetic language from ASCII tokens to an AST, stack bytecode and exact rational evaluation, with independent tests."
category: foundations
difficulty: advanced
updated: 2026-10-11
prerequisites: [formal-languages-finite-automata, context-free-grammars-parsing, programming-semantics-contracts]
sources:
  - {title: "Cornell CS 4120 — Introduction to Compilers, 2026 Lecture Notes", url: "https://www.cs.cornell.edu/courses/cs4120/2026sp/notes/", kind: "university compiler course"}
  - {title: "Robert Nystrom — Crafting Interpreters: Compiling Expressions", url: "https://craftinginterpreters.com/compiling-expressions.html", kind: "original engineering textbook"}
  - {title: "Python Standard Library — fractions.Fraction", url: "https://docs.python.org/3/library/fractions.html", kind: "official language reference"}
  - {title: "Python Standard Library — ast", url: "https://docs.python.org/3/library/ast.html", kind: "official language reference"}
---
A compiler translates one language into a representation that another machine can execute. The distinction from the preceding [context-free grammar chapter](/en/topics/context-free-grammars-parsing/) is that membership alone is insufficient: a real translation pipeline must preserve operator precedence, source positions, evaluation semantics and errors. This chapter builds a **small complete compiler for arithmetic expressions** rather than a list of syntax terms: source characters become tokens, tokens become an abstract syntax tree (AST), the AST becomes postfix stack bytecode, and a virtual machine executes it [1][2]. This is a deliberately bounded teaching language, not Python, a general compiler or a security sandbox.

## Language contract and the boundaries between phases

The entire language has decimal **ASCII nonnegative integer literals** and the symbols `+ - * / ( )`. Whitespace is restricted to ASCII space, tab, carriage return and newline. There are no names, variables, assignments, strings, functions, booleans, Unicode digits or implicit multiplication. A lexical minus is always a separate token: `-12` is a unary operation applied to the literal 12, not a signed integer token. Operator `/` denotes **exact rational division**, not Python floating-point division or integer truncation [3].

An unambiguous reading of the grammar is: `expression -> additive`; `additive -> multiplicative (('+' | '-') multiplicative)*`; `multiplicative -> unary (('*' | '/') unary)*`; `unary -> ('+' | '-') unary | primary`; `primary -> INT | '(' expression ')'`. The repetition in the additive and multiplicative rules is **left-associative**. Prefix plus and minus bind more strongly than multiplication and division. All parsing must end at EOF, so a valid prefix followed by an extra token is an error. A language specification needs these declarations: a generic `E -> E + E | E * E | INT` grammar is ambiguous and does not establish precedence.

The [compilable reference module](https://github.com/christianrss/manual/blob/main/examples/python/expression_compiler.py) publishes the contracts `tokenize`, `parse_expression`, `compile_expression`, `run_bytecode`, `interpret_ast` and `evaluate`. The implementation uses Python as its **implementation language**, never as the interpreted source syntax. Passing an expression through this compiler cannot invoke arbitrary Python functions: identifiers, brackets, quotes and statements fail lexing. This absence of features reduces the accepted language; it is not a claim that this code safely executes untrusted workloads under arbitrary resource budgets.

## Scanner: tokens, offsets and lexical rejection

The lexer moves a cursor over the character string. It skips allowed whitespace, consumes maximal consecutive ASCII digits for each integer, emits a one-character operator or parenthesis token, or raises `CompileError` for an unknown character. Each token records `(kind, text, start, end)` with **half-open** character offsets, and one `EOF` token is appended at the source length. In `"12 +3"`, the tokens are `INT[0,2)`, `+[3,4)`, `INT[4,5)` and `EOF[5,5)`. Offsets index Python string characters, not UTF-8 byte positions, although this particular language only permits ASCII tokens.

**Lexing invariant:** immediately before each iteration, the source prefix before the cursor has been partitioned into valid tokens and permitted whitespace; nothing after the cursor has been consumed. Consuming all consecutive digits ensures the scanner does not split `123` into three separate literals. If an unexpected character appears, the scanner fails at its current offset instead of skipping data that might change an expression's meaning. This is the same separation between lexing and parsing used in compiler courses [1].

The lexer rejects `2**3`, `0x10`, `1.5`, `2_000` and non-ASCII digits. Lexical failure differs from grammatical failure: the characters in `"1+"` are individually valid tokens, but there is no operand after plus. Validating tokens and grammar separately gives better fault localization than evaluating a source string with a host-language `eval`.

## Parsing precedence and associativity into an immutable AST

The parser uses a **precedence-climbing** routine `expression(minimum, depth)`. A prefix parse consumes an integer, a unary operator with a higher binding power, or a parenthesized expression. The following loop consumes binary operators as long as their precedence is at least the current minimum. Addition/subtraction use binding power 10, multiplication/division use 20 and prefixes use 30. To make a binary operator **left-associative**, parse its right operand with minimum precedence `power + 1`. A second operator of equal precedence then belongs to the surrounding loop, not to the right subtree [2].

For `10-3-2`, the AST is equivalent to `Binary('-', Binary('-', 10, 3), 2)` and evaluates to 5; the alternative `10-(3-2)` would evaluate to 9. For `1+2*3`, the higher-precedence multiplication is a subtree of addition, producing 7. Parentheses override that hierarchy: `(1+2)*3` produces 9. Repeated unary symbols such as `--5` are legal and compose in order.

The AST consists of immutable `Literal`, `Unary` and `Binary` dataclass nodes with operator and source offsets. Parentheses deliberately disappear from the semantic tree: grouping affects structure, not arithmetic operations. Source spans in these retained nodes are **not** a lossless concrete syntax tree; the opening parenthesis around a primary is not preserved as a separate node. This is adequate for arithmetic value computation, not for reconstructing the original spacing or punctuation exactly.

## From AST to stack bytecode

A second phase walks the AST **after visiting its operands**, yielding postfix instructions. A literal emits `PUSH n`, a unary operation emits `NEG` or `POS`, and a binary operation emits `ADD`, `SUB`, `MUL` or `DIV`. The compiler carries an operator source offset with each instruction for error reporting. An explicit work stack, instead of recursive code generation, supports long left-associated chains without overflowing the Python call stack.

For the source `8/(2+2)+-3`, the generated operations, omitting offsets, are:

```text
PUSH 8
PUSH 2
PUSH 2
ADD
DIV
PUSH 3
NEG
ADD
```

The virtual machine processes instructions sequentially. A `PUSH` increases stack height by one; `NEG` or `POS` replaces the top element; and a binary operation removes two elements and pushes one result, decreasing height by one. **Stack-height invariant:** every prefix of compiler-generated code has sufficient operands for its next instruction, and a complete expression leaves exactly one value. The final result is `8/4 + (-3) = -1`. This is a stack VM, not CPU machine code; register allocation, linking and native assembly are out of scope [2].

## Syntax-directed evaluation and exact arithmetic

The AST has an independent semantics: `value(Literal(n)) = n`; `value(Unary(op, e)) = op(value(e))`; and `value(Binary(op, l, r)) = value(l) op value(r)` when the operation is defined. `interpret_ast` evaluates this definition using an explicit postorder stack rather than executing the compiled bytecode. `run_bytecode` performs the same arithmetic over values stored on its operand stack. Comparing the two traversals catches a class of code-generation or VM bugs, though they share the language's intended arithmetic rules.

Use `fractions.Fraction`: `1/3+1/6` becomes exactly `1/2`, not a rounded binary float [3]. This choice is deliberate. Exact rational arithmetic avoids a second teaching problem about IEEE 754 rounding, but it still has a cost: numerator and denominator bit lengths can grow after repeated operations. Arithmetic on arbitrary-size integers is **not** guaranteed constant time merely because a VM dispatches one instruction.

Division by zero is a **runtime** error, not a lexical or grammatical error: `1/(2-2)` parses and compiles, then raises `ZeroDivisionError` during evaluation. A different language might perform compile-time constant folding and detect that error sooner, but no such optimization is implemented here. A compiler should distinguish the phases rather than claiming that successful parsing guarantees valid execution.

## Executable demonstration and independent oracle

This testable example is identical in the Portuguese chapter; it uses the committed module and checks AST and VM agreement.

~~~python
from fractions import Fraction
from examples.python.expression_compiler import (
    tokenize, parse_expression, compile_expression,
    run_bytecode, interpret_ast, evaluate,
)

source = "8/(2+2)+-3"
assert [token.kind for token in tokenize(source)] == [
    "INT", "/", "(", "INT", "+", "INT", ")",
    "+", "-", "INT", "EOF",
]
assert [op for op, value, offset in compile_expression(source)] == [
    "PUSH", "PUSH", "PUSH", "ADD", "DIV",
    "PUSH", "NEG", "ADD",
]
assert run_bytecode(compile_expression(source)) == Fraction(-1)
assert interpret_ast(parse_expression(source)) == Fraction(-1)
assert evaluate("1/3+1/6") == Fraction(1, 2)
assert evaluate("10-3-2") == Fraction(5)
~~~

The [independent tests](https://github.com/christianrss/manual/blob/main/tests/test_expression_compiler_contracts.py) use a **restricted visitor over CPython's independent `ast.parse` result** as an oracle; no `eval` or `exec` is applied to learner strings. Only integer constants and the four allowed binary and two unary operators are interpreted by the oracle [4]. Seeded generated expressions exercise nested grouping, prefix operators, association and division; both VM and AST interpreter must agree with the oracle on defined results and must reject zero denominators in corresponding cases.

Other tests validate token offsets, errors and long flat expressions, and walk generated bytecode to assert stack-height discipline. They are stronger than a few hand-selected examples but remain **finite tests**, not a proof of every behavior of the Python implementation. The AST-to-bytecode translation correctness argument is an induction on nodes: a literal leaves its value; an operand's compiled code leaves exactly its value; and emitting the corresponding operator combines the required one or two values into the semantic result.

## Limits, failure modes and engineering trade-offs

For source length n and t tokens, the bounded ASCII scanner performs O(n) character operations and produces O(t) tokens. Precedence climbing and AST construction perform O(t) token-processing work under constant-time node operations for this grammar. Bytecode generation and VM instruction dispatch take O(t) *abstract machine operations*, with O(t) AST/code memory and potentially O(t) VM stack use for arbitrary nesting. The **bit-complexity of rational arithmetic** is additional and depends on the sizes of intermediate numerators and denominators, so the end-to-end cost must not be described unconditionally as O(n) bit operations.

The example imposes a maximum input length of 4,096 characters, 2,048 tokens, 100 digits per literal, and a parser nesting budget of 80. These are **educational bounds**, not protection against all denial-of-service cases. Very large intermediate rational values, process memory, Python exceptions and CPU quotas remain considerations. Bytecode is assumed to be emitted by the compiler; the VM checks unknown opcodes and stack underflow, but does not define an authenticated bytecode-file format. A multi-user service would need separate execution budgets and isolation.

A simple compiler makes each boundary observable, yet missing features matter: no statements, identifiers, symbol tables, variables, static type judgments, optimizations, closures, control flow, garbage collection or machine-code backend are provided. Calling the exercise a full programming language would be misleading. The next chapter should add **typed variables and a semantic environment**, proving type rules before executing bytecode that can refer to names [1].

## Exercises and verification

1. Derive the AST for `8/4/2`. **Check:** left associativity requires `(8/4)/2 = 1`, not `8/(4/2) = 4`.
2. Produce postfix code for `-(2+3)*5/7` and trace stack height. **Check:** `PUSH 2; PUSH 3; ADD; NEG; PUSH 5; MUL; PUSH 7; DIV` leaves exactly one value, `-25/7`.
3. Explain why `1+2*3` and `(1+2)*3` need different ASTs despite identical operators. **Check:** grouping and precedence change the tree, which determines evaluation order.
4. Test `1/(3-3)`. **Check:** lexing, parsing and compilation succeed; VM evaluation raises `ZeroDivisionError`.
5. Change a single precedence rule and predict a counterexample before running it. **Check:** making `+` bind above `*` changes the result of `1+2*3` from 7 to 9.
6. Explain why the independent CPython AST oracle is restricted. **Check:** using the full host interpreter or `eval` would extend the accepted language to calls, attributes or other behavior the toy language intentionally forbids.

This chapter provides a real translation pipeline for a **small arithmetic domain**. Its tested contracts do not establish production compiler safety, typed-language correctness, or general-purpose language semantics.
