---
id: mutable-cells-recursive-functions
title: "Mutable Cells, Shared Closures and Typed Recursive Functions"
description: "Extend typed functions with mutable lexical cells, assignment and let-rec initialization, then verify aliasing and recursive VM execution."
category: foundations
difficulty: advanced
updated: 2026-10-11
prerequisites: [typed-functions-call-frames-closures]
sources:
  - {title: "Robert Nystrom — Crafting Interpreters: Closures", url: "https://craftinginterpreters.com/closures.html", kind: "original compiler engineering textbook"}
  - {title: "Cornell CS3110 — OCaml Programming: Refs", url: "https://cs3110.github.io/textbook/chapters/mut/refs.html", kind: "university programming languages textbook"}
  - {title: "Benjamin C. Pierce — Types and Programming Languages", url: "https://mitpress.mit.edu/9780262162098/types-and-programming-languages/", kind: "academic textbook"}
  - {title: "Robert Nystrom — Crafting Interpreters: Functions", url: "https://craftinginterpreters.com/functions.html", kind: "original compiler engineering textbook"}
---
An immutable closure can store snapshots of lexical bindings. That stops working when a captured variable can be **assigned a new value**: two closures capturing one mutable variable must access **one storage location**, not copies of an old value. This chapter extends [typed functions and activation frames](/en/topics/typed-functions-call-frames-closures/) with shared cells, assignment, typed recursion and bytecode that preserves references beyond returning call frames [1][2]. It changes the existing working compiler rather than presenting unrelated pseudocode.

## Syntax, activation and backward compatibility

Three earlier lexer modes remain unchanged. Only `tokenize(source, extended=True, functions=True, stateful=True)` recognizes the additional reserved words `var`, `set` and `rec`. The previous arithmetic, typed-variable and immutable-function programs continue to use their original entry points; stateful syntax is opt-in.

A mutable binding is `var x: Int = 1 in expression`. Its initializer is evaluated **before** x becomes visible, and the new x is bound only in the body. Assignment has the form `set x = expression`; the right-hand expression is evaluated first, then the visible x is updated. This teaching language makes assignment **an expression returning its assigned value**, unlike the `unit` result of the OCaml assignment operator [2]. Parentheses delimit operations clearly: `(set x=x+1)+x`. There is no separate `Unit` type or statement-sequencing operator.

A recursive function binding is `let rec f: Fn(Int)->Int = fn(n:Int)->Int=>... in expression`. Only an explicitly annotated **function literal** can initialize `let rec`. General recursive values, mutual recursion and reassignment of f are forbidden. This restriction prevents an initializer from evaluating its own missing value before the closure is constructed. It is not an implementation of unrestricted fixed-point evaluation.

## Mutable capture: value versus location

Each `var` binding creates a fresh `Cell` with value, writable flag and initialized flag. Scopes remain dictionaries. At closure creation the environment dictionaries are copied, but **cell objects are shared**. A subsequent call copies the captured dictionaries again, still preserving the same cells. This implements lexical aliasing: copying an environment **mapping** is not the same as copying every variable's **stored value** [1][2].

For `var x:Int=1 in let f:Fn()->Int=fn()->Int=>set x=x+1 in f()+f()`, the first call changes x from 1 to 2 and returns 2; the second sees 2, changes it to 3 and returns 3. The final result is **5**. Separate capture-by-value copies would not produce that behavior. Two different closures defined in the same mutable scope also refer to the same cell. Shadowing does not overwrite an earlier variable: a new `var x` creates a distinct location.

A returned closure may outlive the frame that created the cell. The expression `fn(seed:Int)->Fn()->Int=>var x:Int=seed in fn()->Int=>set x=x+1` produces a callable that retains x after its outer call returns. Python owns the concrete `Cell` memory; this example demonstrates **reachability** and escaped lifetimes, not a user-space allocator or tracing garbage collector. Captured immutable `let` bindings continue to store immutable values directly.

## Static environment and typing rules

The type checker now maps each visible identifier to **(type, writable)**. For `let x:T=e1 in e2`, check the initializer using the incoming environment, require its type to equal T exactly, then check the body with x marked **not writable**. The corresponding `var x:T=e1 in e2` gives the new binding the same static type but marks it writable. The rules preserve lexical shadowing: a mutable outer x does not make a separate immutable inner x mutable [3].

Typing `set x=e` requires a visible binding, a true writable flag and an expression e whose type is **exactly** that binding's T. The result has type T. The checker rejects `let x:Int=1 in set x=2`, `var x:Int=1 in set x=true`, and writes to an out-of-scope name before executing any bytecode. Checking only the destination value at runtime would weaken the language's explicit static contract.

For `let rec f:Fn(A)->B=fn(x:A)->B=>body in e2`, first extend the type environment with f marked **immutable**, then check the lambda initializer in that extended environment. The inferred function type must match the declared type exactly; the `in` body is checked under the same extended environment. This recursive typing rule allows recursive calls while rejecting mismatched arguments, return annotations and illegal assignment to f. A general `let` remains **nonrecursive**, so its new variable is not visible in its initializer [3][4].

## The runtime initialization knot

Compilation of `var` evaluates its initializer, executes `ENTER`, binds the value with `BIND_VAR`, evaluates the body and executes `LEAVE`. `BIND_VAR` allocates a writable `Cell`; `STORE` updates the nearest visible writable cell after evaluating its new value. It leaves the result on the operand stack, preserving the assignment-expression contract.

Recursive functions need a different sequence: **`ENTER` → `DECLARE_REC f` → `CLOSURE` → `INIT_REC f` → body → `LEAVE`**. `DECLARE_REC` places a fresh, **uninitialized and non-writable** cell in the scope. `CLOSURE` captures a reference to that cell. `INIT_REC` fills it with the closure once. Subsequent recursive `LOAD f` operations follow this reference to retrieve the fully initialized function. The implementation can thus build a self-referential value without exposing a partially constructed function to user programs [1][4].

The **initialization invariant** is that no recursive name is read until its cell has been initialized. The syntactic restriction to a lambda initializer ensures user-visible evaluation cannot read f prematurely; the VM also rejects a forged instruction sequence that attempts it. Although f uses a cell internally, it is **not writable** through `set`. This distinction between internal initialization and programmer-visible mutation prevents an accidental escape from the static rules.

## Executable example, independent oracle and regression coverage

The published [stateful compiler facade](https://github.com/christianrss/manual/blob/main/examples/python/stateful_function_compiler.py) exposes `parse_stateful`, `compile_stateful` and `evaluate_stateful` while reusing the existing typed-function code generator and VM. Its tests check earlier language modes as well as the new semantics.

~~~python
from fractions import Fraction
from examples.python.stateful_function_compiler import (
    compile_stateful, evaluate_stateful,
)
from examples.python.typed_function_compiler import run_functions

counter = ("var x:Int=1 in "
           "let inc:Fn()->Int=fn()->Int=>set x=x+1 in "
           "inc()+inc()")
assert evaluate_stateful(counter) == ("Int", Fraction(5))

factorial = ("let rec fact:Fn(Int)->Int="
             "fn(n:Int)->Int=>if n<2 then 1 else n*fact(n-1) "
             "in fact(5)")
assert evaluate_stateful(factorial) == ("Int", Fraction(120))
assert run_functions(compile_stateful(factorial)) == Fraction(120)

escaped = ("let make:Fn(Int)->Fn()->Int="
           "fn(seed:Int)->Fn()->Int=>var x:Int=seed in "
           "fn()->Int=>set x=x+1 in "
           "let next:Fn()->Int=make(5) in next()+next()")
assert evaluate_stateful(escaped) == ("Int", Fraction(13))
~~~

The independent [contract tests](https://github.com/christianrss/manual/blob/main/tests/test_mutable_recursion_compiler_contracts.py) use a separately written **direct AST interpreter** with its own reference-cell representation. It does not execute compiler bytecode. Hand-derived examples and seeded cases cover counters, lexical shadowing, escaped mutable closures, factorial and countdown recursion. Negative tests cover immutable assignment, type mismatches, nonfunction recursive declarations, uninitialized cell reads and VM execution limits. Agreement over finitely many cases supports the design but is not a mechanized universal proof.

## Complexity, memory lifetime and failure models

Let n be the number of AST nodes, d the depth of lexical nesting and c the number of environment entries copied at a capture. Static checking visits O(n) nodes, while copied environments can add up to O(n d) work. A closure capture costs O(c) to copy dictionary entries while **retaining cell identity**; lexical lookup may search O(d) scopes. Recursive program calls consume one distinct VM frame each, even though the bytecode dispatch loop itself is iterative.

The default VM limits are **50,000 dispatched instructions** and **128 simultaneous call frames**, with preexisting source, token and parser-depth limits. These are **educational limits**, not a robust sandbox: one arbitrary-precision rational operation may use substantial CPU or memory, and retained closures may extend the lifetime of many cells. No atomic assignments, threads, race-free memory model, cycle-collecting runtime owned by the VM, general bytecode verifier or native compiler backend exists.

## Exercises and verification

1. Trace both calls in `var x:Int=1 in let f:Fn()->Int=fn()->Int=>set x=x+1 in f()+f()`. **Check:** shared cell values 2 and 3, total 5.
2. Replace `var` with `let` in the example. **Check:** static immutability error.
3. Compute `let rec f:Fn(Int)->Int=fn(n:Int)->Int=>if n<1 then 0 else 1+f(n-1) in f(8)`. **Check:** 8.
4. Explain the order `DECLARE_REC`, `CLOSURE`, `INIT_REC`. **Check:** the closure captures an existing cell whose value is filled only after capture.
5. Have two separate closures capture the same `var` binding. **Check:** one closure's assignment becomes observable to the other.
6. Explain why a dispatch-step budget does not limit all CPU and heap consumption. **Check:** arbitrary-precision arithmetic and closure retention can be expensive within one step.

Next chapters should formalize **store semantics, lexical addresses, bytecode verification and lifetime analysis**. None are considered implemented by this deliberately bounded extension.
