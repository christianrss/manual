# Scheduling foundations — editorial and test record (2026-10-10)

Scope: one complete bilingual CPU-scheduling chapter, prerequisites and references in existing process/concurrency articles, and a dedicated regression module.

A deliberately restricted single-CPU CPU-bound workload defines positive integer bursts, nonnegative arrivals, unique names, no blocking or context-switch costs, and an explicit tie policy that enqueues arrivals at quantum boundaries before the previous job. Both FCFS and Round Robin return exact execution slices. Response, ready-queue waiting and turnaround are distinct only under the stated no-I/O model.

The independent regression suite **does not reuse** the chapter's event-driven scheduling algorithm. Instead it simulates one tick at a time, compares CPU owners including idle time, and derives all three per-job metrics from the reference timeline. It enumerates jobs of lengths up to three, arrival times 0–2, bursts 1–3 and quantum sizes 1–3 in PT/EN, plus boundary and invalid-input cases. The existing chapter-fence runner checks all Python examples.

Sources: [Operating Systems: Three Easy Pieces](https://pages.cs.wisc.edu/~remzi/OSTEP/), [MIT xv6 scheduling](https://mit-pdos.github.io/xv6-riscv-book/sched.html), and [Python deque documentation](https://docs.python.org/3/library/collections.html#collections.deque).

Limitations: no true kernel scheduling, interrupts, priority inheritance, hard real-time deadlines, I/O, multicore, or starvation guarantee for unbounded arrivals. CI does not certify independent human review.
