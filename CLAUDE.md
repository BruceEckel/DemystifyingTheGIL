# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyCon 2026 presentation: "Demystifying The GIL". Demonstrates Python's Global Interpreter Lock (GIL) behavior by contrasting thread-unsafe and thread-safe shared-state access, and showing how the GIL masks race conditions that become visible in Python's free-threaded (no-GIL) build.

## Running the Scripts

The project uses `uv` with Python 3.14. The venv (`.venv`) is pinned to the free-threaded build (`3.14t`).

**With GIL (standard Python 3.14):**
```
python unsafe.py
```
> Do NOT use `uv run` or activate the venv for this — uv defaults to 3.14t, which defeats the purpose of the demo.

**Without GIL (free-threaded Python 3.14t):**
```
uv run --python 3.14t unsafe.py
uv run --python 3.14t safe.py
```

**Install dependencies:**
```
uv sync
```

## Architecture

- **`unsafe.py`** — 8 threads increment a global `counter` 100,000 times each with no synchronization. With GIL: always correct (800,000). Without GIL: race condition produces incorrect results.
- **`safe.py`** — Same as `unsafe.py` but wraps `counter += 1` in a `threading.Lock()`. Correct under both GIL and no-GIL builds.
- **`show_gil.py`** — Utility imported by both scripts; detects `"free-threading"` in `sys.version` and prints whether GIL is active.

The key point being demonstrated: `counter += 1` is not atomic (it compiles to `LOAD`, `BINARY_OP`, `STORE` bytecodes). The GIL serializes these in CPython, hiding the race. The free-threaded build removes that serialization, making the bug observable.
