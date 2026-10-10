---
id: machine-representation-isa-cache
title: "Machine Representation, CPU Instructions and Cache Mapping"
description: "Derive two's complement, endianness, ISA execution and direct-mapped cache conflicts with reproducible Python models and boundary tests."
category: computer-architecture
difficulty: foundational
updated: 2026-10-10
prerequisites: [complexity-analysis]
sources:
  - {title: "RISC-V — RV32I Base Integer Instruction Set", url: "https://docs.riscv.org/reference/isa/v20260120/unpriv/rv32.html", kind: "ratified ISA specification"}
  - {title: "Intel — 64 and IA-32 Optimization Manuals", url: "https://www.intel.com/content/www/us/en/developer/articles/technical/intel64-and-ia32-architectures-optimization.html", kind: "official optimization manuals"}
  - {title: "Python — Built-in Types and integer byte conversion", url: "https://docs.python.org/3/library/stdtypes.html", kind: "official language specification"}
---
A high-level program eventually manipulates binary representations, executes machine instructions and touches a memory hierarchy. These layers explain practical phenomena that Big O alone cannot predict: two algorithms with the same asymptotic cost can differ because of cache behavior, alignment, branching and data layout. The first task is to distinguish **machine representation** (which bit patterns encode values), **ISA** (the operations and architectural state visible to programs), **microarchitecture** (how a CPU implements that ISA), and **operating-system abstractions** (virtual memory and scheduling) [1][2].

This chapter establishes a carefully limited foundation. It does **not** teach an entire processor, digital logic, pipelining, cache coherence, privileged RISC-V, or real x86 execution. The Python models below are small **teaching machines**, not instruction-accurate emulators. They allow mechanical verification of specific contracts before studying the real systems.

## Bits, bytes, unsigned values and two's complement

One bit has values 0 or 1. An 8-bit sequence represents one of `2^8=256` patterns. Under **unsigned** interpretation, it ranges from 0 to 255. Under **two's-complement signed** interpretation, the same eight bits represent values from -128 to 127: if the high bit is one, subtract 256 from the unsigned value. These are *different interpretations of the same bytes*, not different kinds of memory [1].

For a fixed width `w`, arithmetic in a `w`-bit integer register commonly retains the low `w` bits of a sum, which is arithmetic modulo `2^w`. This is not the same as Python's unlimited-precision integer semantics. It is also not a universal rule for every language: signed integer overflow in C/C++ has distinct language semantics, and checked arithmetic in other environments may raise. Never infer a language's overflow behavior from a CPU demonstration [1].

```python
def signed8(raw):
    if type(raw) is not int or not 0 <= raw < 256:
        raise ValueError("raw must be an unsigned 8-bit integer")
    return raw - 256 if raw & 0x80 else raw

def add8(left, right):
    if (type(left) is not int or type(right) is not int
            or not 0 <= left < 256 or not 0 <= right < 256):
        raise ValueError("8-bit operands required")
    return (left + right) & 0xff

assert signed8(0b01111111) == 127
assert signed8(0b10000000) == -128
assert signed8(0b11111111) == -1
assert add8(255, 1) == 0
assert signed8(add8(127, 1)) == -128
```

**Derivation:** the mask `0xff` keeps bits 0–7. Therefore `add8(a,b)=(a+b) mod 256`. The signed decoder then subtracts 256 exactly when bit 7 is set. Exhaustive tests can check every possible byte and all 65,536 input pairs, which is practical precisely because the model is finite. For 64-bit quantities the same exhaustive approach is infeasible, so algebraic proofs and carefully chosen boundaries become more important.

## Byte order, address order and alignment

A **byte-addressed** machine assigns addresses to individual bytes. Endianness determines the order in which a multibyte value's constituent bytes appear at consecutive addresses; it does not reverse bits inside each byte. For 0x12345678, big-endian storage is `12 34 56 78`, whereas little-endian storage is `78 56 34 12`. The RISC-V specification explicitly describes this distinction for its load/store environments [1].

```python
value = 0x12345678
big = value.to_bytes(4, "big")
little = value.to_bytes(4, "little")
assert big.hex() == "12345678"
assert little.hex() == "78563412"
assert int.from_bytes(big, "big") == value
assert int.from_bytes(little, "little") == value
assert int.from_bytes(big, "little") != value
assert (-2).to_bytes(2, "little", signed=True) == bytes([254, 255])
assert int.from_bytes(bytes([254, 255]), "little", signed=True) == -2
```

The Python API makes byte order and signed interpretation explicit [3]. A network protocol, file format or binary interface must specify them; guessing the host's endianness causes portability defects. **Alignment** is separate: a 4-byte word is naturally aligned when its starting address is divisible by 4. Some ISA/environment combinations support unaligned accesses directly, some handle them slowly or through traps, and some reject them; there is no universal "unaligned always faults" rule [1].

## ISA versus microarchitecture: what is actually promised?

An **instruction set architecture** is the software-visible contract: registers, instructions, exceptions and other architecturally defined effects. RV32I, for example, defines 32 general-purpose 32-bit integer registers, `x0` permanently zero, and a program counter. Arithmetic like `ADD` acts on registers; loads and stores move values between registers and memory. This is a **load/store** model. Programs observe the same ISA-level results on implementations with quite different pipelines, caches or frequencies [1].

**Microarchitecture** describes the implementation: fetch/decode paths, execution units, branch prediction, speculation, out-of-order scheduling and cache organization. Two processors may expose the same ISA but differ substantially in power or latency. Neither source-code line count nor instruction count alone determines elapsed time; memory stalls and dependencies matter [2]. A compiler also transforms high-level code, allocates registers and selects instructions, so one high-level statement is not generally one machine instruction.

## Worked program: a tiny, explicitly non-RISC-V machine

To make the difference concrete, this toy executor has **four** eight-bit registers, a byte-addressed memory array and no branches, privilege modes or interrupts. The made-up instructions `LI`, `LD`, `ADD`, `ST` respectively load a literal, load from memory, add with 8-bit wraparound and store. This syntax is **not RISC-V assembly**. It merely illustrates the idea of a sequential architectural state transition [1].

```python
class TinyMachine:
    def __init__(self, memory):
        if any(type(v) is not int or not 0 <= v < 256 for v in memory):
            raise ValueError("memory must contain bytes")
        self.memory = bytearray(memory)
        self.registers = [0, 0, 0, 0]
        self.pc = 0

    def run(self, program):
        for ins in program:
            op, *args = ins
            if op == "LI" and len(args) == 2:
                dst, immediate = args
                self._reg(dst)
                if type(immediate) is not int or not 0 <= immediate < 256:
                    raise ValueError("bad immediate")
                self.registers[dst] = immediate
            elif op == "LD" and len(args) == 2:
                dst, address = args
                self._reg(dst)
                self._addr(address)
                self.registers[dst] = self.memory[address]
            elif op == "ADD" and len(args) == 3:
                dst, a, b = args
                for r in (dst, a, b):
                    self._reg(r)
                self.registers[dst] = add8(self.registers[a], self.registers[b])
            elif op == "ST" and len(args) == 2:
                src, address = args
                self._reg(src)
                self._addr(address)
                self.memory[address] = self.registers[src]
            else:
                raise ValueError("unknown or malformed instruction")
            self.pc += 1

    def _reg(self, index):
        if type(index) is not int or not 0 <= index < len(self.registers):
            raise ValueError("invalid register")

    def _addr(self, address):
        if type(address) is not int or not 0 <= address < len(self.memory):
            raise ValueError("invalid memory address")

machine = TinyMachine([250, 9, 0])
machine.run([("LD", 0, 0), ("LD", 1, 1), ("ADD", 2, 0, 1), ("ST", 2, 2)])
assert machine.registers[2] == 3
assert list(machine.memory) == [250, 9, 3]
assert machine.pc == 4
```

Here the final 8-bit sum is `(250+9) mod 256 = 3`. Each completed instruction advances `pc` by **one list position**, *not* by bytes as a real ISA program counter does. Validation may fail after earlier instructions have modified state; the executor is not atomic, transactional, security-isolated or concurrency-safe. Even the `ADD` opcode borrows only the broad notion of register arithmetic, not a real instruction encoding. The exercise is to reason about **observable state transitions**, not to mistake this model for hardware emulation.

## Cache lines: offsets, sets, tags and conflict misses

A cache stores recently used **blocks/lines**, usually serving multiple bytes per fill. For an instructional **direct-mapped** cache with `S` slots and line size `B` bytes, for nonnegative address `a`:

`block = floor(a/B)`, `offset = a mod B`, `slot = block mod S`, and `tag = floor(block/S)`.

The slot identifies *where* that block may reside; the tag determines *which* block currently occupies the slot. If two blocks have the same slot but different tags, accessing one evicts the other: a **conflict miss**. This differs from a compulsory miss (first use of a block). Real caches may be set-associative, multi-level and governed by replacement/coherence rules not represented here [2].

```python
class DirectMappedCache:
    def __init__(self, line_bytes, slots):
        if (type(line_bytes) is not int or type(slots) is not int
                or line_bytes <= 0 or slots <= 0):
            raise ValueError("positive integer geometry required")
        self.line_bytes = line_bytes
        self.slots = slots
        self.tags = [None] * slots
        self.hits = self.misses = 0

    def access(self, address):
        if type(address) is not int or address < 0:
            raise ValueError("nonnegative byte address required")
        block = address // self.line_bytes
        slot = block % self.slots
        tag = block // self.slots
        hit = self.tags[slot] == tag
        if hit:
            self.hits += 1
        else:
            self.misses += 1
            self.tags[slot] = tag
        return hit

cache = DirectMappedCache(4, 2)
trace = [0, 1, 8, 0, 4, 5, 0]
assert [cache.access(a) for a in trace] == [
    False, True, False, False, False, True, True
]
assert (cache.hits, cache.misses) == (3, 4)
```

This simulator models **one byte access per trace entry**, ignores writes, carries no data values and has no timing. It has `O(1)` modeled work per access and `O(S)` tag storage under a unit-cost arithmetic model; the code's list of tags is not a physical cache. Address 0 and address 8 map to slot 0 for 4-byte lines and two slots, forcing an eviction. Address 0 and 1 share a block, so the second access hits. The output is deterministic for this model but does **not** predict a modern CPU's cache miss rate or execution time.

## Why locality matters for algorithms and data layout

**Spatial locality** means nearby addresses are used close together, so fetching a line can satisfy several subsequent accesses. **Temporal locality** means the same blocks are revisited before eviction. A row-major dense array traversal often makes more effective use of spatial locality than chasing scattered linked-list nodes. This can make an `O(n)` scan outperform another `O(n)` algorithm that requires irregular pointer accesses. The effect depends on actual layout, cache geometry, compiler, working-set size and concurrency; benchmark claims require measurements rather than slogans [2].

A **TLB** is not a data cache: it accelerates virtual-to-physical address translation. A page fault differs from a cache miss, and a system call is not simply a slow function call. Caches, TLBs, coherence, virtual pages, memory permissions and thread scheduling are related but distinct mechanisms. The next chapter on [processes and virtual memory](/en/topics/processes-virtual-memory/) develops address translation separately. The [pipeline and branch-prediction chapter](/en/topics/cpu-pipeline-hazards-branch-prediction/) now covers modeled stalls and hazards. Cache associativity, coherent multi-core memory and hardware performance measurement still need dedicated treatment.

## Exercises and verification

1. Enumerate 8-bit representations for -128, -1, 0, 127. Prove that `signed8((x+256) % 256)` equals `x` for all `-128 <= x <= 127`.
2. Independently derive all 65,536 outcomes of byte addition using modular arithmetic. Explain why signed interpretation can disagree with the mathematical integer sum.
3. Translate 0x01020304 into four bytes under each byte order. Explain why endianness and alignment answer different questions.
4. Trace the toy machine by hand; change the second operand and find the first instruction whose result differs. Identify exactly which state becomes observable.
5. For `B=4` and `S=2`, calculate block/slot/tag for 0, 1, 4, 8, 12. Predict the cache-hit sequence before running code.
6. Construct a sequence where every access has an address different from the previous one, yet nearly all accesses hit due to spatial locality; then build a conflict-thrashing sequence.
7. Explain why neither this model nor a cache simulator proves the performance of a production database query or parallel program.
8. Classify each property as **ISA**, **microarchitecture**, **OS** or **language runtime**: register width, cache policy, page-table permissions, Python arbitrary-precision integers.

**Read next:** [Pipeline, hazards and branch prediction](/en/topics/cpu-pipeline-hazards-branch-prediction/) explains implementation timing; [Processes and virtual memory](/en/topics/processes-virtual-memory/) for translation and protection; [concurrency](/en/topics/concurrency-synchronization/) for races and locks; [complexity](/en/topics/complexity-analysis/) for abstract resource models. A chapter title does not replace independent implementation review or measurements [1][2][3].
