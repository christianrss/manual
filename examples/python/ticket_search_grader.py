"""Public grader for the *unsolved* legacy-refactoring assessment IV.

No implementation or hidden tests are included. This grader checks a declared
new contract, NOT observed legacy behavior. It must never run on real PII.
"""
from copy import deepcopy
from refactor_ticket_search import search_tickets


def ticket(ticket_id, tenant, status, created, **extra):
    return {
        "id": ticket_id, "tenant_id": tenant, "status": status,
        "created_at": created, **extra,
    }


BASE = [
    ticket("a1", "a", "open", 10, owner_email="fictional@example.invalid"),
    ticket("b1", "b", "open", 30, internal_note="synthetic"),
    ticket("a3", "a", "open", 20, private_phone="000"),
    ticket("a2", "a", "closed", 20, internal_note="not public"),
]
A1 = {"id": "a1", "status": "open", "created_at": 10}
A2 = {"id": "a2", "status": "closed", "created_at": 20}
A3 = {"id": "a3", "status": "open", "created_at": 20}

# tuple: (tickets, tenant, status, offset, limit, expected envelope)
VALID_CASES = [
    ([], "a", None, 0, 10, {"items": [], "total": 0}),
    (BASE, "a", None, 0, 10, {"items": [A2, A3, A1], "total": 3}),
    (BASE, "a", None, 0, 1, {"items": [A2], "total": 3}),
    (BASE, "a", None, 1, 1, {"items": [A3], "total": 3}),
    (BASE, "a", None, 3, 1, {"items": [], "total": 3}),
    (BASE, "a", "open", 0, 2, {"items": [A3, A1], "total": 2}),
    (BASE, "a", "closed", 0, 2, {"items": [A2], "total": 1}),
    (BASE, "a", "missing", 0, 10, {"items": [], "total": 0}),
    (BASE, "missing", None, 0, 10, {"items": [], "total": 0}),
    (BASE, "b", None, 0, 10,
     {"items": [{"id": "b1", "status": "open", "created_at": 30}], "total": 1}),
    ([ticket("z", "a", "open", 7), ticket("a", "a", "open", 7)],
     "a", None, 0, 10,
     {"items": [{"id": "a", "status": "open", "created_at": 7},
                {"id": "z", "status": "open", "created_at": 7}], "total": 2}),
    ([ticket("x", "b", "open", 100), ticket("y", "a", "open", 2)],
     "a", None, 0, 1,
     {"items": [{"id": "y", "status": "open", "created_at": 2}], "total": 1}),
    ([ticket("same", "a", "open", 4), ticket("same", "b", "closed", 6)],
     "a", None, 0, 5,
     {"items": [{"id": "same", "status": "open", "created_at": 4}], "total": 1}),
    (tuple(BASE), "a", None, 0, 100, {"items": [A2, A3, A1], "total": 3}),
    ([ticket("zero", "a", "open", 0)], "a", None, 0, 1,
     {"items": [{"id": "zero", "status": "open", "created_at": 0}], "total": 1}),
]

INVALID_CASES = [
    (None, "a", None, 0, 10),
    ("tickets", "a", None, 0, 10),
    ([], "", None, 0, 10),
    ([], 123, None, 0, 10),
    ([], "a", "", 0, 10),
    ([], "a", 0, 0, 10),
    ([], "a", None, -1, 10),
    ([], "a", None, True, 10),
    ([], "a", None, 0, 0),
    ([], "a", None, 0, 101),
    ([], "a", None, 0, True),
    ([None], "a", None, 0, 10),
    ([{"id": "x", "tenant_id": "a", "status": "open"}], "a", None, 0, 10),
    ([ticket("", "a", "open", 1)], "a", None, 0, 10),
    ([ticket("x", "", "open", 1)], "a", None, 0, 10),
    ([ticket("x", "a", "", 1)], "a", None, 0, 10),
    ([ticket("x", "a", "open", -1)], "a", None, 0, 10),
    ([ticket("x", "a", "open", True)], "a", None, 0, 10),
    ([ticket("x", "a", "open", 1.5)], "a", None, 0, 10),
    ([ticket("x", "a", "open", 1), ticket("x", "a", "closed", 2)],
     "a", None, 0, 10),
    ([ticket("x", "a", "open", 1), ticket("x", "a", "open", 1)],
     "b", None, 0, 10),
]


def check_valid(candidate, case):
    tickets, tenant, status, offset, limit, expected = case
    inputs = deepcopy(tickets)
    before = deepcopy(inputs)
    actual = candidate(inputs, tenant, status, offset, limit)
    if inputs != before:
        raise AssertionError("candidate mutated caller-owned input")
    if type(actual) is not dict or set(actual) != {"items", "total"}:
        raise AssertionError(f"invalid response envelope: {actual!r}")
    if type(actual["total"]) is not int or type(actual["items"]) is not list:
        raise AssertionError(f"invalid response types: {actual!r}")
    if actual != expected:
        raise AssertionError(f"query {(tenant, status, offset, limit)}: expected {expected!r}, got {actual!r}")
    if tickets and actual["items"]:
        # Changing an output row must not modify the caller's data.
        row = actual["items"][0]
        if type(row) is not dict:
            raise AssertionError("response row must be a new dict")
        row["id"] = "modified-after-return"
        if inputs != before:
            raise AssertionError("response row aliases a caller-owned record")
    return True


def check_invalid(candidate, case):
    tickets, tenant, status, offset, limit = case
    inputs = deepcopy(tickets)
    before = deepcopy(inputs)
    try:
        candidate(inputs, tenant, status, offset, limit)
    except ValueError:
        if inputs != before:
            raise AssertionError("candidate mutated invalid caller input")
        return True
    raise AssertionError(f"expected ValueError: {(tickets, tenant, status, offset, limit)!r}")


def evaluate(candidate=search_tickets):
    passed = 0
    for case in VALID_CASES:
        check_valid(candidate, case)
        passed += 1
    for case in INVALID_CASES:
        check_invalid(candidate, case)
        passed += 1
    return passed


if __name__ == "__main__":
    print(f"Passed {evaluate()} public cases; investigate additional adversarial cases.")
