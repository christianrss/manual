---
id: cpu-datapath-fetch-decode-execute
title: "CPU fundamentals: datapath, control and the fetch–decode–execute cycle"
description: "Trace PC, accumulator, memory, ALU and branches using a bounded 8-bit instructional CPU with explicit instruction semantics."
category: computer-architecture
difficulty: foundational
updated: 2026-10-12
prerequisites: [digital-logic-gates-binary-adders, sequential-logic-registers-state-machines, machine-representation-isa-cache]
sources:
  - {title: "MIT 6.004 — Computation Structures: The Digital World", url: "https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/pages/c9/c9s1/", kind: "university architecture course"}
  - {title: "MIT 6.004 — Building the Beta", url: "https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/pages/c13/c13s1/", kind: "university architecture course"}
  - {title: "Nand2Tetris — Project 5 Computer Architecture", url: "https://www.nand2tetris.org/project05", kind: "open educational course"}
---
Logic gates compute Boolean functions, and clocked registers remember state. A CPU connects these ideas so that **the bits in memory select which operations happen next**. The datapath moves and transforms operands; control logic interprets instruction fields and selects the datapath action. This chapter explains those roles through an executable teaching machine before introducing instruction pipelines, caches or speculative execution [1][2].

## Architectural state and the instruction cycle

The machine has a program counter PC, an 8-bit accumulator A, sixteen byte-addressable memory cells and a halted flag. Its entire observable state is (PC,A,M,halted). The instruction located at address PC determines how to compute the next state. An instruction may read a value, write a value, change the PC or halt.

The conceptual sequence is **fetch, decode, read operands, execute, write back and update PC**. Fetch reads M[PC]. Decode splits the byte into an opcode and operand field. Read obtains data from the accumulator or memory. The ALU performs arithmetic if requested. Write-back changes the accumulator or memory as specified. The PC advances by one unless a taken branch selects another address [2].

These names describe functional stages, not necessarily separate physical clock cycles. Our interpreter executes one whole instruction per call; it is not a pipelined hardware timing model.

## An intentionally small one-byte instruction format

An instruction contains eight bits. The upper four bits encode the opcode; the lower four encode an address or immediate value between 0 and 15. The memory has sixteen byte cells with addresses 0 through 15. The supported operations are:

| Opcode | Instruction | Effect |
|---|---|---|
| 1 | LOAD addr | A becomes M[addr] |
| 2 | STORE addr | M[addr] becomes A |
| 3 | ADD addr | A becomes (A+M[addr]) mod 256 |
| 4 | JNZ addr | If A is nonzero, PC becomes addr |
| 5 | LDI value | A becomes the unsigned immediate value 0–15 |
| 6 | SUB addr | A becomes (A−M[addr]) mod 256 |
| F, operand 0 | HALT | Stop subsequent execution |

Opcode zero and other unlisted opcodes are invalid. HALT with a nonzero low nibble is also invalid. These are definitions for a **fictional teaching ISA**; hexadecimal 0x53 means LDI 3 in this model, not in RISC-V or x86. Unlike real processors, the model has no instruction alignment, interrupt state, privileges, cache or pipeline [1][3].

## Datapath components and control decisions

The PC is a register feeding a memory address selector. An instruction register conceptually holds the fetched byte during decode. The opcode bits select operations, while the lower nibble selects a data address, immediate constant or branch destination. A multiplexer conceptually chooses the ALU's input sources. The ALU adds or subtracts eight-bit values; the accumulator registers the result.

Control must also select **where the next PC comes from**: normally PC+1, or the branch operand when JNZ is taken. This distinction separates data values from control flow. STORE illustrates another destination: the accumulator is unchanged while one memory cell is overwritten. The write-enable signal is therefore conceptually different from an accumulator-write signal [1][2].

The program and data share one sixteen-cell memory in this example. Software can therefore overwrite instruction bytes with STORE; the tests deliberately place data in cells 14 and 15 away from the program. Real memory architectures may use separate instruction and data paths or address spaces, but those are design choices beyond this basic model.

## A complete executable CPU model

The constructor copies and validates all sixteen bytes so external changes to the input list cannot silently modify processor state. Every step validates the fetched opcode **before committing any state change**. A malformed instruction raises ValueError and leaves the machine unchanged. A fetch with PC outside 0–15 raises IndexError; fetching after HALT raises RuntimeError.

~~~python
class TinyCPU:
    def __init__(self, memory):
        if (len(memory) != 16 or
                any(type(byte) is not int or not 0 <= byte <= 255
                    for byte in memory)):
            raise ValueError("16 unsigned bytes required")
        self.memory = list(memory)
        self.pc = 0
        self.acc = 0
        self.halted = False

    def step(self):
        if self.halted:
            raise RuntimeError("CPU has halted")
        if not 0 <= self.pc < 16:
            raise IndexError("program counter outside memory")
        old_pc = self.pc
        instruction = self.memory[old_pc]
        opcode, operand = instruction >> 4, instruction & 15
        if opcode not in (1, 2, 3, 4, 5, 6, 15):
            raise ValueError("unknown opcode")
        if opcode == 15 and operand != 0:
            raise ValueError("invalid HALT encoding")

        next_pc = old_pc + 1
        next_acc = self.acc
        if opcode == 1:
            next_acc = self.memory[operand]
        elif opcode == 3:
            next_acc = (self.acc + self.memory[operand]) % 256
        elif opcode == 4 and self.acc != 0:
            next_pc = operand
        elif opcode == 5:
            next_acc = operand
        elif opcode == 6:
            next_acc = (self.acc - self.memory[operand]) % 256

        if opcode == 2:
            self.memory[operand] = self.acc
        self.acc = next_acc
        self.pc = next_pc
        if opcode == 15:
            self.halted = True
        return (old_pc, opcode, operand, self.pc, self.acc)

program = [0x53, 0x2F, 0x1F, 0x6E, 0x2F, 0x42, 0xF0]
program += [0] * 7 + [1, 0]
cpu = TinyCPU(program)
trace = []
while not cpu.halted:
    trace.append(cpu.step())
assert len(trace) == 15
assert cpu.memory[15] == 0 and cpu.acc == 0
assert cpu.pc == 7 and cpu.halted
~~~ 

## Trace a loop instruction by instruction

The first instruction LDI 3 initializes A=3. STORE 15 writes the counter to M[15]. LOAD 15 fetches it; SUB 14 subtracts M[14]=1; STORE 15 writes the decremented value. JNZ 2 returns to the LOAD if A is nonzero. After three iterations the counter becomes zero, the branch falls through and HALT stops execution.

The trace therefore contains two initialization instructions, three repetitions of four instructions, and one final HALT: **2+3×4+1=15 steps**. The accumulator and M[15] both finish at zero. This exercise exposes a genuine dependency: the decision to branch uses the most recent accumulator value, while the memory counter changes only on STORE.

A zero result after SUB does not set a separate zero flag here; JNZ directly examines the accumulator. This is a deliberate simplification, not a description of every real ISA.

## Invariants, errors and architectural correctness

For every valid step, the accumulator and each memory cell remain integers in [0,255]. LOAD copies an existing byte, LDI supplies at most 15, ADD/SUB reduce modulo 256, and STORE copies the accumulator. Branches select addresses 0–15. The PC after executing a nonbranch instruction may equal 16 if its former value was 15; the next attempted fetch then traps. This boundary is not an operating-system exception mechanism.

The step method validates opcodes before committing writes. Consequently an invalid instruction preserves memory, PC and accumulator. HALT is terminal under this API. This makes state transitions independently testable: given the previous state and one instruction, there is at most one defined next state.

These correctness claims concern the interpreter's **architectural transition contract**. They do not prove that an electrical CPU meets clock timing constraints, handles caches coherently or preserves precise exceptions. Those belong to separate implementation layers [2][3].

## Compare execution costs and physical implementations

Each instruction executes constant Python control-flow work for this fixed sixteen-cell memory, assuming bounded-cost integer operations. A trace of k instructions uses O(k) steps and O(k) output storage if all transitions are retained; running without storing the trace uses O(1) extra state for a fixed-size machine.

On a real processor, different instructions can have different latencies, memory accesses may miss in caches, and branches may disrupt speculative pipelines. Counting fifteen interpreter steps is **not** equivalent to measuring fifteen physical clock cycles on another CPU. The mapping from instruction semantics to microarchitectural performance is a separate problem [2].

## Exercises and verification

1. Draw connections between PC, instruction fetch, opcode decoder, accumulator, ALU and memory.
2. Decode 0x53, 0x2F and 0x42 according to this *teaching* ISA.
3. Explain why STORE modifies memory without modifying A, and why JNZ changes PC without writing memory.
4. Trace the loop after changing the initial immediate from 3 to 2. Predict its step count.
5. Verify ADD and SUB wrap at 255 and zero, respectively, and explain why this is not Python's normal unbounded arithmetic.
6. Test invalid opcode and HALT encoding; show that neither partially modifies state.

Next: [logic gates](/en/topics/digital-logic-gates-binary-adders/), [clocked registers](/en/topics/sequential-logic-registers-state-machines/), [ISA and cache](/en/topics/machine-representation-isa-cache/) and [pipelines](/en/topics/cpu-pipeline-hazards-branch-prediction/).
