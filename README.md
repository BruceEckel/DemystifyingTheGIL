# Demystifying The GIL

Companion repository for the PyCon 2026 presentation *Demystifying The GIL*. Contains:

- `examples/`: runnable Python scripts that demonstrate GIL and free-threading behavior
- `presentation/`: Slidev slide source for the talk
- `book/`: a book that grew out of preparing the talk

## Installation

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) for managing Python and dependencies
- GNU Make (on Windows, comes with [Git for Windows](https://git-scm.com/download/win))
- [Node.js](https://nodejs.org/) and `npm` for the Slidev CLI (only needed to view slides)

### Setup

Clone the repo and sync dependencies:

```
git clone https://github.com/BruceEckel/DemystifyingTheGIL.git
cd DemystifyingTheGIL
uv sync
```

`uv sync` creates `.venv` pinned to the free-threaded build (3.14t).

Pre-install both Python builds (uv will fetch them on first use otherwise):

```
uv python install 3.14 3.14t
```

Confirm both are present:

```
uv python list
```

You should see `cpython-3.14.X-...` (with GIL) and `cpython-3.14.X+freethreaded-...` (without).

Install the Slidev CLI globally to view or edit the slides:

```
npm i -g @slidev/cli@0.50.0
```

> Note that version 50 is required to allow highlighting; later version break highlighting

## Using the Makefile

The Makefile lives in `examples/`. Change into that directory first:

```
cd examples
```

`make help` (or `make` with no target) prints the available commands.

### Run a single example

```
make counter_race.py        # GIL run, then no-GIL run
make .\counter_race.py      # same; .\ prefix accepted for PowerShell tab-completion
make gil counter_race.py    # GIL run only
make nogil counter_race.py  # no-GIL run only
```

### Run every example

```
make gil      # run all examples with the GIL
make nogil    # run all examples without the GIL
make all      # both
```

### Other targets

```
make list      # print every <script.py> option, one per line
make overhead  # compare single-threaded performance across builds
make present   # launch the Slidev slide preview, with auto-reload on edits
```

## The Book

`book/` contains a book that grew out of preparing the talk. It explains why the GIL exists, why removing it has been so difficult, and what changes when you turn it off. Chapters in reading order:

1. **Preface**: origin of the talk and the book
2. **Concurrency**: concurrency vs. parallelism, threads vs. processes, race conditions
3. **Concurrency Strategies**: the general menu (locks, actors, CSP, STM, immutability)
4. **Python Concurrency Strategies**: how each strategy maps to Python today
5. **History of the GIL**: the four design decisions that made the GIL inevitable, the alternatives that were tried, what PEP 703 changed
6. **GIL Context Switching**: when the GIL releases, how races become visible
7. **Refcounts and Extensions**: why the GIL is bound up with reference counting and the C extension ABI
8. **The Broken Contract**: what the free-threaded build asks of extension authors and library maintainers
9. **Inside Free-Threading**: biased and deferred refcounting, immortal objects, per-object locks
10. **Appendix: Python and the OS**: Python threads vs. OS threads, the main thread, blocking calls, memory and stack, scheduling, fork/spawn, subinterpreters
