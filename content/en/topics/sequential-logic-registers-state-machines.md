---
id: sequential-logic-registers-state-machines
title: "Sequential logic fundamentals: clocked state, registers and finite-state machines"
description: "Derive clocked state transitions, D flip-flops, registers and finite-state machines with executable invariants and traces."
category: computer-architecture
difficulty: foundational
updated: 2026-10-12
prerequisites: [digital-logic-gates-binary-adders, programming-control-flow-functions]
sources:
  - {title: "Nand2Tetris — Project 3: Memory", url: "https://www.nand2tetris.org/project03", kind: "open educational course"}
  - {title: "MIT OpenCourseWare — Computation Structures", url: "https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/", kind: "university course"}
  - {title: "Nand2Tetris — Hardware course", url: "https://www.nand2tetris.org/course", kind: "open educational course"}
---
Combinational gates calculate an output from the inputs visible at one instant. A working computer must also **retain values between instants**: the instruction address, operand registers and intermediate status all depend on earlier events. Sequential logic adds an explicit state and a clocked rule for updating that state. Understanding it is the missing bridge from truth tables to storage and machine execution, not a requirement to build a complete CPU [1][2].

## Combinational logic versus sequential state

For combinational logic, output at time t can be described by y(t) = f(x(t)). A two-input AND gate does not remember whether the inputs were previously zero. A sequential system has an internal state q(t) and computes next state by q(t+1) = F(q(t), x(t)). An output may be calculated from state alone, as in a Moore machine, or from state and input, as in a Mealy machine. These are two common finite-state machine models, not implementation-specific Python rules.

The state is **information retained across updates**, not a historical list of every input. A state variable might be a single bit, a tuple of register bits or an index among named protocol states. The circuit's contract must say when state changes and how the next state is calculated.

## D flip-flops and the clock edge

An ideal edge-triggered D flip-flop stores one bit. Immediately before an active clock edge, its input D is sampled; immediately after that edge, the stored output Q becomes that sampled bit. Between active edges, Q remains unchanged even when D changes. In discrete time, this is Q[k+1] = D[k] at the sample edge [1][3].

A transparent level-sensitive latch is different: while its enabling level is active, input changes can pass to the output. Equating a latch with an edge-triggered flip-flop can produce timing errors. The examples below deliberately model an ideal edge-triggered device, not transistor implementation, setup/hold violations, metastability or asynchronous hardware timing.

A clock is not a Python timer. Each call to a model's tick operation represents one **logical active edge**. The code cannot infer or guarantee electrical clock frequency or propagation delay.

## Construct a width-n register

A register collects n stored bits updated at the same logical edge. With a load-enable bit L, the transition rule is Q_next = D when L=1 and Q_next = Q when L=0. This is equivalent to choosing between the old value and a new input using a multiplexer before each flip-flop. Initialization of all bits to zero here is a modeling contract, not a claim that every physical flip-flop powers on as zero.

For a 3-bit register, suppose Q=(0,0,0). An input D=(1,0,1) with load false leaves the stored value unchanged. The same input with load true on the next edge changes Q to (1,0,1). A read does not trigger an edge and must not modify state. Validate the full input bus before updating any bit so a malformed element cannot cause a partially updated register.

## Construct a finite-state counter

An n-bit unsigned counter has 2^n states, represented by integers 0 through 2^n-1. Choose the transition rule in priority order: reset forces zero; otherwise enable increments the state modulo 2^n; otherwise it holds. For a three-bit counter, the transition 7 to 0 is expected wraparound, not unhandled numerical overflow.

The order of these rules is part of the interface. If reset and enable are both asserted, **reset wins**. A counter could instead have a different reset priority or an asynchronous reset, but its truth table and transition rule must explicitly say so. The counter model is pure: given current state, bit width and controls, it produces next state without modifying a physical device.

~~~python
def bit(value):
    if type(value) is not int or value not in (0, 1):
        raise ValueError("expected one binary digit")
    return value

class ClockedRegister:
    def __init__(self, width):
        if type(width) is not int or width <= 0:
            raise ValueError("positive register width required")
        self._bits = (0,) * width

    def read(self):
        return self._bits

    def tick(self, data, load):
        if type(load) is not bool:
            raise ValueError("load must be Boolean")
        incoming = tuple(bit(x) for x in data)
        if len(incoming) != len(self._bits):
            raise ValueError("data bus width mismatch")
        if load:
            self._bits = incoming
        return self._bits

def counter_tick(value, width, reset, enable):
    if (type(value) is not int or type(width) is not int
            or type(reset) is not bool or type(enable) is not bool
            or width <= 0 or not 0 <= value < 2 ** width):
        raise ValueError("invalid counter state or control")
    if reset:
        return 0
    if enable:
        return (value + 1) % (2 ** width)
    return value

r = ClockedRegister(3)
assert r.read() == (0, 0, 0)
assert r.tick((1, 0, 1), False) == (0, 0, 0)
assert r.tick((1, 0, 1), True) == (1, 0, 1)
assert r.read() == (1, 0, 1)
assert counter_tick(7, 3, False, True) == 0
assert counter_tick(7, 3, True, True) == 0
try:
    r.tick((1, 2, 1), True)
except ValueError:
    pass
else:
    raise AssertionError("invalid bit accepted")
assert r.read() == (1, 0, 1)
~~~

## Simultaneous updates and state invariants

A synchronous register bank updates its logical state at one clock edge. If there are multiple dependent registers, each next value must be calculated using the **old** state, then all newly calculated values committed together. Sequentially mutating register A before computing register B can accidentally make B read the new A, changing the intended circuit.

For the register example, the invariant is that Q always has the declared width and each element is 0 or 1. Construction satisfies it. An invalid input causes an exception before mutation. A valid hold transition preserves Q; a valid load transition replaces it with a validated tuple. By induction every successful tick preserves the invariant.

For the counter, 0 <= value < 2^n holds by the precondition. Reset returns zero, hold returns value, and modulo increment returns a value in the same range. This proves the numerical invariant of **every valid transition**, independent of how many transitions have occurred.

## Transition tables and traces

Before implementing a state machine, enumerate states, relevant inputs and expected next states. For a counter, the full 3-bit table has eight states; reset and enable each have two possibilities. An explicit trace such as 5 → 6 → 7 → 0 with enable asserted makes wraparound observable. With enable removed, the next state remains unchanged.

A traffic light state machine can have states GREEN, YELLOW and RED, with tick events advancing deterministically. The names by themselves do not establish timing or safety: duration and sensor inputs need explicit rules. Similarly, a login screen's state machine may represent user-interface behavior, but it is not identical to a hardware clocked register. The mathematical idea of state transitions is shared while assumptions differ.

## Storage capacity, costs and failure modes

An n-bit register stores one of 2^n states and physically requires n bits of state. Under a simple gate-count model, updating each bit uses bounded work, so applying a whole-register tick costs O(n) bit operations and O(n) stored bits. A counter represented by a fixed-width hardware register updates modulo 2^n; the teaching Python integer implementation does not model the switching activity or carry circuit that realizes that arithmetic.

Real synchronous circuits must account for clock skew, propagation delays, setup and hold constraints. Metastability can arise at asynchronous boundaries; the logical model here explicitly abstracts it away. Test success establishes the correctness of the discrete transition model **only**, not that a physical circuit meets timing constraints [2].

## Exercises and verification

1. Explain why a latch and an edge-triggered D flip-flop respond differently to an input change between clock edges.
2. Write the truth table for the load-enabled one-bit register using old Q, D and load.
3. Enumerate the transitions of a 2-bit counter for all states and both enable values, with reset false.
4. Verify that reset wins if reset and enable are both true, then rewrite the contract with the opposite priority and explain the behavioral difference.
5. Model two registers A and B that exchange values at the same edge, and show why computing B after mutating A is incorrect.
6. Distinguish logical steps in the Python model from propagation delay in a physical circuit.

Continue with [Boolean gates and binary adders](/en/topics/digital-logic-gates-binary-adders/), [machine representation and instructions](/en/topics/machine-representation-isa-cache/) and [finite automata](/en/topics/formal-languages-finite-automata/).