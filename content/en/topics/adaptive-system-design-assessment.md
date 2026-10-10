---
id: adaptive-system-design-assessment
title: "Adaptive System Design Drill: Document Processing Under Changing Requirements"
description: "Redesign a multi-tenant document pipeline as traffic, noisy neighbors, outages, deletion rules and data residency evolve."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [system-design-process, service-boundaries, asynchronous-messaging]
sources:
  - {title: "Amazon SDE II Interview Preparation", url: "https://amazon.jobs/content/en/how-we-hire/sde-ii-interview-prep", kind: "official employer guidance"}
  - {title: "AWS Builders Library — Avoiding Insurmountable Queue Backlogs", url: "https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/", kind: "original engineering guidance"}
---
A strong System Design answer is a **series of justified revisions under new constraints**, not a single diagram memorized in advance. Interviewers can change traffic, data retention, geography or consistency expectations after a candidate has proposed a plausible first version. The engineering skill is to protect invariants, recompute capacity, acknowledge newly introduced failure modes and decide when a new component pays for itself. This original workshop uses a multi-tenant document-processing service; it is **not** an official or recovered employer interview prompt. Public SDE II preparation guidance names design and technical judgment as areas of evaluation, without prescribing this exact problem [1].

## Round zero: define the smallest useful product

A SaaS application accepts PDFs from authenticated tenants, extracts text and returns a searchable document status. The user sends POST /v1/documents with an operation key and uploads a file to an authorized object-store location. They can query GET /v1/documents/{id} and later delete the document. Successful HTTP 202 means the system **durably accepted a processing job**, not that text extraction completed.

Choose an authoritative metadata table containing document ID, tenant ID, content digest, state, object pointer and version. Object storage holds the bytes, while a durable job queue drives worker execution. A search index is a **derived view** of extracted text, not authority for document deletion or tenancy. The first design can be a modular monolith and a single database, with separate worker processes, before service boundaries are justified.

## State machine and ownership

A document moves through `uploaded → queued → processing → ready`, or `processing → failed`. Deletion is a tombstone that must eventually remove the blob and all derived index entries. Define whether users may retry failed documents; retries must carry stable document IDs and a versioned attempt key. If a worker finishes after deletion, it must **not resurrect** a search record or restore visibility. A version check and current authorization state guard completion.

![Architecture evolves from a single durable queue to tenant-aware and region-aware capacity.](/diagrams/adaptive-system-design-drill.svg)

An upload and SQL metadata commit usually are not one ACID transaction. Plan staged persistence: reserve ID, upload to a scoped temporary object, verify checksums, commit the ready-to-process pointer, and later garbage-collect orphaned temporary uploads. This is more complex than saying “the API writes blob and row at once,” but it names the gap that must be tested.

## Round one: quantify workload

Assume **120,000 new documents/day**, average size **4 MiB**, and average extraction time **2 seconds of worker CPU** per document, before indexing and I/O. That's about 1.39 jobs/s average, 480,000 MiB/day (roughly 468.75 GiB/day) of new input bytes, and 240,000 CPU-seconds/day for extraction. At 20× peak-to-average job rate, the peak is approximately 27.8 jobs/s. To keep up with peak on dedicated workers that each deliver **one CPU-second per wall-second**, a simplistic CPU budget requires around 56 continuously utilized cores before headroom and overhead.

This is a hypothetical exercise. A real OCR workload varies dramatically with scanned pages, language, compression, file types and hardware; **mean seconds per document may hide long-tail tasks**. Measure p95 processing time and bound memory use rather than buying machines based only on mean. Make explicit whether OCR is included and define maximum accepted file size.

~~~python
from math import ceil

def minimum_worker_cores(documents_per_day, cpu_seconds_per_document,
                         peak_multiplier=1):
    if documents_per_day < 0 or cpu_seconds_per_document <= 0 or peak_multiplier <= 0:
        raise ValueError("invalid workload")
    peak_jobs_per_s = documents_per_day / 86400 * peak_multiplier
    return ceil(peak_jobs_per_s * cpu_seconds_per_document)

assert minimum_worker_cores(120_000, 2, 20) == 56
assert minimum_worker_cores(86_400, 1, 1) == 1
~~~

A result of 56 means nominal parallel CPU budget at an idealized utilization, **not** a recommended production worker count. Add redundancy, admission policy and measured resource profiles.

## Round two: one tenant drives most of the load

New constraint: one tenant suddenly contributes **75% of processing jobs**, with many very large files. A single FIFO queue can let that tenant dominate concurrency and delay every other account. Revision: limit inflight work per tenant, use weighted-fair dispatch across tenant partitions or queues, and apply quotas before accepting work that cannot fit promised completion times [2].

The same mechanism changes billing and SLOs: a quota-rejected request has a distinct response from a durably accepted but delayed job. Do not claim a five-minute completion SLO if admitted backlog cannot be drained within that window. Track oldest job age and completion percentiles per tenant, not just total queue depth.

## Round three: demand doubles after an outage

Suppose workers stop for **ten minutes** at a steady hypothetical 30 jobs/s incoming rate, accumulating 18,000 jobs. When healthy workers resume at 50 jobs/s but arrival stays 30 jobs/s, only 20 jobs/s of spare capacity is available for backlog. It takes **900 seconds, or 15 minutes**, to drain the accumulated tasks, assuming constant rates and no retries [2].

~~~python
def recovery_seconds(arrivals, outage_seconds, processing_capacity):
    if arrivals < 0 or outage_seconds < 0 or processing_capacity <= arrivals:
        raise ValueError("positive drain margin required")
    from math import ceil
    return ceil(arrivals * outage_seconds /
                (processing_capacity - arrivals))

assert recovery_seconds(30, 600, 50) == 900
assert recovery_seconds(30, 600, 45) == 1200
try:
    recovery_seconds(30, 600, 30)
    assert False
except ValueError:
    pass
~~~

This fluid-rate calculation does not bound p99 completion, account for 4 MiB upload traffic, or incorporate expensive retries. A team may reserve a recovery pool or temporarily lower admission to restore SLOs; queueing alone does not create throughput.

## Round four: strict deletion and geographic requirements

New requirement: a tenant can demand that documents never leave a named geographic region. Routing by user IP is not an adequate data-residency policy: users travel, CDN caches exist, and background workers might process elsewhere. Record region as a **tenant-level authority constraint** and bind blob storage, processing queue, workers, metadata and derived indexes to that permitted residency domain. Cross-region failover becomes conditional on explicit policy, not an automatic availability win.

Another constraint: documents must be deleted on request within a defined deadline. Search index cleanup is asynchronous, so authorize reads against the metadata tombstone **even while the index is stale**. Set separate retention rules for backups, logs, processing scratch files and derived text. A SQL `DELETE` statement does not magically erase every copy or backup.

## Round five: preserve correctness under ambiguous retries

If an extractor writes the search index and crashes before committing job completion, the broker may retry. The worker must index using a stable (document ID, version) key, or upsert a deterministic version, so a retry does not duplicate search entries. If the user deleted the document meanwhile, an index rebuild must obey the latest tombstone. This is a conflict of **versioned authority**, not just an API retry loop.

A response timeout after an accepted POST likewise requires an idempotency key scoped to tenant and payload fingerprint. The same key with different document bytes should be rejected or handled by an explicitly documented conflict policy. A client-generated digest helps detect differences but must not act as an authorization token.

## Review rubric and decision points

| Changed requirement | What to reconsider | What must remain true |
| --- | --- | --- |
| 20× peak | Worker concurrency, quotas, buffering | Accepted jobs have durable identity |
| Hot tenant | Scheduling and fair shares | Other tenants remain isolated |
| Ten-minute outage | Recovery margin and backlog age | No unacknowledged job silently disappears |
| Regional restriction | Storage and processing placement | No forbidden data movement |
| Immediate user delete | Tombstones and derived views | Deleted data cannot be served |
| Retry after ambiguous response | Idempotency keys and versions | Same intent is not duplicated |

Use a review rubric of 20 points for clarification and contracts, 20 for capacity math, 20 for authority and consistency, 20 for failure and recovery, and 20 for communicating changed trade-offs. This is an **independent educational rubric**, not an employer scoring guide. An elegant diagram with no answer about deletion races should not pass a serious architecture review.

## Exercises and verification

1. Recompute nominal CPU capacity for 600,000 documents/day with average 1.5 CPU-seconds and 8× peak.
2. Show why one shared FIFO may violate fairness when a single tenant supplies 75% of jobs.
3. Propose a tombstone/version race test where deletion occurs while OCR work finishes.
4. Explain which components must remain regional for a tenant with strict data-residency policy.
5. Revisit the architecture after a **new** constraint: files are encrypted with tenant-managed keys that can be revoked instantly. State which prior assumptions fail.

**Related chapters:** [System Design methodology](/en/topics/system-design-process/), [service boundaries](/en/topics/service-boundaries/), [RabbitMQ integration](/en/topics/rabbitmq-durable-consumer-integration/) and [queue recovery](/en/topics/system-design-notifications/) support this iterative approach [1][2].
