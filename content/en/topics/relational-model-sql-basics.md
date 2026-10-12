---
id: relational-model-sql-basics
title: "Relational database fundamentals: keys, joins and data integrity"
description: "Derive tables, primary and foreign keys, normalization and SQL joins from a small data model with executable constraints."
category: databases
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-control-flow-functions]
sources:
  - {title: "PostgreSQL tutorial — SQL language", url: "https://www.postgresql.org/docs/current/tutorial-sql.html", kind: "official database tutorial"}
  - {title: "PostgreSQL documentation — Constraints", url: "https://www.postgresql.org/docs/current/ddl-constraints.html", kind: "official database documentation"}
  - {title: "SQLite documentation — Foreign key support", url: "https://www.sqlite.org/foreignkeys.html", kind: "official database documentation"}
---
A relational database is best understood first as **relations, keys, constraints and queries**, not as a set of database products. Before learning replication, transaction isolation or distributed persistence, an engineer must explain what a row represents, which values identify it, how tables relate, and why SQL queries can duplicate or omit rows. The SQL language provides operations to define and query relations, while constraints preserve selected data rules [1][2].

## Relations, rows, columns and schema

A relation has named attributes (columns) and tuples (rows) with values from defined domains. A database table is SQL's practical representation of a relation, but SQL tables can contain duplicate rows unless constrained and can contain NULL, so SQL does not perfectly model the mathematical set abstraction. A schema names tables, columns, types, defaults and rules for acceptable data. Each table should have an identifiable purpose: customers store customer attributes; orders represent purchases; order lines connect an order to purchased products.

Choosing a column type is part of modeling. A price in integer cents avoids representing 12.50 in binary floating point when a simple single-currency example requires exact cent accounting. This does not decide tax or foreign exchange rules. A quantity must be positive; the database can enforce it with CHECK rather than relying entirely on application validation.

## Keys, uniqueness and references

A **candidate key** is a minimal set of attributes that uniquely identifies a row according to the data model. A primary key selects one such identifier; other uniqueness constraints can protect additional candidate keys. A **foreign key** requires referenced values to exist in a target key, implementing referential integrity [2]. A compound key, such as (order_id, product_id), uses both fields to distinguish order lines; neither field alone is unique.

Keys embody business assumptions. If the same product is allowed on multiple order lines because discounts or batches differ, (order_id, product_id) is not a correct key for that domain. One might use a separate line_id or include a line position. Database design begins with requirements about identity rather than adopting an arbitrary schema from sample data.

A foreign key does not automatically grant permission to read a customer, and a unique index does not enforce every business policy. Authorization and transactional workflows require separate decisions. A nullable foreign key may be permitted depending on the schema; NOT NULL excludes that case. For SQLite, foreign-key enforcement must be explicitly enabled on the database connection used in the example [3].

## Functional dependencies and normalization

A *functional dependency* A → B states that values of attribute set A determine one value of attribute set B in the relation under the declared domain rules. Suppose an order table redundantly repeats customer_name on every order line. If customer_id determines customer_name, updating the customer's name may require changing many rows; missed updates create contradictory names. Splitting customers from orders reduces this update anomaly.

First normal form (1NF) is conventionally taught as using attribute values appropriate to the relational domains rather than packing arbitrarily repeated groups into a column. Second normal form addresses non-key attributes depending on only part of a composite candidate key; third normal form prevents certain transitive dependencies of non-prime attributes on keys. These are conceptual design rules with precise formal definitions; saying “never store a list” or “every table must have an auto-increment ID” oversimplifies them.

Denormalization is sometimes justified by workload and consistency design, but a duplicated fact then needs a clear update policy. Normalization is not automatically a performance optimization or a guarantee that two concurrent transactions are correct.

## SELECT, JOIN, grouping and NULL

`SELECT ... FROM` determines a query result; `WHERE` filters rows, `JOIN` combines rows whose join predicate matches, and `GROUP BY` collects rows into groups before aggregate functions operate. An INNER JOIN omits rows without matches. A LEFT JOIN keeps left-side rows and supplies NULL for missing right-side fields. SQL's NULL is not an empty string or numeric zero; arithmetic with NULL often yields NULL, and predicates can evaluate to UNKNOWN rather than true or false [1].

An order without lines should still appear in a report of orders. The query below uses LEFT JOIN and COALESCE to return a zero total for that hypothetical empty order. This is a **reporting convention**: an actual checkout may prohibit empty orders, but keeping the row here demonstrates query semantics. The line prices are stored as snapshots so changing a product catalog title does not change historical order totals.

~~~python
import sqlite3

db = sqlite3.connect(":memory:")
db.execute("PRAGMA foreign_keys = ON")
db.executescript("""
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL
);
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id)
);
CREATE TABLE order_lines (
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_cents INTEGER NOT NULL CHECK (unit_cents >= 0),
    PRIMARY KEY (order_id, product_id)
);
""")
db.executemany("INSERT INTO customers VALUES (?, ?)",
               [(1, "Ada"), (2, "Grace")])
db.executemany("INSERT INTO products VALUES (?, ?)",
               [(10, "Book"), (11, "Pen")])
db.executemany("INSERT INTO orders VALUES (?, ?)",
               [(100, 1), (101, 2)])
db.executemany("INSERT INTO order_lines VALUES (?, ?, ?, ?)",
               [(100, 10, 2, 1250), (100, 11, 3, 200)])

result = db.execute("""
SELECT c.name, o.order_id,
       COALESCE(SUM(l.quantity * l.unit_cents), 0) AS total_cents
FROM orders AS o
JOIN customers AS c ON c.customer_id = o.customer_id
LEFT JOIN order_lines AS l ON l.order_id = o.order_id
GROUP BY c.name, o.order_id
ORDER BY o.order_id
""").fetchall()
assert result == [("Ada", 100, 3100), ("Grace", 101, 0)]

try:
    db.execute("INSERT INTO order_lines VALUES (?, ?, ?, ?)",
               (100, 999, 1, 100))
except sqlite3.IntegrityError:
    pass
else:
    raise AssertionError("foreign key was not enforced")

try:
    db.execute("INSERT INTO order_lines VALUES (?, ?, ?, ?)",
               (100, 10, 1, 100))
except sqlite3.IntegrityError:
    pass
else:
    raise AssertionError("duplicate composite key was accepted")

assert db.execute("SELECT COUNT(*) FROM order_lines").fetchone()[0] == 2
db.close()
~~~

## Reason about correctness and query results

The inserts establish two customers, two products and two orders. Only order 100 has two lines: 2×1250 plus 3×200 gives 3100 cents. Order 101 has no matches in order_lines, so a LEFT JOIN preserves it and SUM returns NULL, which COALESCE maps to zero. An INNER JOIN instead would drop order 101 entirely. Replacing the JOIN condition with an unrelated predicate can multiply rows, making aggregate totals incorrect even when SQL syntax remains valid.

A relational constraint protects the invariant that no order line references an unknown product and that a given (order_id, product_id) appears at most once. The executable example tests both error paths. In SQLite, the CHECK and foreign-key behavior must be interpreted under the explicitly configured engine; the same SQL text is not evidence that every SQL dialect has identical behavior [3].

## Indexes, costs and the limits of simple complexity claims

For n order rows and m line rows, a naïve nested comparison of every order against every line could require O(nm) candidate checks. An optimizer may instead choose indexed lookups, hashing or sorting. A B-tree index can speed up many equality and range predicates, but index maintenance costs writes and memory; actual plans depend on cardinality, selectivity, statistics and the database engine. Do not claim “JOIN is O(1)” or “indexes always improve performance” from a small example.

Use `EXPLAIN` on a representative database and inspect scans, estimated versus actual row counts where supported, and index use. A primary key typically has supporting index behavior in common engines, but its implementation and clustered storage layout vary. The important foundation is knowing **which result should exist** before optimizing how it is computed.

## Counterexamples and exercises

A single table with customer name repeated on every line creates update anomalies. A many-to-many relation without a join table may force lists into columns and complicate integrity. A query with `COUNT(*)` across a LEFT JOIN counts the preserved left row even when no right match exists; `COUNT(l.product_id)` counts only matched products. These produce different results for order 101.

## Exercises and verification

1. Change the aggregate query from LEFT JOIN to JOIN and predict which order disappears. Check with the sample dataset.
2. Add a CHECK on quantity, then attempt quantity zero and verify the original data remains unchanged.
3. Allow repeated product lines and propose a new key; explain why the previous compound key no longer represents identity.
4. Explain how `COUNT(*)` and `COUNT(l.product_id)` differ for an order without lines.
5. Write the functional dependency customer_id → customer_name and demonstrate an update anomaly in a deliberately denormalized table.
6. Compare an index on (order_id, product_id) with one on (product_id, order_id), considering two different query predicates and ordered prefixes.

Continue with [SQL query planning](/en/topics/sql-query-planning/), [database consistency](/en/topics/database-consistency/) and [transaction isolation](/en/topics/transactional-indexing-isolation/) after mastering the relational model.