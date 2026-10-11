"""Opt-in stateful extension of the typed-function compiler.

Use parse_stateful / compile_stateful / evaluate_stateful for mutable cells
and explicitly typed recursive function definitions. The original APIs
compile_functions(...), evaluate_functions(...) remain nonrecursive by default.
"""
from .typed_function_compiler import (
    Cell, Var, SetVar, LetRec, FunctionType, Lambda, Closure,
    TypeCheckError, parse_functions, typecheck_functions,
    compile_functions, run_functions,
)


def parse_stateful(source):
    """Parse var, set and let rec along with the typed function language."""
    return parse_functions(source, stateful=True)


def compile_stateful(source):
    """Typecheck all branches and emit bytecode for shared cells and recursion."""
    return compile_functions(source, stateful=True)


def evaluate_stateful(source, **limits):
    """Return (static type, result) for a stateful source program."""
    program = compile_stateful(source)
    return program.result_type, run_functions(program, **limits)
