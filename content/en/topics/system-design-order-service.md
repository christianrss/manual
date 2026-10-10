---
id: system-design-order-service
title: "System Design Case: Orders, Inventory Reservations and Payments"
description: "Design order checkout with atomic stock reservation, durable idempotency, transactional outbox and safe payment saga recovery."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [system-design-process, storage-selection, asynchronous-messaging, transactional-indexing-isolation]
sources:
  - {title: "PostgreSQL — Transaction Isolation", url: "https://www.postgresql.org/docs/current/transaction-iso.html", kind: "official database documentation"}
  - {title: "AWS Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
---
An order service is a useful **full system design case** because a seemingly simple checkout crosses three different authorities: the product catalog, inventory ownership, and an external payment provider. A successful HTTP response must have an exact meaning. Accepting an order request is not the same as reserving stock, authorizing payment, capturing funds or fulfilling a shipment. A reliable architecture names each boundary and defines what happens when the process crashes between them [1][2].

## Requirements, invariants and scenario

Assume a hypothetical online shop sells physical items. Customers submit a basket, receive an order ID, view status and cancel when policy allows. The system must never reserve more units of an SKU than are available under its stock authority. Retrying checkout with the same scoped client operation key must return the **same logical order** without a second stock reservation. Payment may be temporarily unavailable, and a successful reservation must eventually be completed or released according to policy.

Out of scope: tax calculation by jurisdiction, multi-currency exchange rates, split merchants and partial shipments. They are substantial product rules, not details to silently invent. Define monetary rounding, currency and shipping promise before implementation. The state machine is part of the contract: created → reserved → payment_pending → confirmed or cancelled; fulfillment is a separate state progression. Each edge has guards and audit history.

## Capacity and nonfunctional assumptions

Assume **864,000 checkout attempts/day** at 30× peak-to-average ratio. That gives 10 attempts/s average and a peak scenario of **300 attempts/s**. If each accepted order averages three order lines, peak can involve roughly 900 line-level stock checks/s, plus order, idempotency and outbox writes. These numbers exclude abandoned checkout retries, payment callbacks and fulfillment events. If an order record and lines average 2 KiB of logical data, 864,000 successful orders/day correspond to roughly 1.65 GiB/day and 602 GiB/year before indexes, WAL, replication and backups.

Set hypothetical SLOs: 99.9% accepted checkout requests reach a **durable reserved or rejected outcome** within 750 ms server-side, excluding client network delay; 99% of healthy-provider payment authorizations finish within two minutes. Whether provider outages count as failures must be explicit rather than silently excluded. Track conversion and duplicate-charge reports separately from request latency.

## Architecture and ownership boundaries

Start with client → authenticated Checkout API → transactional **order/inventory authority**. The authority owns stock availability, reservations, order identity and an outbox. An outbox publisher delivers payment requests to a durable queue. Payment workers call a PSP using a stable provider-side idempotency key. A payment-result consumer advances order state and emits a fulfillment event. Catalog and product-search read models may be stale, but the stock authority must check current availability before granting a reservation.

![Checkout transaction owns stock and order state; payment and fulfillment run as separate durable stages.](/diagrams/order-service-saga.svg)

The catalog should not deduct stock merely because a product page showed “in stock.” That display may be a cached estimate. Never ask the browser to supply a price that becomes authoritative; snapshot verified product prices and product identifiers in the checkout transaction, and bind stock decisions to a durable SKU identity.

## HTTP contracts and checkout semantics

A proposed `POST /v1/orders` takes a basket, shipping reference and an `Idempotency-Key` scoped to authenticated account. It validates quantities, currency, prices and ownership, then atomically reserves inventory and persists the order plus payment-request outbox. Return **202 Accepted** with order ID and status URL if payment will happen later; this is acceptance into an asynchronous workflow, not evidence of payment. A reservation rejection returns a documented out-of-stock conflict, while a reused key with a different payload must be rejected.

`GET /v1/orders/{id}` authorizes ownership and returns states such as `payment_pending`, `confirmed`, `cancelled` and `payment_failed`. Avoid retrying client-side with a different key after a timeout: a committed reservation may already exist. If the client resends the same key, the service retrieves its durable outcome. A unique constraint and transaction enforce this even across multiple application instances [1].

## Model one atomic local transaction

The following **SQLite teaching model** demonstrates the core local invariant for a single SKU: inventory decreases only when sufficient stock exists, order insertion and outbox insertion happen in the same transaction, and repeated client keys have no additional stock effect. It is not a multi-node checkout deployment or a payment implementation.

~~~python
import sqlite3

db = sqlite3.connect(":memory:", isolation_level=None)
db.executescript("""
CREATE TABLE stock(sku TEXT PRIMARY KEY,
    available INTEGER NOT NULL CHECK(available>=0));
CREATE TABLE orders(order_id TEXT PRIMARY KEY,
    operation_key TEXT UNIQUE, sku TEXT, quantity INTEGER, state TEXT);
CREATE TABLE outbox(order_id TEXT UNIQUE, event_type TEXT);
INSERT INTO stock VALUES ('sku-A', 4);
""")

def reserve(conn, operation_key, sku, quantity):
    if not operation_key or quantity <= 0:
        raise ValueError("invalid command")
    conn.execute("BEGIN IMMEDIATE")
    try:
        old = conn.execute(
            "SELECT order_id,sku,quantity FROM orders WHERE operation_key=?",
            (operation_key,)).fetchone()
        if old:
            if old[1:] != (sku, quantity):
                raise ValueError("idempotency payload mismatch")
            conn.commit()
            return old[0], "replayed"
        count = conn.execute(
            "UPDATE stock SET available=available-? "
            "WHERE sku=? AND available>=?",
            (quantity, sku, quantity)).rowcount
        if count != 1:
            conn.rollback()
            return None, "out_of_stock"
        conn.execute("INSERT INTO orders VALUES (?,?,?,?,?)",
                     (operation_key, operation_key, sku, quantity, "payment_pending"))
        conn.execute("INSERT INTO outbox VALUES (?,?)",
                     (operation_key, "authorize_payment"))
        conn.commit()
        return operation_key, "accepted"
    except Exception:
        conn.rollback()
        raise

assert reserve(db, "order-1", "sku-A", 3) == ("order-1", "accepted")
assert reserve(db, "order-1", "sku-A", 3) == ("order-1", "replayed")
assert reserve(db, "order-2", "sku-A", 2) == (None, "out_of_stock")
assert db.execute("SELECT available FROM stock").fetchone() == (1,)
assert db.execute("SELECT COUNT(*) FROM outbox").fetchone() == (1,)
try:
    reserve(db, "order-1", "sku-A", 1)
    assert False
except ValueError:
    pass
~~~

Here BEGIN IMMEDIATE serializes SQLite writers for this database file/connection environment; the conditional UPDATE prevents stock below zero. A real PostgreSQL or distributed deployment requires tests with **separate concurrent connections**, actual transaction isolation, client-key scopes, and a deterministic order ID strategy. The model's operation_key-as-order-ID is deliberately simple. Reservation TTL and release on failure are not implemented in this tiny example.

## Payment processing and the saga boundary

The order database **cannot** atomically commit with an independent PSP just because both use transactional APIs. A saga coordinates local state transitions with compensating actions. One route is: reserve stock → send payment authorization → on success confirm order; on definite failure release reservation; on unknown payment outcome **reconcile** with the PSP before releasing or charging again [2].

The PSP call must carry an idempotency key recognized by the provider when supported; the response may be lost after a real authorization. Retrying with a fresh provider key can double-charge or create multiple authorizations. Compensation is not time reversal: a refund may take time, incur fees or fail and require human reconciliation. Store durable provider references, attempt history and monetary reconciliation states. Never persist raw payment card details unless the entire compliance model explicitly requires and supports it.

## Prevent overselling under contention

Suppose two customers each see three units of stock and each orders two while only three units actually exist. A preliminary `SELECT available` followed later by unconditional decrement can grant four units. The invariant is **available ≥ 0 after every committed reservation**. Enforce it in one conditional database write (as above) or with appropriate locks and isolation under a single stock authority.

Inventory for a very popular SKU is a **hot key**. Sharding customers does not distribute atomic updates to the same SKU automatically; overselling prevention might remain a serialized bottleneck. Consider inventory allocation by warehouse, bounded preallocated quotas, admission control, or explicitly weaker backorder semantics instead of pretending the hotspot disappears when nodes are added.

## Expiry, cancellation and idempotent release

Reservations must not remain forever when payments time out. A background reaper should find expired reservations and release stock **exactly once at the local stock authority** using an atomic conditional transition such as `reserved → released`. An arriving late payment result may race with expiry, so define which state wins and how a paid-but-cancelled order is compensated. An outbox event announcing release may be delivered repeatedly: downstream consumers deduplicate using a durable event identity.

Reserve, confirm, release and cancel should be individually idempotent under stable operation identities. A process-local boolean is insufficient after failover. Order state transitions require optimistic version checks or protected row locks and an audit trail. Any transition that moves money requires deeper reconciliation and a separate failure analysis.

## Failures, metrics and operational validation

| Failure | Safe handling | Verification |
| --- | --- | --- |
| Two concurrent checkouts for one SKU | Conditional stock update / lock | Separate-connection contention test |
| HTTP timeout after order commit | Reuse client idempotency key | Replay with same/different payload |
| Outbox relay publishes twice | Deduplicate payment command | Duplicate queue messages |
| PSP accepts then response is lost | Same PSP key + reconciliation | Timeout after external effect |
| Reservation expires as payment succeeds | Fenced state transition, defined compensation | Controlled race test |
| Inventory authority unavailable | Fail closed, do not overpromise stock | Failure injection |

Instrument checkout rejection reason, stock contention, reservation age, outbox lag, repeated keys, PSP timeout rate, settled-versus-authorized amount, cancellations and compensation backlog. A checkout API can return 202 quickly while payments remain stalled; track **business completion** separately.

## Exercises and verification

1. Derive the 300 peak attempts/s assumption and discuss what happens when 30% of clients retry due to timeouts.
2. Show the overselling interleaving of two customers ordering two units from three available units without a conditional update.
3. Prove why one database transaction containing order, stock and outbox records avoids a committed order without a corresponding payment request intent.
4. Explain what a PSP timeout does **not** tell the merchant and when reconciliation is mandatory.
5. Design a race test for payment success arriving exactly as reservation expiry attempts to release inventory.

**Related chapters:** [System Design method](/en/topics/system-design-process/), [storage selection](/en/topics/storage-selection/), [transaction isolation](/en/topics/transactional-indexing-isolation/), [asynchronous messaging](/en/topics/asynchronous-messaging/) and [API idempotency](/en/topics/api-reliability/) provide the building blocks.
