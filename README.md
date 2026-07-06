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

Install the Slidev CLI and theme into `presentation/` (only needed to view or edit the slides):

```
cd presentation
npm install
cd ..
```

This populates `presentation/node_modules/` with `@slidev/cli` and `@slidev/theme-default` at the versions pinned in `presentation/package.json`. The `make present` target invokes the local install, so no global `slidev` is needed.

## Using the Makefile

The Makefile lives in `examples/`:

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

`book/` contains a book that grew out of preparing the talk. It explains why the GIL exists, why removing it has been so difficult, and what changes when you turn it off. It's published at [bruceeckel.github.io/DemystifyingTheGIL](https://bruceeckel.github.io/DemystifyingTheGIL/), built from `book/src/` with [mdBook](https://rust-lang.github.io/mdBook/) and deployed automatically by `.github/workflows/pages.yml` on every push to `main` that touches `book/`.

To preview it locally, [install mdBook](https://rust-lang.github.io/mdBook/guide/installation.html) and run:

```
mdbook serve book
```

Chapters in reading order:

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
