# Introduction: Why are we doing this?

Speed. Only start messing with this if things aren't running fast enough.

The complexity jump is big: all of a sudden you must think about things you've previously been able to ignore.
If your system is already fast enough, don't wade into this.

If it's not fast enough, first consider simpler alternatives (use Occam's razor):

- **Profile your system and identify bottleneck functions**. Convert these into Rust modules via PyO3; using AI this is now surprisingly straightforward and reliable. It sidesteps the whole question rather than working around it.

- **NumPy / SciPy / array-oriented libraries**.
  If your CPU bottleneck is numeric work, the answer is often "stop looping in Python." NumPy operations drop into
  C/Fortran, release the GIL, and are already parallelized internally (via BLAS, LAPACK, etc.). No threading required.

- **Dask / Ray / joblib**.
  Distributed task schedulers handle parallelism above the process level. Dask in particular integrates with
  NumPy/Pandas idioms. Good when the dataset or compute exceeds a single machine.

- **GPU compute (CuPy, PyTorch, JAX)**.
  For the right workloads (dense numeric, ML), the GPU has thousands of cores and bypasses the GIL entirely. Not
  universally applicable, but when it fits, nothing else competes.

- **mmap + worker processes reading shared data**.
  For the large-dataset-in-memory problem: memory-map a file and let multiple processes read it without copying. The OS
  handles sharing at the page level.

Any form of concurrency is not simple, and opens a Pandora's Box of issues you must understand intimately.

## Workload Categories

-  **CPU-bound, independent tasks (embarrassingly parallel)**.
  No shared data between tasks. Each unit of work is self-contained. Examples: image resizing, password hashing,
  compression, rendering frames. Best fit: multiprocessing, free-threaded threads, Rust extensions.

-  **CPU-bound, shared large dataset**.
  All workers need read access to the same large data structure simultaneously. Copying it per-process is impractical.
  Examples: ML inference, search index queries, large matrix operations. Best fit: NumPy/GPU (vectorized, avoids the
  problem), shared memory, or free-threaded threads (one copy in memory).

-  **CPU-bound, shared mutable state**.
  Workers both read and write common state. The hardest category. Examples: simulation with interacting agents, graph
  algorithms. Best fit: careful free-threaded threading with fine-grained locks, or redesign to reduce sharing.

-  **I/O-bound, many concurrent connections**.
  Waiting dominates. The bottleneck is latency, not compute. Examples: web scraping, API clients, WebSocket servers,
  database query fans. Best fit: async/await.

-  **I/O-bound, blocking libraries**.
  Same waiting problem but you can't go async because the library doesn't support it. Examples: legacy database drivers,
   synchronous SDKs. Best fit: threading (GIL build is fine; no-GIL makes thread executors more powerful).

-  **Pipeline / producer-consumer**.
  Data flows through stages with different bottlenecks at each stage. One stage might be I/O-bound, the next CPU-bound.
  Examples: media transcoding, event processing. Best fit: queues connecting threads or processes, or async with
  executor offload for CPU stages.

- **Extract, Transform, Load (ETL)**. A data pipeline pattern:
  - Extract: pull data from a source (database, API, files, streams)
  - Transform: clean, reshape, or compute on it (filter rows, join tables, aggregate, normalize)
  - Load: write the result to a destination (data warehouse, another database, files)

  Classic example: nightly job that pulls sales records from a transactional database, calculates daily summaries, and
  writes them to a reporting database.

  It naturally fits the pipeline/producer-consumer category because each stage has a different bottleneck: Extract is
  I/O-bound, Transform is often CPU-bound, Load is I/O-bound again.

-  **Background / fire-and-forget**.
  Work that must not block the main thread but doesn't need to return a result quickly. Examples: sending emails,
  logging to a remote service, cache warming. Best fit: threading or async tasks; multiprocessing if isolation matters.

-  **Latency-sensitive / event-driven**.
  Must respond to external events within a deadline. Examples: trading systems, game servers, UI event loops. Best fit:
  async/await (predictable yield points), or carefully tuned threading.

-  **Distributed / beyond one machine**.
  The problem is too large for one process or one machine. Examples: batch ML training, large-scale web crawling. Best
  fit: Dask, Ray, Celery; the GIL is irrelevant at this level.

The GIL matters most for the first three categories. For everything I/O-bound, it is not the bottleneck.

## Concurrency Problems

Broadly, concurrency problems fall into these categories:

- **Race conditions**.
  Two or more threads read and write shared state without coordination. The result depends on timing.

- **Atomicity violations**.
  A sequence of operations that must happen as a unit gets interrupted mid-way. stats_race.py is a good example: count
  and total are updated on separate lines, so a thread can observe them in an inconsistent intermediate state.

- **Order violations**.
  Code assumes operations happen in a specific order across threads, but nothing enforces that order. Thread A assumes
  Thread B has finished initialization before using the result; sometimes it has, sometimes it hasn't.

- **Deadlock**.
  Two threads each hold a lock the other needs. Both wait forever. Classic with two locks acquired in opposite order.

- **Livelock**.
  Threads keep responding to each other but make no progress. Neither is blocked, but neither advances. Less common in
  Python but possible with complex retry logic.

- **Starvation**.
  One thread never gets scheduled or never acquires a lock because others keep taking priority. Can happen with unfair
  lock implementations or heavy contention.

- **Memory visibility**.
  On hardware with weak memory models, one thread's writes may not be visible to another thread without a memory
  barrier. Python largely hides this, but C extensions that bypass the object model can encounter it.

- **Convoying**.
  A slow thread holds a lock and forces all other threads to queue behind it, serializing what should be parallel work.
  A subtle performance problem rather than a correctness problem.
