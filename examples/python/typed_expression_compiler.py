"""Typed expression language layered on the published arithmetic compiler.

Grammar extensions: let name: Type = expression in expression;
if expression then expression else expression; true/false; named references;
numeric '<'. Lexical scopes have immutable, annotated bindings.

Static typecheck precedes all bytecode generation/execution. This is a finite
educational language, not a sandbox or production bytecode verifier.
"""
from dataclasses import dataclass
from fractions import Fraction

from .expression_compiler import (
    tokenize, Literal, Unary, Binary, CompileError, MAX_DEPTH,
    BINARY_PRECEDENCE,
)

TYPES = frozenset(("Int", "Rat", "Bool"))
PRECEDENCE = {"<": 5, **BINARY_PRECEDENCE}


class TypeCheckError(CompileError):
    """Static type/scope error with a character offset."""


@dataclass(frozen=True)
class Boolean:
    value: bool
    start: int
    end: int


@dataclass(frozen=True)
class Name:
    identifier: str
    start: int
    end: int


@dataclass(frozen=True)
class Let:
    identifier: str
    declared: str
    initializer: object
    body: object
    start: int
    end: int


@dataclass(frozen=True)
class If:
    condition: object
    yes: object
    no: object
    start: int
    end: int


@dataclass(frozen=True)
class TypedProgram:
    result_type: str
    instructions: tuple


class _TypedParser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0

    def peek(self):
        return self.tokens[self.index]

    def take(self):
        token = self.peek()
        self.index += 1
        return token

    def require(self, kind):
        token = self.peek()
        if token.kind != kind:
            raise CompileError("expected " + kind, token.start)
        return self.take()

    def expression(self, minimum=0, depth=0):
        if depth > MAX_DEPTH:
            raise CompileError("expression nesting too deep", self.peek().start)
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
            name = self.require("IDENT")
            self.require(":")
            declared = self.take()
            if declared.kind not in TYPES:
                raise CompileError("expected Int, Rat or Bool", declared.start)
            self.require("=")
            initializer = self.expression(0, depth + 1)
            self.require("in")
            body = self.expression(0, depth + 1)
            node = Let(name.text, declared.kind, initializer, body,
                       first.start, body.end)
        elif first.kind == "if":
            condition = self.expression(0, depth + 1)
            self.require("then")
            yes = self.expression(0, depth + 1)
            self.require("else")
            no = self.expression(0, depth + 1)
            node = If(condition, yes, no, first.start, no.end)
        else:
            raise CompileError("expected expression", first.start)

        while self.peek().kind in PRECEDENCE:
            token = self.peek()
            power = PRECEDENCE[token.kind]
            if power < minimum:
                break
            self.take()
            right = self.expression(power + 1, depth + 1)
            node = Binary(token.kind, node, right, node.start, right.end)
        return node

    def parse(self):
        root = self.expression()
        if self.peek().kind != "EOF":
            raise CompileError("unexpected trailing token", self.peek().start)
        return root


def parse_typed(source):
    return _TypedParser(tokenize(source, extended=True)).parse()


def typecheck(node):
    """Static judgments for Int, Rat, Bool; no implicit annotation casts."""
    def visit(n, env, depth):
        if depth > MAX_DEPTH:
            raise TypeCheckError("AST depth limit", n.start)
        if isinstance(n, Literal):
            return "Int"
        if isinstance(n, Boolean):
            return "Bool"
        if isinstance(n, Name):
            if n.identifier not in env:
                raise TypeCheckError("unbound name " + n.identifier, n.start)
            return env[n.identifier]
        if isinstance(n, Unary):
            operand = visit(n.operand, env, depth + 1)
            if operand not in ("Int", "Rat"):
                raise TypeCheckError("unary arithmetic requires a number", n.start)
            return operand
        if isinstance(n, Binary):
            left = visit(n.left, env, depth + 1)
            right = visit(n.right, env, depth + 1)
            if left not in ("Int", "Rat") or right not in ("Int", "Rat"):
                raise TypeCheckError("arithmetic/comparison requires numbers", n.start)
            if n.op == "<":
                return "Bool"
            if n.op == "/":
                return "Rat"
            return "Rat" if "Rat" in (left, right) else "Int"
        if isinstance(n, Let):
            actual = visit(n.initializer, env, depth + 1)
            if actual != n.declared:
                raise TypeCheckError(
                    "initializer has type " + actual + ", expected " + n.declared,
                    n.start)
            extended = dict(env)
            extended[n.identifier] = actual
            return visit(n.body, extended, depth + 1)
        if isinstance(n, If):
            condition = visit(n.condition, env, depth + 1)
            if condition != "Bool":
                raise TypeCheckError("if condition must be Bool", n.start)
            yes = visit(n.yes, env, depth + 1)
            no = visit(n.no, env, depth + 1)
            if yes != no:
                raise TypeCheckError("if branches must share one type", n.start)
            return yes
        raise TypeCheckError("unknown AST node", getattr(n, "start", 0))
    return visit(node, {}, 0)


def compile_typed(source):
    root = parse_typed(source)
    result_type = typecheck(root)
    code = []

    def emit(op, arg=None, pos=0):
        code.append((op, arg, pos))
        return len(code) - 1

    def compile_node(node):
        if isinstance(node, Literal):
            emit("PUSH_INT", node.value, node.start)
        elif isinstance(node, Boolean):
            emit("PUSH_BOOL", node.value, node.start)
        elif isinstance(node, Name):
            emit("LOAD", node.identifier, node.start)
        elif isinstance(node, Unary):
            compile_node(node.operand)
            emit("NEG" if node.op == "-" else "POS", None, node.start)
        elif isinstance(node, Binary):
            compile_node(node.left)
            compile_node(node.right)
            emit({"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV",
                  "<": "LT"}[node.op], None, node.start)
        elif isinstance(node, Let):
            compile_node(node.initializer)
            emit("ENTER", None, node.start)
            emit("BIND", node.identifier, node.start)
            compile_node(node.body)
            emit("LEAVE", None, node.end)
        elif isinstance(node, If):
            compile_node(node.condition)
            branch = emit("JUMP_IF_FALSE", None, node.start)
            compile_node(node.yes)
            jump = emit("JUMP", None, node.start)
            code[branch] = ("JUMP_IF_FALSE", len(code), node.start)
            compile_node(node.no)
            code[jump] = ("JUMP", len(code), node.start)
        else:
            raise TypeCheckError("unknown AST node", node.start)

    compile_node(root)
    return TypedProgram(result_type, tuple(code))


def run_typed(program):
    """Execute compiler-produced instructions with lexical runtime frames."""
    if not isinstance(program, TypedProgram):
        raise TypeError("expected compiler-produced TypedProgram")
    code = program.instructions
    stack = []
    scopes = [{}]
    ip = 0
    while ip < len(code):
        op, arg, pos = code[ip]
        ip += 1
        if op == "PUSH_INT":
            stack.append(Fraction(arg))
        elif op == "PUSH_BOOL":
            stack.append(arg)
        elif op == "LOAD":
            for scope in reversed(scopes):
                if arg in scope:
                    stack.append(scope[arg])
                    break
            else:
                raise ValueError("invalid bytecode: unbound name")
        elif op == "ENTER":
            scopes.append({})
        elif op == "BIND":
            if not stack:
                raise ValueError("invalid bytecode: binding underflow")
            if arg in scopes[-1]:
                raise ValueError("invalid bytecode: duplicate binding")
            scopes[-1][arg] = stack.pop()
        elif op == "LEAVE":
            if len(scopes) < 2:
                raise ValueError("invalid bytecode: scope underflow")
            scopes.pop()
        elif op in ("NEG", "POS"):
            if not stack:
                raise ValueError("invalid bytecode: unary underflow")
            x = stack.pop()
            stack.append(-x if op == "NEG" else x)
        elif op == "JUMP_IF_FALSE":
            if not stack:
                raise ValueError("invalid bytecode: branch underflow")
            condition = stack.pop()
            if type(condition) is not bool:
                raise ValueError("invalid bytecode: nonboolean branch")
            if not condition:
                ip = arg
        elif op == "JUMP":
            ip = arg
        elif op in ("ADD", "SUB", "MUL", "DIV", "LT"):
            if len(stack) < 2:
                raise ValueError("invalid bytecode: binary underflow")
            right = stack.pop()
            left = stack.pop()
            if op == "ADD":
                stack.append(left + right)
            elif op == "SUB":
                stack.append(left - right)
            elif op == "MUL":
                stack.append(left * right)
            elif op == "LT":
                stack.append(left < right)
            else:
                if right == 0:
                    raise ZeroDivisionError(f"division by zero at offset {pos}")
                stack.append(left / right)
        else:
            raise ValueError("invalid bytecode: unknown instruction")
    if len(scopes) != 1 or len(stack) != 1:
        raise ValueError("invalid bytecode: unbalanced scope or stack")
    answer = stack[0]
    if program.result_type == "Bool":
        if type(answer) is not bool:
            raise ValueError("invalid bytecode: wrong result type")
    elif type(answer) is not Fraction:
        raise ValueError("invalid bytecode: nonnumeric result")
    return answer


def evaluate_typed(source):
    program = compile_typed(source)
    return program.result_type, run_typed(program)


if __name__ == "__main__":
    examples = [
        ("let x: Int = 5 in let x: Int = x+1 in x", ("Int", Fraction(6))),
        ("let x: Int = 2 in let y: Rat = x/3 in if y<1 then y+1 else y",
         ("Rat", Fraction(5, 3))),
        ("let x: Bool = true in if x then 2 else 3", ("Int", Fraction(2))),
        ("if false then 1/(2-2) else 1/2", ("Rat", Fraction(1, 2))),
    ]
    for source, expected in examples:
        assert evaluate_typed(source) == expected
