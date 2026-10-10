# CPU pipeline, hazards and branch-prediction review — 2026-10-10

Scope: one new bilingual computer-architecture chapter, deliberate inter-chapter links, taxonomy and curriculum updates, and new finite independently specified tests. No claim of full CPU microarchitecture coverage or measured hardware behavior.

Technical contracts:

- Toy **five-stage single-issue** pipeline with IF/ID/EX/MEM/WB and fixed conventions: read at start of ID/EX, producer values at end of EX/MEM/WB.
- RAW issue separation with/without forwarding; *load-use* one-bubble case. Schedules validated by an independent brute-force timeline oracle scanning preceding writers for all programs up to length 4 over five instruction forms, in both languages.
- Two-bit saturating counter **pre-update predictions** checked against an independently specified four-state transition table across every outcome sequence up to length seven and all initial states, in both languages.
- Explicitly distinguishes fill/drain, throughput vs latency, CPI assumptions, architectural correctness, branch recovery and the lack of memory aliasing/coherence/exceptions/out-of-order behavior.

Primary sources: [MIT 6.004 pipelining lecture](https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/pages/c15/c15s1/), [MIT 6.5900 architecture lecture notes](https://csg.csail.mit.edu/6.5900/lecnotes.html), [Intel optimization guides](https://www.intel.com/content/www/us/en/developer/articles/technical/intel64-and-ia32-architectures-optimization.html).

Remaining work: physical timing measurements, precise exceptions, OoO core mechanics, branch target/history tables, cache coherence, multicore memory ordering and OS scheduling. Passing the code/CI tests is not independent human peer review.
