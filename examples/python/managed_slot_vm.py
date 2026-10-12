"""VM-integrated mark-and-sweep with explicit lexical roots.

Runs verified SlotCode. Managed cells and closures are represented by heap
ids; this uses HeapModel's mark/sweep reachability rather than host GC.
Python still owns this teaching VM and its Python objects. No sandbox,
persistent handles, concurrent mutation, or independent memory allocator.
"""
from dataclasses import dataclass, field
from fractions import Fraction

from .lexical_slot_verifier import (
    VerifiedProgram, SlotCode, BytecodeError, verify_slots, compile_slots,
)
from .typed_function_compiler import MAX_STEPS, MAX_FRAMES
from .mark_sweep_heap import HeapModel, MAX_OBJECTS


@dataclass(frozen=True)
class ManagedRef:
    """Opaque, non-reusable heap object identifier."""
    oid: int


@dataclass
class ManagedCell:
    value: object = None
    writable: bool = False
    initialized: bool = False


@dataclass(frozen=True)
class ManagedClosure:
    code: SlotCode
    captured: tuple


@dataclass(frozen=True)
class ManagedResult:
    value: object
    collections: int
    reclaimed: int
    peak_objects: int
    live_objects: int
    allocated_objects: int


@dataclass
class _Frame:
    code: SlotCode
    scopes: list
    base: int
    ip: int = 0
    stack: list = field(default_factory=list)


class _ManagedRuntime:
    def __init__(self, program, capacity, gc_interval):
        self.heap = HeapModel(capacity=capacity)
        self.payloads = {}
        self.frames = [_Frame(program.code, [[]], 1)]
        self.collections = 0
        self.reclaimed = 0
        self.peak = 0
        self.allocated = 0
        self.gc_interval = gc_interval

    @staticmethod
    def _refs(values):
        return tuple(sorted({v.oid for v in values if isinstance(v, ManagedRef)}))

    def _roots(self, temporary=()):
        roots = list(temporary)
        for frame in self.frames:
            for scope in frame.scopes:
                roots.extend(scope)
            roots.extend(frame.stack)
        return self._refs(roots)

    def collect(self, temporary=()):
        """Stop execution, mark from every operand and lexical slot, then sweep."""
        report = self.heap.collect(self._roots(temporary))
        for oid in report.reclaimed:
            del self.payloads[oid]
        self.collections += 1
        self.reclaimed += len(report.reclaimed)
        if len(self.payloads) != len(self.heap.objects):
            raise RuntimeError("heap and payload tables diverged")
        return report

    def _allocate(self, kind, payload, outgoing=(), temporary=()):
        # An operand popped just before allocation is not yet in a VM root.
        # Temporaries are explicitly retained across a preallocation GC.
        if len(self.heap.objects) == self.heap.capacity:
            self.collect((*temporary, *outgoing))
        address = self.heap.allocate(kind, self._refs(outgoing))
        self.payloads[address] = payload
        self.allocated += 1
        self.peak = max(self.peak, len(self.payloads))
        return ManagedRef(address)

    def cell(self, value=None, *, writable=False, initialized=False):
        return self._allocate("cell", ManagedCell(value,writable,initialized),
                              (value,), (value,))

    def closure(self, code, scopes):
        saved = tuple(tuple(scope) for scope in scopes)
        captured_values = tuple(v for scope in saved for v in scope)
        return self._allocate("closure",ManagedClosure(code,saved),
                              captured_values,captured_values)

    def get(self, handle, kind):
        if not isinstance(handle,ManagedRef):
            raise ValueError("invalid managed reference")
        obj = self.heap.get(handle.oid)
        if obj.kind != kind:
            raise ValueError("wrong managed object kind")
        return self.payloads[handle.oid]

    def change_cell(self, handle, new_value, *, initialize=False):
        cell = self.get(handle, "cell")
        if initialize:
            if cell.initialized or cell.writable or not isinstance(new_value,ManagedRef):
                raise ValueError("invalid recursive initialization")
            self.get(new_value,"closure")
            cell.value = new_value
            cell.initialized = True
        else:
            if not cell.initialized or not cell.writable:
                raise ValueError("illegal assignment")
            cell.value = new_value
        # The graph edge must be updated immediately after the mutator write.
        self.heap.set_references(handle.oid,self._refs((new_value,)))


def run_managed(program, *, gc_interval=8, capacity=MAX_OBJECTS,
                max_steps=MAX_STEPS, max_frames=MAX_FRAMES):
    """Verify, execute with tracked heap references, collect at safe points.

    A result of function type is an opaque ManagedRef, not an externally
    invocable closure. The VM never treats heap simulation as memory isolation.
    """
    verify_slots(program)
    if (type(gc_interval) is not int or gc_interval < 1 or
        type(max_steps) is not int or max_steps < 1 or
        type(max_frames) is not int or max_frames < 1):
        raise ValueError("invalid execution or collection budget")
    rt = _ManagedRuntime(program,capacity,gc_interval)
    steps = 0
    while rt.frames:
        steps += 1
        if steps > max_steps:
            raise RuntimeError("VM step limit exceeded")
        frame = rt.frames[-1]
        op,arg,pos = frame.code.instructions[frame.ip]
        frame.ip += 1
        stack = frame.stack
        scopes = frame.scopes

        def slot(addr):
            return scopes[-1-addr[0]][addr[1]]

        if op == "PUSH_INT":
            stack.append(Fraction(arg))
        elif op == "PUSH_BOOL":
            stack.append(arg)
        elif op == "ENTER":
            scopes.append([])
        elif op == "BIND_SLOT":
            value = stack.pop()
            scopes[-1].append(rt.cell(value,writable=True,initialized=True)
                              if arg.writable else value)
        elif op == "DECLARE_REC_SLOT":
            scopes[-1].append(rt.cell())
        elif op == "INIT_REC_SLOT":
            value = stack.pop()
            rt.change_cell(scopes[-1][arg],value,initialize=True)
        elif op == "LEAVE":
            scopes.pop()
        elif op == "LOAD_SLOT":
            value = slot(arg)
            if isinstance(value,ManagedRef) and rt.heap.get(value.oid).kind == "cell":
                cell = rt.get(value,"cell")
                if not cell.initialized:
                    raise ValueError("read before recursive initialization")
                value = cell.value
            stack.append(value)
        elif op == "STORE_SLOT":
            rt.change_cell(slot(arg),stack[-1])
        elif op == "CLOSURE_SLOT":
            stack.append(rt.closure(arg,scopes))
        elif op == "CALL":
            arguments = [stack.pop() for _ in range(arg)][::-1]
            callable_ref = stack.pop()
            function = rt.get(callable_ref,"closure")
            if len(function.code.parameters) != arg:
                raise ValueError("invalid call arity")
            if len(rt.frames) >= max_frames:
                raise RuntimeError("VM call-frame limit exceeded")
            captured = [list(scope) for scope in function.captured]
            rt.frames.append(_Frame(function.code,
                                    captured+[list(arguments)],
                                    len(captured)+1))
        elif op == "RETURN":
            answer = stack.pop()
            rt.frames.pop()
            if rt.frames:
                rt.frames[-1].stack.append(answer)
            else:
                # The returned result is an external root. An opaque closure
                # result therefore stays reachable in the final snapshot.
                rt.collect((answer,))
                return ManagedResult(answer,rt.collections,rt.reclaimed,
                                     rt.peak,len(rt.heap.objects),rt.allocated)
        elif op == "JUMP_IF_FALSE":
            condition = stack.pop()
            if type(condition) is not bool:
                raise ValueError("runtime branch type mismatch")
            if not condition:
                frame.ip = arg
        elif op == "JUMP":
            frame.ip = arg
        elif op in ("NEG","POS"):
            value = stack.pop()
            stack.append(-value if op == "NEG" else value)
        elif op in ("ADD","SUB","MUL","DIV","LT"):
            right = stack.pop()
            left = stack.pop()
            if op == "ADD":
                stack.append(left+right)
            elif op == "SUB":
                stack.append(left-right)
            elif op == "MUL":
                stack.append(left*right)
            elif op == "LT":
                stack.append(left<right)
            else:
                if right == 0:
                    raise ZeroDivisionError(f"division by zero at offset {pos}")
                stack.append(left/right)
        else:
            raise ValueError("verified VM encountered unexpected instruction")

        if steps % gc_interval == 0:
            rt.collect()
    raise RuntimeError("missing program result")


def evaluate_managed(source, **limits):
    program = compile_slots(source)
    return program.result_type, run_managed(program,**limits)
