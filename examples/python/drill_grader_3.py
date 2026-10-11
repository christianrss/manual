"""Public fixtures for original unsolved coding and engineering assessment III.

This runner has NO implementation of either challenge. Public cases are not
hidden tests. Passing them is necessary but insufficient for correctness.
Run after implementing unsolved_drills_3.py.
"""
from unsolved_drills_3 import minimum_partition_penalty, apply_idempotent_events

PARTITION_CASES = [
    ([2, 3, 1], 2, 2, 20),
    ([2, 3, 1], 2, 20, 60),
    ([], 3, 2, 0),
    ([5], 1, 7, 32),
    ([0, 0, 0], 2, 0, 0),
    ([1, 1, 1], 3, 20, 29),
    ([3, 1, 2, 3], 3, 1, 27),
    ([1, 2, 3, 4], 4, 0, 30),
    ([10, 0, 1], 2, 8, 117),
    ([1, 2, 1, 2, 1], 2, 4, 31),
    ([1, 1, 1], 1, 0, 3),
    ([6, 2, 4], 5, 100, 244),
    ([0, 0, 5], 2, 1, 27),
    ([2, 2, 2, 2], 2, 3, 28),
]

EVENT_CASES = [
    ({}, [], {}),
    ({"a": 10}, [], {"a": 10}),
    ({"a": 10}, [("e1", "a", -3)], {"a": 7}),
    ({"a": 10}, [("e1", "a", -3), ("e1", "a", -3)], {"a": 7}),
    ({"a": 10}, [("e1", "a", -3), ("e2", "a", 3)], {"a": 10}),
    ({"a": 0}, [("x", "a", 0)], {"a": 0}),
    ({"a": 0}, [("x", "a", 10), ("y", "a", -10)], {"a": 0}),
    ({"a": 4, "b": 8}, [("x", "a", 3), ("y", "b", -5), ("x", "a", 3)], {"a": 7, "b": 3}),
    ({"a": 1, "A": 2}, [("x", "A", -1)], {"a": 1, "A": 1}),
    ({"a": 1}, [("x", "a", 10**22)], {"a": 10**22 + 1}),
    ({"a": 5}, [("x", "a", -5), ("x", "a", -5), ("y", "a", 2)], {"a": 2}),
]

PARTITION_INVALID = [
    ([1], 0, 0), ([1], -1, 0), ([1], True, 0), ([1], 1, -1),
    ([1], 1, True), ([1, -1], 2, 0), ([True], 2, 0),
    ([1.5], 2, 0), ("123", 2, 0),
]
EVENT_INVALID = [
    ({"a": -1}, []),
    ({"a": True}, []),
    ({"": 1}, []),
    ({"a": 1}, [("x", "a", -2)]),
    ({"a": 1}, [("x", "missing", 0)]),
    ({"a": 1}, [("x", "a", 1), ("x", "a", 2)]),
    ({"a": 1, "b": 1}, [("x", "a", 0), ("x", "b", 0)]),
    ({"a": 1}, [("", "a", 1)]),
    ({"a": 1}, [("x", "", 1)]),
    ({"a": 1}, [("x", "a", True)]),
    ({"a": 1}, [("x", "a")]),
    ({"a": 1}, [["x", "a", 0]]),
    ({"a": 1}, "x"),
]


def _check_invalid(function, args, name):
    try:
        function(*args)
    except ValueError:
        return
    raise AssertionError(f"{name} expected ValueError for {args!r}")


def evaluate(partitioner=minimum_partition_penalty, projector=apply_idempotent_events):
    passed = 0
    for loads, limit, overhead, expected in PARTITION_CASES:
        candidate = list(loads)
        original = list(candidate)
        actual = partitioner(candidate, limit, overhead)
        if type(actual) is not int or actual != expected:
            raise AssertionError(f"partition({loads}, {limit}, {overhead}): expected {expected}, got {actual!r}")
        if original != candidate:
            raise AssertionError("partition modified input")
        passed += 1
    for args in PARTITION_INVALID:
        _check_invalid(partitioner, args, "partition")
        passed += 1
    for opening, events, expected in EVENT_CASES:
        balances = dict(opening)
        actions = list(events)
        actual = projector(balances, actions)
        if type(actual) is not dict or actual != expected:
            raise AssertionError(f"project({opening}, {events}): expected {expected}, got {actual!r}")
        if actual is balances:
            raise AssertionError("projection returned caller-owned dictionary")
        if balances != opening or actions != events:
            raise AssertionError("projection mutated inputs")
        passed += 1
    for opening, events in EVENT_INVALID:
        _check_invalid(projector, (opening, events), "projection")
        passed += 1
    return passed


if __name__ == "__main__":
    print(f"Passed {evaluate()} public checks. Add adversarial and property-based tests.")
