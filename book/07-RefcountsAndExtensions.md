# Reference Counts and External Modules

## How CPython Manages Memory

Every Python object carries a reference count: an integer field (`ob_refcnt`) that tracks how many things point to it. When the count reaches zero, the object is freed immediately (no garbage-collection pause, no tracing phase).

```
object created      ob_refcnt = 1
assigned to x       ob_refcnt = 2
x goes out of scope ob_refcnt = 1
last reference gone ob_refcnt = 0  → freed
```

Incrementing and decrementing `ob_refcnt` is not a single instruction. It is a read-modify-write sequence:

```
old = obj.ob_refcnt      # LOAD
obj.ob_refcnt = old - 1  # STORE
if obj.ob_refcnt == 0:
    free(obj)
```

A thread switch between LOAD and STORE corrupts the count. This is exactly what `refcount_race.py` demonstrates.

## Cycles and the `gc` Module

Reference counting alone cannot reclaim cyclic garbage. Two objects that point at each other (a parent and child node, any doubly-linked structure, or any cycle of references) keep each other's refcount above zero forever, even when no outside reference exists. Pure refcounted code leaks cycles.

CPython did not address this until **Python 2.0 (October 2000)**, which shipped a cycle-detecting collector as the `gc` module. Neil Schemenauer led the implementation. The algorithm is a standard technique for hybrid refcount-plus-tracing systems, and its shape has not changed materially in 25 years.

### Tracked vs. untracked objects

Only some objects participate in cycle collection. Immutable objects that cannot reference other tracked objects (`int`, `float`, `str`, `bytes`) are skipped entirely. The tracked set is containers and instances: `list`, `dict`, `set`, `tuple` (when it holds at least one tracked element), user-class instances, frames, generators. Each tracked object is linked into a per-generation doubly-linked list inside the runtime.

This selectivity matters: most allocated objects are immutable scalars, and walking them during collection would be wasted work.

### The three generations

Tracked objects start in **generation 0**. Survive a collection, get promoted to generation 1; survive again, generation 2. Generation 0 is collected often; generation 1 less often; generation 2 rarely. Newly created objects are the most likely to be garbage (the *generational hypothesis*), so this concentrates work where it matters.

Defaults are visible and tunable through `gc.get_threshold()` / `gc.set_threshold()`. The gen 0 threshold is the number of allocations minus deallocations that triggers a collection; the gen 1 and gen 2 thresholds count gen 0 (and gen 1) collections, respectively.

### When and how the collector runs

The collector has no dedicated thread. It runs synchronously, in three situations:

**Automatically, during container allocation.** Every time a tracked object is allocated (through `PyObject_GC_New` in the C API, or implicitly when Python code creates a `list`, `dict`, `set`, instance, etc.), CPython increments a per-generation counter. Every tracked deallocation decrements it. After the allocation completes, the runtime checks the counter: if `counter > threshold[0]` (default 700), it runs a gen 0 collection right then, on the same thread that did the allocation, before returning the new object to the caller.

After each gen 0 collection, a separate counter is bumped. If it crosses `threshold[1]` (default 10), gen 1 is collected too. Same for gen 1 → gen 2 via `threshold[2]` (default 10). A full gen 2 sweep therefore happens roughly every 700 × 10 × 10 ≈ 70 000 net container allocations.

The check is post-allocation, not pre-, so a single large allocation never gets scheduled specially. The trigger is the steady drumbeat of container creates.

**Manually, via `gc.collect()`.** Forces a full collection of all generations immediately. Returns the number of unreachable objects found. Useful after dropping a large structure known to contain cycles, for benchmarking, or as a hint before shutdown. You can also call `gc.disable()` to suppress automatic triggering and drive collection yourself, which long-running services sometimes do to control pause timing.

**At interpreter shutdown.** Final cleanup runs collections to free as many objects as possible and surface lingering finalizers. Not perfect: some C state lives outside Python's tracking and may leak across shutdown.

A few details worth knowing:

- The pause is paid by whichever thread happens to do the allocation that crosses the threshold. There is no separate GC thread to amortize this.
- Function calls, imports, attribute lookups, and bytecode dispatch do not trigger the collector directly. Only allocations of tracked objects do.
- C extensions that allocate tracked objects must use `PyObject_GC_New` and call `PyObject_GC_Track` so the new object joins the generation list. Forgetting this is a silent leak of any cycle the object participates in.
- In the free-threaded build, counter updates are atomic and the collection itself is stop-the-world: the triggering thread asks every other Python thread to pause at the next safe point before the walk begins. See chapter 9.

### The cycle-detection algorithm

For a generation being collected:

1. Take a snapshot of each tracked object's `ob_refcnt`. Call this its *GC refcount*.
2. Walk every tracked-to-tracked reference within the generation. For each such reference, **decrement** the target's GC refcount.
3. After the walk, any object whose GC refcount is still > 0 has at least one reference from *outside* the generation (the Python stack, module globals, an older generation, a C extension). It is reachable.
4. Propagate reachability transitively: anything reachable from a still-positive-count object is also reachable.
5. The remainder is unreachable cyclic garbage. Run finalizers (`__del__`), then free it.

The GC refcount is a scratch field; the real `ob_refcnt` is untouched. The collector never moves objects; pointers stay valid throughout. The cost is proportional to the generation's size, not to the heap.

### Why this complements rather than replaces refcounting

The deterministic refcount path still does the bulk of the work and frees objects immediately when their count hits zero. Files close when the last reference drops, sockets release, `with` blocks behave predictably. The cycle collector handles only the edge case refcounting cannot, on a schedule, and only over the tracked subset.

This split is why CPython has the destruction guarantees scripting users expect *and* still reclaims arbitrary object graphs. Pure tracing GCs (Java, C#, JVM-based Jython) cannot promise the first; pure refcounting cannot deliver the second.

Free-threading does not introduce a new collector. It changes how this existing one runs: collections become stop-the-world pauses at safe points, so the algorithm sees a consistent object graph without the GIL. That story is in chapter 9.

## What the GIL Provides

The GIL serializes all Python bytecode execution. Only one thread runs Python at a time, so no two threads can interleave their LOAD/STORE sequences on the same object. Reference counts are always consistent.

This guarantee is invisible to Python programmers; it is simply assumed. It is also what makes writing C extensions straightforward: you can manipulate `ob_refcnt` with plain integer arithmetic and nothing goes wrong.

## Releasing the GIL in Extensions

External modules written in C, Rust, or any other language can release the GIL while doing CPU-bound or I/O-bound work. This is desirable: it lets other Python threads run in parallel during, for example, a long numpy computation or a disk read.

The standard pattern in a C extension:

```c
Py_BEGIN_ALLOW_THREADS
// GIL is released here: do not touch Python objects
do_expensive_work();
Py_END_ALLOW_THREADS
// GIL reacquired: safe to touch Python objects again
```

The contract is strict: **between** `Py_BEGIN_ALLOW_THREADS` and `Py_END_ALLOW_THREADS`, the extension must not read or write any Python object, including its own arguments. Any touch of a Python object without holding the GIL is a data race.

## The Rust Case: PyO3

PyO3 is the standard crate for writing Python extensions in Rust. It encodes the GIL contract in the type system using a lifetime token:

```rust
#[pyfunction]
fn process(py: Python<'_>, data: &PyList) -> PyResult<()> {
    // py token proves we hold the GIL
    // data is a Python object: safe to use here
    
    py.allow_threads(|| {
        // GIL released inside this closure
        // data is NOT accessible here; borrow checker enforces this
        do_expensive_work();
    });
    
    // GIL reacquired automatically when closure returns
    Ok(())
}
```

The `Python<'py>` token is not constructible by user code; PyO3 hands it to you only when you genuinely hold the GIL. Rust's borrow checker then prevents you from using any `&PyAny` (or similar) reference inside `allow_threads`, because those references require the token's lifetime. The memory-safety guarantee is enforced at compile time.

## Free-Threading Changes the Equation

With the GIL removed (Python 3.13+t), the serialization guarantee is gone. Multiple threads can now run Python simultaneously, which means:

- `ob_refcnt` increments and decrements must be **atomic operations**, not plain integer reads and writes.
- CPython's free-threaded build replaces `ob_refcnt` with an atomic integer and uses CPU-level atomic instructions for every `Py_INCREF` / `Py_DECREF`.

Extensions that release the GIL and then reacquire it are largely unaffected; they already respected the contract. Extensions that assumed the GIL was always held, or that did clever things with refcounts outside the normal macros, now have data races.

PyO3 tracks free-threading support explicitly. A Rust extension that declares:

```toml
[package.metadata.maturin]
requires-python = ">=3.13"
```

must also audit every `allow_threads` boundary and ensure no Python objects leak across it (the same rule as before), but now the consequences of getting it wrong are immediate and observable rather than occasional and mysterious.

## What Developers Must Do

| Scenario | GIL build | Free-threaded build |
|---|---|---|
| Pure Python extension logic | Safe by default | May need locks for shared state |
| C extension, respects `Py_BEGIN/END_ALLOW_THREADS` | Safe | Safe |
| C extension, touches objects without holding GIL | Crashes rarely (lucky) | Crashes reliably |
| PyO3 extension, uses `allow_threads` correctly | Safe | Safe |
| PyO3 extension, leaks `Py<T>` across thread boundary | Compile error | Compile error |
| Hand-rolled refcount manipulation | Unsafe | Definitely unsafe |

The core lesson: the GIL did not make extensions safe by magic. It made certain races unlikely by serializing execution. Free-threading reveals the races that were always latent.

## What Gets Refcounted in an Extension

Any `PyObject*` the extension touches. The entire Python object model in C
is `PyObject*`, and every Python value (ints, strings, lists, dicts,
user-defined instances, function objects, modules, types, everything) has
`ob_refcnt` as the first field of its C struct, exposed via the
`PyObject_HEAD` macro.

Concretely, the refcount manipulation happens on:

- **Arguments coming in.** A C function receives its args as `PyObject*`.
  Whether it needs to `Py_INCREF` them depends on "borrowed vs. owned"
  semantics it has to track.
- **Return values going out.** `PyLong_FromLong(42)` returns a *new
  reference* (refcount 1). The caller owns it; whoever eventually receives
  it must `Py_DECREF` when done.
- **Items fetched from containers.** `PyDict_GetItem` returns a *borrowed*
  reference; if the extension wants to hold onto it past the dict's
  lifetime, it must `Py_INCREF`. `PyList_GetItem` is the same.
  `PyList_SetItem` *steals* a reference to the value being inserted, so
  the caller must not `Py_DECREF` after.
- **Cached or stored objects.** Anything the extension stashes in a C
  static variable, a struct field, or its module state needs a
  `Py_INCREF` to keep it alive, and a matching `Py_DECREF` at teardown.
- **Intermediate objects.** Temporaries created during the function body
  (e.g., a list being built up to return) need their refcounts balanced
  before exit.

`Py_INCREF` is a C macro, not a function. It expands inline to
`((PyObject*)(op))->ob_refcnt++`. Every compiled extension has
`ob_refcnt++` written directly into its machine code against the current
struct layout. That's why this is an ABI issue rather than just an API
issue: CPython can't change how refcounting works (atomicize it, add a
bias field, make it deferred) without every already-compiled `.so` or
`.pyd` on users' machines executing the wrong machine instruction against
the new layout.

There is no stack allocation for Python objects. Every `PyObject` lives on
the heap, and refcounting is the only mechanism that ever frees it. If an
extension creates a temporary and doesn't `Py_DECREF` it before returning,
it leaks, even if no Python code or C code outside that function ever saw
it.

A concrete C example:

```c
static PyObject* add_them(PyObject *self, PyObject *args) {
    PyObject *x = PyLong_FromLong(10);   // new reference, refcount = 1
    PyObject *y = PyLong_FromLong(20);   // new reference, refcount = 1
    PyObject *sum = PyNumber_Add(x, y);  // new reference, refcount = 1
    Py_DECREF(x);                        // refcount -> 0, freed immediately
    Py_DECREF(y);                        // refcount -> 0, freed immediately
    return sum;                          // ownership transferred to caller
}
```

`x` and `y` never leave the function. They still need explicit `Py_DECREF`
calls, or they leak. The Python integers `10` and `20` are heap objects
so they are not managed via a "local variable" stack lifetime.

Note:

1. **Borrowed vs. new references.** Objects you *receive* (function
   arguments, results of `PyDict_GetItem`, `PyList_GetItem`) are usually
   borrowed: you do *not* `Py_DECREF` them. Objects you *create* (anything
   with `From`, `New`, or `Py_BuildValue` in its name) are new references:
   you *must* `Py_DECREF` eventually, or transfer ownership. This
   distinction isn't visible in the C type system; it's documented
   per-function and the extension author has to track it mentally.
2. **Immortal objects in 3.12+** (PEP 683). `None`, `True`, `False`, small
   integers, and interned strings now carry a sentinel refcount that never
   changes. `Py_INCREF(Py_None)` is a no-op at runtime. But the extension
   author still writes the macro in source, and still reasons as if it
   were a normal refcount, because the macro is the contract and the
   optimization is invisible below it.

The net effect: the C extension author is essentially hand-rolling garbage
collection, one `Py_INCREF`/`Py_DECREF` pair at a time, for every
`PyObject*` that passes through their code. This is the cost of exposing
reference counting directly in the C API, and it's what makes the
ecosystem so sensitive to any change in how refcounts work.
