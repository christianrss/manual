"""Unsolved training exercises. Implement these functions and run drill_grader.py.

These are original, independently curated exercises, not employer assessment items.
"""

def cheapest_route_with_coupon(node_count, edges):
    """Return minimum 0->(n-1) directed path cost, using at most one
    half-price coupon (floor(weight/2)), or -1 if unreachable.

    node_count >= 1; each edge is (u,v,nonnegative_integer_weight).
    Duplicate directed edges and zero-weight edges are allowed.
    """
    raise NotImplementedError("implement coupon-route challenge")

def parallel_release_rounds(task_count, dependencies):
    """Return minimum sequential rounds for a directed prerequisite DAG.

    (u,v) means u must complete in an earlier round than v.
    Cycles return -1; zero tasks return zero. Duplicate edges are allowed.
    """
    raise NotImplementedError("implement release-rounds challenge")
