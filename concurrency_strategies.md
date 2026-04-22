# Concurrency Strategies

The main division between concurrency models is whether concurrent
units share memory or stay isolated.

**Shared memory.** All units see the same data structures. Communication
is as cheap as reading a pointer. A thread can hand a 10 GB dataset to
another thread by passing its address, zero copying. This is why
scientific computing, game engines, and databases live here: the working
set often doesn't fit anywhere else, and the cost of duplicating it is
prohibitive.

The price: any mutation someone else can observe is a hazard. Reads that
look simple (`total += 1`) are read-modify-write sequences, and a
concurrent writer breaks them. Most bugs in shared-memory code come from
the gap between "this line looks atomic" and "this line is actually
atomic."

**Isolated memory.** Each unit has private state, and communication
crosses a boundary (a channel, a message queue, a socket). Whole
categories of bugs vanish because there is nothing to race on. But every
piece of shared data now has to be copied or serialized, which makes
communication expensive and caps the size of datasets you can move around
cheaply.

Most real systems pick a point on this axis, or mix both: shared memory
inside a process, message passing across processes or machines.

## Strategies for Shared Memory

### Locks (mutexes, semaphores)

The oldest answer: wrap any shared mutation in a mutex. Whoever holds the
lock has exclusive access.

**Apply when:** critical sections are short, contention is low, and the
data being protected fits naturally behind one lock.

**Struggles when:** you need multiple locks (deadlock risk), locks are
held across slow operations (convoying), or the critical section is large
enough that serializing it erases the parallelism gain.

Nearly every mainstream language provides them. They are flexible but
error-prone. The programmer is responsible for knowing what each lock
protects, in what order to acquire multiple locks, and when a lock should
be released.

### Atomic operations and lock-free data structures

Use hardware primitives (compare-and-swap, atomic increment,
fetch-and-add) to build data structures that don't need locks. A
lock-free queue lets producers and consumers make progress simultaneously
without blocking each other.

**Apply when:** a specific data structure is a contention hotspot, and a
specialist can invest in a careful lock-free implementation.

**Struggles when:** you need to compose multiple operations atomically.
Lock-free algorithms protect individual operations, not sequences of
them. The code is also notoriously hard to get right; memory-ordering
bugs manifest only on certain CPUs and only under specific interleavings.

Used in kernel data structures, high-performance databases, and language
runtimes (allocators, garbage collectors). Almost never written by
application programmers.

### Software Transactional Memory (STM)

Instead of locking, mark a block of code as a transaction. The runtime
records every read and write, and commits the transaction only if no
concurrent transaction touched the same data. If a conflict is detected,
the transaction is rolled back and retried.

**Apply when:** you want *composable* atomicity.
`atomically { account.withdraw(100); other.deposit(100) }` is a single
unit; two of them running concurrently will not interleave, even though
neither knew about the other. Locks do not compose this way. Writing two
correctly-locked functions and calling them in sequence does not give you
a correctly-locked sequence.

**Struggles when:** transactions have side effects that can't be rolled
back (I/O, network calls, printing). The runtime also pays a read/write
tracking cost, which makes STM slower than well-tuned locks for
uncontended workloads.

Haskell and Clojure have production-quality STM. Java, Scala, and others
have library implementations with caveats. STM has not displaced locks in
mainstream use, partly because integrating with the rest of the ecosystem
(which does do I/O) is awkward.

### Immutability and persistent data structures

Sidestep the problem: if data never changes, concurrent readers can't
conflict with writers, because there are no writers. Updates produce a
new version of the structure that shares unchanged parts with the old one
(a *persistent* data structure).

**Apply when:** the programming model fits, especially for
functional-leaning code. Readers never need synchronization. Time-travel,
undo, snapshotting, and versioning all become natural.

**Struggles when:** you need high write throughput to a single structure
(each update allocates), or the mutation pattern doesn't decompose into
functional updates (e.g., fine-grained in-place edits to a large
numerical matrix).

Clojure's core collections, Scala's immutable data, Rust's ownership
model with shared-borrow references, and functional languages broadly.
Often combined with one of the other strategies (e.g., STM over immutable
values) to cover the mutation case.

## Strategies for Isolated Memory

### Actors

Each unit of work (an actor) has private state and communicates only via
messages sent to other actors' inboxes. An actor processes messages one
at a time, so its internal state is single-threaded by construction.

**Apply when:** the problem decomposes naturally into independent
entities with their own lifecycles (telecom switches, chat systems, game
entities, distributed supervisors). Failure isolation is excellent: a
crashed actor doesn't corrupt others, and supervision trees can restart
them automatically.

**Struggles when:** actors need to reach consensus across many
participants, or when request-reply patterns dominate (you end up
serializing logic that would be trivial with a direct call). Debugging is
also harder because control flow is distributed across message traces
rather than visible in one call stack.

Erlang built an industry on this (Ericsson's telecom switches).
Elixir carries that model forward on the BEAM
runtime. Akka brought it to the JVM.

### CSP (Communicating Sequential Processes)

CSP is a *communication discipline*, not a memory model. All the units of
work live in one process and one address space. They could touch each
other's memory; the rule is that they don't. Instead, they exchange
values through named channels, and the language's runtime provides cheap
lightweight units (goroutines, coroutines, fibers) that the scheduler
multiplexes onto a handful of OS threads.

Channels are first-class values. Multiple senders can write to one
channel; multiple receivers can read from it. Sends and receives take
nanoseconds, because a channel is just an in-memory queue with some
synchronization around it. No kernel involvement, no serialization.

Rob Pike's slogan for Go captures the stance: "Don't communicate by
sharing memory; share memory by communicating." The memory is shared
(that's why passing a pointer through a channel is instant); the
*communication* is what's disciplined.

**Apply when:** you want concurrency that reads like a sequential
program, inside one process. Each goroutine looks like a little `main`
function, and the channel declarations make the communication topology
explicit in the source. Back-pressure falls out naturally: a full
buffered channel blocks the sender until a receiver catches up.

This is also the model most loved by programmers for its cognitive
economy. Because the idiom is "data flows through channels," most
shared-state bugs simply never get written. The cost of a channel send is
low enough that you don't hesitate to use one.

**Struggles when:** the coordination is request-reply with many-to-many
fan-out, or when the isolation guarantee actually matters. CSP's
isolation is by convention only. A goroutine that ignores the discipline
and pokes a shared variable gets the same races as any other threaded
code. The runtime will not catch it, and a crash in one goroutine takes
the whole process down.

Go is the mainstream example. Occam built the original version in the
1980s for the Transputer hardware. Clojure's `core.async` is a library
implementation on the JVM.

### Isolated processes with IPC

IPC is *physical* isolation. Each process has its own address space, its
own heap, its own file descriptors. The OS and the MMU enforce this: one
process literally cannot read another's memory without an explicit,
mapped-in shared segment. A segfault, a null-pointer dereference, or an
abort in one process affects only that process. The others keep running.

Communication crosses the kernel: pipes, sockets, message queues,
explicit shared memory segments. Every message involves a syscall, a
context switch, and usually serialization into bytes (since native
pointers don't mean anything in another address space). The overhead is
microseconds to milliseconds per message, orders of magnitude more than
a CSP channel send. Data has to be copied or serialized; you cannot just
pass a pointer. This is the price of the hard isolation guarantee.

**Apply when:** isolation is the point. A crash in one worker must not
affect the others. Workers may be in different languages or different
versions of the same language. Security boundaries need to be real
(sandboxing, privilege separation). Workloads span multiple machines
(sockets generalize to TCP; processes generalize to hosts).

**Struggles when:** communication is frequent or data is large. Every
message crosses a kernel boundary and carries serialization cost.
Duplicating a large dataset across N workers costs N times the RAM,
unless you opt into explicit shared memory, which gives back the
isolation you just paid for.

IPC is seen everywhere at the OS level. Unix pipelines. Web servers spawning worker
processes. Database systems with separate query processes. Python's
`multiprocessing`. MPI for scientific computing across cluster nodes.

### CSP vs. IPC in one line

CSP is "threads that agree not to share"; IPC is "processes that
*cannot* share without asking the OS." The first is cheap and
conventional; the second is expensive and enforced. They are aimed at
different problems and often appear in the same system at different
layers.

## Strategies That Change What "Concurrent" Means

### Cooperative scheduling (event loops, coroutines, async/await)

Don't actually run things in parallel. Run them one at a time on a single
thread, but switch between them at well-defined yield points.

**Apply when:** the bottleneck is the fact that you're waiting on something (network, disk, user input),
rather than computing something. Tens of thousands of concurrent connections can share
one thread because most are idle most of the time. There are no race conditions on
shared state between yield points, because there are no preemptive
switches. Control flow is visible in the source because yields are
explicit (`await`, `yield`, channel operations).

**Struggles when:** any task is CPU-bound. A coroutine that doesn't yield
starves every other coroutine on the loop. Integrating with blocking
libraries requires offloading to a thread pool, which brings shared
memory back into the picture.

JavaScript lives here by construction. Python's `asyncio`, C#'s
`async/await`, Rust's async ecosystem, Kotlin's coroutines. Arguably the
most successful concurrency model of the last fifteen years, because
I/O-heavy workloads are extremely common and this model fits them
precisely.

### Data parallelism (SIMD, GPU, vectorized operations)

Apply the same operation to many data elements at once. The hardware
exposes wide vector registers (SIMD) or thousands of simple cores (GPU),
and code expresses work as "do this to every element" rather than "loop
over elements."

**Apply when:** the same operation applies uniformly to large arrays
(image filtering, matrix multiplication, neural network layers, physics
simulations). Hardware speedups are enormous: 10-100x on CPU SIMD,
100-1000x on GPU.

**Struggles when:** the work is branchy, data-dependent, or irregular. A
GPU executing "different things on different elements" spends most of its
time idle, because the hardware is lockstep by design. Memory transfer to
and from the GPU also caps throughput for anything short-lived.

NumPy, SciPy, TensorFlow, PyTorch, CUDA, OpenCL, SIMD intrinsics,
auto-vectorizing compilers. The foundation of modern numerical computing.

### Fork/join and task parallelism

Decompose a problem into tasks. A scheduler picks tasks off a pool and
runs them on worker threads. Tasks can spawn subtasks and wait for their
results. The scheduler handles load balancing via work stealing.

**Apply when:** the problem has recursive structure (divide-and-conquer
sorts, tree traversals, parallel search) and tasks are CPU-bound but
unpredictable in duration. The runtime handles balancing without the
programmer specifying it.

**Struggles when:** tasks have side effects on shared state (back to
locks), or when fine-grained tasks have overhead that swamps their actual
work.

Cilk was the research system. Java's Fork/Join framework, .NET's TPL,
Intel TBB, and OpenMP tasks brought it to production. Rust's Rayon is a
modern library version.

### MapReduce and dataflow

Structure the computation as a graph of operations on datasets, and let a
framework schedule it across many machines. Map, filter, and reduce
primitives compose into pipelines; the framework handles partitioning,
shuffling, and failure recovery.

**Apply when:** data doesn't fit on one machine, computation is
embarrassingly parallel over partitions, and the framework's assumptions
match yours (batch, high throughput, tolerant of restart).

**Struggles when:** you need low latency or tight coordination between
workers. MapReduce-style frameworks are built for throughput, not
interactive queries.

Examples include Hadoop, Spark, Flink, Dask, and Ray.

## Cross-Cutting Observations

### The RAM argument for shared memory

The strongest argument for shared-memory concurrency is that modern
machines have enough memory that many real datasets can fit in one process.
A single server with 512 GB of RAM can hold most datasets an organization
cares about, and accessing that data from multiple threads costs a
pointer dereference. The moment you split into isolated processes, the
same data has to be duplicated across processes (multiplying memory cost)
or accessed through a communication mechanism (adding latency on every
access). For problems dominated by data access rather than communication,
shared memory wins by orders of magnitude.

This is why the GIL has been such a persistent pain point for numeric and
scientific Python: the workloads *want* shared memory, the hardware
supports it, the data is already sitting in one address space, and the
language was blocking threads from using it in parallel.

### The correctness argument for isolation

Conversely, the strongest argument for isolation is that most concurrency
bugs come from unintended sharing, and eliminating shared mutable state
eliminates the bugs at the source. A team that can't find its race
conditions doesn't benefit from having twice the hardware parallelism; it
just produces incorrect results twice as fast. CSP and actors put a
non-trivial cost on communication precisely to force the programmer to be
explicit about what crosses between units. The runtime cost of sending a
message buys back engineering time spent hunting for races.

### Preemptive vs. cooperative

A second axis cuts across the first: does the scheduler preempt units at
arbitrary points, or do units yield control voluntarily?

- **Preemptive** (OS threads, free-threaded Python threads): the
  scheduler can switch at almost any instruction. It's easy to write code that
  blocks one unit without blocking others. But it's hard to reason about
  interleavings, because they can happen anywhere.
- **Cooperative** (event loops, coroutines, Go's scheduler at channel
  ops): switches happen only at named points. It's easy to reason about
  interleavings. But a misbehaving unit can block everything by refusing to
  yield.

The trade-off is symmetric: preemption gives robustness against
uncooperative code at the cost of reasoning difficulty; cooperation gives
reasoning simplicity at the cost of requiring every participant to yield.

### Why real systems mix models

No model wins on every axis, so real systems stack them. A typical web
backend:

- **Across machines:** isolated processes communicating over TCP.
- **Within a machine:** an event loop per process handling many
  connections.
- **For CPU-heavy work inside a request:** thread pool with shared
  memory.
- **For data-parallel work inside those threads:** SIMD, or offload to a
  GPU.

This is not a failure of any one model; it is how you exploit different
levels of the hardware. The GPU wants data parallelism. The thread wants
shared memory. The process wants isolation. The network wants messages.
Picking one strategy for the whole stack means losing orders of magnitude
at some level.

## Summary Table

| Model | Sharing | Scheduling | Best at | Worst at |
|---|---|---|---|---|
| Locks | Shared | Preemptive | General-purpose mutation | Composition; deadlock |
| Atomics / lock-free | Shared | Preemptive | Hotspot data structures | Correctness under review |
| STM | Shared (logical) | Preemptive | Composable atomicity | I/O inside transactions |
| Immutability | Shared (safe) | Any | Read-heavy, snapshot-friendly | In-place mutation |
| Actors | Isolated | Preemptive per actor | Independent entities, fault isolation | Consensus, RPC-heavy flows |
| CSP | Isolated | Preemptive | In-process coordination, pipelines | Distributed consensus |
| Isolated processes | Isolated | Preemptive | Crash isolation, polyglot systems | Large shared datasets |
| Event loop / async | Shared (one thread) | Cooperative | Many concurrent I/O waits | CPU-bound work |
| Data parallel / SIMD / GPU | Specialized | Lockstep | Uniform ops over big arrays | Branchy, irregular work |
| Fork/join | Shared | Preemptive + work stealing | Divide-and-conquer, recursive | Side effects on shared state |
| MapReduce / dataflow | Isolated partitions | Batch | Data that doesn't fit on one machine | Low-latency, interactive |

The right strategy is whichever one matches the shape of the work, the
shape of the data, and the budget for debugging. This is the design challenge, and most non-trivial systems
mix several strategies.
