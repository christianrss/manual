---
id: file-descriptors-buffering-fsync
title: "File Descriptors, Buffered I/O and fsync Crash Boundaries"
description: "Trace open file descriptions, dup, shared offsets, read/write, buffering, fsync and crash recovery with independently verified Python models."
category: operating-systems
difficulty: intermediate
updated: 2026-10-10
prerequisites: [processes-virtual-memory]
sources:
  - {title: "Operating Systems: Three Easy Pieces — File Systems", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/", kind: "university textbook"}
  - {title: "Linux man-pages — open(2)", url: "https://man7.org/linux/man-pages/man2/open.2.html", kind: "official Linux/POSIX API reference"}
  - {title: "Linux man-pages — dup(2)", url: "https://man7.org/linux/man-pages/man2/dup.2.html", kind: "official Linux/POSIX API reference"}
  - {title: "Linux man-pages — fsync(2)", url: "https://man7.org/linux/man-pages/man2/fsync.2.html", kind: "official Linux/POSIX API reference"}
  - {title: "Linux man-pages — write(2)", url: "https://man7.org/linux/man-pages/man2/write.2.html", kind: "official Linux/POSIX API reference"}
---
A file descriptor (FD) is a small integer referencing an open file description, **not** a pathname or a physical disk address. An operating system separates the calling process's descriptor table from the description's current file offset and status flags and from the underlying persistent file object. This distinction explains why two descriptors sometimes share a cursor while two independently opened descriptors do not [2][3].

The [processes and virtual memory chapter](/en/topics/processes-virtual-memory/) introduces process resources and system-call boundaries. Here we model descriptor ownership, `open`, `dup`, `read`, `write`, `lseek`, `close`, buffering and `fsync`. Two **explicit teaching models** make their observable contracts testable. They are not substitutes for a POSIX implementation, real filesystems, persistence tests on hardware or a complete crash-consistency protocol [1].

## File names, inodes, open file descriptions and file descriptors

There are at least three layers of state. A **directory entry** relates a name to a filesystem object, often an inode. An **open file description** maintains an offset and file status flags, associated with that object. A **process file descriptor** is an integer entry pointing to an open description; descriptor-specific flags such as `FD_CLOEXEC` are conceptually distinct from shared description flags [2][3].

| Operation | New descriptor? | New open description? | Cursor relation |
| --- | --- | --- | --- |
| `open("note")` | Yes | Yes | Starts at offset 0 (absent append/other variants) |
| `dup(fd)` | Yes | **No** | Shares the original description's offset |
| A second `open("note")` | Yes | Yes | Independent offset; underlying bytes still shared |
| `close(fd)` | Removes one FD | Description may remain referenced | Other duplicated FDs still usable |

Linux `open(2)` distinguishes an open file description from the name used to obtain it; the description may remain usable even after its original pathname is renamed or unlinked [2]. `dup(2)` allocates the lowest unused descriptor and references the **same** open description, sharing the current offset and file status flags, but not descriptor flags [3]. This teaching model covers only one process, and it deliberately does not implement `fork`, `exec`, descriptor flags, `dup2`, pathname replacement, inode identity or access control.

## Offsets and cursor movement are observable state

The *file offset* determines where a sequential `read` or `write` begins. Successful reads advance it by the **number of bytes actually read**, not the requested count. At end of file, a regular file read returns zero bytes, and the cursor need not advance. An independent `open` creates a fresh description with its own offset; `dup` uses the same object, so a seek through one descriptor changes where subsequent operations using the other begin [2][3].

Writing can overwrite existing bytes or extend the file. In the model, seeking beyond EOF then writing inserts explicit zero bytes in a dense Python `bytearray`. A real filesystem can instead represent this as a **sparse hole** with zero-filled reads but without allocating a physical block for every absent byte. Neither disk block allocation nor sparseness is simulated [1].

Actual `read(2)` and `write(2)` have more outcomes than our functions: I/O may fail, be interrupted, or transfer **fewer** bytes than requested; a successful `write` does not itself promise durable media storage. Callers must inspect the byte count and handle retry/partial progress according to their file and system-call contract [5]. The toy methods deliberately guarantee full transfers for an in-memory regular file and have no injected I/O errors.

## Executable descriptor and open-description model

Each `OpenDescription` is one mutable offset associated with a path key. `DescriptorModel.descriptors` stores FD-to-description references, while `files` holds the underlying byte arrays. `dup` puts the **same Python object** into the table twice; another `open` constructs a **different object** referring to the same bytes. The lowest available nonnegative descriptor is reused.

~~~python
from dataclasses import dataclass

@dataclass
class OpenDescription:
    path: str
    offset: int = 0

class DescriptorModel:
    def __init__(self, files):
        if (not isinstance(files, dict)
                or any(not isinstance(path, str) or not path
                       or type(data) is not bytes
                       for path, data in files.items())):
            raise ValueError("expected a mapping of file names to bytes")
        self.files = {path: bytearray(data) for path, data in files.items()}
        self.descriptors = {}

    def _lowest_fd(self):
        number = 0
        while number in self.descriptors:
            number += 1
        return number

    def _open_description(self, fd):
        if type(fd) is not int or fd not in self.descriptors:
            raise KeyError(fd)
        return self.descriptors[fd]

    def open(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        fd = self._lowest_fd()
        self.descriptors[fd] = OpenDescription(path)
        return fd

    def dup(self, fd):
        description = self._open_description(fd)
        duplicate = self._lowest_fd()
        self.descriptors[duplicate] = description
        return duplicate

    def close(self, fd):
        self._open_description(fd)
        del self.descriptors[fd]

    def seek(self, fd, offset):
        description = self._open_description(fd)
        if type(offset) is not int or offset < 0:
            raise ValueError("nonnegative absolute offset required")
        description.offset = offset

    def tell(self, fd):
        return self._open_description(fd).offset

    def read(self, fd, count):
        description = self._open_description(fd)
        if type(count) is not int or count < 0:
            raise ValueError("nonnegative read count required")
        data = self.files[description.path]
        chunk = bytes(data[description.offset:description.offset + count])
        description.offset += len(chunk)
        return chunk

    def write(self, fd, payload):
        description = self._open_description(fd)
        if type(payload) is not bytes:
            raise ValueError("byte payload required")
        if not payload:
            return 0  # zero-byte writes do not extend the file
        data = self.files[description.path]
        start = description.offset
        if start > len(data):
            data.extend(bytes(start - len(data)))
        end = start + len(payload)
        if end > len(data):
            data.extend(bytes(end - len(data)))
        data[start:end] = payload
        description.offset = end
        return len(payload)

    def snapshot(self, path):
        return bytes(self.files[path])

model = DescriptorModel({"note": b"ABCDE"})
first = model.open("note")
shared = model.dup(first)
assert (first, shared) == (0, 1)
assert model.read(first, 2) == b"AB"
assert model.read(shared, 2) == b"CD"    # same open description
independent = model.open("note")
assert model.read(independent, 2) == b"AB"  # separate offset
model.seek(shared, 1)
assert model.tell(first) == 1
assert model.write(first, b"xy") == 2
assert model.snapshot("note") == b"AxyDE"
assert model.read(shared, 2) == b"DE"
model.close(first)
assert model.read(shared, 1) == b""
model.close(shared)
assert model.open("note") == 0  # lowest unused descriptor
~~~

The central exercise is to explain the difference between `shared` and `independent` without examining their descriptor numbers: `shared` and `first` reference the **same** description, so reading from `first` changes the position of `shared`; `independent` has a separate offset starting at zero. All three see writes to the same in-memory file content. Closing `first` does not close `shared`, and creating another FD after a close can reuse the vacated integer.

The model's **invariants** are: each FD maps to one live open-description object; two descriptors produced by `dup` share that exact object; a separate `open` constructs a new object; each offset is nonnegative; a successful read advances by the number of bytes returned; and all reads and writes refer to bytes in the same underlying file map. Invalid FDs raise `KeyError`, nonexistent names raise `FileNotFoundError`, invalid counts or byte payloads fail before changing state. None of these checks prevents an external native-code data race.

A descriptor lookup and byte-level read/write use expected `O(1)` dictionary access plus `O(k)` copying for `k` bytes; a write beyond EOF may additionally zero-fill an `O(gap)` hole. Allocating the lowest FD uses `O(d)` scans with `d` active descriptors in the worst case, because this simple model lacks an FD free-list. Its memory use is `O(total file bytes + number of descriptors)`, independent of physical disk layout.

## From user buffers to kernel page cache to devices

**Buffered I/O is not one universal buffer.** A high-level language runtime may buffer bytes in userspace before issuing a system call; the kernel can cache dirty file pages after `write` succeeds; a block layer and the underlying device can have additional queues or write caches. `fflush` for a C stdio stream, for example, requests transfer of buffered data toward the kernel, but it is not interchangeable with `fsync` for file durability [4].

A `write` that reaches the kernel may be visible to readers but still reside in volatile cache. Similarly, a successful `close` cannot automatically be treated as proof that all prior changes have reached nonvolatile storage. The correct distinction is between **visibility**, **ordering** and **durability**. Which guarantees are available depends on filesystem semantics, system calls and successful I/O completion, not just whether an application method returned without raising [4][5].

Buffering also changes latency and throughput. Accumulating many tiny writes can reduce syscall overhead, but larger buffers consume memory and can delay error reporting. **Direct I/O** has additional alignment and caching restrictions, and is not equivalent to calling `write` with a large payload. This chapter does not benchmark either route; it derives contractual differences first [1][5].

## fsync, fdatasync, directory entries and crash boundaries

On Linux, `fsync(fd)` requests synchronization of modified data and relevant metadata for the opened file, including transfer through device caches as reported by the storage stack. `fdatasync` may avoid syncing metadata unnecessary to read the file contents. Both can report errors; applications must check return values rather than presume a successful durability boundary [4].

A frequently missed detail is that **fsync on a file does not necessarily persist the directory entry naming it**. To make a newly created or renamed file discoverable after a crash, a protocol commonly requires synchronizing the containing directory as well, with operations and ordering appropriate to the filesystem. Renaming a temporary file into place is not on its own proof of post-crash durability. Nor do successful sync calls magically fix broken drive behavior, remote filesystems, unreported hardware faults or application-level transaction errors [4].

An application crash, a kernel crash, and a power failure have **different failure models**. A process can die while already acknowledged writes remain in the kernel page cache. A full system crash can lose dirty cache pages. A storage device can fail independently. Filesystem journaling and data journaling address narrower concerns than general database transaction recovery; compare the separate [WAL and recovery chapter](/en/topics/database-storage-wal/) [1][4].

## Executable abstract snapshot model of flush and crash

To make the boundary mechanically testable, define **two snapshots of one already-existing file**: `visible` is what the running model can read; `synced` is the durable state last acknowledged by its abstract `fsync`. An append updates only `visible`; a `crash` discards un-synced updates; `fsync` copies the visible snapshot to durable state. This is a **logical crash model**, *not* a simulation of a filesystem or disk and not a guarantee that every Linux crash loses precisely those bytes [4].

~~~python
class CrashSnapshot:
    def __init__(self, original=b""):
        if type(original) is not bytes:
            raise ValueError("initial content must be bytes")
        self.visible = original
        self.synced = original

    def append(self, payload):
        if type(payload) is not bytes:
            raise ValueError("byte payload required")
        self.visible += payload

    def fsync(self):
        self.synced = self.visible

    def crash(self):
        self.visible = self.synced

    def read(self):
        return self.visible

    def durable_read(self):
        return self.synced

store = CrashSnapshot(b"A")
store.append(b"B")
assert store.read() == b"AB"
assert store.durable_read() == b"A"
store.crash()
assert store.read() == b"A"
store.append(b"C")
store.fsync()
store.append(b"D")
store.crash()
assert store.read() == store.durable_read() == b"AC"
~~~

The example demonstrates the distinction: appending B is visible but disappears in the first simulated crash, while appending C and then synchronizing preserves C through a later crash even though the subsequent D append is discarded. The toy model assumes `fsync` always succeeds and atomically persists **all** current bytes; real systems have page-granular writeback, errors, multiple files, metadata ordering and partial persistence. Those dimensions must be modeled separately before claiming real crash safety.

The invariant is simple: `synced` changes only on `fsync`, while `visible` changes on append, `fsync` preserves it, and crash restores it from `synced`. This model can be exhaustively verified over short sequences and repeated crashes, but cannot prove real atomic updates, power-loss durability or the safety of temporary-file replacement.

## Failure handling and filesystem design implications

A robust write path must separate failures at different points: failure to open the file, a partial write, failure to sync, failure to rename, failure to sync the parent directory, and a crash between any two of these steps. Error handling must preserve the state promised to users. A system that acknowledges a transaction before its required durability step is completed has a different loss window from one that acknowledges only after successful synchronization [4][5].

POSIX APIs also carry concurrency concerns. Several descriptors sharing an open description can interact through a common offset; `pread`/`pwrite` are useful when the caller needs an explicit position without changing that offset, subject to their own documented caveats. Separately opened descriptions can maintain independent cursors while operating on shared bytes. The simple Python demonstration runs sequentially and does **not** establish atomicity of concurrent appends, crash-safe updates, locking, advisory-lock behavior or write ordering.

Filesystems add name lookup, directories, inode allocation, block mapping, free-space management, caching, consistency and recovery on top of these APIs. The teaching model intentionally stops at the descriptor and sync boundary, leaving inode layout, extents, journaling, copy-on-write filesystems and device queueing for later standalone studies.

## Exercises and verification

1. Trace `open("note")`, `dup`, `read(2)`, `read(2)` and a second `open("note")`; record each FD's **description identity**, offset and observed file bytes.
2. Close one of two duplicates and prove why the other still works. Reopen the file and demonstrate FD **number reuse** without offset sharing.
3. Seek beyond EOF, write one byte and explain why this model fills explicit zeros while a real filesystem may use a sparse hole.
4. Derive which of `fflush`, `write`, `fsync` and directory `fsync` can establish which durability property, with the assumptions and errors that may invalidate the conclusion.
5. Explain why a successful `write` return count does **not** necessarily imply a complete request or persistence across power loss.
6. Enumerate all short sequences of append, sync and crash; identify which append prefixes survive in the toy snapshot model, and which traces cannot represent actual torn writes.
7. Design a safe replacement protocol using a temporary file, data sync, rename and directory sync. Specify the crash windows and avoid claiming atomic durability without filesystem assumptions.
8. Extend the FD model with `pread` semantics, leaving the shared offset unchanged; use a separate oracle to check independence for every valid descriptor.
9. Identify at least four properties of the true Linux open file description absent from the Python class, including status flags, file identity across rename, access modes and sharing after fork.

**Next:** [Filesystem inodes, blocks and journaling](/en/topics/inode-directories-journaling-recovery/) now develops the on-disk metadata layer; [processes and virtual memory](/en/topics/processes-virtual-memory/) explains ownership and [database WAL](/en/topics/database-storage-wal/) develops transactional recovery. This chapter's in-memory models establish observable contracts, not performance or reliability guarantees on actual filesystems [1][2][3][4][5].
