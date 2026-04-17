# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyCon 2026 presentation: "Demystifying The GIL". Demonstrates Python's Global Interpreter Lock (GIL) behavior by contrasting thread-unsafe and thread-safe shared-state access, and showing how the GIL masks race conditions that become visible in Python's free-threaded (no-GIL) build.

## Running the Scripts

All scripts live in `examples/`. The project uses `uv` with Python 3.14. The venv (`.venv`) is pinned to the free-threaded build (`3.14t`).

**With GIL (standard Python 3.14):**
```
uv run --python 3.14+gil examples/<script.py>
```

**Without GIL (free-threaded Python 3.14t):**
```
uv run --python 3.14t examples/<script.py>
```

**Run all examples via Make (from `examples/`):**
```
cd examples
make gil    # all scripts with GIL
make nogil  # all scripts without GIL
make all    # both
```

**Install dependencies:**
```
uv sync
```

## Architecture

- **`constants.py`** — Shared constants: `NUM_THREADS`, `ITERATIONS`, `EXPECTED`, `FAST_SWITCH_INTERVAL`. Imported as `import constants as c`.
- **`gil_utils.py`** — Utility imported by all demo scripts; detects `"free-threading"` in `sys.version` and prints whether GIL is active.
- **`unsafe.py`** — Threads increment a shared `counter` with no synchronization. With GIL: always correct. Without GIL: race condition produces incorrect results.
- **`safe.py`** — Same as `unsafe.py` but wraps `counter += 1` in a `threading.Lock()`. Correct under both builds.
- **`two_variable.py`** — Two variables incremented together on adjacent lines; they should always be equal. With GIL: always equal. Without GIL: they diverge.
- **`context_switch.py`** — Makes the race in `unsafe.py` certain by using `time.sleep(0)` to force a GIL release between the LOAD and STORE steps.
- **`surprise.py`** — A pure function (`increment(x)`) used to update shared state becomes unsafe because the read-modify-write pattern around the call is not atomic. Shows that even a safe function can participate in a race.
- **`no_surprise.py`** — Thread-safe version of `surprise.py`. Lock covers the full read-modify-write sequence. Also demonstrates that free-threaded code with high lock contention can be slower than GIL code.
- **`connection_pool.py`** — Lazy initialization inside a class: multiple threads pass the `None` check simultaneously and `connect()` runs more than once.
- **`stats.py`** — A stats accumulator with `count` and `total` updated on separate lines. They can diverge under free-threading, producing a wrong or crashing `mean()`.
- **`refcount_race.py`** — Simulates CPython's reference count manipulation to show why the GIL is essential for memory safety. With GIL: always correct. Without GIL: refcount drifts, indicating use-after-free or memory leak.
