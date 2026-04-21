# Why the GIL was Added

## The Setting

Python gained threading support in 1992, in the 0.9.x era. Guido van Rossum added it as a
wrapper over the platform's OS threads (pthreads on Unix, later native threads on Windows).
At the time:

- Multiprocessor machines were rare and expensive; threading was mostly about overlapping
  I/O, not exploiting multiple cores.
- The C extension ecosystem was already central to Python's value proposition (numeric
  libraries, database drivers, graphics bindings).
- CPython's memory model was, and still is, **reference counting**.

These three facts together shaped the decision.

## The Actual Problem: Reference Counting

Every CPython object carries an `ob_refcnt` field. Almost every bytecode operation touches
refcounts: assigning a name, passing an argument, returning a value, putting something in a
list. The operations that matter are `Py_INCREF` and `Py_DECREF`, and each of them is a
read-modify-write sequence:

```
old = obj->ob_refcnt   // LOAD
obj->ob_refcnt = old+1 // STORE
```

Without synchronization, two threads running `Py_INCREF` on the same object can lose an
update. The consequences are not "slightly wrong counts":

- **Refcount too high** → object never freed → memory leak.
- **Refcount too low** → object freed while still in use → use-after-free: crashes, silent
  data corruption, exploitable security bugs.

Refcounts get touched millions of times per second in normal execution. Any scheme that
protects them has to be extremely cheap. That constraint drove the whole design.

See `refcount_race.py` in this project for a direct demonstration.

## Why a Single Big Lock Was the Pragmatic Answer

The GIL is one mutex around the entire interpreter. Only one thread executes Python
bytecode at a time. Given that:

- Every refcount operation is automatically safe — no atomic instructions, no
  per-object locks, no memory barriers, no code changes.
- Every internal data structure (dict, list, frame, type object) is automatically safe
  for the same reason.
- **Every existing C extension is automatically safe**, because the C API assumes
  single-threaded access by default. Extension authors write `obj->ob_refcnt++` and it
  just works.
- Single-threaded performance is essentially free; the lock is acquired once when a
  thread starts running Python code and held until it releases it.

This last point mattered enormously. A language that makes C extensions easy to write
gets a rich ecosystem. A language that requires every extension author to reason about
thread safety, memory ordering, and lock hierarchies does not.

The GIL was not the *best* solution for concurrency. It was the solution that made the
rest of Python's design viable at the time.

## What Other Options Existed

### 1. Fine-Grained Locking

Put a small lock on each mutable object, or on each refcount. This was tried: Greg Stein's
"free-threaded Python" patch (1996) removed the GIL and used per-object locks. The result
was roughly **2× slower for single-threaded code**, because every refcount now needed a
lock acquire/release pair, and every container operation needed its own lock.

This was rejected for the same reason it would be rejected today if proposed without the
engineering work that eventually went into PEP 703: nobody wants to pay a 2× penalty on
existing single-threaded programs so that a minority of workloads can scale on multiple
cores.

### 2. Atomic Refcount Operations

Use CPU atomic instructions (`LOCK XADD` on x86) for `Py_INCREF`/`Py_DECREF`. Cheaper than
a mutex but still significantly slower than a plain integer add, especially under
contention on shared cache lines. And atomics on refcounts alone don't make the
*interpreter* thread-safe — dict internals, the import system, the ready-queue of
generators, etc., all still need protection.

### 3. Tracing Garbage Collection Instead of Refcounting

The problem is refcounting, so remove refcounting. This is what Java, C#, and
JavaScript chose. Pros: no per-operation atomicity problem. Cons:

- Would break every existing C extension that manipulates `ob_refcnt` — the entire
  scientific Python stack would have to be rewritten.
- Introduces GC pause times, which hurt latency-sensitive code.
- Memory footprint is typically higher (objects live longer until a collection cycle).

Jython (on the JVM) and IronPython (on .NET) *do* run Python on tracing GCs, and
correspondingly do not have a GIL. Neither achieved anywhere near CPython's adoption,
largely because they could not host the C extension ecosystem.

### 4. Single-Threaded Only (The JavaScript Choice)

Don't support threads at the language level. JavaScript took this path for a different
reason — it was born in the browser, running alongside a DOM that was explicitly not
thread-safe. The language stayed single-threaded and grew an event loop instead.

Later, JavaScript added **Web Workers**: real OS threads, but they do not share memory
with the main thread. Communication is strictly by message passing (structured clone).
`SharedArrayBuffer` is the narrow exception, and it requires explicit atomics and
careful coordination.

Python could have made this choice, but by 1992 it already had threading and an
expectation that threads shared memory the way C threads did. Removing threads would
have broken users who depended on the I/O-concurrency they already had.

### 5. Message-Passing Only (The Erlang Choice)

No shared mutable state. Every thread (process, in Erlang's terminology) has its own
heap. Communication happens via mailboxes. This is an excellent model for fault-tolerant
distributed systems, but it is a fundamentally different language design. You cannot
retrofit it onto a language whose semantics assume shared mutable objects.

Python eventually approximated this with `multiprocessing`: separate OS processes, IPC
via pickling. It works but is heavy (process startup cost, memory duplication,
serialization overhead).

### 6. A Carefully Specified Memory Model (The Java Choice)

Java went in the opposite direction from Python. From day one it had:

- Tracing GC (no refcount problem).
- A `synchronized` keyword integrated into the language.
- The Java Memory Model, which precisely specifies what one thread is guaranteed to see
  of another thread's writes.

This is a coherent design, but it is a design for a language being built fresh with
concurrency as a first-class concern. Python was not that language in 1992.

## How Ruby Ended Up in the Same Place

Matz's Ruby (MRI) has a **Global VM Lock (GVL)** that plays the same role as Python's GIL,
for essentially the same reasons:

- Ruby historically used refcount-like machinery and now uses a mark-and-sweep GC, but
  its C extension API (written against MRI internals) assumes serialized execution.
- The Ruby community, like Python's, has a large ecosystem of C extensions that would
  break under fine-grained locking.

JRuby (on the JVM) and TruffleRuby (on GraalVM) do not have a GVL, just as Jython and
IronPython do not have a GIL. The pattern is consistent: **if you inherit CPython's or
MRI's C extension contract, you inherit the lock. If you run on a host VM with tracing
GC and a different extension story, you don't.**

## Why Removing It Took Thirty Years

Guido's standing challenge was: remove the GIL without slowing down single-threaded code.
Every attempt before PEP 703 failed that test. Sam Gross's work succeeded by attacking
the refcount cost specifically:

- **Biased reference counting** — most objects are only touched by one thread; refcount
  operations on those don't need atomics.
- **Immortal objects** — `None`, `True`, `False`, small integers, interned strings have a
  sentinel refcount that is never modified.
- **Deferred reference counting** — certain objects (top-level functions, modules) defer
  refcount updates to safe points.
- **Per-object locks for mutable containers** — dict and list get their own locks,
  acquired only when needed.
- **Thorough audit of the interpreter's internal state** — thousands of places that
  implicitly assumed "I'm the only thread here" had to be found and fixed.

This is the free-threaded build (`3.13t`, `3.14t`) that the rest of this project
demonstrates. It is opt-in, it is still maturing, and it changes the contract that
extension authors have relied on for three decades.

## The Contract That Changes

For thirty years, writing a CPython C extension meant writing against a set of
assumptions that were never formally labeled as a contract — they were just how things
worked. Most of them follow from "the GIL is held whenever my code runs." Free-threading
invalidates them one by one.

### What Extension Authors Used to Assume

- **My function is called with the GIL held.** No other Python thread is executing
  bytecode or C extension code simultaneously. I don't need to think about interleavings
  until I explicitly release the GIL.
- **Refcount manipulation is just integer arithmetic.** `Py_INCREF(obj)` expands to
  `obj->ob_refcnt++`. It compiles to a load, an add, and a store. No lock prefix, no
  memory barrier.
- **Direct reads of `ob->ob_refcnt` are coherent.** I can log it, branch on it, use it
  to decide whether to cache something.
- **Module-level C statics and globals need no locks.** My extension's internal state
  — caches, counters, lazy-initialized tables — is implicitly serialized because Python
  code that reaches my module is serialized.
- **Module initialization runs exactly once, on one thread.** I can populate lookup
  tables, register types, and open handles in `PyInit_mymod()` without synchronization.
- **Borrowed references stay valid.** `PyDict_GetItem` returns a borrowed reference.
  As long as I don't release the GIL or call back into Python, nothing can free the
  object underneath me.
- **Iterating a container is safe if I don't mutate it.** No other thread can resize the
  dict or list I'm walking, because no other thread is running.
- **Type slots, method tables, and class hierarchies are read-mostly and stable.** I
  can cache a pointer to a type's `tp_getattro` slot and reuse it.
- **Memory ordering is not my problem.** The GIL acquire/release pair acts as a full
  barrier. Writes one thread performs before releasing the GIL are visible to the next
  thread that acquires it.

### What Free-Threading Forces

- **Concurrent entry is real.** Two Python threads can call into my extension at the
  same instant. Anything I touch that is shared must be protected.
- **Refcount macros now expand to atomics.** `Py_INCREF`/`Py_DECREF` still work, but
  they're no longer cheap integer ops — they're `lock xadd` (or equivalent) under the
  hood. Extensions that bypassed the macros with direct `obj->ob_refcnt++` are broken:
  the write is not atomic and the value is no longer stored in a plain `Py_ssize_t`.
- **Module state needs explicit locking.** That static cache, that lazy initializer,
  that "I'll just remember the last value" optimization — all of them need a mutex,
  or a redesign to avoid sharing.
- **Borrowed references are dangerous.** Another thread can delete the dict entry and
  free the object between `PyDict_GetItem` returning and my code using the result.
  Several APIs have gained strong-reference variants (`PyDict_GetItemRef`, etc.) for
  this reason.
- **Iterating a container while another thread mutates it can fail.** The built-in
  containers have internal locks that keep the interpreter from crashing, but the
  *logical* race — reading a dict that's being written — is now a real concern, not
  a theoretical one.
- **Type mutation is no longer a quiet operation.** Another thread can assign to
  `SomeClass.method` while my code is doing attribute lookup on an instance. The
  interpreter handles this correctly, but any pointer I cached into a type's slot
  table is no longer safe.
- **Memory ordering can matter.** Without the GIL providing implicit barriers, writes
  to shared structures need explicit atomics or locks to be visible in a defined order
  across threads.

### The Opt-In Mechanism

PEP 703 understood that breaking every extension silently would be disastrous. So the
free-threaded build ships a negotiation mechanism:

- A module declares itself free-thread-safe by setting `Py_MOD_GIL_NOT_USED` in its
  module definition (C) or equivalent flag (PyO3, Cython).
- When the interpreter loads a module that does *not* declare itself safe, it
  **re-enables the GIL at runtime**. A single unaudited extension drags the whole
  process back into GIL-held mode.
- Users can override this with `PYTHON_GIL=0`, accepting the risk.

This is an explicit acknowledgment that the contract has changed, that most existing
extensions have not been audited, and that correctness is preserved by falling back to
the old behavior rather than by trusting extensions to behave.

### What the Audit Actually Looks Like

For an extension author, "free-threading support" is not a flag to flip. It is:

1. Find every static/global variable. Decide whether it's read-only (fine), thread-local
   (fine), or shared mutable (needs a lock).
2. Find every borrowed reference. Decide whether concurrent mutation is possible. If so,
   switch to a strong-reference API or hold a critical section.
3. Find every cached pointer into a Python object's internals. Verify the invariants
   that made the cache safe still hold.
4. Find every direct refcount manipulation. Replace with the macros, or with the
   atomic-aware API.
5. Find every place you assumed "I'm the only thread here." This is the hardest step,
   because the assumption is usually implicit.
6. Add tests that actually run the extension from multiple threads. The GIL build
   cannot detect races that free-threading exposes.

NumPy, for example, took **two years and multiple releases** to reach provisional
free-threading support. It is one of the best-resourced extensions in the ecosystem.
Smaller projects will take longer, and many will never be audited at all.

This is what "changes the contract" means in practice: not a subtle reinterpretation of
semantics, but a decades-long backlog of hidden assumptions that every extension author
now has to find and either justify or fix.

## The Short Version

Python added the GIL because CPython's reference-counting memory manager, combined with a
C extension API that lets authors manipulate refcounts directly, made any other form of
thread safety either enormously slow (fine-grained locks), ecosystem-breaking (tracing
GC), or language-design-breaking (no threads, or message-passing only).

The GIL was a pragmatic bet that single-threaded performance and ecosystem compatibility
mattered more than multi-core scaling. For thirty years, that bet held. PEP 703 is the
first serious attempt to pay down the debt without breaking what the bet bought.
