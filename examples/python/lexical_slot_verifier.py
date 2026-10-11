"""Resolved lexical slots and a typed control-flow bytecode verifier.

This is an opt-in educational backend for the earlier statically typed
expression language with first-class functions, mutable captures and let rec.
The resolver and verifier do not accept arbitrary user-source Python code.
Only VerifiedProgram can execute in the slot VM; verification is a bounded
structural/type analysis, NOT a security sandbox or proof against DoS.
"""
from collections import deque
from dataclasses import dataclass, replace
from fractions import Fraction

from .expression_compiler import Literal, Unary, Binary
from .typed_expression_compiler import Boolean, Name, Let, If
from .typed_function_compiler import (
    FunctionType, Lambda, Call, Var, LetRec, SetVar,
    parse_functions, typecheck_functions, Cell, MAX_FRAMES, MAX_STEPS,
)

MAX_CODE = 8192


class BytecodeError(ValueError):
    """Invalid stack, lexical address, control flow or instruction type."""


@dataclass(frozen=True)
class SlotInfo:
    name: str
    typ: object
    writable: bool = False
    recursive: bool = False
    initialized: bool = True


@dataclass(frozen=True)
class SlotCode:
    captured: tuple                 # tuple of frames of SlotInfo
    parameters: tuple               # one frame of SlotInfo
    returns: object
    instructions: tuple             # (operation, argument, offset)


@dataclass(frozen=True)
class VerifiedProgram:
    result_type: object
    code: SlotCode


@dataclass(frozen=True)
class SlotClosure:
    code: SlotCode
    captured: tuple


def _numeric_result(op, left, right):
    if left not in ("Int", "Rat") or right not in ("Int", "Rat"):
        raise BytecodeError("numeric operands required")
    if op == "LT":
        return "Bool"
    if op == "DIV":
        return "Rat"
    return "Rat" if "Rat" in (left, right) else "Int"


def _locate(scopes, name):
    for distance, scope in enumerate(reversed(scopes)):
        for index, slot in enumerate(scope):
            if slot.name == name:
                return distance, index, slot
    raise BytecodeError("unresolved lexical name " + name)


def compile_slots(source, *, stateful=True):
    """Typecheck source, resolve all name accesses and emit slot-address code."""
    root = parse_functions(source, stateful=stateful)
    result = typecheck_functions(root)

    def lower(node, captured=(), parameters=(), expected=None):
        scopes = [list(frame) for frame in captured] + [list(parameters)]
        code = []

        def emit(op, arg=None, pos=0):
            code.append((op, arg, pos))
            if len(code) > MAX_CODE:
                raise BytecodeError("too many instructions")
            return len(code)-1

        def compile_node(n):
            if isinstance(n, Literal):
                emit("PUSH_INT", n.value, n.start)
                return "Int"
            if isinstance(n, Boolean):
                emit("PUSH_BOOL", n.value, n.start)
                return "Bool"
            if isinstance(n, Name):
                distance, index, info = _locate(scopes, n.identifier)
                emit("LOAD_SLOT", (distance, index), n.start)
                return info.typ
            if isinstance(n, Unary):
                result_type = compile_node(n.operand)
                emit("NEG" if n.op == "-" else "POS", None, n.start)
                return result_type
            if isinstance(n, Binary):
                left = compile_node(n.left)
                right = compile_node(n.right)
                op = {"+": "ADD", "-": "SUB", "*": "MUL",
                      "/": "DIV", "<": "LT"}[n.op]
                emit(op, None, n.start)
                return _numeric_result(op, left, right)
            if isinstance(n, (Let, Var)):
                compiled_type = compile_node(n.initializer)
                if compiled_type != n.declared:
                    raise BytecodeError("declaration changed type after checking")
                emit("ENTER", None, n.start)
                scopes.append([])
                info = SlotInfo(n.identifier, n.declared, isinstance(n, Var))
                scopes[-1].append(info)
                emit("BIND_SLOT", info, n.start)
                body_type = compile_node(n.body)
                emit("LEAVE", None, n.end)
                scopes.pop()
                return body_type
            if isinstance(n, LetRec):
                emit("ENTER", None, n.start)
                scopes.append([])
                info = SlotInfo(n.identifier, n.declared, False, True, False)
                scopes[-1].append(info)
                emit("DECLARE_REC_SLOT", info, n.start)
                actual = compile_node(n.initializer)
                if actual != n.declared:
                    raise BytecodeError("incorrect recursive initializer")
                emit("INIT_REC_SLOT", 0, n.start)
                scopes[-1][0] = replace(info, initialized=True)
                body_type = compile_node(n.body)
                emit("LEAVE", None, n.end)
                scopes.pop()
                return body_type
            if isinstance(n, SetVar):
                value_type = compile_node(n.expression)
                distance, index, info = _locate(scopes, n.identifier)
                if not info.writable or value_type != info.typ:
                    raise BytecodeError("invalid assignment to lexical slot")
                emit("STORE_SLOT", (distance, index), n.start)
                return value_type
            if isinstance(n, If):
                condition = compile_node(n.condition)
                if condition != "Bool":
                    raise BytecodeError("invalid branch condition")
                branch = emit("JUMP_IF_FALSE", None, n.start)
                true_type = compile_node(n.yes)
                end = emit("JUMP", None, n.start)
                code[branch] = ("JUMP_IF_FALSE", len(code), n.start)
                false_type = compile_node(n.no)
                code[end] = ("JUMP", len(code), n.start)
                if true_type != false_type:
                    raise BytecodeError("incompatible branches")
                return true_type
            if isinstance(n, Lambda):
                declared_params = tuple(SlotInfo(name, typ) for name, typ in n.parameters)
                block = lower(n.body,
                              tuple(tuple(frame) for frame in scopes),
                              declared_params,
                              n.result_annotation)
                emit("CLOSURE_SLOT", block, n.start)
                return FunctionType(tuple(info.typ for info in declared_params),
                                    block.returns)
            if isinstance(n, Call):
                callee_type = compile_node(n.function)
                argument_types = tuple(compile_node(arg) for arg in n.arguments)
                if not isinstance(callee_type, FunctionType) or (
                    argument_types != callee_type.arguments
                ):
                    raise BytecodeError("invalid typed call")
                emit("CALL", len(n.arguments), n.start)
                return callee_type.result
            raise BytecodeError("unknown AST node")

        inferred = compile_node(node)
        if expected is not None and inferred != expected:
            raise BytecodeError("body return type mismatch")
        emit("RETURN", None, node.end)
        return SlotCode(tuple(tuple(scope) for scope in captured),
                        tuple(parameters), inferred, tuple(code))

    block = lower(root, expected=result)
    candidate = VerifiedProgram(result, block)
    verify_slots(candidate)
    return candidate


def verify_slots(program, *, max_codes=256, max_instructions=MAX_CODE):
    """Abstract-interpret each code body: types, stack, scopes and CFG joins.

    Verifies structural bytecode shape and compiler's type discipline.
    Recursive closures can capture a pending slot ONLY in the strict
    DECLARE_REC -> CLOSURE_SLOT -> INIT_REC_SLOT initialization sequence.
    It is not a general verifier for foreign serialized bytecode.
    """
    if not isinstance(program, VerifiedProgram):
        raise BytecodeError("expected VerifiedProgram")
    seen = set()

    def verify_block(block):
        if not isinstance(block, SlotCode):
            raise BytecodeError("bad code object")
        identity = id(block)
        if identity in seen:
            raise BytecodeError("shared/cyclic code objects unsupported")
        seen.add(identity)
        if len(seen) > max_codes:
            raise BytecodeError("too many code objects")
        ops = block.instructions
        if not ops or len(ops) > max_instructions:
            raise BytecodeError("instruction count out of bounds")
        for frame in block.captured + (block.parameters,):
            if not isinstance(frame, tuple) or not all(
                isinstance(slot, SlotInfo) for slot in frame
            ):
                raise BytecodeError("invalid scope descriptor")
            if len(set(s.name for s in frame)) != len(frame):
                raise BytecodeError("duplicate lexical slot")

        baseline = block.captured + (block.parameters,)
        base_count = len(baseline)
        work = deque([(0, (), baseline)])
        reached = {}
        nested = []

        while work:
            pc, stack, scopes = work.popleft()
            if not isinstance(pc, int) or not 0 <= pc < len(ops):
                raise BytecodeError("control flow escaped code")
            old = reached.get(pc)
            state = (stack, scopes)
            if old is not None:
                if old != state:
                    raise BytecodeError("incompatible stack or scopes at CFG join")
                continue
            reached[pc] = state
            entry = ops[pc]
            if (not isinstance(entry, tuple) or len(entry) != 3 or
                type(entry[0]) is not str or type(entry[2]) is not int or
                entry[2] < 0):
                raise BytecodeError("invalid instruction tuple")
            op, arg, _ = entry
            values = list(stack)
            env = list(scopes)

            def pop():
                if not values:
                    raise BytecodeError("operand stack underflow")
                return values.pop()

            def address():
                if (not isinstance(arg, tuple) or len(arg) != 2 or
                    any(type(x) is not int or x < 0 for x in arg)):
                    raise BytecodeError("invalid lexical address")
                distance, index = arg
                if distance >= len(env) or index >= len(env[-1-distance]):
                    raise BytecodeError("lexical address out of bounds")
                return env[-1-distance][index], distance

            def step(target):
                work.append((target, tuple(values), tuple(env)))

            if op == "PUSH_INT":
                if type(arg) is not int:
                    raise BytecodeError("invalid integer immediate")
                values.append("Int")
            elif op == "PUSH_BOOL":
                if type(arg) is not bool:
                    raise BytecodeError("invalid Boolean immediate")
                values.append("Bool")
            elif op == "LOAD_SLOT":
                slot, distance = address()
                if not slot.initialized and distance < len(env)-base_count+1:
                    raise BytecodeError("read before recursive initialization")
                values.append(slot.typ)
            elif op == "STORE_SLOT":
                slot, _ = address()
                if not slot.writable or not slot.initialized or pop() != slot.typ:
                    raise BytecodeError("illegal or mistyped store")
                values.append(slot.typ)
            elif op == "ENTER":
                if arg is not None:
                    raise BytecodeError("invalid ENTER")
                env.append(())
            elif op == "BIND_SLOT":
                if (not isinstance(arg, SlotInfo) or len(env) <= base_count or
                    len(env[-1]) or arg.recursive or pop() != arg.typ):
                    raise BytecodeError("invalid lexical binding")
                env[-1] = (arg,)
            elif op == "DECLARE_REC_SLOT":
                if (not isinstance(arg, SlotInfo) or not arg.recursive or
                    arg.initialized or arg.writable or
                    not isinstance(arg.typ, FunctionType) or
                    len(env) <= base_count or len(env[-1])):
                    raise BytecodeError("invalid recursive declaration")
                if (pc+2 >= len(ops) or ops[pc+1][0] != "CLOSURE_SLOT"
                    or ops[pc+2][0] != "INIT_REC_SLOT"):
                    raise BytecodeError("recursive closure initialization must be adjacent")
                env[-1] = (arg,)
            elif op == "INIT_REC_SLOT":
                if (arg != 0 or len(env) <= base_count or len(env[-1]) != 1
                    or not env[-1][0].recursive or env[-1][0].initialized
                    or pop() != env[-1][0].typ):
                    raise BytecodeError("invalid recursive initialization")
                env[-1] = (replace(env[-1][0], initialized=True),)
            elif op == "LEAVE":
                if arg is not None or len(env) <= base_count:
                    raise BytecodeError("unbalanced lexical scopes")
                env.pop()
            elif op == "CLOSURE_SLOT":
                if not isinstance(arg, SlotCode) or arg.captured != tuple(env):
                    raise BytecodeError("closure lexical environment mismatch")
                nested.append(arg)
                values.append(FunctionType(tuple(s.typ for s in arg.parameters),
                                           arg.returns))
            elif op == "CALL":
                if type(arg) is not int or arg < 0 or len(values) < arg+1:
                    raise BytecodeError("invalid call arity or stack")
                arguments = [pop() for _ in range(arg)][::-1]
                callee = pop()
                if not isinstance(callee, FunctionType) or (
                    tuple(arguments) != callee.arguments
                ):
                    raise BytecodeError("call target/argument type mismatch")
                values.append(callee.result)
            elif op in ("NEG", "POS"):
                typ = pop()
                if typ not in ("Int", "Rat") or arg is not None:
                    raise BytecodeError("invalid unary operation")
                values.append(typ)
            elif op in ("ADD", "SUB", "MUL", "DIV", "LT"):
                right, left = pop(), pop()
                if arg is not None:
                    raise BytecodeError("invalid arithmetic argument")
                values.append(_numeric_result(op, left, right))
            elif op == "JUMP_IF_FALSE":
                if pop() != "Bool":
                    raise BytecodeError("conditional requires Boolean")
                if type(arg) is not int or not pc < arg < len(ops):
                    raise BytecodeError("invalid forward conditional jump")
                step(arg)
            elif op == "JUMP":
                if type(arg) is not int or not pc < arg < len(ops):
                    raise BytecodeError("invalid forward jump")
                step(arg)
                continue
            elif op == "RETURN":
                if arg is not None or len(values) != 1 or (
                    values[0] != block.returns or len(env) != base_count
                ):
                    raise BytecodeError("wrong return stack/type/scope state")
                continue
            else:
                raise BytecodeError("unsupported opcode " + op)
            step(pc+1)

        if len(reached) != len(ops):
            raise BytecodeError("unreachable instructions")
        for child in nested:
            verify_block(child)

    if program.result_type != program.code.returns or program.code.captured or (
        program.code.parameters
    ):
        raise BytecodeError("invalid top-level signature")
    verify_block(program.code)
    return True


def run_slots(program, *, max_steps=MAX_STEPS, max_frames=MAX_FRAMES):
    """Execute only code with a successful static verification pass."""
    verify_slots(program)
    if (type(max_steps) is not int or max_steps < 1 or
        type(max_frames) is not int or max_frames < 1):
        raise ValueError("invalid VM execution budget")

    @dataclass
    class Frame:
        code: SlotCode
        scopes: list
        base: int
        ip: int = 0
        stack: list = None

        def __post_init__(self):
            self.stack = []

    calls = [Frame(program.code, [[]], 1)]
    steps = 0
    while calls:
        steps += 1
        if steps > max_steps:
            raise RuntimeError("VM step limit exceeded")
        frame = calls[-1]
        op, arg, pos = frame.code.instructions[frame.ip]
        frame.ip += 1
        stack = frame.stack
        env = frame.scopes

        def cell_at(address):
            distance, index = address
            return env[-1-distance][index]

        if op == "PUSH_INT":
            stack.append(Fraction(arg))
        elif op == "PUSH_BOOL":
            stack.append(arg)
        elif op == "ENTER":
            env.append([])
        elif op == "BIND_SLOT":
            value = stack.pop()
            env[-1].append(Cell(value, True, True) if arg.writable else value)
        elif op == "DECLARE_REC_SLOT":
            env[-1].append(Cell(None, False, False))
        elif op == "INIT_REC_SLOT":
            cell = env[-1][arg]
            value = stack.pop()
            if cell.initialized or not isinstance(value, SlotClosure):
                raise ValueError("illegal recursive initialization")
            cell.value = value
            cell.initialized = True
        elif op == "LEAVE":
            env.pop()
        elif op == "LOAD_SLOT":
            val = cell_at(arg)
            if isinstance(val, Cell):
                if not val.initialized:
                    raise ValueError("uninitialized recursive cell")
                val = val.value
            stack.append(val)
        elif op == "STORE_SLOT":
            val = stack[-1]
            cell = cell_at(arg)
            if not isinstance(cell, Cell) or not cell.writable or not cell.initialized:
                raise ValueError("illegal immutable store")
            cell.value = val
        elif op == "CLOSURE_SLOT":
            stack.append(SlotClosure(arg, tuple(tuple(s) for s in env)))
        elif op == "CALL":
            args = tuple(stack.pop() for _ in range(arg))[::-1]
            fn = stack.pop()
            if not isinstance(fn, SlotClosure) or len(fn.code.parameters) != arg:
                raise ValueError("invalid function call")
            if len(calls) >= max_frames:
                raise RuntimeError("VM call-frame limit exceeded")
            new_scopes = [list(scope) for scope in fn.captured] + [list(args)]
            calls.append(Frame(fn.code, new_scopes, len(new_scopes)))
        elif op == "RETURN":
            answer = stack.pop()
            calls.pop()
            if calls:
                calls[-1].stack.append(answer)
            else:
                return answer
        elif op == "JUMP_IF_FALSE":
            condition = stack.pop()
            if not condition:
                frame.ip = arg
        elif op == "JUMP":
            frame.ip = arg
        elif op in ("NEG", "POS"):
            a = stack.pop()
            stack.append(-a if op == "NEG" else a)
        elif op in ("ADD", "SUB", "MUL", "DIV", "LT"):
            b, a = stack.pop(), stack.pop()
            if op == "ADD":
                stack.append(a+b)
            elif op == "SUB":
                stack.append(a-b)
            elif op == "MUL":
                stack.append(a*b)
            elif op == "LT":
                stack.append(a < b)
            else:
                if b == 0:
                    raise ZeroDivisionError(f"division by zero at offset {pos}")
                stack.append(a/b)
    raise ValueError("missing top-level result")


def evaluate_slots(source, *, stateful=True, **limits):
    program = compile_slots(source, stateful=stateful)
    return program.result_type, run_slots(program, **limits)
