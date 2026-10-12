---
id: build-dependency-graphs-gnu-make
title: "Build fundamentals: dependency graphs, incremental compilation and GNU Make"
description: "Derive a build DAG and test C11 recompilation rules with header dependencies, phony targets and failure propagation."
category: engineering
difficulty: foundational
updated: 2026-10-12
prerequisites: [git-version-control-commits-branches, c-compilation-object-files-linking]
sources:
  - {title: "GNU make — What a Rule Looks Like", url: "https://www.gnu.org/software/make/manual/html_node/Rule-Introduction.html", kind: "official build tool manual"}
  - {title: "GNU make — Rules and prerequisites", url: "https://www.gnu.org/software/make/manual/html_node/Rules.html", kind: "official build tool manual"}
  - {title: "GNU make — Automatic Variables", url: "https://www.gnu.org/software/make/manual/html_node/Automatic-Variables.html", kind: "official build tool manual"}
  - {title: "GNU make — Phony Targets", url: "https://www.gnu.org/software/make/manual/html_node/Phony-Targets.html", kind: "official build tool manual"}
---
Compiling a two-file C program manually is simple until one header changes and developers must decide which object files require rebuilding. A **build system** records that decision as dependencies between source files, intermediate outputs and the final executable. Its primary responsibility is not to hide compiler commands but to make repeated builds correct, incremental and reproducible under stated assumptions. GNU Make describes this with targets, prerequisites and recipes [1][2].

## Start with the dependency graph

Treat each generated file as a node in a directed dependency graph. In the example, the final executable demo depends on main.o and math_ops.o. The object main.o depends on main.c and math_ops.h; math_ops.o depends on math_ops.c and math_ops.h. An arrow from target to prerequisite means the target can be considered for rebuilding after its prerequisite changes.

A dependency is a **semantic claim**: the target's contents depend on that input. Merely listing compiler arguments is insufficient if a changed included header is omitted from a rule. After changing math_ops.h, both objects must be rebuilt, not only the implementation object. This is why a build graph complements, rather than replaces, the C translation-unit model.

When dependency edges do not form cycles, the build can schedule independent object compilations in parallel and link only after both finish. A topological order of the graph respects these constraints. Cycles among generated targets can prevent meaningful scheduling unless the tool supports a special explicit mechanism.

## Targets, prerequisites and recipes

A Make rule has a target on the left, prerequisites after a colon and a recipe specifying how to produce the target. For ordinary file targets, Make compares modification times: a missing target or a prerequisite newer than its target normally means the target needs rebuilding [1][2].

The recipe lines in the sample start with an actual TAB character. Ordinary spaces are not interchangeable with the expected recipe prefix in a conventional Makefile. Make invokes a shell for command execution, and a command returning a failure status normally causes the target and dependent build to fail instead of treating it as a successful artifact.

A rule expresses both *when* to rebuild and *how* to build. If only the recipe changes while all file timestamps remain unchanged, the simple timestamp model may not detect that the executable should be rebuilt. This limitation matters when changing compiler flags, selected tools or environment-dependent behavior.

## Build two translation units

The following program uses a shared header and a small bounded function. A valid input in [-100,100] is doubled into the provided output location. The output pointer must designate a writable integer; NULL or an out-of-range value causes failure without modifying the output. Multiplication cannot overflow a C int within that interval.

~~~c
// file: math_ops.h
#ifndef MATH_OPS_H
#define MATH_OPS_H
int twice_bounded(int value, int *result);
#endif
~~~

~~~c
// file: math_ops.c
#include "math_ops.h"
#include <stddef.h>
int twice_bounded(int value, int *result) {
    if (!result || value < -100 || value > 100)
        return 0;
    *result = value * 2;
    return 1;
}
~~~

~~~c
// file: main.c
#include "math_ops.h"
#include <stdio.h>
int main(void) {
    int result = 0;
    if (!twice_bounded(21, &result))
        return 1;
    printf("answer=%d\n", result);
    return 0;
}
~~~

~~~make
# file: Makefile
CC = cc
CFLAGS = -std=c11 -Wall -Wextra -Werror -pedantic
.PHONY: all check clean

all: demo

demo: main.o math_ops.o
	$(CC) $(CFLAGS) $^ -o $@

main.o: main.c math_ops.h
	$(CC) $(CFLAGS) -c $< -o $@

math_ops.o: math_ops.c math_ops.h
	$(CC) $(CFLAGS) -c $< -o $@

check: demo
	./demo

clean:
	rm -f demo main.o math_ops.o
~~~

Within a directory containing these four files, running make builds both objects and the executable. Running make check then builds any outdated inputs and executes the program; the expected stdout is answer=42. Running make clean removes generated files but does not touch the source code.

The compile rules explicitly name the header because both source units include it. Omitting this dependency is a **reproducible stale-build defect**: a header change may not trigger compilation, potentially producing inconsistent declarations or binaries until a clean rebuild happens.

## Automatic variables and reuse

The automatic variable $@ is the target's filename; $< is its first prerequisite; $^ lists all normal prerequisites without duplicates [3]. For main.o, the command expands to compile main.c into main.o. For demo, $^ expands to main.o math_ops.o, which are supplied to the final link command.

These symbols have meaning within a rule recipe and should not be interpreted as shell variables with the same syntax. Make performs its own expansion before giving a recipe to the shell. Mixing Make expansion and shell expansion is a common reason for incorrect recipes.

The small sample repeats CFLAGS intentionally so every compile stage uses the same options. Real projects may separate compile flags from link flags and libraries; those are implementation improvements, not a reason to obscure the basic graph.

## Phony tasks versus generated files

An ordinary target such as demo represents a file. The target check instead represents an action that should run when requested, even if a real file named check happens to exist. Declaring check, clean and all as .PHONY makes this intent explicit [4].

The dependency check: demo still ensures the executable exists before the test command runs. It does not prove that a program's output is correct: a recipe that runs ./demo checks the exit code, while checking the exact stdout needs an additional assertion or external test.

A clean target must not be a prerequisite of the default build, because rebuilding after every clean would defeat incrementality. Similarly, checking tests on every source edit may be desirable as a workflow policy, but is separate from the dependency graph required to create object files.

## Derive incremental rebuild expectations

On the first build all generated targets are absent, so both object compilation recipes and the linker recipe run. Without edits, a second make demo should find the generated files up to date and skip those recipes. If only main.c becomes newer, main.o and then demo need rebuilding; math_ops.o does not. If the common math_ops.h becomes newer, both objects and demo need rebuilding.

These claims follow from the dependency graph and the timestamp model, not from empirical guesses. A good test uses an isolated temporary directory, records the build, checks a subsequent dry run reports no compilation, then changes the header's modification time and inspects the planned recompilation of both objects. It should finally execute the rebuilt program and confirm the expected result.

Modification timestamps are not always a perfect representation of dependency changes. Filesystem timestamp resolution, clock skew and deliberately preserved timestamps can defeat a simplistic freshness comparison. Build caches that use content hashes operate under different rules; this chapter specifically explains the GNU Make timestamp model [2].

## Complexity and failure boundaries

Let V denote target nodes and E dependency edges. Traversing a well-formed dependency graph can be analyzed relative to V+E, but full build time also includes preprocessing, compilation, linking and I/O costs. It is misleading to call a complete build O(V+E) regardless of input size or compiler work.

Parallel jobs can reduce wall-clock time when tasks are independent, but must preserve prerequisite ordering. Explicit artifacts from independent recipes should not accidentally share an output file. Concurrent recipes that mutate the same temporary file can introduce races outside the graph's declared dependencies.

Compiler success does not guarantee that tests pass, and test success does not guarantee that a package is portable to another architecture. Tools, system libraries, compiler versions and environmental inputs affect outputs. For stronger repeatability, record tool versions, flags and declared inputs rather than saying every Make run produces byte-identical binaries.

## Exercises and verification

1. Draw the dependency graph and list which targets must rebuild after changing main.c alone.
2. Explain why changing math_ops.h requires recompiling both object files.
3. Predict the outcome when math_ops.o is missing during a link, even though main.o exists.
4. Explain $@, $< and $^ in one of the supplied recipes [3].
5. Create an ordinary file named check and explain why .PHONY still runs the test [4].
6. Compare make demo twice without modifications; distinguish build freshness from passing an independent behavioral test.

Continue with [compilation and linking](/en/topics/c-compilation-object-files-linking/), [Git history and branches](/en/topics/git-version-control-commits-branches/) and [CI/CD and release engineering](/en/topics/ci-cd-release-engineering/).