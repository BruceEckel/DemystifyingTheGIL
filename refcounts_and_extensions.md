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
