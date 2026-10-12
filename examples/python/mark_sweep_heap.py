"""Explicit-root heap graph and stop-the-world mark/sweep teaching model.

This is NOT Python garbage collection and is NOT integrated with the slot VM.
It models reachable closures, environments, cells and cycles with integer ids.
"""
from collections import deque
from dataclasses import dataclass

MAX_OBJECTS = 8192
MAX_EDGES = 32768
KINDS = frozenset(("closure","environment","cell","value","pair"))


@dataclass(frozen=True)
class HeapObject:
    kind: str
    references: tuple


@dataclass(frozen=True)
class Collection:
    reachable: tuple
    reclaimed: tuple
    remaining: int


class HeapModel:
    """Finite owned object graph. Object identifiers never reused."""

    def __init__(self, *, capacity=MAX_OBJECTS):
        if type(capacity) is not int or not 1 <= capacity <= MAX_OBJECTS:
            raise ValueError("invalid heap capacity")
        self.capacity = capacity
        self.objects = {}
        self.next_id = 1

    @staticmethod
    def _addresses(references):
        if type(references) not in (list,tuple,set,frozenset):
            raise ValueError("references must be a finite sequence/set")
        if len(references) > MAX_EDGES:
            raise ValueError("too many references")
        if any(type(address) is not int or address <= 0 for address in references):
            raise ValueError("invalid heap address")
        return tuple(sorted(set(references)))

    def _check_present(self, addresses):
        for address in addresses:
            if address not in self.objects:
                raise ValueError("dangling heap reference")

    def allocate(self, kind, references=()):
        """Allocate a vertex pointing only to existing objects."""
        if kind not in KINDS:
            raise ValueError("unsupported object kind")
        links = self._addresses(references)
        self._check_present(links)
        if len(self.objects) >= self.capacity:
            raise MemoryError("bounded heap is full")
        address = self.next_id
        self.next_id += 1
        self.objects[address] = HeapObject(kind, links)
        return address

    def set_references(self, address, references):
        """Mutator writes outgoing edges. Self-edges and cycles are allowed."""
        if type(address) is not int or address not in self.objects:
            raise ValueError("unknown object")
        links = self._addresses(references)
        self._check_present(links)
        previous = self.objects[address]
        self.objects[address] = HeapObject(previous.kind, links)

    def mark(self, roots):
        """Trace reachable ids without recursion and without mutating heap."""
        initial = self._addresses(roots)
        self._check_present(initial)
        pending = deque(initial)
        reached = set()
        while pending:
            address = pending.pop()
            if address in reached:
                continue
            reached.add(address)
            pending.extend(self.objects[address].references)
        return tuple(sorted(reached))

    def collect(self, roots):
        """Stop-the-world mark/sweep: reclaim exactly unreachable objects."""
        live = self.mark(roots)
        protected = set(live)
        freed = tuple(sorted(set(self.objects) - protected))
        for address in freed:
            del self.objects[address]
        return Collection(live,freed,len(self.objects))

    def get(self, address):
        if type(address) is not int or address not in self.objects:
            raise ValueError("unknown object")
        return self.objects[address]


def closure_lifetime_example():
    """One closure retains its cell after an activation frame is discarded."""
    heap = HeapModel()
    cell = heap.allocate("cell")
    env = heap.allocate("environment",(cell,))
    closure = heap.allocate("closure",(env,))
    discarded_frame = heap.allocate("pair")
    first = heap.collect((closure,))
    assert discarded_frame in first.reclaimed
    assert cell in first.reachable
    last = heap.collect(())
    assert set(last.reclaimed) == {cell,env,closure}
    return first,last


def cyclic_collection_example():
    heap = HeapModel()
    a = heap.allocate("pair")
    b = heap.allocate("pair",(a,))
    heap.set_references(a,(b,))
    report = heap.collect(())
    assert report.reclaimed == (a,b)
    return report
