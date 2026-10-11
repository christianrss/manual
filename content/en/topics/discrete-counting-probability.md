---
id: discrete-counting-probability
title: "Discrete Mathematics: Sets, Counting and Exact Probability"
description: "Prove counting identities, distinguish arrangements and combinations, derive conditional probability, Bayes and expected values using exact fractions and tested enumerations."
category: foundations
difficulty: foundational
updated: 2026-10-10
prerequisites: [logic-proofs-invariants, programming-semantics-contracts]
sources:
  - {title: "MIT 6.042J — Mathematics for Computer Science", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/", kind: "university open course"}
  - {title: "MIT 6.042J — Counting and Probability Readings", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/pages/readings/", kind: "university open textbook contents"}
  - {title: "Stanford CS109 — Probability for Computer Scientists", url: "https://web.stanford.edu/class/cs109/", kind: "university probability course"}
  - {title: "Python itertools documentation", url: "https://docs.python.org/3/library/itertools.html", kind: "official library reference"}
  - {title: "Python fractions documentation", url: "https://docs.python.org/3/library/fractions.html", kind: "official exact arithmetic reference"}
---
Discrete mathematics supplies the precise language for finite data structures, input spaces, algorithmic lower bounds, hashing arguments and randomized algorithms. A proof about a program requires defined sets, explicit choices about ordering and replacement, and a probability model whose outcomes have stated weights. The earlier [logic and invariants](/en/topics/logic-proofs-invariants/) chapter establishes proof obligations; [programming semantics](/en/topics/programming-semantics-contracts/) establishes executable contracts. This chapter extends those foundations with **finite combinatorics and probability**, following MIT's mathematics-for-computer-science syllabus [1][2].

A finite exhaustive test can validate an identity across many small cases, but it cannot establish a theorem for all natural numbers. The text gives algebraic/combinatorial arguments; Python serves as a separately executable check. Examples use **exact rational arithmetic**, not Monte Carlo estimation or assumptions about real-world birthday distributions.

## Sets, subsets and inclusion–exclusion

A set contains **distinct elements**, without multiplicity or a defined order. A finite sequence may instead contain repeated occurrences, and a multiset preserves multiplicity without necessarily preserving order. These distinctions matter for arrays, hashes and database queries: a list of repeated customer IDs is not mathematically the same object as the set of unique IDs.

For two finite sets `A` and `B`, count their elements separately. Members of the intersection `A ∩ B` are counted twice. Correcting that double count gives

`|A ∪ B| = |A| + |B| − |A ∩ B|`.

This is **inclusion–exclusion for two sets**, not a rule that generalizes by simply adding three sizes. For three sets, add singleton sizes, subtract every pairwise intersection and **add back** the triple intersection. The sign alternation counts each element exactly once. The proof can be performed element by element: an item appearing in exactly `r` sets receives total coefficient `sum((-1)^(j+1) * C(r,j), j=1..r) = 1`.

Every subset of a finite set of size `n` corresponds uniquely to a binary choice per element: include or exclude. Therefore its power set has `2^n` elements. This explains why enumerating **all** subsets becomes exponential even when the input list is small. A Python set itself does not make subset enumeration cheap [1][2].

## Rule of product, rule of sum and the pigeonhole principle

If a task selects one of `a` options and then independently one of `b` available options **for every first choice**, there are `a×b` ordered pairs. The rule of product requires the second count to be consistently `b`; if later choices depend on earlier ones, sum the appropriate branch products instead. For disjoint alternatives `A` or `B`, the number of outcomes is `|A|+|B|`; for overlapping alternatives inclusion–exclusion is necessary.

The **pigeonhole principle** states: distributing `n+1` items among `n` containers forces at least one container to hold two or more items. A proof by contradiction assumes every container holds at most one, giving capacity at most `n`. Generalizing, placing `m` items into `n>0` containers forces some container to have at least `ceil(m/n)` items. This is a deterministic guarantee, not a probabilistic expectation.

Applications include collision inevitability when the number of distinct inputs exceeds available hash values and worst-case occupancy bounds. The principle alone does **not** determine average hash performance: that depends on hash distribution, adversarial choices and table management.

## Arrangements versus combinations

Select `k` **distinct objects** from `n` distinguishable objects.

If **order matters** and objects cannot repeat, the first position has `n` options, the next `n−1`, and so on. Therefore the number of arrangements is

`P(n,k) = n!/(n−k)!`, for `0≤k≤n`.

If **order does not matter**, each chosen `k`-element subset corresponds to `k!` permutations, so

`C(n,k) = n!/(k!(n−k)!)`.

By symmetry, `C(n,k)=C(n,n−k)`: choosing elements to keep is equivalent to choosing those to omit. Pascal's identity `C(n,k)=C(n−1,k−1)+C(n−1,k)` follows by splitting all `k`-subsets according to whether they contain one distinguished element. For `k>n`, no selection without replacement is possible, so both counts are zero by the API contract; for `k=0`, there is exactly one empty choice.

Allowing repetition changes the count: `n^k` ordered sequences of length `k` drawn **with** replacement, while multisets of size `k` from `n` categories number `C(n+k−1,k)` for `n>0`. Mixing the rules produces common interview errors. The cost of enumerating outcomes is also different from the cost of computing how many exist.

## Executable counting identities

The functions below reject negative or nonintegral inputs, including Python `bool`, and use an iterative multiplicative formula rather than computing three potentially enormous factorials. The loop maintains an integer binomial coefficient for each partial product. Arithmetic is exact because `C(n−k+i,i)` is an integer at every step.

~~~python
from math import factorial
from itertools import product

def choose(n, k):
    """Unordered distinct k-subsets from n distinguishable objects."""
    if type(n) is not int or type(k) is not int or n < 0 or k < 0:
        raise ValueError("n and k must be nonnegative integers")
    if k > n:
        return 0
    k = min(k, n - k)
    count = 1
    for i in range(1, k + 1):
        count = count * (n - k + i) // i
    return count

def arrangements(n, k):
    """Ordered k-tuples chosen without replacement."""
    if type(n) is not int or type(k) is not int or n < 0 or k < 0:
        raise ValueError("n and k must be nonnegative integers")
    if k > n:
        return 0
    count = 1
    for i in range(k):
        count *= n - i
    return count

assert choose(5, 2) == 10
assert arrangements(5, 2) == 20
assert choose(0, 0) == arrangements(0, 0) == 1
assert choose(4, 7) == arrangements(4, 7) == 0
assert choose(8, 3) == choose(8, 5) == 56
assert sum(choose(5, k) for k in range(6)) == 2 ** 5

def union_cardinality(a, b):
    if not isinstance(a, (set, frozenset)) or not isinstance(b, (set, frozenset)):
        raise ValueError("finite sets required")
    return len(a) + len(b) - len(a.intersection(b))

assert union_cardinality({1, 2, 3}, {3, 4}) == 4
~~~

After selecting the smaller of `k` and `n−k`, `choose` executes `O(min(k,n−k))` iterations, whereas `arrangements` executes `O(k)` multiplications. These bounds count **arithmetic operations**; very large integers have nonconstant bit-level multiplication cost. Do not assert constant-time arithmetic for arbitrarily large `n`. Using the standard library's `itertools.combinations` and `itertools.permutations` to enumerate small cases provides an **independent** way to test the result without reusing the multiplicative formula [4].

## Probability spaces need specified weights

A finite probability space has a set of possible outcomes `Ω` with total weight one. If outcomes are equally likely, `P(A)=|A|/|Ω|` for event `A⊆Ω`. Without the equally-likely assumption, counting outcomes gives the wrong answer: for a biased coin, heads and tails form two outcomes but do not both have probability one half.

For events `A`, `B` with `P(B)>0`, conditional probability is

`P(A|B)=P(A∩B)/P(B)`.

Two events are **independent** when `P(A∩B)=P(A)P(B)`; independence must not be confused with **disjointness**. Nonempty disjoint events of positive probability cannot be independent, because their intersection has probability zero but the product of their probabilities is positive.

Consider two fair six-sided dice. `A` is “sum at least ten”: six of the 36 ordered outcomes. `B` is “first die at least five”: 12 outcomes. Five outcomes satisfy both events, so `P(A|B)=5/12` while `P(A)=1/6`; the events are dependent. The sample space uses ordered pairs even though a die is physically indistinguishable from another only in unrelated experiments.

## Birthday collisions, expectation and the assumptions behind them

Suppose `r` independent draws are made **uniformly with replacement** from `d` possible labels. The probability that no two draws collide is

`P(no collision) = product((d−i)/d, i=0..r−1)`, provided `r≤d`.

The desired collision probability is **one minus** that quantity, because “collision” and “all distinct” are complementary events. If `r>d`, a collision is certain by the pigeonhole principle. Under a simplified 365-equally-likely-birthdays model, 23 people already yield a collision probability greater than one half. This does **not** model leap days, demographic seasonality or dependence between actual births [2][3].

The **expected number of distinct labels** has another proof: for each label `j`, define `I_j=1` if it appears at least once, else zero. Then `D=sum(I_j)`. By linearity of expectation, `E[D]=sum(E[I_j])`, and `E[I_j]=1−((d−1)/d)^r`. Hence `E[D]=d(1−(1−1/d)^r)`. The indicators are **not independent**, yet expectation still adds: independence is unnecessary for linearity. Expected distinct labels are not the same quantity as the chance of *any* collision.

## Bayes' rule and the base-rate trap

For a diagnostic-style binary classifier, let `p=P(condition)`, `s=P(positive|condition)` (sensitivity) and `f=P(positive|no condition)` (false-positive rate). By splitting positive results according to whether the condition exists,

`P(condition|positive)=ps/(ps+(1−p)f)`.

This is Bayes' rule applied to a two-branch partition. The denominator is the **total** probability of a positive result, not just the true-positive branch. With prevalence 1%, sensitivity 90% and false-positive rate 5%, the posterior probability of a condition after a positive result is exactly `2/13`, about 15.4%, rather than 90%. This is a generic probability exercise, not medical advice or an actual test-performance estimate [3].

The conditioned event must have **positive probability**. If both the true-positive and false-positive mass are zero, no positive result can occur under the model and the conditional probability is undefined. The function below raises instead of silently dividing by zero or inventing an answer.

## Exact finite-probability model

The next examples use `fractions.Fraction` to avoid floating-point rounding hiding disagreements with finite combinatorial identities. Input probabilities must be `Fraction` instances in `[0,1]`. Conditional events must be explicit subsets of a finite set, with a nonempty conditioning event. Invalid domains raise `ValueError`. The functions produce exact outcomes; they make **no random draws**.

~~~python
from fractions import Fraction
from itertools import product

def collision_probability(days, people):
    """Independent uniform draws with replacement from days choices."""
    if (type(days) is not int or days <= 0
            or type(people) is not int or people < 0):
        raise ValueError("positive days and nonnegative people required")
    if people > days:
        return Fraction(1)
    no_collision = Fraction(1)
    for i in range(people):
        no_collision *= Fraction(days - i, days)
    return 1 - no_collision

def expected_distinct(days, people):
    """Linearity of expectation over indicators for used categories."""
    if (type(days) is not int or days <= 0
            or type(people) is not int or people < 0):
        raise ValueError("positive days and nonnegative people required")
    probability_unused = Fraction(days - 1, days) ** people
    return days * (1 - probability_unused)

def conditional_probability(space, event, given):
    if (not all(isinstance(x, (set, frozenset))
                for x in (space, event, given))
            or not event.issubset(space)
            or not given.issubset(space)
            or not given):
        raise ValueError("event and nonempty condition must belong to space")
    return Fraction(len(event.intersection(given)), len(given))

def posterior_positive(prevalence, sensitivity, false_positive_rate):
    if (any(type(p) is not Fraction or not 0 <= p <= 1
            for p in (prevalence, sensitivity, false_positive_rate))):
        raise ValueError("all probabilities must be fractions in [0,1]")
    true_positive = prevalence * sensitivity
    false_positive = (1 - prevalence) * false_positive_rate
    if true_positive + false_positive == 0:
        raise ValueError("cannot condition on a probability-zero test result")
    return true_positive / (true_positive + false_positive)

rolls = set(product(range(1, 7), repeat=2))
sum_ten_or_more = {pair for pair in rolls if sum(pair) >= 10}
first_at_least_five = {pair for pair in rolls if pair[0] >= 5}
assert Fraction(len(sum_ten_or_more), len(rolls)) == Fraction(1, 6)
assert conditional_probability(rolls, sum_ten_or_more, first_at_least_five) == Fraction(5, 12)
assert collision_probability(365, 23) > Fraction(1, 2)
assert collision_probability(5, 6) == 1
assert expected_distinct(2, 2) == Fraction(3, 2)
assert posterior_positive(Fraction(1, 100),
                          Fraction(9, 10),
                          Fraction(1, 20)) == Fraction(2, 13)
~~~

An independent test can enumerate every ordered draw sequence for small `d,r` and count the sequences with repeated labels. It can also enumerate all sequences to calculate mean distinct labels and compare that exact mean with the indicator-derived formula. Separately, a two-stage weighted-outcome oracle can verify Bayes' formula on a finite rational grid, rather than merely invoking the same algebraic expression.

## Complexity, uncertainty and application design

An exponential sample space may be cheap to **count analytically** but expensive to enumerate. For `n` choices at each of `r` independent draws, there are `n^r` sequences; explicit enumeration costs at least proportional to that number, while the probability-of-collision product needs at most `O(min(n,r))` rational multiplications under the stated model. Exact rational numerator and denominator sizes can grow, so **bit complexity** matters for large parameters.

In algorithm analysis, an **expected cost** is meaningful only under a stated distribution over inputs or algorithm randomness. It cannot automatically replace a worst-case bound. Hash tables often have favorable expected lookup behavior under assumptions about hashing, but adversarial collisions and resizing policies still matter. This connects to [complexity analysis](/en/topics/complexity-analysis/) and [hash tables](/en/topics/hash-tables/).

The distinction between proof and test remains central: exhaustive enumeration over `n≤8` validates implementation against independent finite oracles; an algebraic identity proves all `n` admitted by its hypotheses. The examples assume exact independent uniform draws, finite sample spaces, and mathematical integer arithmetic; no empirical distribution, randomized benchmark or production cryptographic entropy claim follows from them.

## Exercises and verification

1. Prove the two-set inclusion–exclusion identity by considering whether an individual element belongs to zero, one or both sets. Extend it to three sets.
2. Derive Pascal's identity by splitting every `k`-subset into those containing a fixed element and those not containing it.
3. Distinguish permutations without replacement, ordered sequences with replacement and unordered multisets for `n=3,k=2`; enumerate all outcomes and show why the counts differ.
4. Use the pigeonhole principle to prove that 13 items distributed over 12 buckets force a collision; explain why this alone does not imply a specific mean search time.
5. Enumerate 36 ordered outcomes of two dice to verify `P(sum≥10)=1/6` and `P(sum≥10|first≥5)=5/12`.
6. Show that the indicator variables for appearance of two distinct labels can be dependent even though the expected total is the sum of individual expectations.
7. Derive the exact collision probability for four independent draws from three labels, and compare an analytical calculation with complete enumeration.
8. For a classifier with prevalence zero and false-positive rate zero, explain why a positive-result posterior is undefined under the stated model.
9. State one problem for which counting outcomes is polynomial-time while enumerating all outcomes is exponential, and distinguish arithmetic-operation complexity from bit complexity.

**Next:** [complexity analysis](/en/topics/complexity-analysis/) applies these counting tools to algorithms; [hash tables](/en/topics/hash-tables/) requires collision assumptions; [logic and invariants](/en/topics/logic-proofs-invariants/) supplies proof techniques. This is a bounded foundations chapter, not a complete discrete-mathematics or statistics curriculum [1][2][3][4][5].
