"""Assessment IV: refactor a synthetic tenant-scoped search (UNSOLVED).

Read legacy_ticket_search.py and characterize its observed behavior, then
implement the NEW specification here. Keep the public signature and return
envelope; deliberately correct the documented authorization/data-contract
defects. Public grader: python examples/python/ticket_search_grader.py
"""

def search_tickets(tickets, tenant_id, status=None, offset=0, limit=10):
    """Return {'items': [...], 'total': int} for authorized tickets.

    Contract:
    - tickets: list or tuple of dicts. Each record must have four required
      keys: id, tenant_id, status (all nonempty strings) and created_at
      (nonnegative integer, excluding bool). Extra keys may exist.
    - IDs must be unique WITHIN each tenant, but may recur across tenants.
    - tenant_id: nonempty string from an already AUTHENTICATED caller/context;
      this function does NOT authenticate or authorize that context.
    - status: None (all statuses) or nonempty string.
    - offset: integer >= 0; limit: integer in [1,100]; bool is not valid.
    - Filter tenant and optional status BEFORE paging.
    - Sort by created_at descending, breaking ties by id ascending.
    - total: matching record count BEFORE offset and limit are applied.
    - items: fresh dicts with EXACTLY id, status, created_at keys, in the
      documented order. Never expose any other stored fields.
    - Invalid input (including duplicate IDs per tenant) raises ValueError.
      Never mutate input list, record dicts, or caller-owned nested data.
    - Target O(n log n) time and O(n) extra memory in a comparison-based
      sorting model (excluding costs of arbitrary-size integer operations).
    """
    raise NotImplementedError("implement tenant-scoped refactored search")
