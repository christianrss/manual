---
id: digital-logic-gates-binary-adders
title: "Digital logic fundamentals: Boolean gates, truth tables and binary adders"
description: "Derive AND, OR, NOT and XOR from truth tables and construct verified half-adders, full-adders and fixed-width addition."
category: computer-architecture
difficulty: foundational
updated: 2026-10-12
prerequisites: [data-types-bytes-and-representation]
sources:
  - {title: "Nand2Tetris — Course, hardware construction", url: "https://www.nand2tetris.org/course", kind: "open educational course"}
  - {title: "MIT OpenCourseWare — Computation Structures", url: "https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/", kind: "university course"}
  - {title: "Python Language Reference — Binary bitwise operations", url: "https://docs.python.org/3/reference/expressions.html#binary-bitwise-operations", kind: "official language reference"}
---
Programs ultimately execute on hardware that manipulates electrical signals, but understanding a CPU starts with a smaller mathematical abstraction: **digital signals represented as 0 or 1 and logic functions mapping input bits to output bits**. This abstraction explains how arithmetic and decisions can arise from simple components. It does not require designing transistors, fabrication processes or a complete processor [1][2].

## From physical signals to logical values

A digital circuit works with physical voltages and timing. At a selected abstraction level, its input and output are interpreted as binary values. A logical 1 does not mean that every computer wire uses the same voltage; electrical encoding and acceptable noise margins depend on the implementation. For this chapter, assume stable binary inputs, ideal logical gates and no propagation delays. The model is sufficient for deriving truth tables but not for predicting real switching behavior.

A **combinational circuit** computes its outputs from the current inputs without remembering an earlier state. A sequential circuit has state and will be considered after this prerequisite. Two distinct inputs can yield the same output: a circuit is a function, not necessarily an invertible function. The engineer must describe the domain, possible outputs and combination rule before using gate names.

## Truth tables define the operators

A truth table enumerates all possible binary inputs and corresponding outputs. With two independent binary inputs a and b, there are four combinations. AND outputs 1 only when both inputs are 1. OR outputs 1 when at least one input is 1. XOR outputs 1 when exactly one is 1. NOT has only one input and reverses it [1].

| a | b | AND | OR | XOR |
|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 |
| 0 | 1 | 0 | 1 | 1 |
| 1 | 0 | 0 | 1 | 1 |
| 1 | 1 | 1 | 1 | 0 |

A truth table is stronger than an informal analogy. It specifies an operator for **every valid input**, so candidate implementations can be checked exhaustively. NAND is NOT(AND(a,b)); NOR is NOT(OR(a,b)). Either NAND or NOR can be used as a universal gate, meaning arbitrary finite Boolean functions can be assembled from it, although practical implementations combine several gate types for convenience [1][2].

## Boolean identities and circuit simplification

Boolean algebra gives identities for rearranging gates. AND with 1 leaves a unchanged; OR with 0 leaves a unchanged. Double negation restores a. The distributive identity a AND (b OR c) equals (a AND b) OR (a AND c). De Morgan's laws state NOT(a AND b) equals (NOT a) OR (NOT b), and NOT(a OR b) equals (NOT a) AND (NOT b).

These are algebraic equalities about Boolean values, not claims that physical implementations are equally fast or power efficient. One expression can require more gates or more levels of propagation than another. Check a proposed simplification using all eight combinations of three inputs before discussing physical circuit costs. Boolean identities also recur in program conditions, permissions and database predicates, but those settings may introduce other values or side effects that invalidate naïve substitutions.

## Binary addition requires both sum and carry

Adding one-bit values cannot be represented by a single output bit in all cases: 1 + 1 = 2, written as binary 10. A **half-adder** therefore emits a low-order sum bit s and a carry bit c. Its equations are s = a XOR b and c = a AND b. From the truth table, 0+0 produces (0,0); 0+1 and 1+0 produce (1,0); 1+1 produces (0,1).

A **full-adder** also accepts a carry from the less-significant position. First add a and b to obtain temporary sum p and carry c1. Then add p and carry_in, obtaining sum s and carry c2. The final carry_out is c1 OR c2. This construction is correct because a+b+carry_in = s + 2×carry_out for every possible triple of input bits. There are only eight triples, making exhaustive checking possible [1][2].

## Construct a fixed-width adder

To add unsigned w-bit values, process positions from least significant to most significant. At each position, a full-adder consumes operand bits and the carry from the previous position. The result bit goes back to that position, while the carry moves to the next one. Starting with carry=0 gives ordinary addition. A carry left after the most-significant position indicates unsigned overflow beyond the w-bit result.

For w=4, 5 is binary 0101 and 3 is 0011. The sum 8 is 1000 and produces no outgoing carry. In contrast, 15+1 produces binary 10000: the four retained result bits are 0000, and carry_out=1. The retained bits represent addition modulo 2^w, not an assertion that mathematical 15+1 equals zero.

~~~python
def bit(value):
    if type(value) is not int or value not in (0, 1):
        raise ValueError("expected binary digit 0 or 1")
    return value

def gate_not(a):
    return 1 - bit(a)

def gate_and(a, b):
    return bit(a) & bit(b)

def gate_or(a, b):
    return bit(a) | bit(b)

def gate_xor(a, b):
    return bit(a) ^ bit(b)

def half_adder(a, b):
    return gate_xor(a, b), gate_and(a, b)

def full_adder(a, b, carry_in):
    partial, carry_a = half_adder(a, b)
    result, carry_b = half_adder(partial, carry_in)
    return result, gate_or(carry_a, carry_b)

def add_fixed_width(a, b, width):
    if (type(width) is not int or width <= 0
            or type(a) is not int or type(b) is not int
            or a < 0 or b < 0 or a >= 2 ** width or b >= 2 ** width):
        raise ValueError("invalid unsigned operands or width")
    result = 0
    carry = 0
    for position in range(width):
        digit, carry = full_adder((a >> position) & 1,
                                  (b >> position) & 1, carry)
        result |= digit << position
    return result, carry

assert half_adder(1, 1) == (0, 1)
assert full_adder(1, 1, 1) == (1, 1)
assert add_fixed_width(5, 3, 4) == (8, 0)
assert add_fixed_width(15, 1, 4) == (0, 1)
assert add_fixed_width(7, 9, 4) == (0, 1)
try:
    half_adder(1, 2)
except ValueError:
    pass
else:
    raise AssertionError("nonbinary input accepted")
~~~

## Proof, assumptions and complexity

For each processed position i, maintain the invariant that the low i bits of the result equal the low i bits of a+b and that the carry is the contribution to position i from the lower positions. The full-adder identity establishes the next result bit and carry. Initially i=0, no lower bits have been processed and carry=0. After processing w positions, the result contains exactly (a+b) modulo 2^w, and the outgoing carry is 1 precisely when the unsigned sum is at least 2^w.

The algorithm performs w iterations and a constant number of gate operations per iteration: O(w) time under the standard unit-cost gate model and O(1) auxiliary scalar variables when the integer result is treated as a fixed-width register. In Python, the result integer and operand conversions can occupy O(w) bits and bit operations on unbounded integers have nonconstant cost; the model is an **idealized logical circuit**, not a Python performance benchmark [3].

A serial ripple-carry adder has a carry dependency from lower to higher positions, so its *logical depth* grows linearly with width. More advanced adder designs reduce carry delay by more complex logic, trading circuit area and power. None of those physical timing claims can be measured from the Python function.

## Signed numbers and counterexamples

Two's-complement signed addition uses the same low-level bitwise addition machinery, but interpreting overflow differs. An outgoing carry is a reliable flag for **unsigned overflow**, not by itself a signed-overflow flag. For signed addition, overflow happens when two operands with the same sign yield a result with the opposite sign, interpreted at the selected width. This distinction prevents a common error in low-level code and interview reasoning.

The function intentionally rejects negative operands, widths zero, Boolean operands and operands not representable in the chosen width. It is not a general arbitrary-precision arithmetic function. Using a masked Python `+` would reproduce the mathematical result but conceal the gate-level derivation being taught. This chapter isolates representation and correctness before instruction sets, pipelines, caches or circuit simulation.

## Exercises and verification

1. Enumerate the four input pairs and verify AND, OR and XOR by hand and with a test.
2. Check both of De Morgan's identities for all input pairs; state how they can implement one gate using another.
3. Enumerate the eight full-adder triples and prove a+b+carry_in = sum+2×carry_out.
4. Run add_fixed_width for every pair a,b from 0 through 15, width=4. Compare with `((a+b)%16, (a+b)//16)`.
5. Explain why carry_out=1 does not necessarily mean signed overflow at width four.
6. Draw the dependency chain of a four-bit ripple adder and distinguish gate count from critical-path depth.

Continue with [data representation](/en/topics/data-types-bytes-and-representation/), [Boolean logic and proof](/en/topics/logic-proofs-invariants/) and [machine instructions and cache](/en/topics/machine-representation-isa-cache/).