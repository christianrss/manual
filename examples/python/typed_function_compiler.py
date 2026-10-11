"""Typed first-class functions, lexical closures and an explicit call-frame VM.

Source-language core: immutable let, typed fn, first-class calls and closures.
Opt-in stateful mode adds var/set and let rec. Earlier lexing and semantics
remain unchanged. No eval/exec, native I/O or unbounded recursion guarantees.
"""
from dataclasses import dataclass, field
from fractions import Fraction

from .expression_compiler import (
    tokenize, Literal, Unary, Binary, CompileError, MAX_DEPTH,
)
from .typed_expression_compiler import (
    Boolean, Name, Let, If, TypeCheckError, PRECEDENCE, TYPES,
)

MAX_STEPS = 50000
MAX_FRAMES = 128


@dataclass(frozen=True)
class FunctionType:
    arguments: tuple
    result: object


@dataclass(frozen=True)
class Lambda:
    parameters: tuple  # tuples of (name, annotation)
    result_annotation: object
    body: object
    start: int
    end: int


@dataclass(frozen=True)
class Call:
    function: object
    arguments: tuple
    start: int
    end: int


@dataclass(frozen=True)
class Var:
    identifier: str
    declared: object
    initializer: object
    body: object
    start: int
    end: int


@dataclass(frozen=True)
class SetVar:
    identifier: str
    expression: object
    start: int
    end: int


@dataclass(frozen=True)
class LetRec:
    identifier: str
    declared: object
    initializer: object
    body: object
    start: int
    end: int


@dataclass(frozen=True)
class Code:
    parameters: tuple
    instructions: tuple


@dataclass(frozen=True)
class Program:
    result_type: object
    code: Code


@dataclass(frozen=True)
class Closure:
    code: Code
    captured: tuple


@dataclass
class Cell:
    """Heap-like shared cell; immutable captures retain object identity."""
    value: object = None
    writable: bool = False
    initialized: bool = False


@dataclass
class _Frame:
    code: Code
    scopes: list
    base_scopes: int
    stack: list = field(default_factory=list)
    ip: int = 0


def format_type(typ):
    if isinstance(typ, FunctionType):
        return ("Fn(" + ",".join(format_type(t) for t in typ.arguments)
                + ")->" + format_type(typ.result))
    return typ


class _Parser:
    def __init__(self, tokens, *, stateful=False):
        self.tokens = tokens
        self.index = 0
        self.stateful = stateful

    def peek(self):
        return self.tokens[self.index]

    def take(self):
        tok = self.peek()
        self.index += 1
        return tok

    def require(self, kind):
        if self.peek().kind != kind:
            raise CompileError("expected " + kind, self.peek().start)
        return self.take()

    def annotation(self, depth=0):
        if depth > MAX_DEPTH:
            raise CompileError("function type nesting limit", self.peek().start)
        tok = self.take()
        if tok.kind in TYPES:
            return tok.kind
        if tok.kind != "Fn":
            raise CompileError("expected type Int, Rat, Bool or Fn", tok.start)
        self.require("(")
        args = []
        if self.peek().kind != ")":
            while True:
                args.append(self.annotation(depth + 1))
                if self.peek().kind != ",":
                    break
                self.take()
        self.require(")")
        self.require("->")
        return FunctionType(tuple(args), self.annotation(depth + 1))

    def expression(self, minimum=0, depth=0):
        if depth > MAX_DEPTH:
            raise CompileError("expression nesting limit", self.peek().start)
        first = self.take()
        if first.kind == "INT":
            node = Literal(int(first.text), first.start, first.end)
        elif first.kind in ("true", "false"):
            node = Boolean(first.kind == "true", first.start, first.end)
        elif first.kind == "IDENT":
            node = Name(first.text, first.start, first.end)
        elif first.kind in ("+", "-"):
            operand = self.expression(30, depth + 1)
            node = Unary(first.kind, operand, first.start, operand.end)
        elif first.kind == "(":
            node = self.expression(0, depth + 1)
            self.require(")")
        elif first.kind == "let":
            recursive = self.stateful and self.peek().kind == "rec"
            if recursive:
                self.take()
            name = self.require("IDENT")
            self.require(":")
            declared = self.annotation(depth + 1)
            self.require("=")
            initializer = self.expression(0, depth + 1)
            self.require("in")
            body = self.expression(0, depth + 1)
            node_type = LetRec if recursive else Let
            node = node_type(name.text, declared, initializer, body,
                             first.start, body.end)
        elif self.stateful and first.kind == "var":
            name = self.require("IDENT")
            self.require(":")
            declared = self.annotation(depth + 1)
            self.require("=")
            initializer = self.expression(0, depth + 1)
            self.require("in")
            body = self.expression(0, depth + 1)
            node = Var(name.text, declared, initializer, body,
                       first.start, body.end)
        elif self.stateful and first.kind == "set":
            name = self.require("IDENT")
            self.require("=")
            expression = self.expression(0, depth + 1)
            node = SetVar(name.text, expression, first.start, expression.end)
        elif first.kind == "if":
            condition = self.expression(0, depth + 1)
            self.require("then")
            yes = self.expression(0, depth + 1)
            self.require("else")
            no = self.expression(0, depth + 1)
            node = If(condition, yes, no, first.start, no.end)
        elif first.kind == "fn":
            self.require("(")
            params = []
            if self.peek().kind != ")":
                while True:
                    name = self.require("IDENT")
                    if name.text in {param for param, _ in params}:
                        raise CompileError("duplicate function parameter", name.start)
                    self.require(":")
                    params.append((name.text, self.annotation(depth + 1)))
                    if self.peek().kind != ",":
                        break
                    self.take()
            self.require(")")
            self.require("->")
            result = self.annotation(depth + 1)
            self.require("=>")
            body = self.expression(0, depth + 1)
            node = Lambda(tuple(params), result, body,
                          first.start, body.end)
        else:
            raise CompileError("expected expression", first.start)

        while True:
            if self.peek().kind == "(" and minimum <= 40:
                self.take()
                arguments = []
                if self.peek().kind != ")":
                    while True:
                        arguments.append(self.expression(0, depth + 1))
                        if self.peek().kind != ",":
                            break
                        self.take()
                close = self.require(")")
                node = Call(node, tuple(arguments), node.start, close.end)
                continue
            op = self.peek()
            power = PRECEDENCE.get(op.kind)
            if power is None or power < minimum:
                break
            self.take()
            right = self.expression(power + 1, depth + 1)
            node = Binary(op.kind, node, right, node.start, right.end)
        return node

    def parse(self):
        node = self.expression()
        if self.peek().kind != "EOF":
            raise CompileError("trailing token", self.peek().start)
        return node


def parse_functions(source, *, stateful=False):
    return _Parser(
        tokenize(source, extended=True, functions=True, stateful=stateful),
        stateful=stateful,
    ).parse()


def typecheck_functions(node):
    """A function's body is checked in its definition-time type environment."""
    def check(n, environment, depth):
        if depth > MAX_DEPTH:
            raise TypeCheckError("AST nesting limit", n.start)
        if isinstance(n, Literal):
            return "Int"
        if isinstance(n, Boolean):
            return "Bool"
        if isinstance(n, Name):
            if n.identifier not in environment:
                raise TypeCheckError("unbound name " + n.identifier, n.start)
            return environment[n.identifier][0]
        if isinstance(n, Unary):
            typ = check(n.operand, environment, depth + 1)
            if typ not in ("Int", "Rat"):
                raise TypeCheckError("unary arithmetic requires a number", n.start)
            return typ
        if isinstance(n, Binary):
            left = check(n.left, environment, depth + 1)
            right = check(n.right, environment, depth + 1)
            if left not in ("Int", "Rat") or right not in ("Int", "Rat"):
                raise TypeCheckError("binary operation requires numbers", n.start)
            if n.op == "<":
                return "Bool"
            if n.op == "/":
                return "Rat"
            return "Rat" if "Rat" in (left, right) else "Int"
        if isinstance(n, If):
            cond = check(n.condition, environment, depth + 1)
            yes = check(n.yes, environment, depth + 1)
            no = check(n.no, environment, depth + 1)
            if cond != "Bool":
                raise TypeCheckError("if requires Bool condition", n.start)
            if yes != no:
                raise TypeCheckError("if branches must have equal types", n.start)
            return yes
        if isinstance(n, (Let, Var)):
            actual = check(n.initializer, environment, depth + 1)
            if actual != n.declared:
                raise TypeCheckError("binding annotation mismatch", n.start)
            inner = dict(environment)
            inner[n.identifier] = (actual, isinstance(n, Var))
            return check(n.body, inner, depth + 1)
        if isinstance(n, LetRec):
            if not isinstance(n.declared, FunctionType) or not isinstance(n.initializer, Lambda):
                raise TypeCheckError("let rec requires an annotated function literal", n.start)
            inner = dict(environment)
            inner[n.identifier] = (n.declared, False)
            actual = check(n.initializer, inner, depth + 1)
            if actual != n.declared:
                raise TypeCheckError("recursive function type mismatch", n.start)
            return check(n.body, inner, depth + 1)
        if isinstance(n, SetVar):
            binding = environment.get(n.identifier)
            if binding is None:
                raise TypeCheckError("unbound assignment target", n.start)
            if not binding[1]:
                raise TypeCheckError("assignment to immutable binding", n.start)
            actual = check(n.expression, environment, depth + 1)
            if actual != binding[0]:
                raise TypeCheckError("assignment type mismatch", n.start)
            return actual
        if isinstance(n, Lambda):
            inner = dict(environment)
            for name, typ in n.parameters:
                inner[name] = (typ, False)
            inferred = check(n.body, inner, depth + 1)
            if inferred != n.result_annotation:
                raise TypeCheckError("function return type mismatch", n.start)
            return FunctionType(tuple(t for _, t in n.parameters), inferred)
        if isinstance(n, Call):
            callee = check(n.function, environment, depth + 1)
            args = tuple(check(a, environment, depth + 1)
                         for a in n.arguments)
            if not isinstance(callee, FunctionType):
                raise TypeCheckError("call target is not a function", n.start)
            if len(args) != len(callee.arguments):
                raise TypeCheckError("wrong number of arguments", n.start)
            if args != callee.arguments:
                raise TypeCheckError("argument type mismatch", n.start)
            return callee.result
        raise TypeCheckError("unsupported AST node", getattr(n, "start", 0))

    return check(node, {}, 0)


def compile_functions(source, *, stateful=False):
    root = parse_functions(source, stateful=stateful)
    result_type = typecheck_functions(root)

    def compile_code(expression, parameters=()):
        instructions = []

        def emit(op, arg=None, pos=0):
            instructions.append((op, arg, pos))
            return len(instructions) - 1

        def generate(node):
            if isinstance(node, Literal):
                emit("PUSH_INT", node.value, node.start)
            elif isinstance(node, Boolean):
                emit("PUSH_BOOL", node.value, node.start)
            elif isinstance(node, Name):
                emit("LOAD", node.identifier, node.start)
            elif isinstance(node, Unary):
                generate(node.operand)
                emit("NEG" if node.op == "-" else "POS", None, node.start)
            elif isinstance(node, Binary):
                generate(node.left)
                generate(node.right)
                emit({"+": "ADD", "-": "SUB", "*": "MUL",
                      "/": "DIV", "<": "LT"}[node.op], None, node.start)
            elif isinstance(node, (Let, Var)):
                generate(node.initializer)
                emit("ENTER", None, node.start)
                emit("BIND_VAR" if isinstance(node, Var) else "BIND",
                     node.identifier, node.start)
                generate(node.body)
                emit("LEAVE", None, node.end)
            elif isinstance(node, LetRec):
                emit("ENTER", None, node.start)
                emit("DECLARE_REC", node.identifier, node.start)
                generate(node.initializer)
                emit("INIT_REC", node.identifier, node.start)
                generate(node.body)
                emit("LEAVE", None, node.end)
            elif isinstance(node, SetVar):
                generate(node.expression)
                emit("STORE", node.identifier, node.start)
            elif isinstance(node, If):
                generate(node.condition)
                branch = emit("JUMP_IF_FALSE", None, node.start)
                generate(node.yes)
                jump = emit("JUMP", None, node.start)
                instructions[branch] = ("JUMP_IF_FALSE", len(instructions), node.start)
                generate(node.no)
                instructions[jump] = ("JUMP", len(instructions), node.start)
            elif isinstance(node, Lambda):
                body = compile_code(node.body,
                                    tuple(name for name, _ in node.parameters))
                emit("CLOSURE", body, node.start)
            elif isinstance(node, Call):
                generate(node.function)
                for arg in node.arguments:
                    generate(arg)
                emit("CALL", len(node.arguments), node.start)
            else:
                raise AssertionError("unhandled checked AST")

        generate(expression)
        emit("RETURN", None, expression.end)
        return Code(parameters, tuple(instructions))

    return Program(result_type, compile_code(root))


def run_functions(program, *, max_steps=MAX_STEPS, max_frames=MAX_FRAMES):
    """Execute compiled code with isolated operand stacks and lexical frames."""
    if not isinstance(program, Program):
        raise TypeError("expected compiled Program")
    if type(max_steps) is not int or max_steps < 1:
        raise ValueError("max_steps must be positive")
    if type(max_frames) is not int or max_frames < 1:
        raise ValueError("max_frames must be positive")
    calls = [_Frame(program.code, [{}], 1)]
    steps = 0
    while calls:
        steps += 1
        if steps > max_steps:
            raise RuntimeError("VM step limit exceeded")
        frame = calls[-1]
        if frame.ip >= len(frame.code.instructions):
            raise ValueError("invalid bytecode: missing RETURN")
        op, arg, offset = frame.code.instructions[frame.ip]
        frame.ip += 1
        stack = frame.stack
        if op == "PUSH_INT":
            stack.append(Fraction(arg))
        elif op == "PUSH_BOOL":
            stack.append(arg)
        elif op == "LOAD":
            for scope in reversed(frame.scopes):
                if arg in scope:
                    found = scope[arg]
                    if isinstance(found, Cell):
                        if not found.initialized:
                            raise ValueError("invalid bytecode: uninitialized cell")
                        stack.append(found.value)
                    else:
                        stack.append(found)
                    break
            else:
                raise ValueError("invalid bytecode: missing binding")
        elif op == "ENTER":
            frame.scopes.append({})
        elif op in ("BIND", "BIND_VAR"):
            if not stack or arg in frame.scopes[-1]:
                raise ValueError("invalid bytecode: binding failure")
            value = stack.pop()
            frame.scopes[-1][arg] = (Cell(value, True, True)
                                      if op == "BIND_VAR" else value)
        elif op == "DECLARE_REC":
            if arg in frame.scopes[-1]:
                raise ValueError("invalid bytecode: duplicate recursive binding")
            frame.scopes[-1][arg] = Cell(None, False, False)
        elif op == "INIT_REC":
            target = frame.scopes[-1].get(arg)
            if not stack or not isinstance(target, Cell) or target.initialized:
                raise ValueError("invalid bytecode: recursive initialization")
            value = stack.pop()
            if not isinstance(value, Closure):
                raise ValueError("invalid bytecode: recursive initializer")
            target.value = value
            target.initialized = True
        elif op == "STORE":
            if not stack:
                raise ValueError("invalid bytecode: assignment underflow")
            for scope in reversed(frame.scopes):
                if arg in scope:
                    cell = scope[arg]
                    if not isinstance(cell, Cell) or not cell.writable or not cell.initialized:
                        raise ValueError("invalid bytecode: immutable assignment")
                    cell.value = stack[-1]  # assignment is an expression
                    break
            else:
                raise ValueError("invalid bytecode: unknown assignment target")
        elif op == "LEAVE":
            if len(frame.scopes) <= frame.base_scopes:
                raise ValueError("invalid bytecode: scope underflow")
            frame.scopes.pop()
        elif op == "CLOSURE":
            if not isinstance(arg, Code):
                raise ValueError("invalid bytecode: invalid function body")
            stack.append(Closure(arg, tuple(dict(s) for s in frame.scopes)))
        elif op == "CALL":
            if type(arg) is not int or arg < 0 or len(stack) < arg + 1:
                raise ValueError("invalid bytecode: call underflow")
            args = [stack.pop() for _ in range(arg)][::-1]
            function = stack.pop()
            if not isinstance(function, Closure) or len(function.code.parameters) != arg:
                raise ValueError("invalid bytecode: call target or arity")
            if len(calls) >= max_frames:
                raise RuntimeError("VM call-frame limit exceeded")
            nested_scopes = [dict(s) for s in function.captured]
            nested_scopes.append(dict(zip(function.code.parameters, args)))
            calls.append(_Frame(function.code, nested_scopes, len(nested_scopes)))
        elif op == "RETURN":
            if len(frame.scopes) != frame.base_scopes or len(stack) != 1:
                raise ValueError("invalid bytecode: invalid return state")
            result = stack.pop()
            calls.pop()
            if calls:
                calls[-1].stack.append(result)
            else:
                return result
        elif op in ("NEG", "POS"):
            if not stack:
                raise ValueError("invalid bytecode: unary underflow")
            x = stack.pop()
            stack.append(-x if op == "NEG" else x)
        elif op == "JUMP_IF_FALSE":
            if not stack:
                raise ValueError("invalid bytecode: branch underflow")
            cond = stack.pop()
            if type(cond) is not bool:
                raise ValueError("invalid bytecode: nonboolean condition")
            if not cond:
                if type(arg) is not int or not 0 <= arg < len(frame.code.instructions):
                    raise ValueError("invalid bytecode: jump target")
                frame.ip = arg
        elif op == "JUMP":
            if type(arg) is not int or not 0 <= arg < len(frame.code.instructions):
                raise ValueError("invalid bytecode: jump target")
            frame.ip = arg
        elif op in ("ADD", "SUB", "MUL", "DIV", "LT"):
            if len(stack) < 2:
                raise ValueError("invalid bytecode: binary underflow")
            b = stack.pop()
            a = stack.pop()
            if op == "ADD":
                stack.append(a + b)
            elif op == "SUB":
                stack.append(a - b)
            elif op == "MUL":
                stack.append(a * b)
            elif op == "LT":
                stack.append(a < b)
            else:
                if b == 0:
                    raise ZeroDivisionError(f"division by zero at offset {offset}")
                stack.append(a / b)
        else:
            raise ValueError("invalid bytecode: unknown opcode")
    raise ValueError("invalid bytecode: no result")


def evaluate_functions(source, *, stateful=False, **limits):
    program = compile_functions(source, stateful=stateful)
    return program.result_type, run_functions(program, **limits)


if __name__ == "__main__":
    cases = (
        ("let add: Fn(Int,Int)->Int = fn(x:Int,y:Int)->Int => x+y in add(2,3)", 5),
        ("let x:Int=10 in let f:Fn(Int)->Int=fn(y:Int)->Int=>x+y in "
         "let x:Int=99 in f(2)", 12),
        ("let make:Fn(Int)->Fn(Int)->Int=fn(x:Int)->Fn(Int)->Int=>"
         "fn(y:Int)->Int=>x+y in let f:Fn(Int)->Int=make(3) in f(4)", 7),
    )
    for source, answer in cases:
        assert run_functions(compile_functions(source)) == Fraction(answer)
