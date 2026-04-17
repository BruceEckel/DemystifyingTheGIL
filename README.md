# Demystifying The GIL

PyCon 2026 Presentation

## Setup

Install dependencies and ensure both Python builds are available:

```
uv sync
```

The examples require standard Python 3.14 (with GIL) and the free-threaded
build (3.14t, no GIL). Run `uv python list` to confirm both are installed.

## Step 1: A function that looks completely safe

Start with `surprise.py`. It defines a pure function with no shared state
and no side effects:

```python
def increment(x):
    return x + 1
```

Nothing about this function looks dangerous. It takes a value, adds one,
returns the result. No globals, no mutation.

The script runs three scenarios and compares the result to the expected value
of 800,000 (8 threads, 100,000 iterations each):

- **sequential:** one thread, no concurrency
- **threaded:** 8 threads, normal GIL switch interval (5ms)
- **fast switch:** 8 threads, switch interval forced to 0.0000001s

## Step 2: Run with the GIL

```
uv run --python 3.14+gil surprise.py
```

Expected output:

```
Python 3.14: Standard GIL
  sequential      800,000   OK
  threaded        800,000   OK
  fast switch     241,037   WRONG  (lost 558,963)
```

Sequential is always correct. Threaded with the normal switch interval is also
correct, which may give you false confidence. The fast switch row reveals the
truth: the race exists, the GIL just makes it rare under normal conditions.

Why? `counter = increment(counter)` compiles to three steps:

1. Read `counter`
2. Call `increment` (a GIL check point in Python 3.11+)
3. Write the result back

The GIL can release at step 2. If another thread runs between steps 1 and 3,
both threads read the same value and one increment is lost. Under the default
5ms switch interval this rarely happens. Forcing a much shorter interval makes
it happen on almost every iteration.

## Step 3: Run without the GIL

```
uv run --python 3.14t surprise.py
```

Expected output:

```
Python 3.14t: No GIL
  sequential      800,000   OK
  threaded        302,815   WRONG  (lost 497,185)
  fast switch     198,403   WRONG  (lost 601,597)
```

Sequential is still correct. But now both threaded rows are wrong, and neither
requires the forced switch interval to fail. With no GIL, all 8 threads run
simultaneously and the race is continuous.

The surprise: `increment(x)` is genuinely safe. The problem is the pattern
`counter = increment(counter)`, which reads and writes shared state with a
function call in between. The GIL was silently protecting that pattern all along.

## Step 4: Fix it with a lock

`no_surprise.py` adds a `threading.Lock()` around the read-modify-write
sequence:

```python
lock = threading.Lock()

def worker():
    global counter
    for _ in range(ITERATIONS):
        with lock:
            counter = increment(counter)
```

The lock must cover all three steps together. Locking only the call to
`increment()` would do nothing, because the function itself was never the
problem.

## Step 5: Run the fixed version with the GIL

```
uv run --python 3.14+gil no_surprise.py
```

Expected output:

```
Python 3.14: Standard GIL
  sequential      800,000   OK
  threaded        800,000   OK
  fast switch     800,000   OK
```

All three rows are correct, including fast switch. The lock works.

## Step 6: Run the fixed version without the GIL

```
uv run --python 3.14t no_surprise.py
```

Expected output:

```
Python 3.14t: No GIL
  sequential      800,000   OK
  threaded        800,000   OK
  fast switch     800,000   OK
```

Correct again. But notice that the free-threaded run is visibly slower than
the GIL version.

With the GIL, threads do not run in parallel, so the lock is rarely contested
and cheap to acquire. With free-threading, all 8 threads run simultaneously
on separate cores and compete for the same lock on every iteration. The lock
and counter bounce between CPU cache lines as ownership transfers, and the OS
wakes and sleeps threads constantly. Our explicit lock re-serializes the threads 
by design, so you get the overhead of true parallelism with none of the benefit.

The deeper lesson is that free-threading does not automatically make code
faster. When all threads share one resource and contend on every operation,
a lock can make free-threaded code slower than the GIL. The performance
benefit of free-threading only appears when threads work on independent data
and rarely contend.
