# Why the GIL was Added

The GIL looks, at first glance, like a design mistake — a lock that prevents a
popular language from exploiting multi-core hardware. But it is not a mistake.
It is the natural consequence of four architectural decisions, each of which
was correct in isolation and each of which reinforced the others. The GIL is
what those decisions produce when you combine them.

This document traces that evolution. The claim is not that the GIL was optimal,
but that — given the path Python actually took — it was the only realistic
outcome at the point it was needed.

## The Four Decisions

1. **Reference counting** as the memory management strategy.
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

Reasons this was a good choice in 1990:

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
is a resource leak. And refcount operations happen millions of times per second
in normal execution, so any fix must be essentially free on the common path.

Nothing about this mattered in 1990, because Python had no threads. But the
decision was now baked in. The rest of the story is shaped by it.

## 1991: A Direct C Extension API

Python 0.9.0 shipped in February 1991. One of its defining features was how
easy it was to write C extensions. The C API did not hide the object model: it
exposed `PyObject*` as a raw pointer and `Py_INCREF`/`Py_DECREF` as public
macros. Any C programmer could wrap a library in an afternoon.

This was a strategic decision, and it paid off enormously. Python became a
**coordination language**: the glue you used to drive numeric libraries,
database drivers, graphics toolkits, scientific codes written in Fortran and
C. The entire scientific Python stack — NumPy, SciPy, pandas, PyTorch — exists
because writing extensions was easy.

The cost: **the reference count is now part of the public ABI.**

Extension authors don't just *use* refcounting; they *manipulate refcounts
directly*. Every extension written between 1991 and today contains code that
assumes `ob_refcnt` is a plain integer and that incrementing it is just an
integer add. You cannot change how refcounting works without breaking every
extension in existence.

Compare this to Java's JNI: JNI hides the GC entirely. Extensions get opaque
object handles; the GC can relocate objects, change its algorithm, or run
concurrently, and no JNI code notices. Python chose the opposite trade — a
leakier but simpler API — and got a richer ecosystem in exchange for a much
tighter constraint on future evolution.

At this point the trap is set. The spring hasn't been released yet.

## 1992: Threads are Added

Python 0.9.x introduced threading around 1992. Guido wrapped the platform's OS
threads (pthreads on Unix, native threads on Windows) and exposed them through
the `thread` (later `threading`) module.

The motivation was **I/O concurrency**, not multi-core performance:

- Multiprocessor machines were rare and expensive.
- Network servers wanted to handle multiple clients without blocking on one
  slow read.
- GUIs wanted to keep the interface responsive while work ran in the
  background.
- Event loops as we now know them didn't exist yet in mainstream languages.

A thread that blocks on a syscall doesn't need CPU; having another thread ready
to use the CPU while it waits is the entire point. This use case doesn't need
threads to run Python code in parallel — it just needs them to exist and to
share memory the way C threads do.

At this moment the spring releases. Python now has:

- **Refcounts that need atomicity** across threads (from 1990).
- **An extension ecosystem manipulating those refcounts directly** (from 1991).
- **Threads that share memory** (from 1992).

Something has to give. The question is what.

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
of that. And you've already slowed down every single-threaded Python program
for the benefit of the multi-threaded case.

### Fine-grained per-object locking

Give every mutable object its own lock. Take it when you mutate the object,
release it when you're done.

This was tried. Greg Stein's 1996 "free-threaded Python" patch implemented
exactly this. Result: **roughly 2× slower on single-threaded code.** Every
container operation now required lock acquire/release. Every refcount update
did too.

Nobody was going to accept a 2× penalty on existing programs so that a minority
of workloads could scale on multiple cores — especially when those workloads
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
story — they can't host NumPy or any other CPython C extension without
emulation.

### Remove threads

Don't have threads at all. JavaScript took this path — not by choice, but
because it was born in the browser next to a non-thread-safe DOM. It grew an
event loop instead, and parallelism came much later via Web Workers that don't
share memory.

Python could have done this in 1992, but users who wanted threads for I/O
already had them. Taking them away would have broken code that already worked.
And Python's embedding story (CPython runs *inside* C programs that might
already be multithreaded) made "no threads" a non-starter.

### Single interpreter-wide lock

One mutex, held whenever a thread runs Python bytecode. Released around
blocking I/O so other threads can run during the wait. Given the three prior
decisions, this is almost free:

- Refcount operations are automatically safe — no code changes anywhere, not
  in the interpreter, not in any extension.
- Interpreter internals are automatically safe — dict, list, type objects,
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
  GC. And they had decision (3) designed in from the start, with language-level
  synchronization primitives and a specified memory model.
- **Erlang** skipped a more fundamental premise: no shared mutable state
  between processes at all. A coherent design, but not one you can retrofit
  onto a language that already has shared objects.
- **Jython and IronPython** are Python with decision (1) replaced: they run on
  the JVM and CLR with tracing GC. They have no GIL. They also cannot host
  CPython's C extension ecosystem, which is why most users stayed on CPython.
- **Ruby (MRI)** made all four of the same decisions as CPython and got the
  same result: a Global VM Lock. JRuby and TruffleRuby, running on different
  VMs, have no GVL — same pattern as Jython and IronPython.

The pattern is consistent: inherit CPython's (or MRI's) decisions, inherit the
lock. Change any of them, and the lock becomes unnecessary or impossible.

## 1996: The First Attempt to Remove It

Greg Stein's free-threaded patch, mentioned above, was the first serious
attempt. It used fine-grained locking throughout the interpreter. It worked
correctly. It was about 2× slower on single-threaded code. Guido rejected it,
and in doing so set the standing challenge that would define the next three
decades:

> Remove the GIL without slowing down single-threaded code.

Several later attempts — Larry Hastings's "gilectomy" (2016) among them —
tried and failed to clear that bar.

The difficulty was not implementation skill; the people working on it were
excellent. The difficulty was structural. Refcounting imposes a per-operation
cost that you pay whether or not you have threads, and making refcounts
thread-safe with traditional techniques *always* makes that cost visibly
higher. As long as that was true, the challenge couldn't be met.

## 2023: PEP 703

Sam Gross's PEP 703, accepted in October 2023, is the first approach that
actually met Guido's challenge. It did so by attacking the refcount cost
directly, using techniques that didn't exist (or weren't mature enough) in the
1990s:

- **Biased reference counting.** Most objects are only touched by one thread
  throughout their lifetime. Those refcount operations don't need atomics at
  all — they use plain integer ops, with a fallback to atomics only when an
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
still opt-in. And it changes the contract that extension authors have relied
on for three decades.

## The Contract That Changes

For thirty years, writing a CPython C extension meant writing against a set of
assumptions that were never formally labeled as a contract — they were just how
things worked. Most of them follow from "the GIL is held whenever my code
runs." Free-threading invalidates them one by one.

### What Extension Authors Used to Assume

- **My function is called with the GIL held.** No other Python thread is
  executing bytecode or C extension code simultaneously. I don't need to
  think about interleavings until I explicitly release the GIL.
- **Refcount manipulation is just integer arithmetic.** `Py_INCREF(obj)`
  expands to `obj->ob_refcnt++`. It compiles to a load, an add, and a store.
  No lock prefix, no memory barrier.
- **Direct reads of `ob->ob_refcnt` are coherent.** I can log it, branch on
  it, use it to decide whether to cache something.
- **Module-level C statics and globals need no locks.** My extension's
  internal state — caches, counters, lazy-initialized tables — is implicitly
  serialized because Python code that reaches my module is serialized.
- **Module initialization runs exactly once, on one thread.** I can populate
  lookup tables, register types, and open handles in `PyInit_mymod()` without
  synchronization.
- **Borrowed references stay valid.** `PyDict_GetItem` returns a borrowed
  reference. As long as I don't release the GIL or call back into Python,
  nothing can free the object underneath me.
- **Iterating a container is safe if I don't mutate it.** No other thread can
  resize the dict or list I'm walking, because no other thread is running.
- **Type slots, method tables, and class hierarchies are read-mostly and
  stable.** I can cache a pointer to a type's `tp_getattro` slot and reuse it.
- **Memory ordering is not my problem.** The GIL acquire/release pair acts as
  a full barrier. Writes one thread performs before releasing the GIL are
  visible to the next thread that acquires it.

### What Free-Threading Forces

- **Concurrent entry is real.** Two Python threads can call into my extension
  at the same instant. Anything I touch that is shared must be protected.
- **Refcount macros now expand to atomics.** `Py_INCREF`/`Py_DECREF` still
  work, but they're no longer cheap integer ops — they're `lock xadd` (or
  equivalent) under the hood. Extensions that bypassed the macros with direct
  `obj->ob_refcnt++` are broken: the write is not atomic and the value is no
  longer stored in a plain `Py_ssize_t`.
- **Module state needs explicit locking.** That static cache, that lazy
  initializer, that "I'll just remember the last value" optimization — all of
  them need a mutex, or a redesign to avoid sharing.
- **Borrowed references are dangerous.** Another thread can delete the dict
  entry and free the object between `PyDict_GetItem` returning and my code
  using the result. Several APIs have gained strong-reference variants
  (`PyDict_GetItemRef`, etc.) for this reason.
- **Iterating a container while another thread mutates it can fail.** The
  built-in containers have internal locks that keep the interpreter from
  crashing, but the *logical* race — reading a dict that's being written — is
  now a real concern, not a theoretical one.
- **Type mutation is no longer a quiet operation.** Another thread can assign
  to `SomeClass.method` while my code is doing attribute lookup on an
  instance. The interpreter handles this correctly, but any pointer I cached
  into a type's slot table is no longer safe.
- **Memory ordering can matter.** Without the GIL providing implicit barriers,
  writes to shared structures need explicit atomics or locks to be visible in
  a defined order across threads.

### The Opt-In Mechanism

PEP 703 understood that breaking every extension silently would be disastrous.
So the free-threaded build ships a negotiation mechanism:

- A module declares itself free-thread-safe by setting `Py_MOD_GIL_NOT_USED`
  in its module definition (C) or equivalent flag (PyO3, Cython).
- When the interpreter loads a module that does *not* declare itself safe, it
  **re-enables the GIL at runtime**. A single unaudited extension drags the
  whole process back into GIL-held mode.
- Users can override this with `PYTHON_GIL=0`, accepting the risk.

This is an explicit acknowledgment that the contract has changed, that most
existing extensions have not been audited, and that correctness is preserved
by falling back to the old behavior rather than by trusting extensions to
behave.

### What the Audit Actually Looks Like

For an extension author, "free-threading support" is not a flag to flip. It is:

1. Find every static/global variable. Decide whether it's read-only (fine),
   thread-local (fine), or shared mutable (needs a lock).
2. Find every borrowed reference. Decide whether concurrent mutation is
   possible. If so, switch to a strong-reference API or hold a critical
   section.
3. Find every cached pointer into a Python object's internals. Verify the
   invariants that made the cache safe still hold.
4. Find every direct refcount manipulation. Replace with the macros, or with
   the atomic-aware API.
5. Find every place you assumed "I'm the only thread here." This is the
   hardest step, because the assumption is usually implicit.
6. Add tests that actually run the extension from multiple threads. The GIL
   build cannot detect races that free-threading exposes.

NumPy, for example, took **two years and multiple releases** to reach
provisional free-threading support. It is one of the best-resourced extensions
in the ecosystem. Smaller projects will take longer, and many will never be
audited at all.

This is what "changes the contract" means in practice: not a subtle
reinterpretation of semantics, but a decades-long backlog of hidden
assumptions that every extension author now has to find and either justify or
fix.

## The Short Version

The GIL is what you get when you choose refcounting, expose it through a
direct extension API, add threads for I/O, and then need to make refcounts
thread-safe without breaking anything. Every alternative at that point was
worse: atomics alone weren't enough, fine-grained locks were 2× slower,
tracing GC would break the ecosystem, and removing threads would break
existing users.

For thirty years the GIL was a pragmatic bet that single-threaded performance
and ecosystem compatibility mattered more than multi-core scaling. PEP 703 is
the first approach that pays down the debt without breaking what the bet
bought — and it only works because biased refcounting and immortal objects
finally made refcount arithmetic cheap enough to be thread-safe by default.
