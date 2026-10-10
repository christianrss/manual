# First architecture-foundations review — 2026-10-10

Scope: one new **bilingual** foundational article and a focused prerequisite correction; not an audit of the entire manual.

- **Machine representation:** eight-bit signed/two's-complement derivation, modular addition, byte order and alignment. The independent test checks all 256 signed values and all 65,536 possible pairs of 8-bit additions per language.
- **ISA vs microarchitecture:** RV32I is described using the ratified specification; the four-register eight-bit interpreter is explicitly **invented** and is not an emulator of real RISC-V instructions, exceptions, instruction encodings or timing.
- **Cache mapping:** direct-mapped address/block/set/tag derivation, conflict example, finite exhaustive traces independently verified by scanning preceding owners of the set. No associative caches, memory coherence, timing or CPU benchmarking claims.
- **Dependency repair:** first computer-architecture module entry in both core tracks and explicit prerequisite of the existing virtual-memory article.
- **Sources:** [RISC-V RV32I](https://docs.riscv.org/reference/isa/v20260120/unpriv/rv32.html), [Intel optimization manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel64-and-ia32-architectures-optimization.html), [Python integer bytes](https://docs.python.org/3/library/stdtypes.html).

Missing remain computer logic, ISA instruction encodings, microarchitectural pipelines, caches beyond direct mapping, coherence, DRAM, TLB details, interrupts, storage devices, performance counters and measurement. Successful CI validates the stated models, not real hardware behavior or independent academic peer review.
