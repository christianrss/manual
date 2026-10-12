---
id: algorithmic-problem-solving-method
title: "Algorithmic reasoning: specifications, brute force, invariants and optimization"
description: "Learn a repeatable problem-solving method by deriving a correct linear-time solution from a quadratic reference algorithm."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-control-flow-functions, logic-proofs-invariants, complexity-analysis]
sources:
  - {title: "MIT OCW — Introduction to Algorithms (6.006)", url: "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/", kind: "university course"}
  - {title: "MIT Mathematics for Computer Science (6.042J)", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/", kind: "university course and textbook"}
  - {title: "Python documentation — Built-in types", url: "https://docs.python.org/3/library/stdtypes.html", kind: "official language documentation"}
---
An algorithm is not merely code that happens to produce an answer for a sample. It is a **finite procedure with a specified input domain and an observable result**, together with a reason to believe the result is correct. Efficient solutions begin with understanding the problem, not with memorizing a template. The standard foundations of algorithm analysis distinguish correctness, representation, cost and implementation [1][2]. Here a small optimization problem provides a complete reasoning path from specification to proof.

## State the contract before choosing a data structure

Given an ordered sequence of daily prices, find one purchase day and one **later** sale day that maximize strictly positive profit. Buying and selling on the same day is forbidden. Prices are nonnegative integers representing hypothetical units; taxes, currency conversion, fees and short selling are excluded. If no positive trade exists, return None. If several trades have the same maximum profit, choose the pair with the earliest purchase day and then earliest sale day. The return value is a triple of indices and profit.

This formulation immediately answers several ambiguous questions. A decreasing input has no valid profitable trade; negative profit must not be returned just because a trade is possible. Equal prices do not constitute a positive trade. Zero prices are valid. Integers avoid unnecessary floating-point comparison issues in this example, but do not imply that financial applications should use unlimited integer money without domain-specific limits.

## Make examples into mathematical claims

For prices [9, 1, 5, 3, 6], buying at index 1 and selling at index 4 yields profit 6−1=5. Buying at index 1 and selling at index 2 yields 4. Buying at index 0 and selling later cannot improve the result because every later price is lower than 9. A correct algorithm must examine the constraints buy < sell and not merely subtract the global minimum from the global maximum: the maximum might occur before the minimum.

The example [8, 7, 7, 3] makes the no-profit rule visible. The example [3, 1, 4, 1, 4] makes tie resolution visible: (1, 2) must win over later equivalent trades. Edge cases are part of the specification, not optional additions after the main algorithm.

## Start with an obviously correct exhaustive solution

A reference method enumerates every ordered pair (buy, sell) with buy < sell, computes price[sell] − price[buy], and retains the positive pair with greatest profit. To obey ties, enumerate purchase indices in increasing order and sale indices in increasing order, updating only for a **strictly** larger profit. All valid pairs are considered, so the returned maximum is correct by exhaustive comparison. If the input has n elements, there are n(n−1)/2 ordered valid pairs: this yields O(n²) time and O(1) extra storage under constant-cost arithmetic assumptions.

Brute force is not a failure. It provides a correctness oracle for small inputs and clarifies exactly what the optimized algorithm must preserve. The proof that it covers all pairs is often simpler than the optimized proof, making it useful for automated differential testing.

## Derive a better recurrence from the search space

Fix a sale day s. Its best prior purchase day is any index b < s with minimum price[b]. Therefore, to evaluate a sale day, we do not need to revisit all earlier days; we need only the smallest earlier price and its **earliest** index. After evaluating sale s, that day's price may become the new minimum available for future sales. This ordering matters: the current day must be considered as a sale **before** it becomes eligible as a purchase for later days.

Maintain three pieces of state: the minimum price among processed earlier days, the earliest index attaining that minimum, and the best profitable pair already seen. The first two summarize the entire prefix relevant to future profit calculation; retaining all earlier pairs is unnecessary.

~~~python
def best_trade(prices):
    """Earliest (buy_index, sell_index, profit), or None if no gain."""
    if not isinstance(prices, (list, tuple)):
        raise TypeError("prices must be a sequence")
    for price in prices:
        if type(price) is not int or price < 0:
            raise ValueError("prices must be nonnegative integers")
    if len(prices) < 2:
        return None

    min_price = prices[0]
    min_index = 0
    best_profit = 0
    best = None

    for sell in range(1, len(prices)):
        profit = prices[sell] - min_price
        if profit > best_profit:
            best_profit = profit
            best = (min_index, sell, profit)
        if prices[sell] < min_price:
            min_price = prices[sell]
            min_index = sell
    return best

assert best_trade([]) is None
assert best_trade([5]) is None
assert best_trade([9, 1, 5, 3, 6]) == (1, 4, 5)
assert best_trade([8, 7, 7, 3]) is None
assert best_trade([3, 1, 4, 1, 4]) == (1, 2, 3)
assert best_trade([0, 1, 0, 2]) == (0, 3, 2)
try:
    best_trade([1, True, 4])
except ValueError:
    pass
else:
    raise AssertionError("boolean is not a price")
~~~


## Prove the loop invariant and termination

Just before iteration s (where s ranges from 1 through n−1), `min_price` is the minimum of prices[0:s], and `min_index` is its earliest location. `best` is the earliest lexicographically ordered pair among the profitable pairs with sale index less than s that attain the greatest profit. Initially s=1, so the prefix has one value and no earlier valid sale: the invariant holds.

During iteration s, `prices[s] - min_price` is the maximum profit of all possible purchases preceding that sale. If it strictly improves `best_profit`, replace the stored pair. If profit ties, do not replace: earlier sale indices have already been visited, and the earliest minimum purchase index was retained because the minimum is replaced only on strictly lower prices. Finally, compare prices[s] with the prefix minimum to prepare the invariant for s+1. After the last sale is inspected, the best pair is globally optimal. Since the loop advances by one until a fixed bound, it terminates.

There are at most n−1 sale iterations, plus n validations, so time is O(n) for fixed-width integer operations. State consists of a fixed number of scalars, giving O(1) auxiliary space. In Python, integers can be arbitrarily large, so a bit-complexity analysis would account for operand magnitude; O(n) describes the conventional unit-cost model [1].

## Trace the optimized solution

For [9,1,5,3,6], the initial minimum is (price=9, index=0). At sale index 1 the calculated profit is negative, then the new prefix minimum becomes (1,1). Sale index 2 yields 4, which becomes the best candidate (1,2,4). Sale index 3 yields 2, leaving the best unchanged. Sale index 4 yields 5, so the answer is (1,4,5).

The most common incorrect optimization is to update `min_price` before calculating the sale profit and to forget that buying and selling must occur on different days. With strictly positive-profit requirements, this implementation may still appear to work on common samples, but its invariant is then misstated. Another mistake is to keep the latest minimum on equality, violating the earliest-purchase tie requirement.

## Testing is an argument with limits

Run the optimized code against the quadratic oracle on all short sequences from a small alphabet. This catches off-by-one errors, tie mistakes and decreasing-input failures. It does not prove correctness for all integer sizes; the loop invariant supplies the general argument. Random tests are useful after exhaustive small-state checks, not a substitute for specification. For languages with fixed-width integers, include overflow cases and choose a representation or checked arithmetic policy.

Not every problem admits the same prefix-summary trick. This one does because future sales depend on earlier days only through the minimum eligible price. Problems whose constraints depend on multiple prior states, transaction limits, or fees require a different state summary, often dynamic programming. Optimize from a proven property of the problem, not from a fashionable data structure.

## Exercises and verification

1. Write the quadratic reference algorithm and test every sequence of length at most five over {0,1,2,3}. Compare exact triples, including tie behavior.
2. Prove that updating `min_index` when a price is **equal** to the current minimum changes the stated tie contract.
3. Modify the contract to allow negative profits; explain how the initialization must change.
4. Add a fixed per-trade fee. Determine which parts of the invariant remain valid and what changes in the no-profit rule.
5. Explain why subtracting global min from global max is incorrect for [10,1,4], even though both extrema are known.
6. Compare the asymptotic costs of exhaustive enumeration and prefix minimum maintenance, identifying the input size and arithmetic assumptions.

Related material: [control flow](/en/topics/programming-control-flow-functions/), [proofs](/en/topics/logic-proofs-invariants/), [complexity](/en/topics/complexity-analysis/) and [arrays](/en/topics/arrays-and-strings/).