---
id: postgresql-serializable-retry-lab
title: "PostgreSQL Serializable Lab: Write Skew and Whole-Transaction Retries"
description: "Reproduce real PostgreSQL write skew at READ COMMITTED, block it with SERIALIZABLE and retry the full transaction."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [postgresql-concurrency-integration, transactional-indexing-isolation]
sources:
  - {title: "PostgreSQL 17 — Transaction Isolation", url: "https://www.postgresql.org/docs/17/transaction-iso.html", kind: "official database documentation"}
  - {title: "PostgreSQL 17 — Serialization Failure Handling", url: "https://www.postgresql.org/docs/17/mvcc-serialization-failure-handling.html", kind: "official database documentation"}
  - {title: "PostgreSQL 17 — Explicit Locking and Deadlocks", url: "https://www.postgresql.org/docs/17/explicit-locking.html", kind: "official database documentation"}
---
A database transaction can protect each row it updates and still violate a **business invariant involving several rows**. The canonical example is **write skew**: two doctors are on call, and each is allowed to leave only if at least one other doctor remains. They read the same initial state and update **different rows**, so a naive implementation can let both leave without any direct write/write conflict. This workshop demonstrates that anomaly against real PostgreSQL, then runs it at **SERIALIZABLE** isolation and retries the entire rejected transaction [1][2].

## Business rule and isolation assumptions

Define table `oncall(doctor PRIMARY KEY, active BOOLEAN)` initially containing A=true and B=true. An operation `leave(doctor)` must preserve **at least one active doctor**. Each operation reads the number of active doctors, checks whether it is greater than one, and, if so, updates its own doctor's row. A successful response means the update **committed**; an aborted transaction must not report success.

Two clients can independently use distinct database connections. With PostgreSQL's READ COMMITTED isolation, each SELECT sees a snapshot at statement start. If both reads occur before either UPDATE, both observe two active doctors. Updating different rows allows the two transactions to complete even though the **global invariant is broken** [1].

## Force both transactions to read first

The executable example [postgres_serializable_lab.py](https://github.com/christianrss/manual/blob/main/examples/python/postgres_serializable_lab.py) accepts an optional `threading.Barrier`. The real integration test starts two Python threads, each with an **independent PostgreSQL connection**, and requires both SELECT operations to finish before either worker issues its UPDATE. This is a deterministic coordination of a dangerous execution order, not an assumption that random load testing will eventually reproduce the anomaly.

![Two transactions both observe two active doctors and try to disable different rows; serializable isolation aborts one.](/diagrams/postgresql-write-skew.svg)

~~~python
def evaluate_snapshot(active_count):
    if active_count <= 1:
        return "denied"
    return "eligible_to_leave"

assert evaluate_snapshot(2) == "eligible_to_leave"
assert evaluate_snapshot(1) == "denied"
assert evaluate_snapshot(0) == "denied"
~~~

This pure function is **not a concurrency solution**: evaluating it twice with the same stale count of two produces two authorizations. The key issue is whether the reads and later writes are made consistent across the concurrent transactions.

## Observe READ COMMITTED write skew

The first test runs both operations in READ COMMITTED. After the barrier releases, A writes its own row false, and B writes the other row false. They do not directly conflict on the same row, and both can commit. The test deliberately asserts two `left` outcomes **and zero active doctors**, thereby documenting an expected failure of the business invariant.

It is important that the test considers this outcome evidence of the isolation level's limitation, **not** evidence that the database engine is defective. READ COMMITTED provides defined lower-level behavior; the application selected an insufficient guarantee for its cross-row rule [1].

## Prevent the anomaly with SERIALIZABLE

PostgreSQL's SERIALIZABLE isolation aims to make the outcome equivalent to some serial execution order. In a serial order, the first departure would leave one active doctor and the second must deny leaving. With the forced concurrent reads, PostgreSQL's serializable implementation detects the problematic dependency pattern and aborts one transaction with SQLSTATE **40001**, `serialization_failure` [1][2].

The test checks that one operation committed and the other raised SQLSTATE 40001, leaving exactly one doctor active. It does not assume **which** doctor commits. PostgreSQL may abort transactions for other reasons too; developers should not rely on a particular victim or error text.

## Retry the whole decision, not only the UPDATE

The official PostgreSQL guidance explicitly requires re-running **the complete transaction**, including decisions about which SQL statements or values to use, after serialization failure [2]. Repeating only the failed UPDATE could operate on stale logic and break the original invariant. A fresh transaction must re-read the number of active doctors; seeing one, it denies the second departure.

~~~python
RETRYABLE_SQLSTATE = {"40001", "40P01"}

def may_retry(sqlstate, attempts_so_far, max_attempts):
    return sqlstate in RETRYABLE_SQLSTATE and attempts_so_far < max_attempts

assert may_retry("40001", 1, 3)
assert may_retry("40P01", 1, 3)
assert not may_retry("23505", 1, 3)
assert not may_retry("40001", 3, 3)
~~~

The published `retry_off_call` uses a fresh connection and transaction for each attempt, with a **bounded retry count**. An interactive production service should also implement a total deadline, an appropriate jittered backoff, metrics for retry exhaustion and an idempotent external operation identity. The simple example avoids sleeping to keep the integration test deterministic and fast.

## Deadlocks are different from serialization anomalies

SQLSTATE **40P01** means a deadlock was detected. A classic deadlock occurs when transaction A holds lock on row X and waits for Y while B holds Y and waits for X. PostgreSQL detects the cycle and aborts one transaction [3]. Consistent lock ordering is a primary prevention technique, while a bounded whole-transaction retry may be appropriate when deadlocks remain possible.

In contrast, the doctor write-skew schedule updates **different rows**. It is not fixed just by selecting a random row lock per doctor. The rule spans the *set* of doctors, so the design must serialize or otherwise protect the rule, for example with a shared guard row or application-defined exclusive lock, or SERIALIZABLE plus correctly implemented retries.

## Concurrency, performance and operational limits

Strong isolation has operational costs. Serializable transactions may need retries under contention, so throughput and tail latency depend on conflicting read/write patterns. Holding a transaction open while waiting for a user or network dependency is particularly harmful: it increases lock lifetimes and makes retry logic difficult to reason about.

| Observation | Interpretation | Next action |
| --- | --- | --- |
| Two doctors leave in READ COMMITTED | Write skew under the forced schedule | Protect cross-row rule |
| One SERIALIZABLE transaction aborts | SSI prevents that anomalous commit | Retry the entire decision |
| Repeated 40001 under load | Contention or dangerous dependencies | Measure rate and tune workload |
| 40P01 | Deadlock, possibly inconsistent lock order | Inspect lock graph and order |
| 23505 | Unique constraint violation | Decide if business conflict or retryable race |

A green integration run demonstrates the chosen schedule against one PostgreSQL server. It does **not** certify replication failover, network partitions, all possible transaction interleavings or absence of starvation. Keeping that limitation explicit is part of production engineering.

## Exercises and verification

1. Write the READ COMMITTED interleaving that ends with zero active doctors while both clients believe they succeeded.
2. Explain why the two UPDATE statements do not cause a direct same-row write conflict.
3. Show why retrying only the UPDATE would skip the second doctor's now-invalid eligibility decision.
4. Replace SERIALIZABLE with a shared guard row lock and discuss the additional contention point.
5. Design metrics for 40001 and 40P01 rates, transaction attempts, p99 latency and permanently exhausted retries.

**Related chapters:** [Database isolation](/en/topics/transactional-indexing-isolation/), [concurrency workshop](/en/topics/concurrency-interview-workshop/), [PostgreSQL reservation lab](/en/topics/postgresql-concurrency-integration/) and [formal model checking](/en/topics/formal-model-checking/) deepen the analysis [1][2][3].
