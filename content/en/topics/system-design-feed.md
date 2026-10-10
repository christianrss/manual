---
id: system-design-feed
title: "System Design Case: Social Feed, Fanout and Timeline Ranking"
description: "Design a read-heavy feed using hybrid fanout, durable posts, chronological cursors, candidate hydration and privacy filters."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [system-design-process, data-partitioning-sharding, caching, api-contracts-pagination]
sources:
  - {title: "DynamoDB Data Modeling", url: "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/data-modeling.html", kind: "official engineering documentation"}
  - {title: "AWS Builders Library — Avoiding Insurmountable Queue Backlogs", url: "https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/", kind: "engineering article"}
---
A home feed combines content from many authors into one ordered view for a reader. It is deceptively expensive because a single post may have millions of followers, while some users refresh their feeds many times without posting. The fundamental design decision is **when to combine candidate posts**: when the author writes, when a reader asks, or through a hybrid. Neither extreme guarantees low cost across all follower distributions. This chapter develops a hypothetical chronological social feed; it does not claim to document any particular company's current architecture [1][2].

## Functional requirements, exclusions and privacy

Assume users publish text posts, follow or unfollow other accounts and read their home timeline in reverse chronological order. A user may delete their post or block a reader. The initial version supports **chronological ordering**, not personalized ML ranking, advertising, comments or recommendations outside the follow graph. Client pagination must be bounded and stable under ties. Posting an accepted message must create a durable record; appearing on every follower's home timeline may occur after a documented delay.

**Privacy and authorization** are requirements, not a downstream cache optimization. A timeline entry is merely a candidate: before returning it, verify the post still exists, the viewer can see the author and no block or deletion policy forbids visibility. An unfollow may race with precomputed fanout; the read path must filter stale candidate entries rather than trusting old caches.

## Read and write capacity assumptions

Consider **100,000 new posts/day**, 20 million home-feed requests/day and hypothetical 10× peak-to-average burst for both paths. Average post rate is about 1.16/s, while feed reads average 231.5/s and peak around 2,315/s. If each post is materialized into an average of 250 follower inboxes, all-push fanout generates **25 million inbox writes/day**, averaging 289 writes/s and potentially 2,894/s under the same hypothetical peak multiplier.

Assume each materialized pointer, its indexing and metadata are **200 logical bytes**. That means 5 GB of new logical pointers/day or about **1.83 TB/year** before replication, backups, index overhead and retention pruning. These are scenario numbers rather than platform claims. The mean is especially misleading: an author with five million followers creates five million writes from a **single post**, regardless of average fanout.

## Fanout on read, on write and hybrid

**Fanout on read** stores one authoritative author timeline and, when user U asks for a home feed, fetches recent posts from all accounts U follows, merging the lists. Posts are cheap to create and follows/unfollows take effect naturally if the graph is current. But readers following many authors may force hundreds of index range queries or distributed reads per refresh.

**Fanout on write** publishes each new post's ID into every follower's materialized home timeline. Readers mostly perform one indexed lookup of precomputed IDs, then hydrate bodies from post storage. The cost is write amplification, stale inbox references, repairs when a worker crashes and potentially massive bursts from high-follower authors. A precomputed timeline is a **derived index**, not the authority for post existence or visibility.

A **hybrid** uses push for ordinary authors and pull at read time for accounts with high follower counts or unfavorable fanout cost. The threshold should depend on measured active followers, write frequency, read volume, latency budget and operation costs, not an arbitrary label such as 'celebrity'. The approach balances average cost but retains complexity in merging, consistency and privacy.

![Hybrid feed architecture combining push fanout for ordinary authors and pull candidates for high-fanout accounts.](/diagrams/feed-hybrid-fanout.svg)

## API, authoritative data and indexing

One proposed contract uses POST /v1/posts (return 201 only after durable commit), POST /v1/follows/{author}, DELETE /v1/follows/{author}, and GET /v1/feed?limit=20&cursor=.... Ownership derives from the authenticated principal, not a client-supplied author ID. Explicitly define whether private posts can be indexed and how immediately blocks and deletions take effect.

A minimal model includes Post(post_id,author_id,created_at,body,deleted_at), Follow(follower_id,followee_id), AuthorTimeline(author_id,created_at,post_id) and HomeCandidate(viewer_id,created_at,post_id). Stable sorting uses (created_at DESC,post_id DESC). Composite keyset pagination returns items with an exclusive ordering key less than the last item displayed. A cursor is not an access-control token; each page still needs authorization.

The authoritative Post and Follow records are distinct from precomputed HomeCandidate. A durable outbox or change stream publishes the post ID so consumers can rebuild materializations after failure. Duplicate events are expected: a unique candidate key such as (viewer_id,post_id) makes fanout idempotent under at-least-once delivery.

## Executable hybrid reference model

The model below builds **push inboxes** for authors with fewer than three followers and merges **pull candidates** for larger authors. It intentionally runs in memory, assumes every post is public, and performs full scans to make semantics visible; real stores need indexed, bounded lookups and explicit privacy checks.

~~~python
def build_inboxes(posts, followers, cutoff):
    inboxes = {}
    for created, post_id, author in posts:
        readers = followers.get(author, set())
        if len(readers) < cutoff:
            for reader in readers:
                inboxes.setdefault(reader, []).append((created, post_id, author))
    return inboxes

def home_page(user, following, followers, posts, inboxes, cutoff,
              limit, cursor=None):
    if limit <= 0:
        raise ValueError("positive page size required")
    authors = following.get(user, set())
    candidates = list(inboxes.get(user, ()))
    for item in posts:
        if item[2] in authors and len(followers.get(item[2], set())) >= cutoff:
            candidates.append(item)
    dedup = {item[1]: item for item in candidates if item[2] in authors}
    ordered = sorted(dedup.values(), key=lambda p: (p[0], p[1]), reverse=True)
    if cursor is not None:
        ordered = [p for p in ordered if (p[0], p[1]) < cursor]
    page = ordered[:limit]
    continuation = (page[-1][0], page[-1][1]) if page else None
    return [p[1] for p in page], continuation

followers = {"alice": {"bob", "carol"},
             "star": {"bob", "carol", "dave", "erin"}}
posts = [(104,4,"alice"),(103,3,"star"),(102,2,"alice"),(101,1,"star")]
inboxes = build_inboxes(posts, followers, cutoff=3)
following = {"bob": {"alice", "star"}}
page1, cursor = home_page("bob", following, followers, posts, inboxes, 3, 2)
page2, _ = home_page("bob", following, followers, posts, inboxes, 3, 2, cursor)
assert page1 == [4, 3] and page2 == [2, 1]
assert len(inboxes["bob"]) == 2  # Only ordinary-author posts pushed.
following["bob"] = {"alice"}
assert home_page("bob", following, followers, posts, inboxes, 3, 5)[0] == [4, 2]
~~~

The tie-breaker is post_id, assumed unique. The demonstration has no persistent state, cancellation, ranking or optimized index. It illustrates that **unfollow filters candidates on read**, even if old materialized pointers still exist. Deletion, blocks and private-account policy require further filters at hydration time; a real API must not trust the given `following` mapping unless derived from an authenticated authority.

## Read-path architecture and ranking option

A practical read path is: authenticate reader → obtain the reader's materialized candidate IDs → query recent posts of high-fanout followed authors → merge and deduplicate IDs → filter visibility/deletions → optionally rank → hydrate bodies/media → emit a bounded page. Put caches at measured hotspots, but do not bypass block/deletion checks. Batching hydration by post ID is important; one database query per post creates N+1 remote-call amplification.

For ranked rather than chronological feeds, define the **ranking contract**: which signals are allowed, whether results need a snapshot, freshness bounds and explainable exclusions. Ranking can reorder candidates between page requests, invalidating a simple chronological cursor. A ranked feed may need a stable session snapshot, rank-token version or an explicitly approximate pagination contract.

## Backpressure, deletion and recovery

Fanout workers consuming a durable queue can fail after writing some follower entries and before acknowledging the event. Retrying should upsert by (viewer,post_id) rather than duplicate candidates. If a major author posts and a backlog forms, a queue is not an infinite buffer: bounded admission, priority fairness, oldest-age monitoring and recovery capacity protect useful latency [2].

Deletion is subtle: removing the Post authority should make its body invisible immediately under the product's stated consistency goal; stale inbox IDs can be lazily filtered and later cleaned. A blocked viewer must not be served private content just because a materialization pipeline missed an update. If a follower graph change races with fanout, reconcile or filter using the **current authorization relation**.

| Failure or trade-off | Expected mitigation | Remaining risk |
| --- | --- | --- |
| Celebrity creates millions of pushes | Pull high-fanout posts on read | Read-path merge cost |
| Fanout worker publishes twice | Unique viewer/post key | Backfill lag remains |
| User unfollows after materialization | Filter current graph at read | More work per page |
| Post deleted but cached | Read-time visibility check and invalidation | Stale caches before purge |
| Reader follows thousands of authors | Bounded candidate lookup, selective precompute | Scatter/gather pressure |
| Ranked feed changes between pages | Session snapshot/version policy | Extra storage and complexity |

## Verification and operational metrics

Test the correctness of merge and pagination under equal timestamps, duplicate events, deleted posts and unfollow/block races. Measure post-to-visible propagation delay (p50/p95/p99), materialized writes per post, candidate retrieval latency, per-author fanout skew, outbox/queue age, pagination duplicate rate, cache hit ratio and unauthorized-content incidents. Failure injection should kill a worker mid-fanout and show that replay repairs missing pointers without creating duplicates.

## Exercises and verification

1. Derive the 25 million daily fanout writes and 1.83 TB/year pointer estimate, naming the chosen units and assumptions.
2. Explain why a high-follower account invalidates an average-only capacity plan.
3. Prove the candidate sort and exclusive cursor avoid duplicates for **unchanged** chronological data with unique post IDs.
4. Write a filter that removes deleted posts and blocked authors before returning any hydrated bodies.
5. Compare the operational costs of pure push, pure pull and hybrid for a user following 2,000 accounts, one of which has ten million followers.

**Related chapters:** [System Design process](/en/topics/system-design-process/), [sharding](/en/topics/data-partitioning-sharding/), [asynchronous messaging](/en/topics/asynchronous-messaging/), [cache](/en/topics/caching/) and [API cursor contracts](/en/topics/api-contracts-pagination/) support this case.
