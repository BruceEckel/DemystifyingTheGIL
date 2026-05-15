---
title: Demystifying The GIL
author: Bruce Eckel
theme: default
layout: default
contextMenu: false
drawings:
  enabled: false
navigation: false
selectable: false
drawers: false
info: false
css: style.css
---

---
layout: image
image: TitleSlide.png
---
---
layout: image
image: TheGILLandscape.png
---

---

<<< ../examples/concurrency_is_easy.py

---

<<< ../examples/utils.py#run_in_threads

---

# The Atomicity of `counter += 1`

```
LOAD_GLOBAL     counter  # read value from memory
LOAD_SMALL_INT  1        # push the constant 1
BINARY_OP       13 (+=)  # compute counter + 1
STORE_GLOBAL    counter  # write result back
```

- Two threads read the same value → both increment → one write is lost
- Before 3.11, context switches happened between any opcodes, but only one thread could execute at a time
- In 3.11+, `counter += 1` **is** atomic: context switches only happen on function calls and back jumps
- With free threads, multiple threads execute opcodes in parallel; nothing serializes them

---

<<< ../examples/the_camels_nose.py#show {5,10}

---

<<< ../examples/embarrassingly_parallel.py#setup

---

<<< ../examples/embarrassingly_parallel.py#comparison

---

# When Free Threading Is Useful (`make FTFriendly`)

| Pattern                    | File                         | GIL    | FT     | Speedup |
|----------------------------|------------------------------|--------|--------|---------|
| Embarrassingly parallel    | `embarrassingly_parallel.py` | 4.30s  | 0.77s  | 5.58x   |
| Async + CPU offload        | `async_cpu_offload.py`       | 4.37s  | 0.87s  | 5.02x   |
| Sharded accumulators       | `counter_sharded.py`         | 0.02s  | 0.01s  | 2.00x   |
| Coarse-grained locking     | `counter_coarse.py`          | 0.08s  | 0.02s  | 4.00x   |
| Read-mostly shared state   | `cache_readmostly.py`        | 8.01s  | 1.19s  | 6.73x   |
| Pipeline parallelism (CSP) | `counter_csp_work.py`        | 35.93s | 16.44s | 2.19x   |

---

# FT Overhead in 3.14t (`make overhead`)

- Cost of single-threaded code might get to 2-5% eventually

| task              | GIL (s)    | FT (s)     | delta      |
|-------------------|------------|------------|------------|
| int +=            | 0.4034     | 0.4604     | +14.1%     |
| obj alloc         | 0.2331     | 0.2823     | +21.1%     |
| tuple new         | 0.2371     | 0.2621     | +10.5%     |
| dict set          | 0.1227     | 0.1455     | +18.6%     |
| list append & pop | 0.0630     | 0.0852     | +35.2%     |
| attr read         | 0.3311     | 0.3898     | +17.7%     |
| func call         | 0.2249     | 0.2479     | +10.2%     |
| str join          | 0.0098     | 0.0106     | +8.2%      |
| **total**         | **1.6251** | **1.8838** | **+15.9%** |

---

# How We Got the GIL

- **1990: Reference counted garbage collection**<br>
  Simple and deterministic<br>
  Every `INCREF` & `DECREF` is read-modify-write<br>
  Python 1 leaked cycles; no cycle collector until Python 2
- **1991: Direct C API**<br>
  `ob_refcnt` is part of the *Application Binary Interface* (ABI)<br>
  Refcount semantics can never change without breaking every extension
- **1992: We need I/O**<br>
  The OS already does context switching for threads<br>
  Now refcount updates can race
- **Single interpreter-wide lock**<br>
  The only option that keeps refcounts safe, extensions safe, and single-threaded code fast

---

# The GIL Protects

- **Reference counts**: GIL ensures `ob_refcnt` inc/dec is atomic
- **Memory allocator**: `PyMem_Malloc` / `PyObject_New` are not thread-safe without it
- **Cyclic garbage collector**: needs exclusive traversal of the entire object graph
- **CPython internals**: module `__dict__`, type objects, interned strings are unprotected
- **Import system**: `sys.modules` lookups and insertions during `import`
- **Signal handling**: only the main thread handles signals; GIL ensures it gets scheduled
- **C extensions**: most extensions assume single-threaded bytecode execution
- **`sys.settrace` / profiling**: frame inspection assumes serialized execution
- <mark>**Accidental thread safety**: code not written for concurrency works anyway</mark>

---

# Removal Attempts & Workarounds

- **1996: Greg Stein's free-threaded patch**<br>
  Fine-grained locks, ~2× slower single-threaded, rejected
- **2008 (2.6): `multiprocessing`**<br>
  Sidestep the GIL with separate processes
- **2011 (3.2): New GIL**<br>
  100-opcode counter replaced with a 5ms timer; releaser waits for another thread before re-acquiring
- **2014–15 (3.4, 3.5): `asyncio` / `async`-`await`**<br>
  Removes the I/O motivation for threads (but not the CPU one)
- **2016: Gilectomy**<br>
  Another attempt; still couldn't clear the single-threaded performance bar

---

# Removal Attempts & Workarounds (continued)

- **2022 (3.11): Adaptive interpreter**<br>
  Check points move from *every opcode* to **backward jumps and function calls only**<br>
  `counter += 1` becomes atomic in practice
- **2023 (3.12, PEP 684): Per-interpreter GIL**<br>
  One process, many interpreters, one GIL each<br>
  Shared address space, but isolated object worlds (channels, not shared objects)<br>
  Prep for subinterpreters
- **PEP 703 accepted 2023; 3.13t shipped 2024, 3.14t in 2025**<br>
  Biased refcounting + immortal objects finally make refcounts thread-safe<br>
  Cheap enough (?) to remove the GIL

---

# Patterns That Break Without the GIL

- **Module-level mutable state**<br>
  Shared caches, counters, registries initialized at import time
- **Lazy initialization**<br>
  `if _cache is None: _cache = build_cache()`<br>
  Note lazy imports coming up
- **`dict` / `list` mutations**<br>
  Appending to a shared list, updating a shared dict
- **Connection pools**<br>
  Checkout/checkin logic that assumes serialized access
- **Logging handlers**<br>
  Writing to shared buffers or files
- **C extensions**<br>
  Any extension that touches Python objects without the GIL held

---

```python
# module-level shared state
# (cache, registry, plugin)
_registry = {}

def register(name, obj):
    _registry[name] = obj

def lookup(name):
    return _registry.get(name)
```

- Two threads resize the dict simultaneously → internal structure corruption
- A thread iterates, another inserts → `RuntimeError: dictionary changed size`

---

# Should You Use Concurrency?

- **Only if things run painfully slow**<br>
  Concurrency always adds complexity
- **Use Occam's razor**<br>
  Faster hardware<br>
  Profile & optimize (ask your AI)<br>
  Rewrite a function in Rust using AI and PyO3
- **There are numerous types of concurrency problems**<br>
  You must understand which one(s) you are trying to solve, to choose the right concurrency pattern(s)
- **Stop when it's fast enough**<br>
  Don't unnecessarily add development and maintenance costs
- **Concurrency is often an architectural choice**<br>
  Do early experiments to see if you need it

---
layout: image
image: FinalSlideEscher.png
---
