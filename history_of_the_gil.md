# The History of the GIL

The GIL might look like a design mistake: a lock that prevents
Python from exploiting multi-core hardware.
However, it is the natural consequence of four architectural decisions, each of which
was correct in isolation and each of which reinforced the others.

This document traces that evolution. The claim is not that the GIL was optimal,
but that, given the path Python actually took, it was the only realistic
outcome at the point it was needed.

## The Four Decisions

1. **Reference counting** as the memory management (garbage collection) strategy.
2. **A direct C extension API** that exposes refcount manipulation to extension
   authors, turning Python into a "coordination language" for C libraries.
3. **OS-level threads**, added for I/O concurrency.
4. **A single interpreter-wide lock** as the cheapest sufficient way to make
   (1), (2), and (3) coexist.

Remove any one of (1), (2), or (3) and the GIL either isn't needed or isn't the
obvious answer. Keep all three, and (4) is essentially forced. The rest of this
document works through each step.

## 1990: Reference Counting

Guido van Rossum started Python in December 1989. One of the earliest
architectural decisions was how to manage memory. He chose reference counting.

Every object carries an `ob_refcnt` field. When something starts pointing at the
object, the count goes up. When something stops, the count goes down. When it
reaches zero, the object is freed immediately.

This was a good choice in 1990:

- **Simple to implement.** A small number of macros (`Py_INCREF`, `Py_DECREF`)
  and no separate collector thread.
- **Deterministic destruction.** Files close when their last reference drops.
  Locks release. Sockets shut down. No "wait for GC to get around to it." This
  matters for a language designed to glue C libraries together, where those
  libraries hold OS resources.
- **No world-stop pauses.** Tracing garbage collectors of the era stopped every
  thread to scan the heap. Refcounting spreads the cost across every operation
  and never pauses.
- **Cache-friendly.** Objects die close to their last use, often while still in
  cache.
- **Tractable in an extension API.** Extension authors could reason about
  ownership locally: "I take a reference here, I release it there." No need to
  tell a tracing collector which roots to scan.

The cost of the choice, not yet visible in 1990: every `Py_INCREF` and
`Py_DECREF` is a read-modify-write sequence.

```
old = obj->ob_refcnt   // LOAD
obj->ob_refcnt = old+1 // STORE
```

This is fine on a single thread. With two threads, updates can be lost. A lost
`Py_INCREF` leaves the refcount too low and the object gets freed while still in
use. A lost `Py_DECREF` leaks it. The first is a memory safety bug; the second
is a resource leak. Refcount operations also happen millions of times per
second in normal execution, so any fix must be essentially free on the
common path.

Nothing about this mattered in 1990, because Python had no threads. But the
decision was now baked in. The rest of the story is shaped by it.

## 1991: A Direct C Extension API

Python 0.9.0 shipped in February 1991. One of its defining features was how
easy it was to write C extensions. The C API did not hide the object model: it
exposed `PyObject*` as a raw pointer and `Py_INCREF`/`Py_DECREF` as public
macros.

This was a deliberate design choice. Python became a **coordination
language**: the glue used to drive numeric libraries, database drivers,
graphics toolkits, and scientific codes written in Fortran and C. The
scientific Python stack (NumPy, SciPy, pandas, PyTorch) exists because
writing extensions was easy.

The cost: **the reference count is now part of the public ABI.**

Extension authors *manipulate refcounts
directly*. Every extension written between 1991 and today contains code that
assumes `ob_refcnt` is a plain integer and that incrementing it is just an
integer add. You cannot change how refcounting works without breaking every
extension in existence.

Compare this to Java's JNI: JNI hides the GC entirely. Extensions get opaque
object handles; the GC can relocate objects, change its algorithm, or run
concurrently, and no JNI code notices. Python chose the opposite trade: a
leakier but simpler API, and got a richer ecosystem in exchange for a much
tighter constraint on future evolution.

## 1992: Threads are Added

Python 0.9.x introduced threading around 1992, wrapping the platform's OS
threads (pthreads on Unix, native threads on Windows) and exposing them through
the `thread` (later `threading`) module.

The motivation was **I/O concurrency**, not multi-core performance:

- Multiprocessor machines were rare and expensive.
- Network servers wanted to handle multiple clients without blocking on one
  slow read.
- GUIs wanted to keep the interface responsive while work ran in the
  background.
- Event loops existed (GUI toolkits like X11 and Tcl/Tk ran them, as did
  servers built directly on `select()`), but programming against them
  required manual state machines or callback chains. The ergonomic syntax
  came much later: generators in 2001, `yield from` in 2008, `async` and
  `await` in 2015.

A thread that blocks on a syscall doesn't need CPU; having another thread ready
to use the CPU while it waits is the entire point. This use case doesn't need
threads to run Python code in parallel; it just needs them to exist and to
share memory the way C threads do.

With threads added, all three ingredients are now present:

- **Refcounts that need atomicity** across threads (from 1990).
- **An extension ecosystem manipulating those refcounts directly** (from 1991).
- **Threads that share memory** (from 1992).

Real programs can now have races during object reference counts.Synchronization is *required*.

## The Synchronization Choice

Given the three decisions above, the options are:

### Atomic refcount operations

Replace `obj->ob_refcnt++` with a CPU atomic (`LOCK XADD` on x86). Cheaper than
a mutex but still far more expensive than a plain integer add, especially under
contention on shared cache lines. On 1992 hardware, atomics were substantially
slower than they are today.

More fundamentally: atomics on refcounts protect refcounts, but they don't
protect dict internals, the import system, the bytecode interpreter's own
bookkeeping, the module loader, the type system. You still need locks on all
of that. Meanwhile, you've already slowed down every single-threaded
Python program for the benefit of the multi-threaded case.

### Fine-grained per-object locking

Give every mutable object its own lock. Take it when you mutate the object,
release it when you're done.

This was tried. Greg Stein's 1996 "free-threaded Python" patch implemented
exactly this. Result: **roughly 2× slower on single-threaded code.** Every
container operation now required lock acquire/release. Every refcount update
did too.

Nobody was going to accept a 2× penalty on existing programs so that a minority
of workloads could scale on multiple cores, especially when those workloads
were rare (multicore wasn't mainstream until the mid-2000s).

This approach would also require auditing every C extension. The cost wasn't
just in the interpreter; it was ecosystem-wide.

### Switch to tracing garbage collection

Remove refcounting entirely. No refcounts means no refcount races. This is
what Java, C#, and JavaScript did.

But this undoes **1990 and 1991 simultaneously**. Every extension that
manipulates `ob_refcnt` breaks. The entire scientific Python stack would have
to be rewritten. The deterministic-destruction guarantees that make
`with open(...) as f:` work would have to be replaced with some less
predictable mechanism.

Jython (on the JVM) and IronPython (on .NET) actually did this: they run
Python on tracing GCs and correspondingly have no GIL. Neither achieved
anywhere near CPython's adoption, and the reason is exactly the extension
story: they can't host NumPy or any other CPython C extension without
emulation.

### Remove threads

Don't have threads at all. JavaScript took this path, not by choice but
because it was born in the browser next to a non-thread-safe DOM. It grew an
event loop instead, and parallelism came much later via Web Workers that don't
share memory.

Python could have done this in 1992, but users who wanted threads for I/O
already had them. Taking them away would have broken code that already worked.
Python's embedding story (CPython runs *inside* C programs that might
already be multithreaded) also made "no threads" a non-starter.

### Single interpreter-wide lock

One mutex, held whenever a thread runs Python bytecode. Released around
blocking I/O so other threads can run during the wait. Given the three prior
decisions, this is almost free:

- Refcount operations are automatically safe, with no code changes anywhere,
  not in the interpreter, not in any extension.
- Interpreter internals are automatically safe: dict, list, type objects,
  import, the ready queue.
- **Every existing extension is automatically safe**, because the C API's
  implicit single-threaded assumption is now explicitly enforced.
- Single-threaded performance is essentially unaffected; the lock is
  uncontended, held across long stretches, and cheap on modern hardware.
- The I/O use case still works: threads release the GIL around blocking
  syscalls, so another thread can run Python during the wait.

The GIL was not chosen because it was the best concurrency model. It was
chosen because it was the **cheapest synchronization mechanism compatible with
decisions already made.** Every alternative required undoing one of those
decisions, at costs ranging from "2× slowdown" to "break the entire
ecosystem."

## How Other Languages Avoided This

The four-decision chain is a useful lens. Languages that look GIL-free mostly
skipped one of the decisions:

- **JavaScript** skipped decision (3). No threads with shared memory, ever.
  The DOM forced the choice and the language stuck with it. Web Workers came
  later, but they're message-passing only.
- **Java and C#** skipped decision (1). Tracing GC from day one. They also
  skipped the leaky-extension-API problem via JNI and P/Invoke, which hide the
  GC. They also had decision (3) designed in from the start, with
  language-level synchronization primitives and a specified memory model.
- **Erlang** skipped a more fundamental premise: no shared mutable state
  between processes at all. A coherent design, but not one you can retrofit
  onto a language that already has shared objects.
- **Jython and IronPython** are Python with decision (1) replaced: they run on
  the JVM and CLR with tracing GC. They have no GIL. They also cannot host
  CPython's C extension ecosystem, which is why most users stayed on CPython.
- **Ruby (MRI)** made all four of the same decisions as CPython and got the
  same result: a Global VM Lock. JRuby and TruffleRuby, running on different
  VMs, have no GVL, the same pattern as Jython and IronPython.

The pattern is consistent: inherit CPython's (or MRI's) decisions, inherit the
lock. Change any of them, and the lock becomes unnecessary or impossible.

## 1996: The First Attempt to Remove It

Greg Stein's free-threaded patch, mentioned above, was the first serious
attempt. It used fine-grained locking throughout the interpreter. It worked
correctly. It was about 2× slower on single-threaded code. Guido rejected it,
and in doing so set the standing challenge that would define the next three
decades:

> Remove the GIL without slowing down single-threaded code.

Several later attempts, including Larry Hastings's "gilectomy" (2016),
tried and failed to clear that bar.

The difficulty was not implementation skill; the people working on it were
excellent. The difficulty was structural. Refcounting imposes a per-operation
cost that you pay whether or not you have threads, and making refcounts
thread-safe with traditional techniques *always* makes that cost visibly
higher. As long as that was true, the challenge couldn't be met.

## 2008: multiprocessing

Python 2.6 (2008) added the `multiprocessing` module. It exposes a
threading-like API (`Process`, `Queue`, `Pool`) but spawns OS processes
instead of threads. Each process has its own interpreter, its own memory
space, and its own GIL, so CPU-bound work scales linearly across cores with
no lock contention.

This is a workaround rather than a fix. The GIL is still there, and the API
cost is real:

- **Process startup is expensive.** `fork` is cheap on Linux, but `spawn`
  (the default on Windows and macOS for recent versions) serializes and
  re-imports everything, which can take hundreds of milliseconds per worker.
- **Sharing goes through pickling.** Objects passed between processes are
  serialized, which is slow and rejects many types.
  `multiprocessing.shared_memory` (3.8) and `Manager` proxies help, at the
  cost of extra code.
- **Debugging, logging, and exception handling all cross process
  boundaries**, which complicates the tooling story.

`multiprocessing` works well for coarse-grained parallelism: map a function
over a large input, run a pool of long-lived workers. It is a poor fit for
fine-grained sharing, which is exactly the case threads handle well on
other runtimes. Closing that gap is what per-interpreter GIL and
free-threading are for.

## 2014: asyncio and async/await

The original 1992 motivation for threads was I/O concurrency. Python 3.4
(2014) introduced the `asyncio` module, and Python 3.5 (2015) added the
`async` and `await` keywords. Together they provide an event-loop-based
alternative to threads for the exact workload threads were added to handle:
programs that spend most of their time waiting on I/O.

### What asyncio solves

An `async def` function is a coroutine. A single thread runs the event loop
and drives thousands of these coroutines. When one suspends on `await`, the
loop picks up another coroutine that is ready to run. No OS threads are
created; no refcount races are possible; no GIL is ever contended, because
there is only ever one thread running Python code.

For the original 1992 use cases this is often a better fit than threads:

- **Network servers.** A single-threaded event loop handles tens of
  thousands of concurrent connections at a fraction of the memory cost of
  one OS thread per connection.
- **Clients making many parallel requests.** `asyncio.gather` runs
  hundreds of HTTP calls concurrently with no synchronization code.
- **Responsive applications.** Long-running work expressed as coroutines
  yields to the loop at each `await`, keeping the program responsive.

Because all coroutines run on one thread, none of the problems this project
demonstrates exist in `asyncio` code. There is no shared-state race, because
there is no concurrent execution of Python code: context switches happen
only at explicit `await` points, which makes the interleavings visible in
the source.

### What asyncio does not solve

- **CPU-bound work.** A coroutine that computes without awaiting starves
  every other coroutine on the loop. A long regex, a large JSON parse, a
  numeric loop without a release point: all of these freeze the loop. CPU
  parallelism still requires threads (on the free-threaded build) or
  processes (`multiprocessing`, `ProcessPoolExecutor`).
- **Blocking libraries.** `asyncio` only helps if every I/O call goes
  through an async-aware API. A single `requests.get()`, `psycopg2` query,
  or `time.sleep()` blocks the loop and kills concurrency for every other
  task. The standard workaround is `loop.run_in_executor()`, which runs
  the blocking call on a background thread pool. That puts threads back in
  the picture.
- **Function coloring.** `async` functions can only be awaited from other
  `async` functions. Introducing async into an existing synchronous
  codebase is not a local refactor; it propagates up every call site.
  Large conversions are effectively rewrites.
- **C extension behavior.** Async changes when Python schedules work, not
  what C extensions do. A C extension that blocks on a syscall without
  releasing the GIL still blocks the event loop.

### How asyncio affects the GIL story

`asyncio` retroactively weakens the 1992 argument for threads. If
async/await had existed in 1992, Guido might have chosen a single-threaded
event-loop model (roughly what JavaScript later did) and skipped decision
(3) entirely. No threads, no refcount races, no GIL.

But `asyncio` arrived 22 years after threads did. By 2014:

- Threading was established in the language and in production code.
- The CPython C extension ecosystem had been built on the assumption that
  threads exist and the GIL serializes them.
- Users who needed CPU parallelism (numeric computing, machine learning)
  still needed something threads or processes could provide and coroutines
  could not.

So `asyncio` does not remove the need for threads; it removes the need for
*some common uses* of threads. The case of "many concurrent I/O operations
in one process" is now often better served by coroutines, and modern
Python code increasingly uses `asyncio` for that workload. Threads remain
necessary for:

- CPU-bound parallelism on the free-threaded build.
- Integrating with blocking libraries that have no async equivalent.
- GUI frameworks with their own event loops that need worker threads for
  background work.
- Embedding scenarios where a host C program calls into Python from
  multiple threads.

The four-decision chain still holds. `asyncio` provides an alternative
concurrency model for one workload, not a replacement for threads in
general, so the GIL (or the PEP 703 machinery that replaces it) is still
required.

## 2023: Per-Interpreter GIL

CPython has always supported multiple interpreters inside one process
through the `Py_NewInterpreter` C API. Until recently they all shared one
GIL and most of the runtime's global state, so they offered no parallelism
benefit.

PEP 684, accepted in 2022 and shipped in Python 3.12 (October 2023), gave
each subinterpreter its own GIL by moving runtime state off globals and
onto per-interpreter structures. PEP 734, shipped in Python 3.14, adds the
stdlib `interpreters` module so Python code (not just C code) can create
and drive them.

The model: one OS process, multiple interpreters, each with its own GIL
and its own set of imported modules. Interpreters communicate through
explicit channels rather than shared objects, closer to Go or Erlang than
to traditional threading.

Compared to `multiprocessing`:

- **Cheaper startup**, with no new process and no re-import.
- **Lower IPC overhead.** Channels can pass a limited set of types without
  pickling.
- **Same address space**, leaving room for zero-copy sharing of immutable
  data.

Compared to free-threading (PEP 703):

- **Existing extensions keep working**, as long as they are
  interpreter-aware. This is a much weaker requirement than full thread
  safety.
- **No shared mutable state.** That is a safety property, not a limitation
  to overcome.

Subinterpreters and free-threading target different workloads.
Free-threading is for code that wants the shared-memory thread model
running on multiple cores. Subinterpreters are for code that wants
isolation and message passing on multiple cores without the cost of
separate processes.

## 2023: PEP 703

Sam Gross's PEP 703, accepted in October 2023, is the first approach that
actually met Guido's challenge. It did so by attacking the refcount cost
directly, using techniques that didn't exist (or weren't mature enough) in the
1990s:

- **Biased reference counting.** Most objects are only touched by one thread
  throughout their lifetime. Those refcount operations don't need atomics at
  all; they use plain integer ops, with a fallback to atomics only when an
  object becomes shared.
- **Immortal objects.** `None`, `True`, `False`, small integers, interned
  strings get a sentinel refcount that is never modified. No atomics, no
  locks, ever.
- **Deferred reference counting.** Certain objects (top-level functions,
  modules) defer their refcount updates to safe points, avoiding contention on
  frequently-referenced objects.
- **Per-object locks for mutable containers.** Dicts and lists get their own
  locks, acquired only when needed. Acceptable because they're not the hot
  path for refcounts.
- **A thorough audit of interpreter state.** Thousands of places that
  implicitly assumed "I'm the only thread here" had to be found and fixed.

This is the free-threaded build (`3.13t`, `3.14t`) that the rest of this
project demonstrates. It meets the single-threaded performance bar. It is
still opt-in. It also changes the contract that extension authors have
relied on for three decades.

## Summary

The GIL is what you get when you choose refcounting, expose it through a
direct extension API, add threads for I/O, and then need to make refcounts
thread-safe without breaking anything. Every alternative at that point was
worse: atomics alone weren't enough, fine-grained locks were 2× slower,
tracing GC would break the ecosystem, and removing threads would break
existing users.

For thirty years that trade-off favored single-threaded performance and
ecosystem compatibility over multi-core scaling. PEP 703 is the first approach
that preserves both while removing the GIL, and it only works because biased
refcounting and immortal objects finally made refcount arithmetic cheap enough
to be thread-safe by default.
