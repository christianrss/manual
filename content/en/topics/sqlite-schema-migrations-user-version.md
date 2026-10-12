---
id: sqlite-schema-migrations-user-version
title: "SQLite schema migrations: user_version, compatibility and rollback"
description: "Evolve a SQLite database safely from two schema versions while preserving rows and rejecting inconsistent states."
category: databases
difficulty: foundational
updated: 2026-10-12
prerequisites: [sqlite-parameterized-crud-transactions]
sources:
  - {title: "SQLite — PRAGMA user_version", url: "https://www.sqlite.org/pragma.html#pragma_user_version", kind: "official SQLite reference"}
  - {title: "SQLite — ALTER TABLE", url: "https://www.sqlite.org/lang_altertable.html", kind: "official SQLite reference"}
  - {title: "SQLite — Transactions", url: "https://www.sqlite.org/lang_transaction.html", kind: "official SQLite reference"}
  - {title: "Python standard library — sqlite3", url: "https://docs.python.org/3/library/sqlite3.html", kind: "official Python documentation"}
---
A database schema changes as a program evolves. An application may begin with a table of stock identifiers and quantities, then later require a textual description. Deleting and recreating that table would discard existing records. A **schema migration** is a controlled transformation from one known representation to another while preserving the data invariants the application promises [1][2].

## Distinguish schema from stored rows

A schema defines table names, columns, constraints and relations. The rows are instances of data governed by that structure. Adding a column can be compatible with existing rows when the new column has a suitable default; replacing or dropping a column can require a more careful transformation.

For this exercise, version 1 contains an inventory table with a non-null SKU and an integer quantity that must be nonnegative. Version 2 adds a non-null description field whose default is an empty string. The migration must preserve every existing SKU and quantity and present empty descriptions for older rows.

This is a deliberately small, forward-only sequence. Large production systems may need multiple application versions reading the same schema, backup policy, migration windows and recovery procedures. Those concerns must not be silently inferred from a simple ALTER TABLE statement.

## Record a user-managed schema version

SQLite exposes PRAGMA user_version as a 32-bit application-managed integer in the database header. **SQLite does not automatically increment this value when a table changes** [1]. An application can use it as a version marker, but it must keep it synchronized with its own migration operations.

Version zero is the initial state in this example. The first migration creates the inventory table and records version one. The next migration adds the description column and records version two. Calling migrate again on a valid version-two schema should perform no further structural transformation.

Do not confuse user_version with schema_version. The latter serves SQLite's internal schema invalidation checks and is not a safe substitute for a user-managed migration version [1]. Manipulating internal schema metadata to force a version is not an acceptable workaround for a failed migration.

## Choose a compatible change

The ALTER TABLE operation adds description as TEXT NOT NULL DEFAULT ''. Existing rows then observe the documented default without losing their previous columns [2]. This change is appropriate because no existing row can provide a manually entered description at migration time.

Adding a non-null field without a compatible default to a table that already has rows may fail. Changing column meanings, splitting tables or moving data requires explicit transformation logic. The choice between an empty string and NULL is also a domain decision: here an empty string means the historical description is not supplied, without pretending the text is known.

The quantity constraint additionally checks typeof(quantity) so that floating-point values cannot be stored as noninteger quantities merely because SQLite uses flexible type affinity. This demonstrates that schema constraints should match the domain, not rely on declaration syntax alone.

## Commit the schema and the version together

An interrupted migration must not leave a new column present while the version marker still denotes an old schema, or mark a new version before the column exists. The example opens an explicit write transaction with BEGIN IMMEDIATE, executes each statement separately, and commits the structural change together with the user_version update [3][4].

If a statement or validation fails, ROLLBACK discards changes made within that transaction. In Python sqlite3, executescript can implicitly commit a pending transaction under documented behaviors; using it inside this explicit migration would be inappropriate without accounting for that boundary [4]. Therefore the code uses separate execute calls.

When a database has an unknown future version, the migration raises an error rather than trying to reinterpret the database as version zero. Downgrading a schema is not a safe automatic assumption. It may require a separately designed and tested reverse transformation.

## Runnable migration and verification

The code operates on a SQLite connection configured for explicit transaction control. It includes a structural check for the expected three column names after migration. That check detects some mismatches between the marker and the structure; it does not prove that every constraint and index matches a formal version-two schema.

~~~python
import sqlite3

def migrate(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2):
            raise ValueError("unsupported schema version")
        if version == 0:
            db.execute("""
                CREATE TABLE inventory (
                    sku TEXT PRIMARY KEY NOT NULL,
                    quantity INTEGER NOT NULL
                        CHECK(typeof(quantity) = 'integer' AND quantity >= 0)
                )
            """)
            db.execute("PRAGMA user_version = 1")
            version = 1
        if version == 1:
            db.execute("""
                ALTER TABLE inventory
                ADD COLUMN description TEXT NOT NULL DEFAULT ''
            """)
            db.execute("PRAGMA user_version = 2")
        names = [r[1] for r in db.execute("PRAGMA table_info(inventory)")]
        if names != ["sku", "quantity", "description"]:
            raise ValueError("schema does not match version 2")
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise

db = sqlite3.connect(":memory:", isolation_level=None)
try:
    migrate(db)
    db.execute("INSERT INTO inventory(sku, quantity) VALUES (?, ?)",
               ("guitar-01", 4))
    migrate(db)
    row = db.execute(
        "SELECT sku, quantity, description FROM inventory WHERE sku = ?",
        ("guitar-01",)
    ).fetchone()
    assert row == ("guitar-01", 4, "")
    assert db.execute("PRAGMA user_version").fetchone()[0] == 2
finally:
    db.close()
~~~

## Preserve existing records and make reruns safe

For an existing version-one database, a row such as (guitar-01, 4) must remain present after the upgrade, with description equal to the default empty string. A query using bound parameters retrieves that row. No CREATE TABLE or ALTER TABLE step should run again once the marker is two and the shape check succeeds.

Repeated execution is important because a deployment script may be restarted after its status becomes uncertain. Idempotence here means rerunning the migration against a valid version-two database leaves its rows and declared columns unchanged. It does not mean an arbitrary corrupted or conflicting database can be repaired automatically.

A migration from zero creates the table before raising the marker to one and then performs the version-two upgrade in the same explicit transaction. A failed later step therefore rolls back the entire attempted sequence, leaving the pre-migration state instead of an unintended intermediate version [3].

## Counterexamples and failure tests

Construct a version-one database with inventory rows and run migrate. Verify the preserved quantity, default description, and resulting marker two. Reopen the file and run migrate again, confirming that the data and column list are unchanged.

Next, construct a database whose marker is one but whose inventory table is missing. ALTER TABLE must fail and the marker must remain one. A database marked as version two without the expected table must also be rejected by the structural validation. A database marked as version 99 must not be silently downgraded.

These tests distinguish three contracts: correct upgrade of supported historical data, rejection of inconsistent states, and stable behavior after successful upgrading. A simple successful execution on a brand-new empty database does not test the first contract.

## Costs and operational boundaries

Checking schema version and names is bounded work for this fixed schema. The complexity of schema alteration can depend on SQLite version, constraints, whether existing table contents must be scanned, the size of the table and the filesystem. It is incorrect to declare all schema migrations O(1) from the small number of SQL statements [2].

A transaction is a logical atomicity boundary; crash recovery still depends on the database configuration and underlying storage assumptions [3]. Before altering a production database, preserve tested backups, validate application compatibility and develop a rollback or forward-repair plan. An automated schema marker alone cannot replace those controls.

## Exercises and verification

1. Upgrade a file-backed version-one table with existing records and prove that SKUs and quantities are preserved.
2. Run the upgrade twice and compare schema column names and row counts.
3. Start from a marker of 99 and show that the algorithm rejects it without altering the schema.
4. Construct a version-one marker without its required table and confirm the transaction rolls back.
5. Explain why setting user_version after a structural change in a separate transaction creates a failure window.
6. Identify a schema change that cannot be safely expressed as simply adding a column with a default.

Continue with [SQLite transactional CRUD](/en/topics/sqlite-parameterized-crud-transactions/), [relational design](/en/topics/relational-model-sql-basics/) and [storage and recovery boundaries](/en/topics/database-storage-wal/).