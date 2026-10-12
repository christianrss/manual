---
id: online-mean-variance-welford
title: "Numerically stable statistics: online mean and Welford variance"
description: "Derive one-pass mean and variance updates, distinguish sample and population denominators and test against exact fractions."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [floating-point-error-compensated-summation, discrete-counting-probability]
sources:
  - {title: "Welford (1962) — Corrected sums of squares and products", url: "https://doi.org/10.1080/00401706.1962.10490022", kind: "original research paper"}
  - {title: "Python standard library — statistics", url: "https://docs.python.org/3/library/statistics.html", kind: "official Python documentation"}
  - {title: "Python tutorial — Floating-point arithmetic", url: "https://docs.python.org/3/tutorial/floatingpoint.html", kind: "official language tutorial"}
  - {title: "Python standard library — fractions", url: "https://docs.python.org/3/library/fractions.html", kind: "official Python documentation"}
---
Mean and variance are basic statistical quantities, but implementing their formulas literally can produce severe errors in floating-point arithmetic. The problem becomes visible when measurements have **large common offsets and relatively small differences**. Welford's one-pass recurrence computes a running mean and a corrected sum of squared deviations without subtracting two nearly equal large second moments [1][2].

## Define mean and variance precisely

For n observations x1 through xn, the arithmetic mean is the sum divided by n. The population variance is the average squared distance from that mean, with denominator n. The sample variance uses denominator n-1 when n is greater than one. These are different mathematical definitions, not interchangeable output labels.

An empty sequence has no arithmetic mean under this contract. A sequence containing a single value has a valid mean and population variance zero, but no sample variance using the n-1 denominator. This chapter chooses to return None for that unavailable sample variance rather than silently divide by zero.

All observations in the executable model must be finite Python float values. The restriction avoids mixing arbitrary integer precision, decimals and special infinities into a single unstated representation rule.

## Why the direct second-moment identity is dangerous

An exact mathematical identity is variance = mean of squared values minus square of the mean. It is tempting to compute a single sum of x and a single sum of x squared and subtract the two resulting large numbers. Yet when observations are close to a large baseline, those quantities are nearly equal and their subtraction loses significant digits [3].

Consider three exact binary64-representable values 10^12+0.25, 10^12+0.50 and 10^12+0.75. Their mean is 10^12+0.50. Their deviations are -0.25, 0 and 0.25. The sum of squared deviations is exactly 0.125, so population variance is 1/24 and sample variance is 1/16.

The expression mean(x squared)-mean(x)^2 instead subtracts two quantities around 10^24 to obtain a result smaller than one. Under ordinary float rounding, it can produce zero or a grossly incorrect value. This is not evidence that the mathematical identity is false; it demonstrates that an algebraically equivalent expression can be numerically unstable.

## Derive the online mean recurrence

Assume n-1 observations have mean m. After receiving x, the new mean is ((n-1)m+x)/n. Rearranging gives new_mean = m+(x-m)/n. This update needs the previous mean, the new observation and the count. No list of historical observations is necessary.

Let delta=x-m. After computing the new mean, define delta2=x-new_mean. Welford's corrected sum of squares updates by new_M2 = old_M2+delta*delta2 [1]. The variable M2 tracks the sum of squared differences from the current mean in exact arithmetic.

Using delta and delta2 avoids directly computing two huge second moments and subtracting them. It does not make every intermediate operation exact: the mean, delta, delta2 and correction still use finite-precision arithmetic.

## Prove the corrected-squares update

Before the new observation, assume M2 equals the sum of (xi-m)^2 for the first n-1 values. The new mean differs by delta/n. When existing deviations are recentered around the new mean, their cross term sums to zero because the deviations from m add to zero.

The shift of existing observations contributes (n-1)*(delta/n)^2. The new observation contributes (delta*(n-1)/n)^2. Their combined contribution simplifies to delta^2*(n-1)/n, which is exactly delta*(x-new_mean). Therefore adding delta*delta2 produces the corrected sum of squares for all n observations.

The invariant initially holds with n=0, mean=0 and M2=0 as internal state. This initial mean is not an externally defined statistical mean for empty input. Each accepted value extends the invariant, and division at the end yields population or sample variance according to the chosen denominator.

## Executable state and failure boundaries

The implementation creates an accumulator containing count, running mean and M2. An add operation validates the new value and computes the proposed updated state into local variables. It checks for nonfinite intermediate results **before assigning to object fields**. Thus a rejected value or detected arithmetic overflow leaves the previous state unchanged.

This is an exception-safety guarantee, not a promise that overflow can always be avoided. For example, subtracting large finite values of opposite signs can itself overflow the finite float range. The example signals that failure rather than attempting to produce a misleading result.

After receiving at least one valid observation, summary returns count, mean, population variance and sample variance or None. Repeated summary calls do not modify state; this is useful when observing a stream while data collection continues.

## Verify using exact rational arithmetic

Python fractions can represent each finite input float exactly with Fraction.from_float [4]. For small test sequences, calculate the exact rational mean and squared deviations from those represented input values, then convert the final rational reference to float for comparison.

This reference answers a narrow question: did the online float algorithm approximate the exact statistics of its float inputs reasonably well? It cannot recover the unknown original real-world measurements rounded before collection. A correct statistical algorithm does not automatically establish unbiased sampling, representative datasets or sound causal conclusions.

The example with quarter-unit differences is particularly useful because its observations are exactly representable and its expected population/sample variances can be derived by hand. Compare both numerical outputs against 1/24 and 1/16 with an explicit tolerance.

## Complexity and numerical guarantees

An online update performs a constant number of arithmetic operations and stores three scalar fields: processing n observations costs O(n) time and O(1) auxiliary storage under the unit-cost model. Storing all observations to recompute variance from scratch would require O(n) memory, though a two-pass algorithm can also be accurate when the data is available for rereading.

Welford's recurrence is usually much better conditioned than subtracting large raw second moments, but it is **not universally exact**. Finite precision can still affect results, and adverse ranges can overflow. Sample variance is not defined for n less than two under this interface; an API should never silently substitute the population variance.

Units matter: if observations are measured in volts, variance is measured in squared volts. Standard deviation, obtained as the square root of variance, restores the original units. Neither value establishes that the underlying measurement process is reliable.

## Exercises and independent verification

1. Calculate both variances by hand for the three quarter-offset observations.
2. Derive the online mean recurrence from the ordinary mean formula.
3. Prove the corrected-sum-of-squares update using the zero sum of deviations.
4. Compare the direct second-moment identity with Welford's method for large-offset inputs.
5. Verify that empty input raises and a single observation has no sample variance.
6. Compare small sequences with an exact Fraction oracle; specify tolerances and explain the remaining floating-point error.

Continue with [floating-point error](/en/topics/floating-point-error-compensated-summation/), [exact probability](/en/topics/discrete-counting-probability/) and [data representation](/en/topics/data-types-bytes-and-representation/).
