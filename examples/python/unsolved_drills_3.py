"""Independent Coding & Engineering Assessment III — original unsolved exercises.

These tasks are independently authored, not employer examination items.
Complete both functions without changing their public signatures.
Run: python examples/python/drill_grader_3.py
"""

def minimum_partition_penalty(loads, max_group_size, overhead):
    """Minimize total cost of splitting ordered loads into nonempty contiguous groups.

    Each group may contain at most max_group_size elements. Its cost is
    (sum of group loads) ** 2 + overhead. Return the minimum total cost.

    loads: list or tuple of nonnegative integers (bool is invalid).
    max_group_size: positive integer. overhead: nonnegative integer.
    Empty loads => 0. Reject invalid inputs with ValueError.
    Do not mutate the caller's inputs. Use exact integer arithmetic.
    Target: O(n * min(n, max_group_size)) time and O(n) extra space.
    """
    raise NotImplementedError("implement minimum_partition_penalty")


def apply_idempotent_events(opening, events):
    """Apply an ordered, in-memory event sequence to account balances.

    opening: dict mapping nonempty, case-sensitive string account IDs to
      nonnegative integer amounts in the smallest currency unit (not bool).
    events: list or tuple of (event_id, account_id, delta) tuples; event IDs
      and account IDs are nonempty strings, delta is an integer (not bool).
    Each event_id is global within this call. First occurrence applies its
    signed delta to an existing account, never allowing a negative balance.
    Exact duplicates of an earlier (id, account, delta) are ignored.
    Reused IDs with a DIFFERENT account or delta raise ValueError.
    Invalid shapes, types, unknown accounts or insufficient funds raise
    ValueError. Return a fresh dict; never mutate opening or events.

    Atomicity here means a raised error leaves the *caller-owned input*
    untouched, not a durable transaction. There is no cross-call dedup,
    interprocess locking, retry protocol, or external persistence.
    Target: O(A + E) expected-time operations, O(A + E) extra space.
    """
    raise NotImplementedError("implement apply_idempotent_events")
