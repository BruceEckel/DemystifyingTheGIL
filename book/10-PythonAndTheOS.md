# Appendix: Python and the OS

Python threads, the GIL, and free-threading all sit on top of the
operating system's process and thread model. This appendix collects
the OS-level facts that affect how Python concurrency actually
behaves, including a few questions the rest of the book skips over.

## Python Threads Are OS Threads

`threading.Thread` is not a Python abstraction with a separate
scheduler. It is a thin wrapper over the platform's native thread
API: `pthread_create` on Linux and macOS, `_beginthreadex` on
Windows. Every `Thread` you create produces a real OS thread, owned
and scheduled by the kernel, with its own stack and its own entry in
the kernel's run queue.

The OS does not know or care about the GIL. It sees a process with
N threads and schedules them according to its own policies. Whether
those threads can run Python bytecode in parallel is a separate
question, determined by the interpreter rather than the kernel.

Under the standard GIL build, all N OS threads exist but only one
can hold the GIL at a time, so only one runs Python bytecode at
once. The OS may still preempt the thread that holds the GIL, and
on a multicore machine the other threads can still be running C
code outside the interpreter (a NumPy operation, a blocking I/O
call, an extension that released the GIL). The model is "N OS
threads, one bytecode runner."

Under the free-threaded build the GIL is gone. The same N OS
threads now run Python bytecode simultaneously on different cores.
Same threads, same OS scheduler, different gating.

What is *not* an OS thread:

- **Coroutines** (`async def` / `await`). All multiplexed onto a
  single OS thread by the asyncio event loop. The kernel sees one
  thread; the loop sees thousands of coroutines.
- **Green threads** (gevent, eventlet). User-space schedulers built
  on coroutines or stack-switching. Same single-OS-thread picture.
- **Subinterpreters** (PEP 684, 734). Distinct Python interpreter
  contexts inside one process. Each one runs on an OS thread, but
  they have separate `sys.modules` and separate object worlds.
- **Processes** (`multiprocessing`). Separate OS *processes*, each
  with its own OS threads and its own Python interpreter.

A `threading.Thread` from CPython is the same kind of OS-level
object as a `pthread_t` from C. The difference is purely in what
Python does on top of it.

## The Main Thread

A process always has a primary thread, the one that exists when the
process starts. In Python this is the thread that imports the
script and runs the top-level module code. `threading.main_thread()`
returns it, and `threading.current_thread() is threading.main_thread()`
is the usual check.

The main thread is not a GIL concept. The GIL did not create it,
and removing the GIL does not remove it. It is a property of the OS
process model and of CPython's startup and shutdown sequence. Its
privileges all come from outside the GIL:

- **Signal handlers run only on the main thread.** This is a POSIX
  rule: signals are delivered to the main thread by the kernel.
  Python therefore queues signal handler invocations and runs them
  the next time the main thread is at a safe point. No other thread
  ever sees a signal directly.
- **`atexit` handlers run on the main thread** when it exits.
- **Interpreter lifecycle.** When the main thread returns from its
  top-level code, CPython calls `Py_Finalize`, which tears down the
  interpreter. Other threads still alive at that point are either
  joined (non-daemon) or abruptly stopped (daemon). The interpreter
  does not stay up just because other threads are running unless
  they are non-daemon and the main thread explicitly waits on them.
- **GUI toolkits.** Tkinter, Cocoa via PyObjC, and Qt under certain
  configurations all require their event loop on the main thread.
  This is not a Python rule; the OS-level windowing systems require
  it. Python's threading model has no choice in the matter.
- **Some debug hooks.** `sys.settrace` semantics around the main
  thread, and `signal` module interactions, continue to treat the
  main thread specially.

The shift from GIL to free-threading does not change any of this.
Under FT, the main thread is just one of several threads that can
run bytecode in parallel, but it remains the only one allowed to
handle signals or to drive a GUI event loop.

## How Blocking Calls Release the GIL

The original 1992 motivation for Python threads was I/O concurrency:
let one thread block on `read()` while another keeps doing work.
This works under the GIL because the convention in the C API is
that blocking calls release the GIL before they block and
re-acquire it afterward.

The pattern in extension code:

```c
Py_BEGIN_ALLOW_THREADS
// blocking syscall, e.g. read(), select(), poll(), recv()
Py_END_ALLOW_THREADS
```

`Py_BEGIN_ALLOW_THREADS` releases the GIL, so other Python threads
can run while this one waits in the kernel. `Py_END_ALLOW_THREADS`
re-acquires it before the function returns to Python code.

Every stdlib I/O call follows this convention. `time.sleep`,
`socket.recv`, `subprocess.Popen.wait`, file I/O on regular file
handles: all release the GIL around their blocking points. This is
why Python can do meaningful I/O concurrency despite the GIL: the
GIL is released exactly when it would otherwise stall progress.

Under free-threading the dance is unnecessary for parallelism (all
threads can run bytecode simultaneously anyway), but the macros
still exist. Extension code shouldn't run for long stretches
without yielding, and existing extensions that wrap blocking calls
should continue to work without modification.

## Memory and Stack

A process has one address space. Every thread in the process sees
the same heap, the same globals, the same loaded modules. This is
what makes threads attractive (shared data with no inter-process
communication) and what makes them dangerous (any thread can
overwrite any other thread's data).

Each thread has its own stack. Default stack size is platform
dependent:

- Linux: 8 MB by default, configurable per thread.
- macOS: 8 MB for the main thread, 512 KB for others by default.
- Windows: 1 MB by default.

Python's `threading.stack_size()` lets you change the size for new
threads. The default usually fits Python recursion plus a generous
margin, but deep recursion can blow the stack faster on platforms
with smaller defaults.

Practical consequence: creating thousands of threads is expensive
in address space and kernel memory, not just in CPU time. This is
one of the reasons asyncio is preferred for very high concurrency
counts (tens of thousands of connections): coroutines share one
thread's stack via continuations, with no per-coroutine OS cost.

## Thread-Local Storage

`threading.local()` provides per-thread storage. Attributes set on
a `threading.local()` instance from one thread are invisible to
other threads. This works under both the GIL and free-threading
because the implementation uses a per-thread dictionary keyed on
the thread's identity.

Useful for thread-bound resources: database connections held by a
worker thread, request context in a server, scratch buffers reused
across calls in the same thread. The pattern lets you avoid locks
entirely for state that doesn't need to be shared.

## Thread Scheduling

The OS scheduler is preemptive: it can interrupt any thread at any
instruction boundary and run a different thread, on the same core
or a different one. Python has no say in this. The GIL changed
*which* thread could run Python bytecode at a given moment; it did
not change *whether* threads were preemptively scheduled.

A few related details:

- **CPU affinity** (`sched_setaffinity` on Linux,
  `SetThreadAffinityMask` on Windows) can pin a thread to specific
  cores. `os.sched_setaffinity` exists on Linux; `psutil` exposes
  it portably.
- **Thread priority.** Nice values on Unix, priority classes on
  Windows. The stdlib does not expose a portable way to change
  thread priority.
- **The check interval** (`sys.setswitchinterval`) controls how
  often the interpreter yields the GIL, not how often the OS
  schedules. Under FT this setting still exists (it affects
  cooperative yield points in some interpreter paths) but matters
  much less, because threads no longer queue on a single lock.

## Process Model: fork, spawn, forkserver

The `multiprocessing` module exposes three start methods:

- **`fork`** (Linux default until 3.14): clone the current process,
  including all of its memory. Fast and avoids re-import, but
  unsafe in the presence of threads. A thread holding a lock in the
  parent leaves that lock held in the child, and other threads
  simply vanish. Many libraries, including some C extensions,
  cannot survive a `fork` from a multi-threaded program.
- **`spawn`** (default on Windows and macOS, and on Linux from 3.14):
  start a fresh Python process and re-import everything. Slower
  but safe with threads. The child does not inherit file
  descriptors or state implicitly.
- **`forkserver`** (Linux and macOS): a single-threaded helper
  process forks workers on demand. Combines `fork`'s speed with
  thread safety, at the cost of more complex setup.

The interaction with Python's GIL is indirect: under both GIL and
FT builds, each process gets its own interpreter and its own GIL
state (or absence thereof). `multiprocessing` was originally a way
to get multi-core CPU parallelism around the GIL. With FT, threads
can do that too, and the choice between processes and threads is
now governed by whether you need isolation (processes) or shared
memory (threads).

## Subinterpreters: An Orthogonal Direction

PEP 684 (3.12) and PEP 734 (3.14) introduced per-interpreter GIL
and a `concurrent.interpreters` stdlib module. A subinterpreter is
a Python interpreter instance running inside one OS process. Each
subinterpreter has its own `sys.modules`, its own type objects, its
own GIL (in the standard build) or its own runtime state (in the FT
build), and communicates with other subinterpreters only through
explicit channels.

From the OS's perspective, a subinterpreter is still hosted by an
OS thread. From Python's perspective, the subinterpreter is a
separate world that cannot reach into other subinterpreters' state.

Subinterpreters and free-threading solve different problems.
Free-threading lets shared-memory threads run Python in parallel.
Subinterpreters provide isolation between concurrent Python
contexts in one process, closer to Erlang processes than to
traditional threads. Both can coexist: the FT build supports
subinterpreters, and a subinterpreter under FT can spawn threads
that run its code in parallel.

## Summary

- A Python thread is an OS thread. The GIL was a property of the
  interpreter that ran on top, not of the thread object itself.
- The main thread is an OS and interpreter concept, not a GIL
  concept. It retains its signal-handling, lifecycle, and
  GUI-driving privileges under both GIL and FT builds.
- Blocking C calls release the GIL by convention, which is why
  threads have always provided real I/O concurrency.
- Each thread has its own stack but shares the process's address
  space. This is what makes shared-memory races possible at all.
- Free-threading removes the GIL but does not change the OS
  process model, the main-thread concept, or any of the
  conventions built on top.
- Subinterpreters are an orthogonal path that gives isolation
  rather than shared-memory parallelism.

The recurring theme: free-threading is a change to the Python
interpreter, not to the operating system underneath. Everything
the OS does (scheduling, signals, memory layout, process model)
keeps doing what it always did. The only thing that changes is
which thread is allowed to run Python bytecode when.
