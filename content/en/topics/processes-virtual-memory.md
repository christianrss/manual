---
id: processes-virtual-memory
title: "Processes, Virtual Memory and System Calls"
description: "Derive process isolation, virtual-address translation, page tables, TLBs, context switching, syscalls and protection guarantees."
category: foundations
difficulty: intermediate
updated: 2026-10-10
prerequisites: [complexity-analysis, machine-representation-isa-cache]
sources:
  - {title: "MIT 6.1810 — xv6 teaching operating system", url: "https://pdos.csail.mit.edu/6.1810/2025/xv6.html", kind: "university reference"}
  - {title: "Operating Systems: Three Easy Pieces", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/", kind: "university textbook"}
---
An operating system provides controlled sharing of CPUs, memory and devices while isolating programs that should not trust one another. A **process** is more than a running executable file: it has an address space, execution state, open resources, permissions and a kernel-maintained identity. A **thread** is a sequence of execution within a process; multiple threads typically share the process address space while keeping separate registers and stacks [1][2].

The preceding [machine-representation and ISA chapter](/en/topics/machine-representation-isa-cache/) develops byte addressing and architectural state. Here we move one abstraction layer up: **virtual** addresses and kernel-managed protection are not CPU cache-line tags or a toy machine's physical byte indices. This distinction is essential before deriving page tables [1][2].


## Why isolation is needed

Two ordinary applications may use the *same numerical virtual address* without accessing the same physical bytes. Hardware privilege modes, virtual-memory translation and kernel-controlled page-table configuration establish boundaries between them. A process cannot safely write arbitrary kernel memory simply by computing its numerical address: privilege and mapping checks must reject the operation. Process isolation is a security **mechanism**, not a guarantee against all side channels, kernel vulnerabilities or incorrectly shared memory.

An executable on disk is passive; a process has dynamic state including program counter, register values, memory mappings and descriptors. Loading a program constructs an initial process image and arranges for instructions to begin in user mode. Scheduling determines when a runnable thread executes, and context switching saves/restores state so another can run. A switch can involve cache and TLB costs and is not always a cheap single instruction [2]. The [CPU scheduling chapter](/en/topics/cpu-scheduling-fcfs-round-robin/) derives FCFS and Round Robin separately from the context-switch mechanism.

## Virtual-to-physical address derivation

A virtual address does not directly name an arbitrary physical cell. For a page size P, decompose virtual address v into virtual page number floor(v/P) and offset v mod P. The page table maps the virtual page to a physical frame number, together with permission and validity bits. Translation becomes physical = frame×P + offset when the mapping exists and allows the requested operation. Different virtual pages can map the same frame intentionally, enabling shared memory, although aliasing then requires synchronization.

![Virtual page index, offset and physical frame translation.](/diagrams/page-translation.svg)

~~~python
def translate(virtual_address, page_size, page_table, operation="read"):
    if virtual_address < 0 or page_size <= 0:
        raise ValueError("invalid address or page size")
    vpn, offset = divmod(virtual_address, page_size)
    if vpn not in page_table:
        raise MemoryError("unmapped virtual page")
    frame, permissions = page_table[vpn]
    if frame < 0 or operation not in permissions:
        raise PermissionError("invalid mapping or denied operation")
    return frame * page_size + offset

table = {1: (7, {"read", "write"}), 2: (11, {"read"})}
assert translate(4096 + 13, 4096, table) == 7*4096 + 13
assert translate(8192, 4096, table, "read") == 11*4096
try:
    translate(8192, 4096, table, "write")
    assert False
except PermissionError:
    pass
~~~

This is a conceptual one-level translation example; real operating systems use multi-level page tables, hardware-defined page sizes and architecture-specific permission bits. The mapping belongs to a particular address space. Never use this code as a memory-safety enforcement mechanism; it merely illustrates arithmetic and logical checks.

## Page faults, TLBs and demand paging

A missing or prohibited mapping leads to a **page fault** or protection exception, depending on architecture and system policy. A fault is not automatically a bug: an OS may map a previously unallocated anonymous page or bring data from secondary storage. A prohibited access may instead terminate the process. The kernel handles the trap, distinguishes recoverable conditions from invalid accesses and resumes or reports failure.

A **translation lookaside buffer (TLB)** caches address translations. Without a matching entry, the processor or software may walk page tables; this adds work even if all referenced data are in RAM. Switching address spaces may require translation invalidation or tagging mechanisms such as address-space identifiers, depending on the CPU. A process with tiny CPU requirements may still incur significant overhead through memory access patterns and page faults [1].

## System calls and privilege transitions

A system call is a controlled entrance from user mode into privileged kernel code, usually via a special instruction and a validated system-call number/argument set. The kernel must validate user pointers and lengths; a user-provided pointer is not trusted kernel memory. Arguments may refer to file descriptors, buffer addresses or process identifiers. Returning from the call restores the appropriate execution context and privileges. An interrupt is initiated by an external event, whereas a syscall is an intentionally requested synchronous trap; both can enter kernel handlers, but their sources differ.

Consider reading a file: the program calls read(fd, buffer, count), the kernel verifies the descriptor and writable destination, resolves the underlying object, copies data according to the kernel's implementation, then returns the actual byte count or an error. A successful read may return fewer bytes than requested, so correct callers handle partial reads. This is an interface contract, not necessarily one direct disk access.

## Scheduling, switching and resource semantics

A running process may be preempted, block while waiting for I/O, or voluntarily yield. The scheduler chooses runnable work under policy, subject to fairness, priority and responsiveness goals. Thread switching within one address space can avoid some memory-map changes, but must still preserve stack and registers; concurrency also introduces race conditions when shared state is accessed.

| Concept | What it controls | Common misconception |
| --- | --- | --- |
| Virtual memory | Address translation and permissions | Every virtual byte occupies RAM immediately |
| Process | Isolation and resource namespace | Process means exactly one thread |
| Syscall | Controlled privileged service | User pointers are inherently trustworthy |
| Page fault | Invalid or absent translation event | Every fault must crash the application |
| Context switch | CPU execution ownership | Switching has zero cost |

## Trade-offs and limitations

Large pages reduce some translation overhead but increase internal fragmentation and may complicate allocation. Copy-on-write can share physical pages until a write requires copying; it demands accurate access permissions and fault handling. Excessive threads consume stacks and scheduling overhead, while too few threads may underutilize I/O waits. Security cannot be inferred from language runtime alone; kernel permission boundaries are a separate layer.

**Next chapter:** [Concurrency and synchronization](/en/topics/concurrency-synchronization/) builds on the distinction between process isolation, shared address spaces and independently scheduled threads.

## Exercises and verification

1. With page size 4096 and address 12,345, compute VPN=3 and offset=57; verify 3×4096+57=12,345.
2. Explain how two processes can both map virtual page 3 to different physical frames without conflict.
3. Distinguish a demand-zero page fault from a write to a read-only mapping: what action should the kernel take in each under a stated policy?
4. Why may a translation be incorrect after changing a page table unless stale TLB entries are addressed?
5. Trace open→read→close and identify the kernel validation boundary for file descriptors and user buffers.
