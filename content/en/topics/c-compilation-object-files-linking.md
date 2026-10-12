---
id: c-compilation-object-files-linking
title: "From C source to executable: preprocessing, object files and linking"
description: "Compile multi-file C11, understand translation units, object symbols, linking failures and loader boundaries."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [c-pointers-arrays-object-lifetimes, modular-programming-interfaces]
sources:
  - {title: "GCC — Options Controlling the Kind of Output", url: "https://gcc.gnu.org/onlinedocs/gcc/Overall-Options.html", kind: "official compiler documentation"}
  - {title: "GCC — Link Options", url: "https://gcc.gnu.org/onlinedocs/gcc/Link-Options.html", kind: "official compiler documentation"}
  - {title: "GNU ld — Linker documentation", url: "https://sourceware.org/binutils/docs/ld/", kind: "official linker documentation"}
---
A program can compile successfully as an individual C file but fail to produce an executable when a second implementation file is absent. The explanation requires separating **source code, declarations, translation units, object files, symbol resolution, linking and execution**. These phases have different inputs and errors. A compiler does not automatically provide the implementation of every function whose declaration it recognizes. GCC documents which stages can be stopped independently [1][2].

## Source files and translation units

A translation unit is the source delivered to a C compiler after preprocessing. A source file and the header contents it includes generally form one translation unit. Another source file is compiled as a distinct unit. Units can share compatible declarations and subsequently contribute definitions to one program.

A declaration supplies the name and type of a function. Its definition supplies the body. A caller can be compiled using a correct declaration even if the implementation has not yet been compiled, because the object file can retain an external reference for the linker. This is useful for modular programs but requires an explicit contract between producer and consumer.

A header is source text rather than a compiled binary library. Placing every non-inline external function definition in a header included by multiple source files can cause conflicting definitions. The example keeps the declaration in a guarded header and the function body in exactly one implementation source file.

## Preprocessing and translation

The preprocessor handles include directives and conditional compilation before ordinary compilation. An include directive with a quoted header name copies its relevant tokens into the translation unit; include guards prevent repeated inclusion inside that unit. A guard is not a runtime condition, nor does it prevent another source file from including the same header.

Macros are token substitutions and can repeat the evaluation of an expression passed as a parameter. They are not interchangeable with typed functions. Prefer a real function when it supplies clearer type checking and a single evaluation of its arguments.

With a GCC-compatible compiler, the -E flag stops after preprocessing, so its output remains C text rather than machine instructions. The -S flag stops after compilation proper, commonly producing target-specific assembly source. The -c flag compiles and assembles as required, but does not invoke the final link. The exact emitted assembly depends on compiler, optimization and architecture [1].

## Object files and symbols

An object file commonly contains machine instructions, data, symbols and relocation records. A function call may refer to a symbol defined in another object. The object file need not contain a complete entry path or the final address of every referenced function. A linker resolves compatible references and arranges sections in the output program [2][3].

The externally visible name double_small appears as a declaration in the caller's translation unit. Its body occurs in the implementation's translation unit. Neither object is the entire application by itself. During linking, the caller's unresolved reference is matched with the implementation definition.

An ABI determines binary interface details such as calling conventions, register use, data layout and symbol naming. Combining objects compiled for incompatible targets is not made valid by giving them matching filenames. Do not assume that a particular object suffix or executable format is universal to Windows, Unix and embedded platforms.

## Worked example: interface, implementation and caller

The program's contract accepts integer input from -10000 through 10000 and an output pointer referring to a writable integer. On success, it writes twice the input and returns 1. Invalid numeric input or a null output pointer produces failure 0 without changing the caller's stored result. The resulting magnitude is at most 20000, which fits the minimum range guaranteed for C int.

~~~c
// file: math_ops.h
#ifndef MATH_OPS_H
#define MATH_OPS_H

/* On success, store twice the value and return 1.
   Reject inputs outside [-10000, 10000] or null output. */
int double_small(int value, int *out);

#endif
~~~

~~~c
// file: math_ops.c
#include "math_ops.h"
#include <stddef.h>

int double_small(int value, int *out) {
    if (out == NULL || value < -10000 || value > 10000)
        return 0;
    *out = value * 2;
    return 1;
}
~~~

~~~c
// file: main.c
#include "math_ops.h"
#include <stdio.h>

int main(void) {
    int result = -1;
    if (!double_small(21, &result))
        return 1;
    printf("result=%d\n", result);
    return 0;
}
~~~

Compile and link using a POSIX-like shell and a C11 GCC-compatible toolchain:

~~~sh
cc -std=c11 -Wall -Wextra -Werror -pedantic -c math_ops.c -o math_ops.o
cc -std=c11 -Wall -Wextra -Werror -pedantic -c main.c -o main.o
cc main.o math_ops.o -o demo
./demo
# result=42
~~~

The explicit pointer requirement matters: a non-null but invalid pointer is not made safe by a null check. The function's success contract assumes its caller supplies valid storage.

## Why missing definitions fail at link time

If math_ops.o is omitted, compiling main.c still succeeds because the compiler knows the declaration. Attempting to link the main object alone must fail because the function definition is missing. The diagnostic wording varies with the linker. Conversely, supplying multiple incompatible external definitions may cause duplicate-definition diagnostics.

Object linking is not file concatenation. Resolved symbols, relocated references, section layout and libraries all influence the final result. A static archive typically stores object files, whereas a shared library can be resolved through mechanisms involving a dynamic linker at runtime. The precise rules depend on the platform and linker [2][3].

A valid interface declaration does not prove that the implementation honors the intended semantics. The compiler may validate types without proving numeric limits or application correctness. This is why separate behavioral tests remain necessary even when the linker accepts the program.

## Linking, loading and process startup

A successful link produces an executable artifact; it does not launch it. The host operating system must still recognize the executable format and arrange the resources for execution. Hosted systems commonly use runtime startup machinery that eventually invokes the C main function. The low-level entry point need not literally be main.

A target CPU mismatch, absent dynamic library, missing permission or incompatible runtime can prevent a valid binary from executing. Those failures arise after successful compilation. The subsequent chapter explains the process interface that supplies arguments, environment, streams and exit status.

## Rebuilds, verification and complexity

The independent integration test should compile each translation unit, link both objects and check the program prints result=42 with a successful exit. It should also deliberately omit the implementation object and require that the link fail. These two observations distinguish successful compilation from successful symbol resolution.

After changing an implementation without changing the header, a build may need only that implementation recompiled and the output relinked. Changing an included header can require recompiling every dependent translation unit. Build systems automate this dependency accounting, but do not redefine what a translation unit means.

There is no universal O(S) time bound for a full optimizing compiler given source size S: macro expansion, parsing, transformations and optimization strategies affect the work. The meaningful first cost comparison is how many affected units must be rebuilt and linked.

## Exercises and verification

1. Identify which stage handles include directives and which resolves the double_small symbol.
2. Compare preprocessor (-E), assembly (-S) and object (-c) outputs for the same input [1].
3. Link the caller object alone and explain the unresolved symbol.
4. Introduce a definition inconsistent with its own header and observe the compiler error.
5. Add a duplicate external definition and explain why linking is invalid.
6. Distinguish successful linking from successful process execution on another machine.

Continue with [C pointer contracts](/en/topics/c-pointers-arrays-object-lifetimes/), [modular programming](/en/topics/modular-programming-interfaces/) and [process interfaces](/en/topics/process-cli-arguments-environment-exit-status/).