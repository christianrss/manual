---
id: process-cli-arguments-environment-exit-status
title: "How programs run: command-line arguments, environment, streams and exit status"
description: "Trace a program invocation using C11 arguments, environment variables, stdout, stderr and subprocess tests."
category: operating-systems
difficulty: foundational
updated: 2026-10-12
prerequisites: [c-compilation-object-files-linking, c-pointers-arrays-object-lifetimes]
sources:
  - {title: "POSIX.1-2024 — exec functions", url: "https://pubs.opengroup.org/onlinepubs/9799919799/functions/exec.html", kind: "official POSIX standard"}
  - {title: "POSIX.1-2024 — Environment variables", url: "https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap08.html", kind: "official POSIX standard"}
  - {title: "POSIX.1-2024 — Process termination", url: "https://pubs.opengroup.org/onlinepubs/9799919799/functions/_exit.html", kind: "official POSIX standard"}
---
An executable on disk is not a running process. Launching a program supplies more than machine instructions: it also establishes an **argument vector, environmental configuration, input/output streams and termination status**. These contracts are essential for shell commands, build tools, test runners and development environments. Distinguishing what the process receives at startup from what it computes afterward is the first step toward understanding the operating system interface [1][2].

## The executable and the process are separate

Compiling and linking create an executable artifact. On a compatible host, a process-launching mechanism arranges an execution image and the resources associated with it. Under POSIX, an exec-family call replaces the image of the *existing calling process*; it does not create another process ID. A separate creation operation, such as fork or an appropriate spawning API, is needed for a new process [1].

The C main function is an entry at the language level. Runtime startup work can occur before main runs, so the low-level executable entry is not necessarily the function named main. A valid executable file can still be impossible to launch because of permissions, missing dependencies or incompatible instruction architecture.

## Arguments arrive as text

The parameters argc and argv describe a count and an array of argument strings. For one supplied operand, argc is normally 2: the invocation-name entry argv[0] and the operand argv[1]. The invocation name is not necessarily a trusted absolute path and must not be used to authorize access [1].

The argument 42 arrives as characters, not as a validated integer. A correct parser checks not only the numeric conversion, but also that input is not empty, the whole string was consumed and no overflow was reported. Accepting the prefix of 12garbage as 12 violates a strict integer contract. The example permits exactly one decimal integer in the inclusive interval from 0 to 100.

Shell quoting, wildcard expansion and variable substitution happen in the invoking shell. Programs can also be started directly by other applications without a shell. Therefore, an API must define its argument contract independently of what someone happens to type in a terminal.

## Environment variables are another input

The environment provides named string values to the program when it starts [2]. Standard C getenv can retrieve the value of a named entry, or return a null pointer when it does not exist. The sample recognizes MANUAL_EXAMPLE_MODE=verbose and ignores all other values for that variable.

Environment variables support configuration, but do not establish authentication. A parent process or user can often control them. Changing an environment in one process does not automatically change the environment that an already-running child received at launch. Tests must therefore construct a controlled child environment rather than accidentally inheriting a developer's settings.

Some environment values are sensitive. This teaching program compares one predefined value rather than printing arbitrary environment contents. Do not treat the presence of an environment variable as proof of identity, permissions or the safe handling of secrets.

## Stdout and stderr have different responsibilities

Stdout carries the intended machine-readable result, while stderr conventionally carries usage information and diagnostics. They are distinct streams even when the terminal presents them together. A parent process can capture and assert each one independently.

For a valid argument 42, the example writes next=43 on stdout. Missing arguments produce a usage message on stderr and no normal result. An invalid number writes a separate error. Optional verbose mode adds a diagnostic on stderr while leaving stdout unchanged. This division lets scripts consume the result without parsing diagnostic text.

stdio is buffered. Merging streams into one destination does not automatically preserve a simple total order inferred from the program's source statements. When exact ordering matters, the program needs an explicit protocol or synchronization rather than assuming immediate writes.

## Exit status is an observable contract

A hosted C program returning zero from main reports success. Nonzero values report failure, with meanings selected by the program. The example chooses return code 2 for incorrect argument count, code 3 for invalid numeric input, and code 0 for success. A parent can use these to decide whether the command completed normally.

POSIX process interfaces distinguish normal exit codes from termination by signals. Only the low eight bits of an ordinary exit status are exposed by some wait interfaces, while other interfaces may expose richer information [3]. Test libraries often normalize these details. An automation should check both the chosen status and expected output, not infer success from nonempty stdout alone.

## A bounded, executable C11 example

The code parses a decimal integer with strtol, validates the complete token, checks errno for conversion errors and enforces the interval [0,100]. It prints the successor and optionally a verbose diagnostic. It never constructs a shell command from the argument, and it never uses an unvalidated number as an index or memory length.

~~~c
// file: cli.c
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "usage: cli NUMBER\n");
        return 2;
    }
    char *end = NULL;
    errno = 0;
    long number = strtol(argv[1], &end, 10);
    if (errno != 0 || end == argv[1] || *end != '\0'
            || number < 0 || number > 100) {
        fprintf(stderr, "invalid NUMBER\n");
        return 3;
    }
    const char *mode = getenv("MANUAL_EXAMPLE_MODE");
    if (mode != NULL && strcmp(mode, "verbose") == 0)
        fprintf(stderr, "mode=verbose\n");
    printf("next=%ld\n", number + 1);
    return 0;
}
~~~

This program does not read stdin. Adding streamed input would require a separate contract about how records are delimited, how errors propagate and when the consumer decides the input is complete.

## Test the program from outside the process

A black-box test should compile the C program and launch it with a list of arguments, capture stdout and stderr separately, and check the return code. With argument 42 and no verbose setting, expect exactly next=43, no stderr output and status zero. With 101, expect invalid NUMBER on stderr and status 3, without stdout.

The test should also cover an empty argument, an extra argument, negative values, numeric suffixes and very large integers that strtol cannot represent. A controlled environment setting of verbose must yield an additional stderr diagnostic without changing stdout or success status.

A launch itself may fail before the program starts. Such a failure is distinct from the process executing and returning a nonzero status. A reliable test harness distinguishes both outcomes instead of conflating them into one generic command failure.

## Portability, limits and verification

The C language defines argument parsing and streams, while POSIX defines particular process-execution and wait conventions. Systems without POSIX can use different process and status APIs. The example does not claim that every system has fork, shell pipes, ELF binaries or identical Unicode handling for process arguments.

Checking the exit status and the two streams establishes this *local process contract* for observed inputs. It does not prove the absence of every implementation bug or a security property for arbitrary environment contents.

## Exercises and verification

1. Explain the difference between the executable file, the running process and the main function.
2. Predict the result, diagnostics and return code for 42, -1, 101, empty text and two operands.
3. Show why parsing a numeric prefix without checking the end pointer violates the contract.
4. Verify that verbose mode leaves the stdout result unchanged.
5. Explain why nonzero exit status and signal termination cannot always be interpreted as the same event.
6. Distinguish replacing a process image with exec from creating a separate process [1].

Continue with [the C compiler and linker](/en/topics/c-compilation-object-files-linking/), [file descriptors](/en/topics/file-descriptors-buffering-fsync/) and [process memory](/en/topics/processes-virtual-memory/).