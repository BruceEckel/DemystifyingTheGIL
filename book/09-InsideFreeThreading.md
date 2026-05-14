# Inside Free-Threaded Python

This document explains, in implementation terms, what changed inside CPython
to enable the free-threaded build (`3.13t`, `3.14t`, etc.). It assumes you
have read `05-HistoryOfTheGIL.md` and `07-RefcountsAndExtensions.md`, which
cover *why* the GIL existed and how the C extension API depends on
reference counts.

The questions answered here:

- How are reference counts kept consistent without a global lock?
- Is there a cycle-detecting garbage collector now? (Yes, and there always was.)
- How can existing C extensions, which assume the GIL, keep working
  unmodified?
- What did the interpreter itself have to change?

## The Problem Restated

The GIL existed to serialize three things at once:

1. Reference count updates on every Python object.
2. Mutations to the interpreter's own data structures (the import system,
   type slots, the bytecode dispatcher's bookkeeping).
3. Mutations to built-in mutable containers (dict, list, set).

Removing the GIL means each of these needs its own thread-safety story.
None can fall back on "the GIL will sort it out." And the cost of the new
mechanisms must be small enough that single-threaded programs do not
regress.

PEP 703 attacks each of the three independently. The result is not "the
GIL with finer granularity." It is a coordinated set of techniques, each
chosen to keep the common case (one thread, no contention) close to
free.

## Reference Counting: Four Mechanisms

The hot path in CPython is `Py_INCREF` and `Py_DECREF`. They run millions
of times per second. Replacing them with naive atomic adds would cost
roughly 30 percent on single-threaded code, well past the bar Guido set
in 1996. PEP 703 avoids that by recognizing that most objects do not
actually need atomic refcounting. Four mechanisms cooperate to make this
work.

### 1. Immortal Objects

Some objects live forever: `None`, `True`, `False`, the small integers
in `[-5, 256]`, interned strings, type objects for built-in types,
common exception classes. Their refcounts have no meaningful upper
bound, and they are never freed.

Free-threaded CPython gives these objects a sentinel refcount value (a
specific high bit pattern). `Py_INCREF` and `Py_DECREF` check for the
sentinel and return immediately. No atomic operation, no cache line
write, no contention. Across threads, an immortal object is effectively
read-only.

This was actually shipped in 3.12 as PEP 683, predating free-threading.
It pays off most under free-threading, where every avoided atomic on
`None` is real performance.

### 2. Biased Reference Counting

Most objects, even in multi-threaded programs, are touched by exactly
one thread for their entire lifetime: a temporary list inside a
function, an intermediate string, a small dict used to format an error
message. For these, atomic refcount updates are pure overhead.

Biased refcounting (Choi et al., 2018) splits each object's refcount
into two fields:

- A **local refcount** owned by the thread that created the object.
  Updated with plain non-atomic instructions, fast.
- A **shared refcount** for all other threads. Updated atomically.

The owning thread reads and writes its local count freely. Any other
thread that increments or decrements goes through the atomic shared
count. The object is freed when both counts indicate no references
exist, which requires a small reconciliation protocol.

The asymmetry is the point. The owning thread, which does the vast
majority of refcount updates for short-lived objects, pays nothing extra.
The cost of atomics is paid only when a second thread genuinely starts
sharing the object.

When an object becomes shared frequently, ownership can be relinquished
and both threads use the shared (atomic) path going forward. The bias
exists to optimize the common case, not to lock objects to threads.

### 3. Deferred Reference Counting

A handful of object kinds are referenced very frequently from many
threads but rarely deallocated: top-level functions, modules, classes
that have been imported across the program. For these, even atomic
refcount updates would create cache-line contention as multiple cores
write the same memory.

Deferred refcounting marks these objects so that the interpreter
*skips* most refcount updates on them during normal execution. The
omitted increments are tracked implicitly (typically through the
interpreter's own bookkeeping, such as the value stack). At a safe
point, usually a GC cycle, the deferred references are reconciled and
the true refcount is computed.

The trade-off: an object with deferred refcounting cannot be freed
promptly when its last reference drops, because the "true" count is
not known until reconciliation. For modules and top-level functions,
this is fine; they are expected to live until interpreter shutdown.

### 4. Atomic Operations as the Fallback

When none of the above apply (a normal heap object that has been seen
by more than one thread, with no special annotation), refcount updates
fall back to atomic CPU instructions: `lock xadd` on x86, `LDADD` on
ARMv8.1, equivalent primitives elsewhere.

This is the slowest path, but it is also the rarest. The first three
mechanisms together cover the overwhelming majority of refcount
operations in a typical program.

## The Garbage Collector: Yes, There Is One

Reference counting alone cannot reclaim cyclic garbage. Two objects
that point at each other (a parent and child node, or any cycle of
references) keep each other's refcount above zero forever, even when
no outside reference exists. CPython has shipped a *cycle-detecting
garbage collector* in the `gc` module since Python 2.0 (2000) for
exactly this reason. Free-threading does not introduce a garbage
collector. It changes how the existing one runs.

### What the Cycle Collector Does

Periodically, the collector walks objects that opt into tracking
(containers like dict, list, set, instances of user classes). It
computes effective refcounts after temporarily subtracting internal
references between tracked objects. Any object whose effective count
reaches zero is part of an unreachable cycle and is freed.

Under the GIL, the collector ran with the lock held. No other thread
could mutate the object graph during a collection, so the algorithm
saw a consistent snapshot.

### How It Runs Without the GIL

The free-threaded build uses **stop-the-world** garbage collection.
When a collection starts, the runtime asks every other Python thread
to pause at the next safe point. Once all threads have stopped, the
collector runs as before. Then the world resumes.

This is the first time CPython has had stop-the-world pauses in its
mainline execution model. The pauses are short (cycle collections
were already infrequent and scoped to tracked objects), and they
happen at thread-safe checkpoints rather than arbitrary instructions.
Cooperative pausing is necessary because a thread holding internal
state, mid-`Py_INCREF`, cannot be preempted safely.

Stop-the-world is also the moment when **deferred reference counts
are reconciled**. The interpreter walks the value stacks of all
paused threads and adds up the deferred contributions to each
deferred-counted object. After reconciliation, an object whose true
count is zero can finally be freed.

### Quiescent State Based Reclamation (QSBR)

Removing the GIL exposes a new hazard: a thread can read an object
through a borrowed reference while another thread frees it. Even with
correct refcounting, the gap between "I obtained this pointer" and "I
incremented the refcount" is no longer protected by the global lock.

Free-threaded CPython uses **QSBR** to bound this hazard for certain
internal data structures (notably the dict/list resize machinery).
Memory is not freed immediately when its refcount drops; it is queued.
The actual free happens once every thread has passed through a
*quiescent state*, a point where it is known to hold no pointers into
the queued memory. Quiescent states coincide with the same safe
points the GC uses.

QSBR is invisible to Python code and to most extension code. It is
the mechanism that lets borrowed-reference patterns inside the
interpreter remain correct under free-threading without paying for an
atomic increment on every single read.

## Per-Object Locks for Mutable Containers

Dicts, lists, and sets are mutated in-place. Two threads writing to
the same dict can corrupt the hash table; two threads, one writing
and one resizing, can produce a use-after-free even with correct
refcounting. Previously, the GIL made these operations safe by accident.

In the free-threaded build, each mutable container carries its own
lightweight mutex. Operations that mutate the container acquire it;
operations that only read can often avoid it through careful use of
atomics and QSBR.

The locks are designed for the uncontended case. Acquiring a per-dict
mutex when no other thread wants it costs roughly the same as a
single atomic compare-and-swap. The cost only grows when two threads
genuinely race for the same container.

Critically, these locks are **per object**, not interpreter-wide.
Two threads working on two different dicts do not contend with each
other. This is the unlock-the-cores property the GIL never had.

## Memory Allocator: mimalloc

CPython's old object allocator (`obmalloc`) used arenas with no
internal synchronization, relying on the GIL for safety. This approach cannot
work without the GIL.

The free-threaded build replaces the small-object allocator with
**mimalloc**, a thread-aware allocator from Microsoft Research. Each
thread gets its own heap segments and allocates from them without
contention. Cross-thread frees (thread A frees memory thread B
allocated) are handled through a small lock-free hand-off.

mimalloc also gives the GC something it needs: the ability to
*enumerate live objects* by walking heap pages. Several free-threaded
operations rely on this, including the cycle collector and certain
debugging tools.

The standard `malloc` (or whatever the platform provides) is still
used for large allocations. mimalloc is the small-object fast path.

## Interpreter State Cleanup

PEP 684 (per-interpreter GIL, shipped in 3.12) had already done much
of the work of moving runtime state off C globals and onto
per-interpreter structs. Free-threading extends that further: state
that used to be shared across threads of a single interpreter, on the
assumption that the GIL would serialize access, has been audited and
either:

- Made truly thread-local (one copy per thread).
- Protected by a fine-grained lock.
- Made atomic (when read frequently and written rarely).
- Made immutable after initialization (the most common outcome where
  possible).

Examples that needed work:

- The free lists for common object types (small ints, frames, tuples)
  used to be unsynchronized arena-style caches. They are now
  per-thread.
- The import system's module table needed locking, and the import
  lock itself was rebuilt as a per-module lock to avoid serializing
  unrelated imports.
- The bytecode interpreter's *adaptive specialization* machinery
  (PEP 659, "specializing adaptive interpreter") writes to inline
  caches as the program runs. These writes are now atomic, with the
  read path tolerating a partially written cache through careful
  ordering.
- Type objects' method resolution order (MRO) caches, attribute
  lookup caches, and `tp_version_tag` use atomic updates with version
  counters so a stale read is detectable and recoverable.

Most of these changes are invisible at the Python level. They are
expensive in audit time (PEP 703 took years), but each individual
change is small.

## Accommodating Existing C Extensions

The hardest constraint on PEP 703 was not technical. It was social:
hundreds of thousands of compiled C extensions exist in the wild, and
none of them were written with free-threading in mind. Breaking them
silently would have made the free-threaded build unusable for any
real workload.

The solution has three parts.

### 1. The Refcount Macros Still Work

`Py_INCREF` and `Py_DECREF` are still macros (or inline functions),
and they still take a `PyObject*`. An extension compiled against the
free-threaded headers gets the new implementation: the macros now
expand to code that checks for immortality, then for biased ownership,
then falls back to atomics. An extension compiled against the
GIL-build headers and re-linked against `python3t.dll` (or
equivalent) does not magically become safe; it must be rebuilt.

The `ob_refcnt` field still exists on `PyObject`, but its layout has
changed (it now holds the local count and bias bits, with the shared
count elsewhere). Code that touched `ob_refcnt` directly, bypassing
the macros, is broken. This was always discouraged but was never
prevented at the API level.

### 2. The `Py_MOD_GIL_NOT_USED` Opt-In

A C extension declares itself free-thread-safe by setting a flag in
its module definition:

```c
static PyModuleDef_Slot mymodule_slots[] = {
    {Py_mod_exec, mymodule_exec},
    {Py_mod_multiple_interpreters, Py_MOD_PER_INTERPRETER_GIL_SUPPORTED},
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
    {0, NULL}
};
```

When the free-threaded interpreter loads a module, it checks this
flag. If the module declares `Py_MOD_GIL_NOT_USED`, the runtime
assumes the module's author has audited it. If the flag is missing
(the default for any extension built before free-threading existed),
the runtime **re-enables the GIL at process scope** and emits a
runtime warning naming the offending module.

The re-enable is dynamic: the GIL is created and acquired on the
fly, all threads start using it, and refcount paths shift back to
their GIL-compatible behavior (the immortal and biased optimizations
remain, but the cycle GC and per-object locks coexist with a single
serialized executor).

This is the central compatibility lever. It means:

- Existing extensions keep working unchanged. Performance reverts to
  GIL-build behavior, but correctness is preserved.
- New extensions opt in only after audit.
- Users who know their stack is safe can override with
  `PYTHON_GIL=0` and skip the auto-enable.

### 3. Strong-Reference API Extensions

Several borrowed-reference APIs have been augmented with
strong-reference variants. The classic example:

```c
// Borrowed reference: the dict still owns it, may be freed under us.
PyObject *value = PyDict_GetItem(dict, key);

// New reference: caller owns a fresh refcount; safe across thread races.
PyObject *value = NULL;
int rc = PyDict_GetItemRef(dict, key, &value);
```

Borrowed references were never *required* to be borrowed; they were
an optimization. The new APIs let extension authors trade a refcount
update for safety in code paths where the dict could be mutated by
another thread. The borrowed-reference APIs still work but require
the caller to hold a critical section.

## Other-Language Extensions

The compatibility story for Rust, Cython, and other languages
follows the same pattern: the runtime checks for an opt-in flag, and
the binding layer is responsible for providing safe primitives.

### PyO3 (Rust)

PyO3 propagates the free-threading declaration to Rust extensions
through a crate-level attribute:

```rust
#[pymodule(gil_used = false)]
fn my_extension(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(process, m)?)?;
    Ok(())
}
```

This sets `Py_MOD_GIL_NOT_USED` in the underlying module definition.
Rust's borrow checker continues to enforce the `Python<'py>` token
contract described in `07-RefcountsAndExtensions.md`, so the same
patterns that were safe under the GIL remain safe under free-threading,
provided the author has not relied on implicit serialization for
shared mutable state.

A PyO3 extension that uses `static` Rust globals or `lazy_static`
caches still has to add `Mutex` or `RwLock` around them; the borrow
checker does not know about Python threading.

### Cython

Cython 3.1+ supports free-threading through a directive at the top
of a `.pyx` file:

```python
# cython: freethreading_compatible=True
```

This sets the same module flag. Cython-generated C code uses the
standard refcount macros, so the underlying refcounting upgrade is
automatic. Cython does not (yet) statically check for the patterns
that break under free-threading; the developer has to audit
`cdef` globals, `nogil` blocks, and any direct C state.

### Other Languages

Languages that bind to the C API through their own FFI (Julia's
`PyCall`, Haskell's `cpython`, Go's `go-python`) inherit the
compatibility model. They must:

1. Set the `Py_mod_gil` slot in their generated module definition,
   if they want to skip the auto-enable.
2. Audit any state they cache outside Python.
3. Use the new strong-reference APIs in any borrowed-reference
   pattern that crosses a thread boundary.

The runtime treats them identically to a hand-written C extension.

## Summary of the Compatibility Matrix

| Extension | Built against | Loaded into 3.14t | Result |
|---|---|---|---|
| Pure Python | n/a | 3.14t | Works. Races may appear in shared state. |
| C, GIL-only headers | 3.12 or earlier | 3.14t | Loads, GIL re-enables, warning emitted. |
| C, FT headers, no `Py_MOD_GIL_NOT_USED` | 3.13t+ | 3.14t | Loads, GIL re-enables, warning emitted. |
| C, FT headers, `Py_MOD_GIL_NOT_USED` set | 3.13t+ | 3.14t | Runs free-threaded. Extension author asserts safety. |
| PyO3 default | recent | 3.14t | Loads, GIL re-enables. |
| PyO3 with `gil_used = false` | recent | 3.14t | Runs free-threaded. |
| Cython, no directive | 3.1+ | 3.14t | Loads, GIL re-enables. |
| Cython, `freethreading_compatible=True` | 3.1+ | 3.14t | Runs free-threaded. |

The pattern is uniform: opt-in, with the GIL as the safety net.

## What This Costs on Single-Threaded Code

PEP 703's headline claim is that the free-threaded build runs
single-threaded code within a few percent of the GIL build. The
mechanisms above are why:

- Immortal objects pay zero per-operation cost.
- Biased refcounting on owner threads is plain integer ops.
- Deferred refcounting moves work to GC time, which is rare.
- Per-object locks are uncontended in single-threaded use.
- mimalloc's per-thread heaps avoid synchronization on alloc/free.
- The cycle collector runs with the same frequency as before, just
  with a new stop-the-world pause that, for a single thread, is a
  no-op (there is no other thread to wait for).

Measured single-threaded slowdown in 3.13t was around 5-10 percent
versus 3.13. The 3.14t build narrowed that further. The original
2× cost of Greg Stein's 1996 patch is gone, primarily because biased
refcounting and immortal objects together remove almost all of the
per-operation atomic cost.

## What Free-Threading Does Not Provide

Worth stating explicitly:

- **It does not eliminate races in Python code.** A Python program
  with two threads incrementing a shared counter without a lock will
  lose updates. The interpreter is thread-safe; arbitrary Python
  code is not. The examples in this repository (`counter_race.py`,
  `two_counters.py`, `stats_race.py`) exist to demonstrate exactly
  this.
- **It does not provide a memory model for Python.** Python has
  never specified one. The free-threaded build documents the
  guarantees the interpreter itself provides (reference counts are
  consistent, container internals do not corrupt) but not the
  visibility ordering of writes to user-level objects.
- **It does not make all C extensions safe.** It only makes them
  *runnable*. The `Py_MOD_GIL_NOT_USED` flag is an assertion by the
  extension author, not a verification by the interpreter.
- **It does not deprecate the GIL.** The standard CPython build
  (`python3.14`) still ships with the GIL and is the default. The
  free-threaded build (`python3.14t`) is parallel, and
  per-interpreter GIL (PEP 684) is yet another concurrency model
  inside the same process. All three coexist.

## Further Reading

- PEP 703: Making the Global Interpreter Lock Optional in CPython.
- PEP 683: Immortal Objects, Using a Fixed Refcount.
- PEP 684: A Per-Interpreter GIL.
- Choi et al., "Biased Reference Counting: Minimizing Atomic
  Operations in Garbage Collection" (PACT 2018).
- mimalloc: Daan Leijen et al., "Mimalloc: Free List Sharding in
  Action" (Microsoft Research, 2019).
- Sam Gross's nogil prototype write-up (the precursor to PEP 703).
