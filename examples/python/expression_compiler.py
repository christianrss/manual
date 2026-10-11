"""An intentionally small, auditable arithmetic language compiler.

Pipeline: ASCII lexer -> precedence-climbing parser -> immutable AST ->
postorder stack bytecode -> rational-arithmetic virtual machine.

No Python eval/exec, identifiers, assignment, loops, I/O, or imports in the
source language. Compilation returns code; nothing runs until run_bytecode().
"""
from dataclasses import dataclass
from fractions import Fraction

MAX_SOURCE = 4096
MAX_TOKENS = 2048
MAX_DIGITS = 100
MAX_DEPTH = 80
BINARY_PRECEDENCE = {"+": 10, "-": 10, "*": 20, "/": 20}


class CompileError(ValueError):
    """Lexical or grammatical error with a character offset."""

    def __init__(self, message, offset):
        self.offset = offset
        super().__init__(f"{message} at offset {offset}")


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Literal:
    value: int
    start: int
    end: int


@dataclass(frozen=True)
class Unary:
    op: str
    operand: object
    start: int
    end: int


@dataclass(frozen=True)
class Binary:
    op: str
    left: object
    right: object
    start: int
    end: int


KEYWORDS = frozenset(("let", "in", "if", "then", "else", "true", "false",
                      "Int", "Rat", "Bool"))


def tokenize(source, *, extended=False, functions=False, stateful=False):
    """Produce ASCII tokens with [start,end) offsets.

    extended=True adds identifiers, typed-binding keywords, ':' '=' and '<'.
    functions=True additionally enables 'fn', 'Fn', '->', '=>' and ','.
    stateful=True additionally enables 'var', 'set', 'rec' and requires functions.
    The default arithmetic language retains its original exact contract.
    """
    if functions and not extended:
        raise ValueError("function syntax requires extended lexer mode")
    if stateful and not functions:
        raise ValueError("stateful syntax requires function mode")
    if type(source) is not str:
        raise TypeError("source must be a string")
    if len(source) > MAX_SOURCE:
        raise CompileError("source too long", MAX_SOURCE)
    tokens = []
    position = 0
    while position < len(source):
        char = source[position]
        if char in " \t\r\n":
            position += 1
            continue
        start = position
        if "0" <= char <= "9":
            while position < len(source) and "0" <= source[position] <= "9":
                position += 1
            if position - start > MAX_DIGITS:
                raise CompileError("integer literal too long", start)
            tokens.append(Token("INT", source[start:position], start, position))
        elif functions and source.startswith(("->", "=>"), position):
            position += 2
            text = source[start:position]
            tokens.append(Token(text, text, start, position))
        elif char in "+-*/()" or (extended and char in ":=<") or (functions and char == ","):
            position += 1
            tokens.append(Token(char, char, start, position))
        elif extended and (("a" <= char <= "z") or ("A" <= char <= "Z")
                           or char == "_"):
            position += 1
            while position < len(source):
                c = source[position]
                if not (("a" <= c <= "z") or ("A" <= c <= "Z")
                        or ("0" <= c <= "9") or c == "_"):
                    break
                position += 1
            text = source[start:position]
            tokens.append(Token(text if text in KEYWORDS or
                                (functions and text in ("fn", "Fn")) or
                                (stateful and text in ("var", "set", "rec")) else "IDENT",
                                text, start, position))
        else:
            raise CompileError("unexpected character", position)
        if len(tokens) > MAX_TOKENS:
            raise CompileError("too many tokens", start)
    tokens.append(Token("EOF", "", len(source), len(source)))
    return tuple(tokens)


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0

    def peek(self):
        return self.tokens[self.index]

    def take(self):
        token = self.peek()
        self.index += 1
        return token

    def parse(self):
        node = self.expression(0, 0)
        if self.peek().kind != "EOF":
            raise CompileError("trailing token", self.peek().start)
        return node

    def expression(self, minimum, depth):
        if depth > MAX_DEPTH:
            raise CompileError("expression nesting too deep", self.peek().start)
        first = self.take()
        if first.kind == "INT":
            node = Literal(int(first.text), first.start, first.end)
        elif first.kind in ("+", "-"):
            operand = self.expression(30, depth + 1)
            node = Unary(first.kind, operand, first.start, operand.end)
        elif first.kind == "(":
            node = self.expression(0, depth + 1)
            if self.peek().kind != ")":
                raise CompileError("expected closing parenthesis", self.peek().start)
            self.take()
            # Grouping affects the parse but does not require an AST node:
            # semantic AST spans cover actual retained nodes, not punctuation.
        else:
            raise CompileError("expected integer or expression", first.start)
        while self.peek().kind in BINARY_PRECEDENCE:
            op = self.peek()
            power = BINARY_PRECEDENCE[op.kind]
            if power < minimum:
                break
            self.take()
            right = self.expression(power + 1, depth + 1)
            node = Binary(op.kind, node, right, node.start, right.end)
        return node


def parse_expression(source):
    """Return immutable AST, without evaluating or executing source code."""
    return _Parser(tokenize(source)).parse()


def compile_expression(source):
    """Return immutable postfix instructions (opcode, argument, source offset)."""
    root = parse_expression(source)
    pending = [(root, False)]
    instructions = []
    while pending:
        node, done = pending.pop()
        if not done:
            pending.append((node, True))
            if isinstance(node, Binary):
                pending.append((node.right, False))
                pending.append((node.left, False))
            elif isinstance(node, Unary):
                pending.append((node.operand, False))
        elif isinstance(node, Literal):
            instructions.append(("PUSH", node.value, node.start))
        elif isinstance(node, Unary):
            instructions.append(("NEG" if node.op == "-" else "POS", None, node.start))
        else:
            instructions.append(({"+": "ADD", "-": "SUB", "*": "MUL",
                                  "/": "DIV"}[node.op], None, node.start))
    return tuple(instructions)


def run_bytecode(code):
    """Execute only compiler-emitted stack bytecode; exact rational results."""
    stack = []
    for operation, operand, offset in code:
        if operation == "PUSH":
            stack.append(Fraction(operand))
        elif operation in ("NEG", "POS"):
            if not stack:
                raise ValueError("invalid bytecode: stack underflow")
            a = stack.pop()
            stack.append(-a if operation == "NEG" else a)
        elif operation in ("ADD", "SUB", "MUL", "DIV"):
            if len(stack) < 2:
                raise ValueError("invalid bytecode: stack underflow")
            b = stack.pop()
            a = stack.pop()
            if operation == "ADD":
                stack.append(a + b)
            elif operation == "SUB":
                stack.append(a - b)
            elif operation == "MUL":
                stack.append(a * b)
            else:
                if b == 0:
                    raise ZeroDivisionError(f"division by zero at offset {offset}")
                stack.append(a / b)
        else:
            raise ValueError("invalid bytecode: unknown opcode")
    if len(stack) != 1:
        raise ValueError("invalid bytecode: expected exactly one result")
    return stack[0]


def interpret_ast(root):
    """Independent AST walk using an explicit postorder work stack."""
    work = [(root, False)]
    values = []
    while work:
        node, done = work.pop()
        if not done:
            work.append((node, True))
            if isinstance(node, Binary):
                work.append((node.right, False))
                work.append((node.left, False))
            elif isinstance(node, Unary):
                work.append((node.operand, False))
        elif isinstance(node, Literal):
            values.append(Fraction(node.value))
        elif isinstance(node, Unary):
            operand = values.pop()
            values.append(-operand if node.op == "-" else operand)
        else:
            right = values.pop()
            left = values.pop()
            if node.op == "+":
                values.append(left + right)
            elif node.op == "-":
                values.append(left - right)
            elif node.op == "*":
                values.append(left * right)
            else:
                if right == 0:
                    raise ZeroDivisionError(f"division by zero at offset {node.start}")
                values.append(left / right)
    return values.pop()


def evaluate(source):
    """Compile source and execute its bytecode, producing Fraction."""
    return run_bytecode(compile_expression(source))


if __name__ == "__main__":
    for source, answer in (("1+2*3", Fraction(7)),
                           ("(1+2)*3", Fraction(9)),
                           ("8/(2+2)+-3", Fraction(-1)),
                           ("1/3+1/6", Fraction(1, 2)),
                           ("10-3-2", Fraction(5)),
                           ("--5", Fraction(5))):
        assert evaluate(source) == answer
        assert interpret_ast(parse_expression(source)) == answer
    assert [(t.kind, t.start, t.end) for t in tokenize("12 +3")] == [
        ("INT", 0, 2), ("+", 3, 4), ("INT", 4, 5), ("EOF", 5, 5)]
