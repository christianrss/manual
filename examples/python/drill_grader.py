"""Public baseline fixtures for the unsolved coding assessment.

Use: python examples/python/drill_grader.py
The grader deliberately has no reference implementations; your own code
must replace NotImplementedError in unsolved_drills.py.
"""
from unsolved_drills import cheapest_route_with_coupon, parallel_release_rounds

COUPON_CASES = [
    (3, [(0,1,9),(1,2,5),(0,2,30)], 9),
    (3, [(0,1,4)], -1),
    (1, [], 0),
    (2, [(0,1,1)], 0),
    (4, [(0,1,8),(1,3,8),(0,2,5),(2,3,8)], 9),
    (2, [(0,1,0)], 0),
]
RELEASE_CASES = [
    (4, [(0,2),(1,2),(2,3)], 3),
    (3, [], 1),
    (3, [(0,1),(1,2),(2,0)], -1),
    (0, [], 0),
    (1, [], 1),
    (4, [(0,1),(0,1),(1,2),(1,3)], 3),
]

def evaluate(cheap=cheapest_route_with_coupon,
             rounds=parallel_release_rounds):
    results = []
    for count,edges,expected in COUPON_CASES:
        actual=cheap(count, list(edges))
        if actual != expected:
            raise AssertionError(
                f"coupon_route n={count}, edges={edges}: expected {expected}, got {actual}")
        results.append(("coupon", count))
    for count,dependencies,expected in RELEASE_CASES:
        actual=rounds(count, list(dependencies))
        if actual != expected:
            raise AssertionError(
                f"release_rounds n={count}, dependencies={dependencies}: "
                f"expected {expected}, got {actual}")
        results.append(("rounds", count))
    return results

if __name__ == "__main__":
    passed=evaluate()
    print(f"Passed {len(passed)} public baseline checks. "
          "These cases are not exhaustive; write your own adversarial tests.")
