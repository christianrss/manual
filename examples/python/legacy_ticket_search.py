"""Intentionally defective, SYNTHETIC legacy code for a refactoring exercise.

Never use for real authorization, access control, or customer data.
This file is a frozen fixture: characterize it; do not "fix" it.
"""

def legacy_search_tickets(tickets, tenant_id, status=None, offset=0, limit=10):
    """Legacy behavior, NOT the desired specification.

    Deliberate defects: mutates caller order; paginates before tenant/status
    filtering; exposes all record fields; counts only records on the page;
    fails to use an explicit deterministic tie-breaker; validates nothing.
    """
    tickets.sort(key=lambda record: record["created_at"], reverse=True)
    page = tickets[offset:offset + limit]
    filtered = [
        record for record in page
        if record["tenant_id"] == tenant_id
        and (status is None or record["status"] == status)
    ]
    return {"items": filtered, "total": len(filtered)}
