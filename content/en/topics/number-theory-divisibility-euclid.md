---
id: number-theory-divisibility-euclid
title: "Number theory fundamentals: divisibility, GCD and the Euclidean algorithm"
description: "Derive divisibility, the Euclidean algorithm and Bézout coefficients with proofs, signed inputs and independent exercises."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [logic-proofs-invariants, complexity-analysis]
sources:
  - {title: "MIT 6.1200J — Mathematics for Computer Science", url: "https://ocw.mit.edu/courses/6-1200j-mathematics-for-computer-science-spring-2024/", kind: "university course"}
  - {title: "MIT 6.042J — Number Theory lectures", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-fall-2010/", kind: "university course"}
  - {title: "Python math.gcd and math.lcm", url: "https://docs.python.org/3/library/math.html", kind: "official library documentation"}
---
Number theory studies mathematical properties of integers. For programming, its most useful introductory question is not how to factor a gigantic number, but **whether one integer divides another and what that implies for algorithms**. Array strides, repeating schedules, rational fractions and modular computations use the same basic arithmetic. The Euclidean algorithm provides an unusually clear example of turning a mathematical invariant into a terminating, efficient program [1][2].

## Integers, divisibility and factors

For integers a and b, with a nonzero, a divides b if there is an integer k such that b = a times k. We write a | b. For example, 6 divides 42 because 42 = 6 times 7. The number 6 does not divide 43 because no integer multiplier can produce 43. Divisibility is a property of integers, not floating-point approximations. A division returning a rounded floating number is not a proof of divisibility.

If d divides a and b, then d divides every integer linear combination ax + by. Indeed, if a = du and b = dv, then ax+by=d(ux+vy). This single observation is central to the greatest common divisor, Bézout's identity, and solving linear equations over integers. The special integer zero deserves explicit treatment: every nonzero integer divides zero; zero divides only zero under the equation-based definition, although many elementary texts explicitly exclude zero as a divisor.

## Greatest common divisor and the zero cases

For integers a and b, not both zero, gcd(a,b) is the **largest positive integer** dividing both. One defines gcd(0,0)=0 by convention; this is not a positive common divisor maximum. gcd(a,0)=|a| when a is nonzero, and negative signs do not change the positive result. In Python the standard math.gcd operation follows these conventions [3].

Numbers a and b are coprime when gcd(a,b)=1. Coprime does not mean both are prime: 8 and 15 are composite but coprime. The least common multiple, lcm(a,b), is the smallest positive common multiple for nonzero values and is conventionally 0 when either input is 0. For nonzero integers, gcd(a,b) times lcm(a,b) equals |ab|. This identity helps reason about periods that repeat together.

## Why subtraction and remainder preserve GCD

Suppose a = qb + r, where q and r are integers and 0 <= r < b for positive b. Any integer dividing both a and b also divides r = a - qb. Conversely, any integer dividing b and r divides a = qb + r. Thus the set of common positive divisors is unchanged: gcd(a,b)=gcd(b,r). This is the Euclidean invariant [1][2].

For 48 and 18, integer division gives 48=2 times 18+12. Then 18=1 times 12+6; finally 12=2 times 6+0. Therefore gcd(48,18)=6. Every step reduces the nonnegative remainder, and the algorithm stops at remainder zero. The preceding nonzero remainder is the answer.

This reasoning avoids searching all possible factors of a huge number. It also explains correctness without depending on language-specific syntax. The common incorrect implementation that subtracts the smaller number indefinitely when one input is zero does not terminate; the remainder formulation and the explicit zero cases avoid it.

## Bézout's identity and extended Euclid

A stronger result states that when a and b are not both zero, there exist integers x and y such that ax + by = gcd(a,b). For 48 and 18, one solution is 48 times (-1) plus 18 times 3 = 6. The coefficients are not unique. The extended Euclidean algorithm finds one valid pair while computing the gcd, by tracking how each remainder is expressed as a linear combination of the original operands [1][2].

Maintain two remainder values r0 and r1, together with coefficient pairs (s0,t0) and (s1,t1). The invariant is r0 = s0 A + t0 B and r1 = s1 A + t1 B, where A=|a| and B=|b|. A quotient step subtracts q times the second equation from the first, producing new remainder and new coefficients. Once the second remainder reaches zero, r0 is the gcd and its coefficients certify the identity. For signed inputs, adjust coefficients back to the original signs of a and b.

~~~python
def euclid_gcd(a, b):
    if type(a) is not int or type(b) is not int:
        raise TypeError("integer arguments required")
    x, y = abs(a), abs(b)
    while y:
        x, y = y, x % y
    return x

def bezout(a, b):
    """Return (g, x, y), with g >= 0 and a*x + b*y == g."""
    if type(a) is not int or type(b) is not int:
        raise TypeError("integer arguments required")
    if a == 0 and b == 0:
        return (0, 0, 0)
    old_r, r = abs(a), abs(b)
    old_s, s = 1, 0
    old_t, t = 0, 1
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
        old_t, t = t, old_t - q * t
    sign_a = -1 if a < 0 else 1
    sign_b = -1 if b < 0 else 1
    return (old_r, old_s * sign_a, old_t * sign_b)

def least_common_multiple(a, b):
    g = euclid_gcd(a, b)
    return 0 if g == 0 else abs((a // g) * b)

assert euclid_gcd(48, 18) == 6
assert euclid_gcd(0, 0) == 0
assert euclid_gcd(-24, 18) == 6
assert bezout(0, 0) == (0, 0, 0)
for a, b in ((48, 18), (17, 31), (0, -7), (-9, -6)):
    g, x, y = bezout(a, b)
    assert g == euclid_gcd(a, b)
    assert a * x + b * y == g
assert least_common_multiple(12, 18) == 36
assert least_common_multiple(0, 5) == 0
try:
    euclid_gcd(True, 2)
except TypeError:
    pass
else:
    raise AssertionError("Boolean input was accepted")
~~~

## Proof of termination and complexity

After converting to nonnegative values, each nonfinal iteration replaces remainder r1 with r0 modulo r1, a nonnegative integer strictly smaller than r1. This supplies a decreasing nonnegative variant, so the loop terminates. The common-divisor invariant proves that replacing (r0,r1) with (r1,r0 modulo r1) does not change the gcd. At termination, gcd(r0,0)=r0.

For nonzero inputs with maximum absolute magnitude M, Euclid uses O(log M) remainder iterations; the slowest classes of inputs are related to consecutive Fibonacci numbers [1]. Under the unit-cost arithmetic model this is O(log M) time and O(1) scalar variables. For arbitrary-precision integers, modulo and multiplication are not constant-cost as M grows: **bit complexity is a separate question**. The code stores a constant number of Python integers, whose sizes can depend on the operand magnitudes.

Bézout coefficients may be negative. The extended algorithm verifies them by substitution, not by assuming an output is trustworthy. For the all-zero input, the implementation explicitly returns (0,0,0), a convention that preserves 0 times 0 plus 0 times 0 = 0.

## Integer equations and practical interpretations

Consider ax+by=c where a,b,c are integers. If at least one of a,b is nonzero, a solution with integer x,y exists **if and only if gcd(a,b) divides c**. Necessity follows because every integer combination of a and b is a multiple of the gcd. Sufficiency follows by multiplying Bézout coefficients by c/g when g=gcd(a,b) divides c.

For example, 12x+18y=30 is solvable because gcd(12,18)=6 and 6 divides 30. In contrast, 12x+18y=31 has no integer solution. If a=b=0, solutions exist only when c=0; this degenerate case cannot be handled by dividing by gcd(0,0)=0. State these edge cases in an API, not in an untested comment.

When periodic tasks repeat every 12 and 18 units, their positive common repetition period is lcm(12,18)=36. The arithmetic says when schedules line up **under an ideal integer-time model**; it does not model time zones, clock drift, network delays, or production scheduling guarantees.

## Counterexamples, verification and exercises

The equality gcd(a,b)=a modulo b is false in general: gcd(48,18)=6 while 48 modulo 18=12. Coprimality does not imply primality, and a remainder operation with a negative divisor may follow language-specific conventions. Normalizing signs before using the Euclidean recurrence makes the proof easier to transport between programming languages.

An independent small-input oracle can enumerate positive candidate divisors of both magnitudes and choose the largest. Its poor speed is acceptable for testing. Compare every pair in a small symmetric range, including zero and negatives, with the Euclidean implementation and the standard math.gcd function [3]. Validate Bézout by recomputing ax+by.

## Exercises and verification

1. Perform the remainder sequence for gcd(252,198) by hand and compute one pair of Bézout coefficients.
2. Prove that the common divisors of a,b equal those of b,a-qb for any integer q.
3. Compare the algorithm to an exhaustive divisor oracle for every a,b between -20 and 20.
4. Give an example of two nonprime integers that are coprime.
5. Decide whether 14x+21y=22 admits an integer solution, and justify using the gcd.
6. Explain why iteration count O(log M) is not necessarily the full bit-operation cost.

Follow with [modular arithmetic](/en/topics/modular-arithmetic-inverses-exponentiation/), [proofs and invariants](/en/topics/logic-proofs-invariants/) and [complexity](/en/topics/complexity-analysis/).