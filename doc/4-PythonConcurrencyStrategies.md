# Python Concurrency Strategies

In the previous chapter we looked at general concurrency strategies,
and here we will look at the specific Python approaches.

## Quick Reference

| Strategy | CPU parallel | I/O concurrent | GIL removal impact |
|---|---|---|---|
| `async`/`await` | No | Yes | `run_in_executor` gains true CPU parallelism |
| `threading` | No → **Yes** | Yes | Major: unlocks CPU parallelism; shared state now needs explicit locks |
| `multiprocessing` | Yes | Yes | Minor: threads become a lower-overhead alternative |
| Subinterpreters | Yes | Yes | Significant: per-interpreter GIL disappears; isolation remains, parallelism model changes |
| `ThreadPoolExecutor` | No → **Yes** | Yes | `run_in_executor` and thread pools gain true CPU parallelism |
| `ProcessPoolExecutor` | Yes | Yes | None: already process-isolated |

## `async`/`await`

Cooperative, single-threaded concurrency. A *coroutine* is a function that can pause itself: when it executes `await`, it returns control to a scheduler called the *event loop*, which picks another ready coroutine and resumes it. All coroutines run on one thread, taking turns at explicit yield points. No thread is ever switched preemptively.

**Strengths:**
- No race conditions on shared state between `await` points
- Very low overhead (no OS threads, no context switching cost)
- Scales to thousands of concurrent connections
- Explicit yield points make control flow readable

**Weaknesses:**
- Requires async-aware libraries throughout
- No CPU parallelism
- A long CPU-bound loop blocks all other coroutines

**Use when:** You have many concurrent I/O operations (HTTP requests, database queries, WebSocket connections) and can commit to an async library stack.

**Not appropriate for:** CPU-bound work, or when you need to call synchronous blocking libraries without a workaround.

```python
import asyncio
import aiohttp

async def fetch(session, url):
    async with session.get(url) as response:
        return await response.text()

async def main():
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(fetch(session, url_a), fetch(session, url_b))
```

**GIL vs. no-GIL**

The event loop always runs on a single thread, so a blocking call made directly inside a coroutine stalls everything regardless of the build. The difference appears in the workaround: `loop.run_in_executor()` offloads a blocking call to a thread pool.

```python
result = await loop.run_in_executor(None, blocking_library_call, arg)
```

With the GIL, this works well for I/O-bound blocking calls (the thread releases the GIL during I/O), but for CPU-bound blocking calls the executor thread holds the GIL and stalls the event loop anyway. Without the GIL, the executor thread runs truly in parallel with the event loop for both I/O and CPU-bound work. The need for async-aware libraries remains, but the cost of not having them is reduced.

## Threading

Preemptive multitasking using OS threads. The OS schedules threads normally. The `threading` module API is identical in both builds; the GIL determines whether threads run in parallel or take turns.

**Strengths:**
- Simpler than `async`/`await` for some patterns
- Existing blocking libraries work without modification
- Good I/O concurrency in both builds (GIL releases during I/O; no GIL means it just runs)
- Familiar programming model

**Use when:** You have I/O-bound work and blocking libraries to call, or you are integrating with code that cannot be made async.

**GIL vs. no-GIL**

This is where the difference is most significant.

With the GIL, only one thread executes Python bytecode at a time. I/O-bound threads make progress concurrently (the GIL releases during I/O), but two threads doing CPU work simply take turns. The GIL also makes race conditions rare, which creates false confidence: code that "works" may be subtly wrong.

Without the GIL, threads run in true parallel on multiple cores. CPU-bound work scales. But all the races the GIL was quietly suppressing are now real and frequent. Every piece of shared mutable state needs explicit synchronization.

| | With GIL | Without GIL |
|---|---|---|
| CPU parallelism | No | Yes |
| I/O concurrency | Yes | Yes |
| Shared state safety | Accidental (mostly) | Explicit locks required |
| Race condition frequency | Rare | Continuous |
| Single-threaded overhead | None | Small (atomic refcounting) |

**GIL build not appropriate for:** CPU-bound work.

**No-GIL build not appropriate for:** Code with heavy shared-state contention (lock overhead can make it slower than the GIL build), or production systems relying on libraries not yet tested under free-threading.

## `multiprocessing`

Separate OS processes, each with its own Python interpreter and GIL. The OS provides true parallelism. Processes communicate via queues, pipes, or shared memory.

**Strengths:**
- True CPU parallelism, works with any Python build today
- Process isolation: a crash in one worker does not affect others
- No shared state by default, which eliminates entire classes of bugs
- Compatible with all existing libraries

**Weaknesses:**
- High startup cost. *Forking* clones the parent process (fast, but inherits its locks, threads, and open file descriptors, which can misbehave). *Spawning* starts a fresh interpreter (slower, cleaner state). Spawn is the default on Windows and macOS; fork is still available on Linux.
- Data passed between processes must be serialized (pickled), which is slow for large objects
- Shared state requires explicit mechanisms (`multiprocessing.shared_memory`, `Manager`, `Value`)
- Higher memory usage (each process has its own heap)

**Use when:** You have CPU-bound work expressible as independent tasks, startup cost is acceptable, and data exchange between workers is infrequent.

**Not appropriate for:** Fine-grained parallelism with frequent communication, tasks where startup overhead dominates runtime, or workloads with large datasets that must be in memory simultaneously. Each worker gets its own copy of the data, multiplying memory usage by the number of processes. Workarounds exist (`multiprocessing.shared_memory`, memory-mapped files) but add significant complexity.

```python
from multiprocessing import Pool

def crunch(chunk):
    return sum(x * x for x in chunk)

with Pool() as pool:
    results = pool.map(crunch, data_chunks)
```

**GIL vs. no-GIL**

`multiprocessing` is largely unaffected by the GIL, since each process has its own interpreter. The behavior and performance are the same in both builds.

What changes is the relative appeal. With the GIL, `multiprocessing` is often the only practical way to achieve CPU parallelism in Python, so its overhead is accepted as a necessary cost. Without the GIL, free-threaded `threading` can achieve similar parallelism with no process creation cost and no serialization overhead. For workloads where isolation is not the primary goal, `multiprocessing` becomes less compelling as free-threading matures.

## Subinterpreters

Multiple Python interpreters running in the same OS process, each with its own GIL. Added at the C API level in Python 3.12 (PEP 554); higher-level Python APIs are still evolving (PEP 734).

**Strengths:**
- Intra-process parallelism with stronger isolation than threads
- Lower overhead than `multiprocessing` (shared process heap, no fork)
- Objects that cannot cross interpreter boundaries create an early error rather than a silent race

**Weaknesses:**
- Objects cannot be shared directly; data passes through channels using pickling or `memoryview` of shared memory
- Most C extensions assume a single interpreter per process and will fail
- The Python-level API is not yet stable or ergonomic
- Effectively experimental for application code in 2026

**Use when:** You need isolation stronger than threads but lighter than processes, you control all the code involved, and you are willing to work at a low level.

**GIL vs. no-GIL**

Subinterpreters were designed specifically to provide CPU parallelism within a single process while keeping the GIL. Each interpreter has its own GIL, so they run simultaneously without interfering with each other.

Without the GIL, the per-interpreter GIL disappears alongside the main one. Subinterpreters still provide isolation (separate module namespaces, type objects, and memory allocator state), but the parallelism they offer is no longer distinct from what plain threads provide. In the free-threaded build, subinterpreters become a tool for isolation rather than a tool for parallelism. Their practical advantages over threads shrink considerably.

## `concurrent.futures`

A high-level interface over threads and processes. `ThreadPoolExecutor` backs tasks with threads; `ProcessPoolExecutor` backs them with processes. The same `submit`/`map` API works for both, and it integrates with `asyncio` via `loop.run_in_executor()`.

**Strengths:**
- Simple API for embarrassingly parallel tasks
- Easy to switch between thread and process backends
- Handles pool lifecycle, exception propagation, and result collection

**Weaknesses:**
- Inherits all the limitations of the underlying backend
- Less control than using threads or processes directly

**Use when:** You have a collection of independent tasks and want a clean API without managing pools manually. This is the right default for most fan-out-and-collect patterns.

```python
from concurrent.futures import ProcessPoolExecutor

with ProcessPoolExecutor() as ex:
    results = list(ex.map(crunch, data_chunks))
```

**GIL vs. no-GIL**

`ProcessPoolExecutor` is unaffected; it already isolates work in separate processes.

`ThreadPoolExecutor` changes significantly. With the GIL, it provides I/O concurrency but no CPU parallelism. Without the GIL, it provides both. This also applies to `loop.run_in_executor()` in async code: offloading a CPU-bound call to a `ThreadPoolExecutor` actually runs in parallel with the event loop in the free-threaded build, whereas it would stall it in the GIL build.

| Executor | With GIL | Without GIL |
|---|---|---|
| `ThreadPoolExecutor` | I/O parallel only | I/O and CPU parallel |
| `ProcessPoolExecutor` | I/O and CPU parallel | I/O and CPU parallel (unchanged) |

## Decision Guide

```
Is your bottleneck I/O (network, disk, database)?
├── Can you use async libraries throughout?
│   └── Yes → async/await
└── No (blocking libraries, legacy code)
    ├── GIL build → threading or ThreadPoolExecutor
    └── No-GIL build → same, and blocking calls in executors no longer stall event loops

Is your bottleneck CPU?
├── Need it to work today on any Python build?
│   └── multiprocessing / ProcessPoolExecutor
├── Willing to use the free-threaded build and audit shared state?
│   └── threading or ThreadPoolExecutor (no-GIL build)
└── Need isolation stronger than threads, lighter than processes?
    └── Subinterpreters (experimental; check library compatibility first)

Tasks share data heavily?
└── Contention limits gains regardless of strategy; reconsider the design
```

## What the GIL Was Actually Solving

All of these strategies exist partly because of what the GIL was doing quietly:

- Thread-safe reference counting
- Mutual exclusion across interpreter internals
- Accidental safety for user code that never considered concurrency

Free-threading replaces the first two with atomic operations and finer-grained internal locks.
The third item becomes the programmer's responsibility.
The other strategies (async, multiprocessing, subinterpreters) sidestep the problem entirely
by limiting or eliminating shared mutable state between concurrent units.

The cleaner the data boundaries between concurrent units, the easier the code is to reason about,
regardless of which strategy or Python build you choose.
