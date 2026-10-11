---
id: static-types-lexical-scopes
title: "Static Type Checking, Lexical Scopes and a Typed Expression Compiler"
description: "Extend the expression compiler with typed let-bindings, lexical shadowing, Boolean conditionals, static judgments and verified stack bytecode."
category: foundations
difficulty: advanced
updated: 2026-10-11
prerequisites: [lexing-parsing-expression-compiler, programming-semantics-contracts]
sources:
  - {title: "Benjamin C. Pierce — Types and Programming Languages", url: "https://mitpress.mit.edu/9780262162098/types-and-programming-languages/", kind: "original textbook"}
  - {title: "Cornell CS3110 — Type Checking", url: "https://cs3110.github.io/textbook/chapters/interp/typecheck.html", kind: "university teaching reference"}
  - {title: "Robert Nystrom — Crafting Interpreters: Resolving and Binding", url: "https://craftinginterpreters.com/resolving-and-binding.html", kind: "original engineering textbook"}
  - {title: "Python Standard Library — fractions.Fraction", url: "https://docs.python.org/3/library/fractions.html", kind: "official language reference"}
---
A parser proves only that its input has a permitted **shape**. It does not establish that every name exists, an operator receives values it can handle, or the branches of a conditional return compatible types. This chapter extends the executable [arithmetic compiler](/en/topics/lexing-parsing-expression-compiler/) with **lexically scoped, explicitly typed bindings**, Booleans and conditional expressions. The implementation carries the source from tokens through an immutable AST, a static type checker and compiled stack bytecode. The key new boundary is that **type checking finishes before execution begins** [1][2].

The result is a small expression language, not a general-purpose compiler. Its rules are independently defined, its compilation is testable, and its limitations are documented. In particular, the system does not establish that evaluation can never fail: even a statically well-typed rational expression may divide by zero.

## Language grammar and decisions that affect semantics

The previous source language accepted unsigned ASCII integer literals, unary `+` and `-`, binary `+ - * /` and parentheses. The extended lexer adds ASCII identifiers (letters or underscore, followed by letters, digits or underscore), the keywords `let`, `in`, `if`, `then`, `else`, `true`, `false`, type names `Int`, `Rat`, `Bool`, and the symbols `:`, `=` and `<`. The old `tokenize(source)` contract is **unchanged**; the new language opts in with `tokenize(source, extended=True)`. Keywords cannot serve as variable names, and Unicode identifiers are not admitted. This small lexical contract is a choice, not a claim about how programming languages ought to tokenize names.

The expression grammar adds `let IDENT ':' Type '=' expression 'in' expression`, `if expression 'then' expression 'else' expression`, `true`, `false`, and identifier references. Binary `<` binds more weakly than `+` and `*`. All arithmetic retains left associativity and unary operators bind more strongly. Parentheses retain their usual grouping semantics. This grammar has **no statements, loops, assignments, mutable references, functions, equality operator or short-circuit Boolean operators**.

Three type names are recognized. An integer literal has static type `Int`; a Boolean literal has type `Bool`; and exact rational values have type `Rat`. Division `/` always returns `Rat`, even for a value mathematically equal to an integer. `+`, `-` and `*` return `Int` only when **both** inputs are `Int`; otherwise the result is `Rat` if both inputs are numeric. Unary `+` and `-` preserve the numeric operand's type. A comparison `<` between numeric operands returns `Bool`. No arithmetic operation accepts `Bool`. These rules define a language intentionally distinct from Python's implicit coercions.

## Typing judgments and the symbol environment

Write `Gamma |- e : T` to mean “under type environment Gamma, expression e has type T.” Gamma maps visible variable names to their declared types. The rules are **syntax-directed**: inspecting the AST's constructor determines which premises must hold [1][2].

For a literal `42`, the type is `Int`; for `true`, it is `Bool`. A variable reference `x` is well typed only if the **nearest visible binding** of x exists in Gamma. A binary numeric operation requires numerical operand types and returns the type specified by the operator table. In particular, `1/3 + 1/6` is `Rat`, and `1 < 2` is `Bool`. Asking for `true + 1` or `-false` produces a static `TypeCheckError`; the bytecode VM is never invoked.

The `let` rule is crucial. To type `let x: T = e1 in e2`, first check `e1` under the **current** Gamma and require its inferred type to match the declared T **exactly**. Then type the body `e2` under a *new* environment Gamma extended with `x:T`. The result type is that of the body. Thus `let x: Rat = 3 in x` is rejected: the initializer is `Int`, and this version supplies **no implicit Int-to-Rat assignment conversion**. Write `let x: Rat = 3/1 in x` instead. The type rule does not make the new x visible within its own initializer; recursive bindings are absent.

For `if c then a else b`, require `c: Bool`, and require that **both branches** have the same exact type T. The whole expression has type T. Both branches are type-checked even if the condition is literally `true` or `false`: `if true then 1 else false` is invalid, and `if false then unknown else 2` still fails because the unbound name is a static error. This follows the usual conditional typing discipline, without general subtyping, type inference variables, unions or implicit branch promotions [2].

## Lexical scope, shadowing and escaping bindings

**Lexical scope** means a name's binding is determined by the syntactic nesting structure, not by which caller happens to be active at runtime [3]. Consider `let x: Int = 5 in let x: Int = x+1 in x`. The initializer of the second x is evaluated in the outer environment, so it produces 6. Inside the second let's body, x refers to the inner value 6. When its scope closes, the inner binding is no longer visible. This is **shadowing**, not mutation of the outer x.

Contrast `let x: Int = x+1 in x`, which fails at compile time: no x is bound when the initializer is checked. Likewise, `(let x: Int = 2 in x) + x` is invalid because the final x appears **outside** the first binding's body. A system that puts every name in one global dictionary could accidentally accept this expression, giving the wrong language semantics.

The static checker represents an environment as a dictionary and creates a copy with the new binding for each let body. The compiled VM instead maintains a stack of **runtime environment frames**: `ENTER` opens one frame, `BIND x` takes the initialized value from the operand stack and records it in that frame, `LOAD x` searches frames from the innermost outward, and `LEAVE` discards the current frame while preserving the expression's computed value on the operand stack. Static and runtime environment representations differ, but they encode the same lexical lookup relation.

## Type soundness: a limited progress and preservation argument

The principle of **preservation** says that one valid evaluation step should preserve the declared type. Here the literal `Int` representation is an exact `Fraction` with denominator one; a `Rat` is also a `Fraction`, and a `Bool` is an actual Python Boolean. Arithmetic on two integers with `+`, `-` or `*` stays integral, and numeric division yields an exact rational. A `<` comparison produces a Boolean; the VM consumes that Boolean when selecting a conditional branch. For a let expression, the initializer is statically required to match its annotation before binding, so a lookup retrieves a value of the recorded type. The argument proceeds by structural induction over the typed AST and the compiler's instruction emission.

**Progress** requires an explicit qualification. A well-typed expression either is a value, can take an evaluation step, or may reach a **defined dynamic arithmetic error**, notably division by zero. The language does not promise “well typed implies guaranteed completion.” A chosen conditional branch is evaluated, while the unchosen branch is **not** executed. An expression such as `if false then 1/0 else 1/2` is statically valid, has type `Rat`, and returns one half because the division-by-zero instruction is skipped. Both branches remain statically checked even though only one executes.

The compiler does not perform a machine-checked formal proof or enforce a typed bytecode verifier. Its static and runtime invariants are given as mathematical reasoning and backed by finite tests. Exposing a forged `TypedProgram` directly to the VM is **not** equivalent to running verified compiler output; the VM has some defensive checks but is not a secure evaluator for arbitrary instruction streams.

## Executable extension: type checking before bytecode

The [typed compiler implementation](https://github.com/christianrss/manual/blob/main/examples/python/typed_expression_compiler.py) reuses the earlier `Literal`, `Unary` and `Binary` AST nodes, token structure, errors and arithmetic precedence, and adds `Name`, `Boolean`, `Let` and `If`. `parse_typed` constructs the AST. `typecheck` derives a type or raises `TypeCheckError` with a source-character offset. `compile_typed` first checks the AST and only then generates instructions. `evaluate_typed` returns the inferred type and execution result.

~~~python
from fractions import Fraction
from examples.python.typed_expression_compiler import (
    evaluate_typed, parse_typed, typecheck,
    compile_typed, run_typed, TypeCheckError,
)

source = "let x: Int = 5 in let x: Int = x+1 in x"
assert typecheck(parse_typed(source)) == "Int"
assert evaluate_typed(source) == ("Int", Fraction(6))
assert run_typed(compile_typed("let r: Rat = 1/3 in r+1/6")) == Fraction(1, 2)
assert evaluate_typed("if false then 1/0 else 1/2") == (
    "Rat", Fraction(1, 2)
)
assert evaluate_typed("3<4") == ("Bool", True)
try:
    compile_typed("if true then 1 else false")
    assert False, "a mistyped branch must be rejected"
except TypeCheckError:
    pass
~~~

Code generation for a conditional emits `JUMP_IF_FALSE` and an unconditional `JUMP` with **forward-patched destinations**, ensuring only one branch runs. A let emits its initializer, opens a scope, binds the resulting value, compiles the body and closes the scope. Successful compiler-generated bytecode preserves one final operand-stack result, with all scopes closed. A comparison or Boolean literal uses dedicated VM instructions; simply encoding Booleans as integers would defeat the language's explicit static distinction.

## Independent tests, costs and limits

The [contract suite](https://github.com/christianrss/manual/blob/main/tests/test_typed_expression_compiler_contracts.py) tests hand-derived outcomes and a separate **direct AST evaluator** that does not generate or execute stack bytecode. It generates deterministic examples of nested shadowing, arithmetic, comparisons and both conditional outcomes. Additional tests reject unbound names, out-of-scope references, invalid annotations, mismatched conditional branches and arithmetic on Boolean values. They also examine scope enter/leave balance and demonstrate that an unselected division-by-zero branch is skipped. Finite tests are supporting evidence, not a universal proof.

If n is the AST node count and d is maximum lexical nesting, syntax-directed checking visits O(n) nodes but **copying the environment** for each let may take O(d) per binding, yielding O(n d) time and as much as O(d²) simultaneously retained dictionary entries along a deeply nested sequence of bindings. VM name lookup scans up to d runtime frames, also permitting O(n d) dispatch-time behavior for n instructions in the worst case. Exact rational arithmetic adds magnitude-dependent bit cost. These are deliberately unoptimized designs: symbol slots, indexed lexical distances or persistent environments could reduce lookup and copy overhead [3].

The example limits input length, token count and parser/AST nesting depth. It does not support functions, recursive variables, reassignments, statements, closures, polymorphism, inference constraints, dynamic casts, exceptions as language values or native code. A `Rat` and an `Int` are both physically stored using `Fraction`; their **static distinctions** exist in the compiler's judgments, rather than in runtime tagged numerical values. Real optimizing compilers must handle many more execution and representation concerns.

## Exercises and verification

1. Determine the value of `let x: Int = 4 in let x: Int = x*2 in x`. **Check:** the inner initializer sees the outer x; the result is `Int`, 8.
2. Decide whether `let r: Rat = 5 in r` is valid. **No**: its initializer is `Int`; use `5/1` to create a `Rat`.
3. Give a counterexample to compiling only the selected branch of a constant conditional. **Check:** `if true then 1 else false` must fail static checking even though the second branch would not run.
4. Trace `ENTER`, `BIND`, `LOAD` and `LEAVE` through a nested let with shadowing. **Check:** leaving the inner frame restores the outer binding; a load outside both scopes must not succeed.
5. Derive the type of `let x: Int = 2 in if x<3 then x/2 else x/4`. **Check:** condition `Bool`, both branches `Rat`, full expression `Rat`.
6. Explain why a well-typed arithmetic program can still raise `ZeroDivisionError`; distinguish progress with defined runtime errors from a promise of termination.

The next compiler stage could add **assignable storage and functions with parameter/return types**, followed by lexical-address resolution, a type-checkable bytecode format and more substantial validation. Such features have not been implemented here.
