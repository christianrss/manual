---
id: floating-point-error-compensated-summation
title: "Floating-point reasoning: rounding, cancellation and compensated summation"
description: "Analyze binary approximation, nonassociative addition and Neumaier compensated summation using exact rational oracles."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [data-types-bytes-and-representation, complexity-analysis]
sources:
  - {title: "Python tutorial — Floating-point arithmetic", url: "https://docs.python.org/3/tutorial/floatingpoint.html", kind: "official language tutorial"}
  - {title: "Python standard library — math.fsum and isclose", url: "https://docs.python.org/3/library/math.html", kind: "official library documentation"}
  - {title: "Python standard library — fractions.Fraction", url: "https://docs.python.org/3/library/fractions.html", kind: "official library documentation"}
---
Mathematical addition is associative over real numbers, but arithmetic with a fixed amount of stored precision is not. The difference matters when measurements of widely different magnitudes are combined. A program may use a mathematically correct formula and still return an inaccurate answer because **the representation and order of floating-point operations are part of the computation**. This chapter derives the error mechanism and a deliberately bounded improvement, without claiming that any approximate algorithm can guarantee exact real arithmetic [1][2].

## Binary approximation starts before the calculation

Many Python float values are represented as binary fractions with finite precision. The decimal number one tenth has no finite representation in base two. Therefore the float written as 0.1 is a nearby binary value, not the exact fraction 1/10. Printing 0.1 does not reveal all the bits of its representation. The method float.as_integer_ratio or Fraction.from_float exposes the exact rational number represented by a particular finite float [1][3].

This is *representation error*: a mathematical input must be rounded to a representable value before arithmetic begins. A separate *rounding error* can occur whenever an arithmetic result falls between representable values. Converting an already rounded float into Decimal or Fraction records the stored value; it cannot recover the unspecified real-world decimal input.

For counts of cents, integers or appropriately configured Decimal values may be more suitable. For noisy physical measurements, float is often appropriate when an error tolerance is declared. Choosing the type requires a statement of what errors the application can tolerate.

## Why floating-point addition is not associative

In exact arithmetic, (a+b)+c equals a+(b+c). In floating-point arithmetic each intermediate result may be rounded. With a=10^16, b=1 and c=-10^16, adding a and b may lose the small b completely. The following addition can then return zero, although the exact mathematical total is one.

If the values are regrouped or a more careful summation is used, the lost unit can sometimes be recovered. This is **loss of significance through cancellation**. The effect is not limited to artificially large constants: subtracting close measured quantities or accumulating millions of terms can expose similar problems.

Floating-point equality is therefore unsuitable as a universal comparison of independent approximations. The math.isclose function uses absolute and relative tolerances chosen by the caller; it does not infer the scientifically meaningful error budget [2]. A comparison near zero often needs a carefully justified absolute tolerance.

## Establish an exact reference for testing

The first rule of numerical verification is to compare against an independent representation wherever feasible. For Python finite floats, Fraction.from_float converts the represented value to an exact rational. Summing those rational values yields the exact mathematical sum of the **already rounded float inputs**, not the unknown original measurements.

This distinction is essential. An exact rational oracle can prove that a summation routine has introduced additional arithmetic error, but it cannot prove that a sensor supplied an accurate measurement. It is an independent arithmetic test, not a calibration procedure.

For large inputs, an exact rational sum may be expensive in both time and memory. It is best used on small constructed counterexamples and bounded test cases rather than as a default production data path.

## Naive accumulation and compensated accumulation

Naive summation starts at zero and repeatedly updates the total with the next term. Once a small contribution is rounded out of that total, it is usually unrecoverable. The Neumaier variant of compensated summation tracks an additional correction term. At each iteration it compares the magnitudes of the prior accumulated value and the current term to estimate the rounding contribution lost during addition.

The correction is itself represented as a float. Compensation often improves results for severe cancellation but **does not promise an exact answer for every ordering, magnitude or input set**. The built-in math.fsum maintains a more comprehensive account of partial sums and is normally the preferable general-purpose Python function when accurate summation matters [1][2].

The executable examples accept finite Python float values only. The strict type rule rejects integers and Boolean values deliberately so test cases share one representation model. If an intermediate becomes nonfinite, they raise OverflowError rather than return an infinity or NaN as a valid result.

## Executable example and cancellation counterexample

The sample defines a direct left-to-right sum and a Neumaier compensated sum with a common finite-input contract. For the sequence 10^16, 1, -10^16, the direct result is zero while compensation returns one. An independent rational sum and math.fsum also return one for these exactly representable inputs.

A second example compares the exact rational value represented by the float 0.1 with the intended mathematical fraction one tenth. These are not equal; no rearrangement of a summation loop can eliminate that initial representation error.

## A loop invariant and its limitations

For naive addition, the accumulated state after i iterations is the result of left-to-right floating additions on the first i input floats. This is an exact description of the implemented computation, not of the mathematical real-number sum.

For compensated summation, the combined state total+correction is intended to approximate the exact sum of the processed inputs. The correction update accounts for part of the rounding residual from each addition. Its algebraic derivation assumes operations follow an ordinary rounded floating-point model; finite precision applies to the correction as well. The algorithm's invariant describes its recurrence, not a universal bound of zero error.

Termination is immediate for a finite iterable: one term is processed per iteration. With n input values, both algorithms perform O(n) scalar steps and use O(1) additional state under the unit-cost floating-point model. Testing must not mistake expected improvement for a formal guarantee of monotonic accuracy on all inputs.

## Boundary cases, validation and error budgets

Nonfinite inputs need explicit handling. Infinity can obscure a finite cancellation, and NaN comparisons are false even when the other operand is also NaN. Rejecting these values is a valid application choice, not a rule for every scientific computation.

A relative tolerance alone is ill-suited when the true result is zero. A meaningful error budget may use absolute tolerance, relative tolerance, measurement uncertainty or ulp distance depending on the domain. Explain the units of the tolerance and test values near the decision boundary.

Extreme sums can overflow even when each input is finite, and the example intentionally fails in that case. The compensated method does not claim overflow-safe accumulation or correctly rounded output in every environment.

## Exercises and independent verification

1. Show the exact rational held by float 0.1 and compare it with Fraction(1,10).
2. Explain why adding 1 to 10^16 can lose information, whereas adding a quarter to a small integer may not.
3. Compare both routines and math.fsum on the constructed cancellation sequence.
4. Verify the effect of permuting the same three inputs and explain why order matters.
5. Reject NaN, infinity and a Boolean input; distinguish an invalid operand from an overflowed intermediate.
6. Choose an absolute and relative tolerance for a stated physical measurement problem and justify their units.

Continue with [data representation](/en/topics/data-types-bytes-and-representation/), [stable online variance](/en/topics/online-mean-variance-welford/) and [complexity analysis](/en/topics/complexity-analysis/).
