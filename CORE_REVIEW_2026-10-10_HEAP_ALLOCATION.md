# Heap allocation and fragmentation — focused technical review (2026-10-10)

Scope: one detailed bilingual chapter, targeted curriculum adjustments, links from processes/virtual memory, and an **independent** behavioral oracle test. This is not a comprehensive systems-memory audit or a Linux malloc/kernel implementation.

**Contracts**
- One logical address arena [0,N), positive integer capacity and request sizes, unique live string handles; allocation returns start address or None when no sufficiently large **contiguous** hole exists.
- Address-ordered free-list intervals that split on allocation and coalesce adjacent spans on release; unknown handles raise; valid no-space failures leave state unchanged.
- First-fit takes the lowest-address suitable hole; best-fit takes the smallest suitable length, breaking ties by address; neither promised universally low fragmentation.
- Metrics report (total free, largest free, total-largest), explicitly **not** a standardized measure of all wasted memory. Separate class-rounding model distinguishes internal slack from external fragmentation.
- Does not track physical memory, backing bytes, real pointers, alignment, concurrency, memory safety, fragmentation of a Linux buddy page allocator, virtual-to-physical mappings or process permissions.

**Evidence**
- Independent reference allocator represents ownership as **one bitmap entry per address**, reconstructs canonical free spans after every operation, and compares choices and full state for **2×Σ(n=0..4)8ⁿ = 9,362 traces per language** across first/best policies. This includes failure, double-free, duplicate-label and coalescence histories; explicit 16- and 20-unit scenarios.
- Finite checks of rounded reservations across payloads 1..64 and granularities 1..12 and invalid-value rejection.
- The tests run the Python examples extracted from **both** articles, alongside the repository's existing content and CI gates.

Sources: [OSTEP](https://pages.cs.wisc.edu/~remzi/OSTEP/), [Linux physical memory](https://www.kernel.org/doc/html/latest/mm/physical_memory.html), [Linux memory APIs](https://www.kernel.org/doc/html/latest/core-api/mm-api.html).

Remaining work: page buddy allocator simulation, size-class caches and internal allocator metadata, compaction, paging/reclaim, file descriptors, buffered I/O, filesystem crash consistency, and hardening. Finite successful tests do **not** certify correctness on arbitrary inputs or production environments.
