---
id: modular-arithmetic-inverses-exponentiation
title: "Modular arithmetic: congruences, inverses and fast exponentiation"
description: "Derive congruences, modular inverses and repeated squaring with correctness invariants and exhaustive small-number tests."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [number-theory-divisibility-euclid, complexity-analysis]
sources:
  - {title: "MIT 6.1200J — Mathematics for Computer Science", url: "https://ocw.mit.edu/courses/6-1200j-mathematics-for-computer-science-spring-2024/", kind: "university course"}
  - {title: "MIT 6.042J — Mathematics for Computer Science", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/", kind: "university textbook"}
  - {title: "Python built-in pow", url: "https://docs.python.org/3/library/functions.html#pow", kind: "official language documentation"}
---
Modular arithmetic treats integers with the same remainder as equivalent. It turns unbounded integers into a finite number of residue classes without discarding the ordinary rules of addition and multiplication. This foundation appears in cyclic arrays, periodic schedules, hashing and the mathematics underlying public-key cryptography. The central requirement is to understand **which operations preserve congruence and when division is actually permitted** [1][2].

## Define congruence before computing remainders

For a positive modulus m, integers a and b are congruent modulo m when m divides a-b. Write a ≡ b (mod m). For example, 17 ≡ 5 (mod 12) because 17-5=12. Also -1 ≡ 11 (mod 12) because -1-11=-12. Congruence is an equivalence relation: reflexivity is immediate, symmetry follows by changing the sign, and transitivity follows by adding multiples of m [1].

The residue classes modulo m partition the integers into exactly m distinct classes, conventionally represented by 0 through m-1. Remainder operators choose representatives; languages may differ in the sign of a remainder involving negative operands. In Python, for positive m, a % m produces the standard nonnegative representative. The mathematical equivalence relation is independent of this programming-language choice.

## Why addition and multiplication work on residues

If a ≡ b modulo m and c ≡ d modulo m, then a+c ≡ b+d and ac ≡ bd modulo m. For the multiplication proof, write a=b+km and c=d+lm. Expanding gives ac=bd+m(bl+dk+klm), so ac-bd is divisible by m. Therefore reducing intermediate values modulo m preserves the final residue of sums and products [1][2].

For modulus 7, 10 ≡ 3 and 12 ≡ 5. Their product 120 ≡ 15 ≡ 1 modulo 7. Multiplying the smaller representatives 3 times 5 produces the same residue. This property lets algorithms avoid keeping excessively large intermediate results when the representation and arithmetic operations are chosen accordingly.

Congruence is not ordinary equality: a≡b does not imply a=b as integers. Likewise, the modulo operation alone is not encryption. Mapping a large set of values into a small set of residue buckets necessarily permits collisions.

## Modular division requires an inverse

For ordinary nonzero real numbers, division by a is multiplication by one over a. In modular arithmetic, division by a requires an integer x satisfying a times x ≡ 1 modulo m. Such a number is a **multiplicative inverse**. It exists exactly when gcd(a,m)=1, a consequence of Bézout's identity from the previous chapter [1][2].

For modulus 11, the inverse of 3 is 4 because 3 times 4 equals 12, congruent to 1. For modulus 4, the number 2 has no inverse: every product 2x is even and cannot be congruent to 1. Cancelling a common factor from a congruence is therefore unsafe unless the relevant coprimality condition holds.

The extended Euclidean algorithm produces integers x,y with ax+my=gcd(a,m). When the gcd is 1, x modulo m is the inverse. The executable example uses the same remainder-preserving recurrence, tracking the coefficient of the initial residue.

## Linear congruences and invalid cancellation

The congruence ax ≡ b modulo m asks whether m divides ax-b. Equivalently, the integer equation ax-my=b must be solvable. Let g=gcd(a,m). A solution exists if and only if g divides b. When g=1, exactly one residue class solves the equation; its representative is inverse(a) times b modulo m. When g>1 divides b, there are exactly g distinct solutions among the m residue classes [1].

For 2x ≡ 2 modulo 4, both x=1 and x=3 are solutions. Cancelling 2 as if working with real numbers and keeping modulus 4 would incorrectly discard one. Divide a, b and m by g, solve the reduced equation modulo m/g, and then lift that solution to the g residues modulo m.

This is a mathematical reason for explicit failure behavior in an inverse API. Returning an arbitrary value for noninvertible inputs is not a reasonable fallback, and treating the absence of an inverse as zero would confuse failure with a valid residue.

## Derive exponentiation by repeated squaring

To calculate the residue of a raised to the nonnegative exponent e, a direct loop can perform e multiplications. Binary exponentiation instead follows the binary digits of e. Start with accumulator 1 and factor a modulo m. When the current exponent is odd, multiply the accumulator by the factor. Square the factor, then replace e by its integer half. The remaining exponent is cut roughly in half in each iteration.

For 2^10 modulo 17, the binary expansion of 10 is 1010. Its selected powers are 2^2=4 and 2^8=256. Their product is 1024, whose residue modulo 17 is 4. Reducing after intermediate multiplications gives exactly that same residue without constructing a gigantic power. The technique is based on elementary algebra, not a special CPU instruction [1][3].

~~~python
def mod_inverse(a, modulus):
    if type(a) is not int or type(modulus) is not int or modulus <= 1:
        raise ValueError("integers and modulus > 1 required")
    old_r, r = modulus, a % modulus
    old_t, t = 0, 1
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_t, t = t, old_t - q * t
    if old_r != 1:
        raise ValueError("modular inverse does not exist")
    return old_t % modulus

def modular_power(base, exponent, modulus):
    if (type(base) is not int or type(exponent) is not int
            or type(modulus) is not int or exponent < 0 or modulus <= 1):
        raise ValueError("invalid arguments")
    result = 1
    factor = base % modulus
    while exponent:
        if exponent % 2 == 1:
            result = (result * factor) % modulus
        factor = (factor * factor) % modulus
        exponent //= 2
    return result

assert mod_inverse(3, 11) == 4
assert mod_inverse(-3, 11) == 7
assert modular_power(2, 10, 17) == 4
assert modular_power(-2, 3, 5) == 2
assert modular_power(0, 0, 7) == 1
for value, modulus in ((2, 4), (0, 7)):
    try:
        mod_inverse(value, modulus)
    except ValueError:
        pass
    else:
        raise AssertionError("noninvertible value accepted")
try:
    modular_power(2, -1, 7)
except ValueError:
    pass
else:
    raise AssertionError("negative exponent accepted")
~~~

## Correctness invariants and termination

For modular inversion, each remainder of extended Euclid is an integer linear combination of m and the normalized original a. If the final gcd is 1, its associated coefficient t satisfies a times t ≡1 modulo m. If gcd exceeds 1, an inverse would contradict the fact that every combination remains divisible by that common divisor.

For exponentiation, let A be the original base and E the original exponent. The invariant is accumulator times factor raised to the remaining exponent ≡ A^E modulo m. It holds initially with accumulator 1. If the exponent is odd, transferring a factor into the accumulator preserves the equality. Squaring the factor and taking the integer half of the remaining exponent maintains the invariant. At termination, the exponent is zero, leaving the required residue.

For E>0 the exponentiation uses O(log E) iterations with a constant number of modular multiplications each. This is O(log E) time under unit-cost arithmetic and O(1) scalar variables. In actual arbitrary-precision arithmetic, the cost of multiplication also depends on the bit length of the modulus. At exponent zero, the implementation returns the empty-product identity 1; it thus uses 0^0=1 as a programming convention. The contract intentionally excludes modulus 1.

## Security limits, counterexamples and exercises

A base can be negative because its residue modulo positive m is defined; this example forbids negative exponents, which would require a separate inverse-existence rule. Python's built-in three-argument pow is an independent reference for modular powers and supports inverse-based negative exponentiation under documented conditions [3].

This implementation branches on exponent bits and is **not constant-time hardened cryptographic software**. Secret-bearing cryptographic operations require reviewed libraries, parameter validation and side-channel analysis. Hash bucket indices produced by remainders do not guarantee uniform distributions or resistance to collisions.

## Exercises and verification

1. Prove that congruence modulo a positive m is reflexive, symmetric and transitive.
2. Use Euclid to find inverses of 3 modulo 11 and 5 modulo 12, and a case without an inverse.
3. Solve 6x ≡ 8 modulo 14 and list all solutions among residues 0 to 13.
4. Trace the accumulator, factor and exponent for 3^13 modulo 7.
5. Compare modular_power with Python pow for all bases -10 to 10, exponents 0 to 20 and moduli 2 to 20 [3].
6. Explain why cancelling 2 in 2x ≡ 2 modulo 4 loses one valid result.

Continue with [Euclid and divisibility](/en/topics/number-theory-divisibility-euclid/), [discrete relations](/en/topics/discrete-relations-orders/) and [algorithm complexity](/en/topics/complexity-analysis/).