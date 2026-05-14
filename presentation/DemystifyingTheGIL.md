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
---

<<< ../examples/concurrency_is_easy.py

---

<<< ../examples/utils.py#run_in_threads

---

# The Atomicity of `counter += 1`

```
LOAD_GLOBAL   counter  # read value from memory
BINARY_OP     +  1     # compute counter + 1
STORE_GLOBAL  counter  # write result back
```

- Two threads read the same value → both increment → one write is lost
- In 3.11+, `counter += 1` **is** atomic: Context switches only happen on function calls and back jumps
- With free threads, threads context switch **anywhere**

---

<<< ../examples/the_camels_nose.py {5,10}

---

<<< ../examples/cpu_parallel.py#setup

---

<<< ../examples/cpu_parallel.py#comparison

---

# When Free Threading Is Useful (`make FTFriendly`)

| Pattern                    | File                   | GIL    | FT     | delta  |
|----------------------------|------------------------|--------|--------|--------|
| Embarrassingly parallel    | `cpu_parallel.py`      | 4.08s  | 0.78s  | -80.9% |
| Async + CPU offload        | `async_cpu_offload.py` | 4.08s  | 0.78s  | -80.9% |
| Sharded accumulators       | `counter_sharded.py`   | 0.02s  | 0.01s  | -50.0% |
| Coarse-grained locking     | `counter_coarse.py`    | 0.08s  | 0.02s  | -75.0% |
| Read-mostly shared state   | `cache_readmostly.py`  | 7.81s  | 1.11s  | -85.8% |
| Pipeline parallelism (CSP) |` counter_csp_work.py`  | 59.60s | 19.81s | -66.8% |

---

# No-GIL Overhead in 3.14t (`make overhead` )

Cost of operations on single-threaded code. 

| task              | GIL (s) | FT (s) | delta  |
|-------------------|---------|--------|--------|
| int +=            | 0.4034  | 0.4604 | +14.1% |
| obj alloc         | 0.2331  | 0.2823 | +21.1% |
| tuple new         | 0.2371  | 0.2621 | +10.5% |
| dict set          | 0.1227  | 0.1455 | +18.6% |
| list append & pop | 0.0630  | 0.0852 | +35.2% |
| attr read         | 0.3311  | 0.3898 | +17.7% |
| func call         | 0.2249  | 0.2479 | +10.2% |
| str join          | 0.0098  | 0.0106 | +8.2%  |
| **total**         | **1.6251** | **1.8838** | **+15.9%** |

---

# What Is the GIL?

- *Lock* aka *mutex*: protects shared memory from simultaneous modification.
- *Global* + *interpreter*: There's only one protecting the shared memory for the entire interpreter
- More than one thread can be used, but only one thread executes Python bytecodes at a time
- This is a CPython implementation detail; other implementations (Jython, PyPy-STM, which uses Software Transactional Memory) don't have it
- Since Python 1.5 (1997)

---

# What Shared Memory is Protected?

- **Reference counting** — GIL ensures `ob_refcnt` inc/dec is atomic
- **Memory allocator** — `PyMem_Malloc` / `PyObject_New` are not thread-safe without it
- **Cyclic garbage collector** — needs exclusive traversal of the entire object graph
- **CPython internals** — module `__dict__`, type objects, interned strings are unprotected
- **Import system** — `sys.modules` lookups and insertions during `import`
- **Signal handling** — only the main thread handles signals; GIL ensures it gets scheduled
- **C extensions** — most extensions assume single-threaded bytecode execution
- **`sys.settrace` / profiling** — frame inspection assumes serialized execution
- **Accidental thread safety** — code not written for concurrency works anyway


---

# Patterns That Will Break

Code that is "accidentally thread-safe" today:

- **Module-level mutable state**: shared caches, counters, registries initialized at import time
- **Lazy initialization**: `if _cache is None: _cache = build_cache()`
- **`dict` / `list` mutations**: appending to a shared list, updating a shared dict
- **Connection pools**: checkout/checkin logic that assumes serialized access
- **Logging handlers**: writing to shared buffers or files
- **C extensions**: any extension that touches Python objects without the GIL held

---

```python
# module-level shared state (cache, registry, plugin)
_registry = {}

def register(name, obj):
    # dict write: "safe enough" under GIL
    _registry[name] = obj

def lookup(name):
    return _registry.get(name)
```

- Two threads resize the dict simultaneously → internal structure corruption
- A thread iterates, another inserts → `RuntimeError: dictionary changed size`

---
layout: image
image: FinalSlideEscher.png
---
