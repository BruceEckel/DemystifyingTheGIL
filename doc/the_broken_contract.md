# The Broken Contract

For thirty years, writing a CPython C extension meant writing against a set of
assumptions that were never formally labeled as a contract. They were just how
things worked. Most of them follow from "the GIL is held whenever my code
runs." Free-threading invalidates them one by one.

## What Extension Authors Used to Assume

- **My function is called with the GIL held.** No other Python thread is
  executing bytecode or C extension code simultaneously. I don't need to
  think about interleavings until I explicitly release the GIL.
- **Refcount manipulation is just integer arithmetic.** `Py_INCREF(obj)`
  expands to `obj->ob_refcnt++`. It compiles to a load, an add, and a store.
  No lock prefix, no memory barrier.
- **Direct reads of `ob->ob_refcnt` are coherent.** I can log it, branch on
  it, use it to decide whether to cache something.
- **Module-level C statics and globals need no locks.** My extension's
  internal state (caches, counters, lazy-initialized tables) is implicitly
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
  a full *memory barrier* (a synchronization point that forces pending writes
  to become visible across threads, instead of sitting in a CPU's local store
  buffer or cache). Writes one thread performs before releasing the GIL are
  visible to the next thread that acquires it.

## What Free-Threading Forces

- **Concurrent entry is real.** Two Python threads can call into my extension
  at the same instant. Anything I touch that is shared must be protected.
- **Refcount macros now expand to atomics.** `Py_INCREF`/`Py_DECREF` still
  work, but they're no longer cheap integer ops; they're `lock xadd` (or
  equivalent) under the hood. Extensions that bypassed the macros with direct
  `obj->ob_refcnt++` are broken: the write is not atomic and the value is no
  longer stored in a plain `Py_ssize_t`.
- **Module state needs explicit locking.** That static cache, that lazy
  initializer, that "I'll just remember the last value" optimization: all of
  them need a mutex, or a redesign to avoid sharing.
- **Borrowed references are dangerous.** Another thread can delete the dict
  entry and free the object between `PyDict_GetItem` returning and my code
  using the result. Several APIs have gained strong-reference variants
  (`PyDict_GetItemRef`, etc.) for this reason.
- **Iterating a container while another thread mutates it can fail.** The
  built-in containers have internal locks that keep the interpreter from
  crashing, but the *logical* race (reading a dict that's being written) is
  now a real concern, not a theoretical one.
- **Type mutation is no longer a quiet operation.** Another thread can assign
  to `SomeClass.method` while my code is doing attribute lookup on an
  instance. The interpreter handles this correctly, but any pointer I cached
  into a type's slot table is no longer safe.
- **Memory ordering can matter.** Without the GIL providing implicit barriers,
  writes to shared structures need explicit atomics or locks to be visible in
  a defined order across threads.

## The Opt-In Mechanism

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

## What the Audit Actually Looks Like

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

