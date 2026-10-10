---
id: inode-directories-journaling-recovery
title: "Filesystem Internals: Inodes, Block Allocation, Journaling and Recovery"
description: "Model inode identity, directory entries, noncontiguous block allocation and commit/replay crash boundaries with tested finite-state examples."
category: operating-systems
difficulty: intermediate
updated: 2026-10-10
prerequisites: [file-descriptors-buffering-fsync, heap-allocation-fragmentation]
sources:
  - {title: "MIT xv6-riscv book — File systems and logging", url: "https://mit-pdos.github.io/xv6-riscv-book/", kind: "university operating system textbook"}
  - {title: "OSTEP — File System Implementation and Crash Consistency", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/", kind: "university textbook"}
  - {title: "Linux kernel — ext4 on-disk journal (jbd2)", url: "https://www.kernel.org/doc/html/latest/filesystems/ext4/journal.html", kind: "official Linux kernel documentation"}
  - {title: "Linux kernel — ext4 filesystem administrator guide", url: "https://www.kernel.org/doc/html/latest/admin-guide/ext4.html", kind: "official Linux kernel documentation"}
  - {title: "Linux man-pages — fsync(2)", url: "https://man7.org/linux/man-pages/man2/fsync.2.html", kind: "official Linux syscall reference"}
---
A **filesystem** gives names to persistent objects while managing storage blocks, metadata and recovery. The [file-descriptor chapter](/en/topics/file-descriptors-buffering-fsync/) explains how a process refers to open objects and what `fsync` requests. This chapter looks underneath that API: a directory maps **names to inode identifiers**, an inode describes a filesystem object, and block mappings relate logical file ranges to allocated storage. In a real filesystem, changing those structures is a multi-write operation exposed to failures [1][2].

We build **two separate educational models**: a flat directory with inode IDs and a bitmap-like allocation table; and a metadata-only redo journal with an explicit commit record and replay procedure. The models do not share their state and cannot be composed into a reliable on-disk filesystem. This separation is deliberate: correct block allocation and correct transaction replay are different requirements.

## Names are not file identities

A directory entry associates one pathname component with a filesystem object identifier, often an inode number. The inode records attributes such as file type, size, permissions, timestamps and how to locate blocks. A descriptor created by `open` refers to an **open file description**, which in turn refers to a persistent file object. These are distinct levels of identity [1].

This distinction explains several otherwise surprising operations. **Rename** can change a directory name without changing a file's inode identity or its contents. A filesystem may allow multiple names referencing the same inode through **hard links**, tracking link counts. Unlinking a name need not immediately reclaim the inode if other hard links or open references survive. The correct lifetime condition involves both namespace references and active file references; naive deletion at the first unlink can destroy still-open data [1][2].

Our model intentionally permits **exactly one directory entry per inode** and has no open file descriptors. Consequently `unlink` immediately reclaims the inode and its blocks. This is **not Linux unlink semantics** in the presence of open descriptors or multiple hard links. The simplification keeps the conservation proof small instead of smuggling in an incorrect general rule.

## From logical file offsets to physical block identifiers

A file of size `L`, with block size `B`, needs `ceil(L/B)` blocks when stored densely. For a logical file offset `o`, the logical block number is `o // B` and the intra-block offset is `o % B`. An inode maps logical block numbers to storage block IDs; physical blocks do **not** have to be adjacent. This differs from the [contiguous heap allocation chapter](/en/topics/heap-allocation-fragmentation/), where one request must fit in one unbroken interval [1][2].

A free-block bitmap conceptually marks blocks as available or occupied. This can reduce the cost of finding free blocks compared with scanning all inode mappings, but it does not eliminate fragmentation or provide a universal allocation cost bound. Real filesystems use different structures: direct and indirect pointers, extents, allocation groups or B-trees, depending on format. xv6 is a small source-level reference for inodes, directories and logging; ext4 is substantially more complex [1][3].

Our Python array stores either `None` for a free block or exactly `B` bytes for an occupied block. `None` represents ownership state, **not the contents of a real device sector**. When a file grows, we take the lowest free block IDs available, even if noncontiguous, then rewrite the dense file representation. There are no sparse holes, indirect blocks or delayed allocation. The class is a model of **logical block assignment**, not a device driver.

## Allocation failure must preserve the filesystem state

Suppose a two-block file wants a third block but all blocks belong to other files. The operation should fail under this teaching contract without changing inode size, directory entries or previously stored blocks. A naive implementation that updates inode size **before** ensuring a block is available leaves inconsistent metadata after a failed request.

To make this check meaningful, the allocation operation first constructs the prospective file content, computes required block count and checks whether enough free IDs exist. **Only after that preflight** does it mutate block data and inode metadata. Each successful growth reserves its additional blocks; none is simultaneously assigned to another file. A zero-byte append is explicitly a no-op that succeeds even if the device has no remaining free blocks.

An allocation can also fail on an actual system because of quotas, I/O faults, reservations or ENOSPC decisions, none of which this model implements. We reject invalid object names and non-byte payloads to expose the input contract independently of storage exhaustion.

## Executable inode and block model

The flat directory accepts simple names without slash, trimming whitespace or the special entries `.` and `..`. `create` allocates a new inode ID; `rename` changes the directory key without changing inode ID; `append` uses as many noncontiguous free slots as required; `unlink` returns those slots to the free pool. No read/write offset is tracked because open descriptions belong to the preceding chapter.

~~~python
class TinyBlockFS:
    def __init__(self, count=8, block_size=4):
        if (type(count) is not int or count <= 0
                or type(block_size) is not int or block_size <= 0):
            raise ValueError("positive integer block geometry required")
        self.block_size = block_size
        self.slots = [None] * count
        self.directory = {}
        self.inodes = {}
        self.next_inode = 1

    def _name(self, name):
        if (not isinstance(name, str) or not name
                or name != name.strip() or "/" in name
                or name in (".", "..")):
            raise ValueError("invalid flat-directory name")

    def _inode(self, name):
        if name not in self.directory:
            raise KeyError(name)
        return self.inodes[self.directory[name]]

    def create(self, name):
        self._name(name)
        if name in self.directory:
            raise FileExistsError(name)
        inode_id = self.next_inode
        self.next_inode += 1
        self.inodes[inode_id] = {"size": 0, "blocks": []}
        self.directory[name] = inode_id
        return inode_id

    def read(self, name):
        inode = self._inode(name)
        contents = b"".join(self.slots[i] for i in inode["blocks"])
        return contents[:inode["size"]]

    def append(self, name, payload):
        inode = self._inode(name)
        if type(payload) is not bytes:
            raise ValueError("bytes required")
        if not payload:
            return True
        content = self.read(name) + payload
        needed = (len(content) + self.block_size - 1) // self.block_size
        extra = needed - len(inode["blocks"])
        available = [i for i, block in enumerate(self.slots) if block is None]
        if extra > len(available):
            return False  # failure leaves all state unchanged
        allocated = inode["blocks"] + available[:extra]
        for position, index in enumerate(allocated):
            chunk = content[position * self.block_size:
                            (position + 1) * self.block_size]
            self.slots[index] = chunk.ljust(self.block_size, b"\x00")
        inode["blocks"] = allocated
        inode["size"] = len(content)
        return True

    def rename(self, old, new):
        self._name(new)
        if old not in self.directory:
            raise KeyError(old)
        if new in self.directory:
            raise FileExistsError(new)
        self.directory[new] = self.directory.pop(old)

    def unlink(self, name):
        inode = self._inode(name)
        for index in inode["blocks"]:
            self.slots[index] = None
        del self.inodes[self.directory.pop(name)]

    def usage(self):
        used = sum(block is not None for block in self.slots)
        return (used, len(self.slots) - used)

fs = TinyBlockFS(4, 4)
assert fs.create("a") == 1
assert fs.append("a", b"abcde")
assert fs.create("b") == 2
assert fs.append("b", b"1234")
assert fs.append("a", b"fghij")
assert fs.read("a") == b"abcdefghij"
assert fs.usage() == (4, 0)
assert fs.append("b", b"56") is False
assert fs.read("b") == b"1234"  # failed growth did not mutate
fs.unlink("a")
assert fs.usage() == (1, 3)
assert fs.append("b", b"56")
fs.rename("b", "c")
assert fs.read("c") == b"123456"
assert fs.usage() == (2, 2)
~~~

The example first fills four storage blocks. Although files A and B are different, they occupy the same allocation pool and cannot overwrite one another's blocks. The attempted growth of B fails without mutation. Removing A releases its three blocks, allowing B to grow even though the available block indices are not required to form a single contiguous range. Renaming B to C preserves inode ID, content and allocated block ownership.

**Conservation invariant:** let `S` be occupied block indexes and `F` the free indexes. They partition `{0,...,N-1}`. Every allocated index appears in **exactly one** live inode's block sequence, and the number of blocks referenced by an inode is `ceil(file_size/B)` (zero for empty files). Unused tail bytes in the last block are **padding in this model**, not another independent allocation. A directory key references one live inode and every live inode has exactly one key.

With `n` blocks and `L` bytes of existing file contents, `append` scans `O(n)` block slots for availability, joins existing data and rewrites `O(L+payload)` bytes, so it is emphatically **not an efficient write path**. Directory and inode-table lookups are expected-constant average-case dictionary operations for bounded identifiers. The simulation stores full allocated block contents, so its space usage is `O(nB + metadata)` in the worst case. A production filesystem must solve much more than this model [1].

## Directories, hard links and filesystem reachability

The directory is itself a specialized filesystem object in a real implementation, and multi-component path resolution traverses one directory entry at a time. Permissions and symlinks alter lookup behavior, including whether a path is traversable. Our single-level string dictionary does **none** of that: there is no root inode object, no `..` traversal, no symlink cycle, no rename between directories and no atomic rename-over-existing-file operation.

In a real system, after unlinking the last name, an inode may remain reachable through a still-open file description. Conversely, a directory entry pointing to a missing inode is inconsistent metadata. Reachability checks, link counts, orphan lists and recovery mechanisms address these distinctions [1][2]. The simple invariant “one directory name per inode” cannot be applied as an ext4 invariant. It is only a contract of this pedagogical subset.

## Why ordering matters across power loss

Appending a new block can require updating at least **three kinds of storage state**: block contents, an allocation bitmap, and inode size/block pointers. A sudden system failure between these writes can leave the bitmap marking a block free while an inode still points to it, or a block marked allocated but unreachable. The first case risks reuse and data corruption; the second wastes space [2].

**Crash consistency** is distinct from ordinary function-level atomicity. The preflight in our in-memory model prevents partial updates from valid ENOSPC failures, but **does not** make three physical disk writes indivisible across power failure. The earlier [buffering and fsync chapter](/en/topics/file-descriptors-buffering-fsync/) explains that writes can be visible before being durable and why the containing directory can require a separate sync for new names [5].

A filesystem checker (`fsck`) can reconstruct or repair certain invariants by scanning on-disk state; this is different from a journal's replay of previously recorded operations. Checking after a crash may repair consistency while losing file contents or names. It is not a general guarantee that all acknowledged updates survive [2].

## Metadata journaling and the commit marker

A **write-ahead redo journal** records intended changes before applying them to the home metadata blocks. A transaction is replayable only after a complete, durably written journal record set **and a durable commit marker**. After that boundary, updates may be installed in their final locations. If a crash interrupts installation, replay repeats the committed writes. Repeating an assignment of a predetermined value is idempotent, so replay can safely cover records already installed [1][3].

The ordering of stable writes is the essential property; simply appending entries to a Python list is **not** sufficient for crash safety on hardware. Real journals must handle torn writes, checksum verification, barriers, write-cache behavior, log space and recovery ordering. The Linux ext4 jbd2 documentation describes committed metadata transactions and replay; by default, ext4 does **not journal all file data**. Modes such as `data=ordered`, `data=writeback` and `data=journal` have materially different data-ordering guarantees [3][4].

The following second model only stores **integer-valued metadata fields** such as an inode size and a bitmap count. It simulates a transaction with durable journal entries and a commit marker as **indivisible abstract events**. A committed transaction may be partly applied to `home` before a crash, and recovery reapplies the entire journal. It does not model data payloads, a circular journal, real disk sectors or physical fsync operations.

## Executable redo-log recovery model

~~~python
class MetadataRedoLog:
    def __init__(self, home):
        if (not isinstance(home, dict)
                or any(not isinstance(k, str) or not k
                       or type(v) is not int or v < 0
                       for k, v in home.items())):
            raise ValueError("metadata must map keys to nonnegative integers")
        self.home = dict(home)
        self.records = []
        self.committed = False
        self.installed = 0

    def stage(self, key, value):
        if self.committed:
            raise RuntimeError("finish or recover current transaction first")
        if (not isinstance(key, str) or not key
                or type(value) is not int or value < 0):
            raise ValueError("invalid metadata record")
        self.records.append((key, value))

    def commit(self):
        if self.committed or not self.records:
            raise RuntimeError("no new transaction available")
        self.committed = True  # abstract persisted commit marker

    def install_one(self):
        if not self.committed:
            raise RuntimeError("install requires a committed journal")
        if self.installed == len(self.records):
            return False
        key, value = self.records[self.installed]
        self.home[key] = value
        self.installed += 1
        return True

    def finish(self):
        if not self.committed or self.installed != len(self.records):
            raise RuntimeError("checkpoint cannot precede full installation")
        self.records = []
        self.committed = False
        self.installed = 0

    def recover(self):
        if self.committed:
            # Redo is idempotent: replay from the beginning, including
            # entries possibly installed before the crash.
            for key, value in self.records:
                self.home[key] = value
        self.records = []
        self.committed = False
        self.installed = 0

log = MetadataRedoLog({"inode.size": 0, "bitmap.used": 0})
log.stage("inode.size", 8)
log.stage("bitmap.used", 2)
log.recover()  # crash before commit marker: discard transaction
assert log.home == {"inode.size": 0, "bitmap.used": 0}
log.stage("inode.size", 8)
log.stage("bitmap.used", 2)
log.commit()
assert log.install_one()
assert log.home == {"inode.size": 8, "bitmap.used": 0}
log.recover()  # crash after commit: replay both records
assert log.home == {"inode.size": 8, "bitmap.used": 2}
log.stage("inode.size", 12)
log.commit()
assert log.install_one()
log.finish()
log.recover()
assert log.home["inode.size"] == 12
~~~

Trace the failure boundary. Before `commit`, `recover` discards the uncommitted records and preserves the original home metadata. After `commit`, `install_one` updates only the inode size, leaving the home metadata temporarily inconsistent; `recover` replays both committed assignments and restores consistency. The model assumes no reader examines partial checkpoint state, and both records are self-contained repeatable assignments.

The critical **redo invariant** is conditional: if the commit marker is absent, no updates were installed and recovery must ignore the staged transaction. If the marker is present, all of its records will be replayed, even if an initial prefix was already installed. The implementation disallows `install_one` before commitment, and `finish` before all records are installed. Clearing an unfinished committed journal would otherwise lose information required for recovery.

After recovery, the `home` state must equal either the original state (uncommitted) or the state obtained by applying the complete committed record sequence **in record order**. The record sequence may assign the same key more than once; the last assignment wins. These rules can be checked by an independent oracle that computes the expected final dictionary without using the journal's replay routine.

## ext4 jbd2, application fsync and database WAL

The ext4 default mode journals **metadata** and normally orders certain dirty data writes before committing the relevant metadata. That reduces specific crash hazards but does not make arbitrary application writes into atomic database transactions [3][4]. The `data=writeback` mode has weaker data ordering, while `data=journal` journals data and metadata with different performance tradeoffs. Exact effects also depend on filesystem configuration and successful storage writeback.

A successful `fsync` request has defined obligations at the file and directory level; journaling by itself is not a substitute for choosing the correct application synchronization boundary. For replacement via temporary file, applications must reason about writing and syncing the temporary file, renaming it and synchronizing the parent directory, including failures at each stage [5].

Database WAL solves a **different transactional layer**: row changes, indexes and database recovery may require ordered log records before modified database pages are written. A filesystem journal can keep its own metadata structurally consistent without proving a relational transaction committed. The [database-storage and WAL chapter](/en/topics/database-storage-wal/) treats that separate protocol.

## Exercises and verification

1. Compute the logical block index and intra-block offset for file offset 19 with block size 8, and explain why the selected physical block ID need not be 2.
2. Execute a three-block file and another one-block file in a four-block model. Explain why a growth request fails without mutation and why freeing one inode changes available capacity.
3. Rename a file and show which properties stay unchanged: name, inode ID, byte content and block IDs. Discuss what would differ under replace-existing semantics.
4. Extend the inode table with hard-link counts and a separate set of open descriptions. State precisely when blocks may be reclaimed after unlink.
5. Design a checker that discovers duplicate block ownership, missing inode references, leaked occupied blocks and wrong `ceil(size/B)` counts.
6. Enumerate crashes before the journal commit marker and after each installed record. Derive the recovered home state in every case.
7. Modify redo to support multiple transactions sequentially. Explain why checkpointing and journal truncation require ordering, and why the example has no concurrency.
8. Compare `fsync` on a newly created file with `fsync` on its containing directory. What failures can leave the name missing despite durable file bytes?
9. Compare metadata-only journaling, full data journaling, and application/database WAL. Identify a guarantee that **none** can give without assumptions about the storage device.

**Next:** filesystem experiments with controlled fault injection and a real file-backed model can examine intermediate on-disk states, while network fundamentals and cryptographic primitives remain separate curriculum gaps. This chapter proves only its **finite abstract contracts**, not Linux filesystem durability [1][2][3][4][5].
