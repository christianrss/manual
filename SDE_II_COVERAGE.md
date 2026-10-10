# SDE II — Current scope and evidence

Reviewed 2026-10-10. See [CURRICULUM.md](CURRICULUM.md) for the audited prerequisite map, coverage gaps and review gates. See [the live track](https://manual.christiansoftware.org/en/tracks/amazon-sde-ii/) for the published reading path.

The core focuses on correctness, data structures, algorithms, maintainable implementation, databases, design and independent assessments. The core Clean Code/cohesion/coupling chapter is now published as a prerequisite for object design. Builder, Facade and Observer now have tested bilingual examples in addition to Strategy, Adapter and Decorator; remaining specialist patterns and independent evaluation still require further work. Existing broker failover experiments are **electives**, not mandatory SDE II prerequisites. Introductory machine representation and a separately tested five-stage **teaching pipeline** are published; realistic CPU implementation, cache coherence, cryptography, language theory and foundational networking remain **not fully covered**. Successful builds do not establish independent readiness.

Official sources: [OA preparation](https://amazon.jobs/content/en/how-we-hire/sde-ii-oa-prep), [interview preparation](https://amazon.jobs/content/en/how-we-hire/sde-ii-interview-prep), [interview topics](https://amazon.jobs/content/en/how-we-hire/interview-prep/software-development-topics).

A bilingual FCFS/Round Robin chapter now precedes concurrency, with exhaustive finite tick-oracle verification. Real kernel context switching, unbounded fairness, multi-CPU priority scheduling and I/O remain uncovered.

Advanced scheduling now distinguishes MLFQ promotion/aging from transitive lock priority inheritance, with bounded executable tests. It is a model rather than a live Linux scheduler benchmark or real-time guarantee.

A new bilingual introductory allocator model distinguishes external/internal fragmentation and virtual/physical address spaces, with first-fit, best-fit and independent bitmap verification. Production allocator engineering, actual kernel/filesystem I/O testing and real-time/multicore behavior remain beyond the current teaching examples.

File descriptors now have a standalone tested bilingual introduction to shared open descriptions, offsets and an abstract fsync/crash boundary; file layout, hardware failure testing and complete filesystem crash consistency are not certified by these teaching models.

Filesystem foundations now include a bilingual inode/directory/block model and a separate metadata redo-log crash abstraction; independently verified finite sequences do not imply correct Linux/ext4 recovery, real-device durability or a complete filesystem implementation.
