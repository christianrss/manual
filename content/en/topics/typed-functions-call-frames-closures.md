---
id: typed-functions-call-frames-closures
title: "Typed Functions, Lexical Closures and Bytecode Call Frames"
description: "Compile typed first-class functions, lexical closures and higher-order calls with explicit VM activation frames and independent execution tests."
category: foundations
difficulty: advanced
updated: 2026-10-11
prerequisites: [static-types-lexical-scopes]
sources:
  - {title: "Robert Nystrom — Crafting Interpreters: Functions", url: "https://craftinginterpreters.com/functions.html", kind: "original engineering textbook"}
  - {title: "Robert Nystrom — Crafting Interpreters: Closures", url: "https://craftinginterpreters.com/closures.html", kind: "original engineering textbook"}
  - {title: "Robert Nystrom — Crafting Interpreters: Resolving and Binding", url: "https://craftinginterpreters.com/resolving-and-binding.html", kind: "original engineering textbook"}
  - {title: "Benjamin C. Pierce — Types and Programming Languages", url: "https://mitpress.mit.edu/9780262162098/types-and-programming-languages/", kind: "original academic textbook"}
---
A local variable is not a complete language model until a function can **refer to that variable after its defining scope has ended**. The previous [static types and lexical scopes](/en/topics/static-types-lexical-scopes/) chapter implemented immutable `let` bindings and typed conditionals but no callable values. This chapter adds first-class, statically typed anonymous functions, parameter and return annotations, lexical closure capture, higher-order calls and an **explicit stack of virtual-machine activation frames**. Both the implementation and its independent oracle are executable; a general compiler, recursive language or verified bytecode environment is not implied [1][2].

## Syntax and exact contracts

The source language retains ASCII integer literals, arithmetic over exact rational numbers, `Int`, `Rat`, `Bool`, `let`, `if` and lexical shadowing. Function mode adds `fn`, the function-type constructor `Fn`, a comma and two distinct arrows: `->` in a return-type annotation and `=>` introducing the function body. The old arithmetic and typed lexing modes retain their original token contracts; only `tokenize(source, extended=True, functions=True)` enables these extra tokens.

An anonymous function is written `fn(x: Int, y: Int) -> Int => x+y`. A function type is `Fn(Int,Int)->Int`: an ordered list of argument types followed by the result type. The empty parameter list is supported: `fn()->Int=>3` has type `Fn()->Int`. A type itself can be a function type, enabling higher-order functions, such as `Fn(Int)->Fn(Int)->Int`. Types in all parameter, return and `let` annotations are **explicit**. No implicit casts, overloaded functions, optional arguments, default parameters, mutation or recursive bindings are present.

A call has the form `callee(arg1,arg2)`. Calls bind more tightly than multiplication and addition, and arguments are evaluated **from left to right**. A lambda can be called immediately using parentheses for grouping, for example `(fn(x:Int)->Int=>x+1)(3)`. A bare function literal's body extends to the relevant delimiter, so parentheses are important when combining lambda literals, calls and arithmetic. A malformed argument list or an unknown token is a syntax error rather than an evaluation that guesses intent.

## Static judgments for functions and calls

The typing environment Gamma maps visible names to types. For a function with parameter types T1 through Tk and declared return type U, type its body in the environment Gamma extended by the k parameters. If and only if its body has **exactly** type U, the whole literal has type `Fn(T1,...,Tk)->U`. A function declaration with repeated parameter names is rejected before type checking. These premises constitute the introduction rule for function types [4].

The elimination rule is function application: if the callee has type `Fn(T1,...,Tk)->U` and each argument has its corresponding type Ti, then the call has type U. The arity must match exactly, including zero-argument calls. Calling `1(2)` is a static error; `f(true)` is invalid when `f` expects `Int`; and `fn(x:Int)->Bool=>x+1` fails because the inferred body type `Int` disagrees with the return annotation. No arbitrary dynamic type errors need to be deferred until the call for these cases.

The existing rules still apply inside function bodies: `+` requires numeric operands, division returns `Rat`, `<` returns `Bool`, both `if` branches must agree, and a new `let` name is **not** visible inside its own initializer. In particular, `let f: Fn(Int)->Int = fn(x:Int)->Int=>f(x) in f(1)` is rejected: the compiler implements nonrecursive `let`, not `let rec`. Recursive functions and mutually recursive groups require a separate binding discipline and a careful termination/resource model.

## Lexical capture versus dynamic lookup

Consider `let x:Int=10 in let f:Fn(Int)->Int=fn(y:Int)->Int=>x+y in let x:Int=99 in f(2)`. The function literal is created when x is 10. It must return **12**, not 101, even though the caller shadows x with 99. Lexical lookup follows **definition-time textual nesting**, rather than searching the caller's stack frames [2][3]. A function value therefore consists of both executable code and an environment containing the necessary bindings; that pair is called a **closure**.

An even stronger counterexample returns a closure from a function: `fn(x:Int)->Fn()->Int=>fn()->Int=>x`. The inner function's x remains accessible after the outer call has returned and its activation frame is no longer active. The implementation captures **copies of the currently visible immutable scope dictionaries** when the `CLOSURE` instruction executes. This is adequate for a language without assignment: the captured values are immutable integers, Booleans and function values, so later shadowing does not retroactively alter a closure's environment.

A production implementation of mutable captured variables requires a different representation, such as reference cells or upvalues. Copying immutable environment mappings is **not** a correct substitute for mutable capture-by-reference semantics. This chapter deliberately does not implement mutation, reference identity or upvalue closing. The distinction is essential: a solution that appears correct for constant captures can fail immediately when assignments are introduced [2].

## Compilation into bytecode and activation records

After parsing and static checking, `compile_functions` translates each function body into a separate immutable `Code` object. A `Code` object contains its ordered parameter names and bytecode instructions. Compiling a lambda emits `CLOSURE` with that code object. Compiling a call emits instructions to evaluate the callee, then every argument in order, followed by `CALL k`. Each compiled body and the top-level program terminate in an explicit `RETURN` instruction. Existing arithmetic and branch instructions retain their previous meaning.

At runtime a **frame** contains its code, instruction pointer, operand stack and lexical scope dictionaries. Each `CALL` removes its arguments and callable from the current operand stack; it constructs a new frame with snapshots of the closure's captured scopes plus a parameter scope containing the actual arguments. The caller's frame remains untouched on the call stack, retaining its instruction pointer and any intermediate operand values. The callee executes independently until `RETURN` removes exactly one value from its stack and places that result on the caller's stack [1].

The key **stack invariant** is that compiler-generated call instructions find exactly k arguments above one function value; every compiled function body leaves one result at `RETURN`, with all local `let` scopes balanced. Each independent activation record preserves its own operand stack, so nested calls cannot accidentally consume the caller's temporary values. The virtual machine uses an **explicit Python list of frames** rather than recursive Python calls to run bytecode. This makes the boundary between program-language calls and the implementation language's call stack observable.

## Worked higher-order example

A function may both accept another function and return one. For example, `fn(f:Fn(Int)->Int,n:Int)->Int=>f(f(n))` accepts a function that transforms an integer into an integer and applies it twice. The type is `Fn(Fn(Int)->Int,Int)->Int`. No special callback syntax is necessary: the callee is an ordinary expression evaluated to a function value.

Alternatively, the curried function `fn(x:Int)->Fn(Int)->Int=>fn(y:Int)->Int=>x+y` returns a closure of type `Fn(Int)->Int`. Calling it with 3 produces a function that adds 3, so calling that result with 4 returns 7. Its x is captured from the outer activation frame; y is supplied by the later call. The compiler creates one body code object for each lambda syntactic occurrence, while each **execution** of `CLOSURE` can create a distinct closure value with distinct captured bindings [2].

~~~python
from fractions import Fraction
from examples.python.typed_function_compiler import (
    compile_functions, run_functions, evaluate_functions, format_type,
    TypeCheckError,
)

scope = ("let x:Int=10 in "
         "let f:Fn(Int)->Int=fn(y:Int)->Int=>x+y in "
         "let x:Int=99 in f(2)")
typ, result = evaluate_functions(scope)
assert format_type(typ) == "Int" and result == Fraction(12)

higher = ("let make:Fn(Int)->Fn(Int)->Int="
          "fn(x:Int)->Fn(Int)->Int=>fn(y:Int)->Int=>x+y in "
          "let plus3:Fn(Int)->Int=make(3) in plus3(4)")
assert run_functions(compile_functions(higher)) == Fraction(7)

twice = ("let twice:Fn(Fn(Int)->Int,Int)->Int="
         "fn(f:Fn(Int)->Int,n:Int)->Int=>f(f(n)) in "
         "let inc:Fn(Int)->Int=fn(x:Int)->Int=>x+1 in twice(inc,4)")
assert evaluate_functions(twice)[1] == Fraction(6)

try:
    compile_functions("fn(x:Int)->Bool=>x+1")
    assert False
except TypeCheckError:
    pass
~~~

This test is executed in both languages against the committed [typed-function compiler](https://github.com/christianrss/manual/blob/main/examples/python/typed_function_compiler.py), not against pseudocode. The source and the oracle do **not** invoke `eval` or `exec` on learner code.

## Independent evidence, cost and resource limits

The [contract tests](https://github.com/christianrss/manual/blob/main/tests/test_typed_function_compiler_contracts.py) evaluate the parsed AST using a **separately written direct interpreter**, with environment tuples captured by an independent closure representation. That oracle does not compile bytecode, use VM frames or share the VM's instruction dispatch. Hand-derived cases cover lexical versus dynamic scope, escaped closures, higher-order application, shadowing and exact rational returns. Seeded generated cases vary bindings and call arguments; negative cases cover missing bindings, duplicate parameters, mismatched annotations, wrong argument counts and nonfunctions. These bounded tests support, but do not mechanically prove, the static and dynamic semantics.

Let n be the number of AST nodes, d the maximum number of nested lexical bindings and s the number of entries in scopes copied during one closure creation. A syntax-directed type checker with dictionary copying may require O(n d) work on deeply nested expressions; this implementation does not claim constant-time scope construction. Runtime `LOAD` may examine O(d) frames of lexical scopes in the worst case. Capturing a closure copies O(s) stored bindings, and calling one copies the captured dictionaries plus its parameters. This trades simplicity and clear semantics for memory and lookup overhead; flat lexical addresses and shared persistent environment structures would be useful later [3]. Rational arithmetic has additional operand-size-dependent bit complexity.

The VM limits execution to **50,000 dispatched instructions by default** and 128 concurrent activation frames, in addition to the existing source/token/depth limits. These are educational safeguards, **not a sandbox or robust denial-of-service isolation**. In particular, large rational intermediate results can consume resources within the instruction budget. The language does not allow recursive `let` functions, looping constructs, assignments, I/O, exceptions as values, threads, mutable captures, general optimization or machine-code generation. A forged bytecode object is not promised type-safe execution; only compiler-generated programs receive the static-checking guarantee.

## Exercises and verification

1. Evaluate the scope example after changing the caller's x to 1,000. **Check:** the function still returns 12, because its closure was captured where x was 10.
2. Type `fn(x:Int)->Rat=>x/2`. **Check:** the function's type is `Fn(Int)->Rat`, and applying it to 3 returns exactly `3/2`.
3. Evaluate `let f:Fn()->Int=fn()->Int=>11 in f()`. **Check:** the arity is zero; `Fn()->Int` is distinct from `Fn(Int)->Int`.
4. Propose a function with a declared Boolean result and an integer body. **Check:** the checker rejects the definition even if the function is never called.
5. Trace caller stack, callee parameter scope and `RETURN` for `f(f(3))`. **Check:** the inner return restores the outer caller's remaining operand stack without reusing the inner frame's locals.
6. Explain why copying an immutable captured environment works here but is insufficient for a language with assignment. **Check:** mutable closure variables would need shared cells or an equivalent environment model.

The next compiler topics—mutable storage, recursive declarations, verified bytecode, lexical address resolution, memory representation and native backends—remain uncovered. Their prerequisites must be derived and tested instead of being inferred from this limited interpreter.
