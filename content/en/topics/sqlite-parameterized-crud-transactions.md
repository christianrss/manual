---
id: sqlite-parameterized-crud-transactions
title: "SQLite application fundamentals: parameterized CRUD and atomic transactions"
description: "Build and test a small SQLite repository with bound parameters, constrained balances and transaction rollback."
category: databases
difficulty: foundational
updated: 2026-10-12
prerequisites: [relational-model-sql-basics, python-error-contracts-resource-cleanup]
sources:
  - {title: "Python standard library — sqlite3", url: "https://docs.python.org/3/library/sqlite3.html", kind: "official Python documentation"}
  - {title: "SQLite — Transactions", url: "https://www.sqlite.org/lang_transaction.html", kind: "official SQLite reference"}
  - {title: "SQLite — CREATE TABLE constraints", url: "https://www.sqlite.org/lang_createtable.html", kind: "official SQLite reference"}
  - {title: "SQLite — Isolation", url: "https://www.sqlite.org/isolation.html", kind: "official SQLite reference"}
---
A relational database is useful to an application when code can **store records, retrieve them and make related changes without leaving partial results**. SQL syntax alone does not establish a complete contract. A transfer between two accounts must specify allowed inputs, missing accounts, insufficient funds, and what happens when the second update fails. This chapter connects introductory relational modelling with a real SQLite database and independently executable tests [1][2].

## Define the data contract

Represent an account by a unique owner identifier and a balance in whole cents, not floating-point monetary values. In this model the balance belongs to the closed interval from zero through one million cents. An owner identifier is a nonempty Python string with at most forty code points. It represents synthetic data, not authentication or a genuine banking identity.

The database uses a primary key, a NOT NULL restriction and a CHECK condition. The primary key prevents duplicate owners and the balance constraint rejects invalid stored values [3]. Python-level input validation remains necessary because an application may receive values with surprising types. In Python, a Boolean is a subclass of integer; using an exact type check avoids silently accepting True as one cent.

The interface consists of create_account, balance and transfer. Each must state permitted input, output, errors and side effects. A balance lookup returns None when the account is absent; this is different from returning zero for an existing account.

## Parameters are different from SQL source

The driver supports placeholders: a statement with WHERE owner = ? receives the owner string separately from the SQL command [1]. The sequence of characters constituting a suspicious owner name is compared as literal data. It cannot introduce an additional predicate through that placeholder.

Interpolating arbitrary input directly into a SQL string risks changing the query structure and permitting injection. Placeholders protect values, but **cannot safely stand in for table names, column names or SQL keywords**. Dynamically selected identifiers require another policy, such as an allowlist of known identifiers.

Parameters also make the code easier to review. The query structure stays constant while the argument values change. No quote-escaping rules need to be reimplemented by the application.

## A transfer needs two effects and one outcome

Transferring a positive number of cents from one account to a distinct second account produces a debit and a credit. Both must succeed or neither must be committed. If an account does not exist, if the source lacks sufficient funds, or if the destination would exceed the maximum balance, the function reports failure without a partial transfer.

The source UPDATE includes a balance condition and must modify exactly one row. The destination UPDATE includes its maximum allowed prior balance and must also modify exactly one row. These conditions are evaluated by SQLite at write time rather than relying on a stale prior SELECT. The affected-row count is checked explicitly.

This small model intentionally excludes fees, multiple currencies, external payment networks, authorization and an audit trail. Those are separate requirements and should not be silently implied by a correct arithmetic transfer.

## Specify an explicit transaction boundary

The Python sqlite3 module has several transaction-control modes. This example sets isolation_level=None and explicitly issues BEGIN IMMEDIATE, COMMIT and ROLLBACK, following the documented legacy transaction-control behavior [1]. BEGIN IMMEDIATE acquires the database write transaction before the conditional updates [2].

If either conditional update fails, ROLLBACK discards the earlier partial change. COMMIT is executed only after both updates succeed. The exception path also checks whether a transaction remains active if a later operation raises. A process may still encounter database busy errors or I/O failures, so the application must propagate those instead of pretending the transfer completed [4].

Using a connection as a Python context manager can manage transaction completion, but **does not automatically close the connection**. The executable example closes the resource in finally, independent of whether the assertions pass.

## Executable account example

The standard-library code uses an in-memory SQLite database, yet the same functions also work with a file in a temporary directory. Amounts are integers, the queries use bound values, and the error example exercises rollback when the destination is missing.

~~~python
import sqlite3

MAX_CENTS = 1_000_000

def open_db(path):
    db = sqlite3.connect(path, isolation_level=None, timeout=2.0)
    db.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            owner TEXT PRIMARY KEY NOT NULL,
            balance_cents INTEGER NOT NULL
                CHECK (balance_cents BETWEEN 0 AND 1000000)
        )
    """)
    return db

def create_account(db, owner, cents):
    if (type(owner) is not str or not 1 <= len(owner) <= 40
            or type(cents) is not int or not 0 <= cents <= MAX_CENTS):
        raise ValueError("invalid account")
    db.execute("INSERT INTO accounts(owner, balance_cents) VALUES (?, ?)",
               (owner, cents))

def balance(db, owner):
    row = db.execute(
        "SELECT balance_cents FROM accounts WHERE owner = ?", (owner,)
    ).fetchone()
    return None if row is None else row[0]

def transfer(db, source, destination, cents):
    if (type(source) is not str or type(destination) is not str
            or not 1 <= len(source) <= 40
            or not 1 <= len(destination) <= 40
            or source == destination or type(cents) is not int
            or not 1 <= cents <= MAX_CENTS):
        raise ValueError("invalid transfer")
    db.execute("BEGIN IMMEDIATE")
    try:
        debited = db.execute("""
            UPDATE accounts
            SET balance_cents = balance_cents - ?
            WHERE owner = ? AND balance_cents >= ?
        """, (cents, source, cents)).rowcount
        if debited != 1:
            raise ValueError("source missing or insufficient funds")
        credited = db.execute("""
            UPDATE accounts
            SET balance_cents = balance_cents + ?
            WHERE owner = ? AND balance_cents <= ?
        """, (cents, destination, MAX_CENTS - cents)).rowcount
        if credited != 1:
            raise ValueError("destination missing or balance limit")
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise

db = open_db(":memory:")
try:
    create_account(db, "ada", 900)
    create_account(db, "grace", 100)
    transfer(db, "ada", "grace", 250)
    assert (balance(db, "ada"), balance(db, "grace")) == (650, 350)
    try:
        transfer(db, "ada", "missing", 200)
    except ValueError:
        pass
    else:
        raise AssertionError("missing destination accepted")
    assert (balance(db, "ada"), balance(db, "grace")) == (650, 350)
    assert balance(db, "' OR 1=1 --") is None
finally:
    db.close()
~~~

## Proof of the central invariant

Let S and D denote balances before a valid transfer of x cents between two existing, distinct accounts. The preconditions are 1 <= x <= MAX_CENTS, S >= x, and D <= MAX_CENTS-x. The debit produces S-x, while the credit produces D+x. Thus the sum after transfer is (S-x)+(D+x) = S+D. Both balances remain within the schema's bounds.

When the debit or credit affects no row, the function raises an error before committing. The rollback prevents either change from surviving as a successfully completed transaction. A CHECK constraint supplies an additional defensive boundary even if an application bug reaches the database [2][3].

This is an argument about **one SQLite transaction**, not two different databases or a distributed payment network. The model neither proves exactly-once processing of external requests nor prevents a client from intentionally issuing the same valid transfer twice.

## Test the real boundary and understand limitations

Use a file-backed temporary SQLite database in independent tests. Seed two accounts, execute a valid transfer, close and reopen the database and check persisted balances. Test missing destinations, missing sources, overdrafts, duplicate accounts, negative amounts, Boolean amounts, a full destination account and suspicious quote characters in identifiers.

The SQLite engine coordinates writers and transactions on a database file, but crash behavior depends on journaling, synchronization settings and the filesystem [4]. A successful local test is not evidence that storage never loses recent changes under every power-failure model.

The program executes a bounded number of SQL statements. Their number is O(1), but database execution cost depends on indexes, B-tree pages, I/O, contention and storage size. Constant statement count is not a promise of constant elapsed time.

## Exercises and verification

1. Demonstrate rollback after the source debit succeeds but the destination does not exist.
2. Confirm insufficient funds never produce a negative persisted balance.
3. Test a credit that would push the destination above the schema maximum.
4. Show that a quoted owner name is compared as data instead of changing SQL syntax.
5. Reopen a file-backed database and verify a committed transfer.
6. Explain why local transaction atomicity does not guarantee exactly-once behavior for external requests.

Continue with [relational modelling](/en/topics/relational-model-sql-basics/), [schema migrations](/en/topics/sqlite-schema-migrations-user-version/) and [transactional consistency](/en/topics/database-consistency/).