---
title: Demystifying The GIL
author: Bruce Eckel
theme: default
---

# Demystifying The GIL
(Global Interpreter Lock)

Bruce Eckel

github.com/BruceEckel/DemystifyingTheGIL

---

# Making a Dent in the GIL

---

# The GIL Landscape, Before & After

---

# Dunning-Kruger Strikes Again!

<<< ../examples/concurrency_is_easy.py

---

# `counter += 1` Is Not Atomic

```
LOAD_GLOBAL   counter       # read value from memory
BINARY_OP     +  1          # compute counter + 1
STORE_GLOBAL  counter       # write result back
```

- A context switch can happen **between any two of these steps**
- Two threads read the same value → both increment → one write is lost

---

# Sipping from the Concurrency Firehose

<<< ../examples/the_camels_nose.py{9-11}

---

# What Is the GIL?

- A *lock* (aka *mutex*) protects shared memory from simultaneous modification.
- *Global* + *interpreter*: There's only one protecting the shared memory for the entire interpreter
- Only one thread executes Python bytecode at a time
- A CPython implementation detail; other implementations (Jython, PyPy-STM, which uses Software Transactional Memory) don't have it
- Since Python 1.5 (1997)

---

# What Shared Memory is Protected?

- **Reference counting** — `ob_refcnt` inc/dec must be atomic; GIL makes it so
- **Memory allocator** — `PyMem_Malloc` / `PyObject_New` are not thread-safe without it
- **Cyclic garbage collector** — needs exclusive traversal of the entire object graph
- **CPython internals** — module `__dict__`, type objects, interned strings are unprotected
- **Import system** — `sys.modules` lookups and insertions during `import`
- **Signal handling** — only the main thread handles signals; GIL ensures it gets scheduled
- **C extensions** — most extensions were written assuming single-threaded bytecode execution
- **`sys.settrace` / profiling** — frame inspection assumes serialized execution
- **Accidental thread safety** — your code, not written for concurrency, works anyway

---


# Why It "Works" With the GIL

- The GIL is released only at predictable points — every N bytecodes (the "check interval")
- Those 3 bytecodes are short enough that the GIL often isn't released between them
- But this is **not guaranteed** — it's timing luck
- Even with the GIL, long enough critical sections *can* be interrupted
- You've been getting away with it, not writing correct code

---

# Python 3.14t — Free-Threaded Build

- GIL disabled by default; threads run in **true parallel** on multiple cores

---

# The Iceberg

- You rewrote your code. You added locks. Your tests pass under 3.14t.
- **But you didn't write most of the code you run.**
- Every library you import was written under the GIL assumption
- Most library authors didn't know they needed to think about thread safety
- The GIL was their lock — silently, invisibly, without their knowledge

---

# Library Patterns That Will Break

Code that is "accidentally thread-safe" today:

- **Module-level mutable state** — shared caches, counters, registries initialized at import time
- **Lazy initialization** — `if _cache is None: _cache = build_cache()` (classic TOCTOU)
- **`dict` / `list` mutations** — appending to a shared list, updating a shared dict
- **Connection pools** — checkout/checkin logic that assumes serialized access
- **Logging handlers** — writing to shared buffers or files
- **C extensions** — any extension that touches Python objects without the GIL held

---

# A Concrete Example

A common pattern in library code today:

```python
# module-level shared state — common in caching, registries, plugins
_registry = {}

def register(name, obj):
    _registry[name] = obj   # dict write — "safe enough" under GIL

def lookup(name):
    return _registry.get(name)
```

Under 3.14t with concurrent `register()` calls:

- Two threads resize the dict simultaneously → internal structure corruption
- Or one thread iterates while another inserts → `RuntimeError: dictionary changed size`
- **The code didn't change. The behavior did.**

---

# Why This Is Hard to Find

- Race conditions are **non-deterministic** — the bug may appear 1 in 10,000 runs
- Your test suite runs sequentially or with low concurrency → green CI
- The bug surfaces under production load, specific hardware, or after an OS scheduler change
- Python 3.14t makes races *more likely* but still not certain
- Luckily: 3.14t is a correctness checker you can run today

---

# What You Should Do Now

1. **Audit shared mutable state** — anything touched by more than one thread
2. **Run your test suite under 3.14t** — it will expose latent races that the GIL was hiding
3. **Add explicit locks** — `threading.Lock`, `threading.RLock`, `queue.Queue`
4. **Prefer immutable data** — objects created once and never mutated are safe
5. **Check your dependencies** — file issues against libraries that don't declare thread safety

---

# The Payoff

Why bother? Because without the GIL:

- CPU-bound threads actually run in parallel on multiple cores
- `threading` becomes a genuine tool for parallelism, not just I/O concurrency
- Python can compete with Go and Java for multi-core throughput
- The ecosystem has 30 years of battle-tested concurrency primitives to use
- Libraries that do the work correctly will be faster and more scalable

---

# The Rule

> If two threads touch the same data and at least one of them writes,
> you need a lock — **GIL or not**.

- This has always been true
- The GIL made it optional in CPython — that era is ending
- Code that follows this rule works correctly on every Python implementation, today and tomorrow
