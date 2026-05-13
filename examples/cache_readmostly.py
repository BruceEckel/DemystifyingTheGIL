# cache_readmostly.py
"""
Read-mostly shared state: many readers, rare writers. The cache is
queried on every iteration; the writer thread occasionally refreshes
an entry. Readers never lock.

Caching exists to avoid recomputing expensive work, so each lookup is
followed by real per-item work that uses the cached value. Under
free-threading this work runs in parallel across cores; the dict
itself is safe for concurrent reads.

A `threading.Lock` still guards writes, since two writers updating the
same key concurrently could leave the dict in a torn state.
"""

import random
import threading
from concurrent.futures import ThreadPoolExecutor

import constants as c
from utils import Timer

TABLE_SIZE = 10_000
LOOKUPS = 20_000
WRITES = 100
WORK_PER_LOOKUP = 250  # iterations of per-item work after each read

cache: dict[int, int] = {i: i * i for i in range(TABLE_SIZE)}
writer_lock = threading.Lock()


def reader() -> int:
    total = 0
    for i in range(LOOKUPS):
        v = cache[i % TABLE_SIZE]
        for _ in range(WORK_PER_LOOKUP):
            v = (v * 1103515245 + 12345) & 0x7FFFFFFF
        total += v
    return total


def writer() -> None:
    rng = random.Random()
    for _ in range(WRITES):
        key = rng.randrange(TABLE_SIZE)
        with writer_lock:
            cache[key] = key * key  # idempotent refresh


num_readers = max(1, c.NUM_THREADS - 1)

with Timer() as t, ThreadPoolExecutor(max_workers=c.NUM_THREADS) as pool:
    reads = [pool.submit(reader) for _ in range(num_readers)]
    pool.submit(writer)
    totals = [f.result() for f in reads]

print(f"readers={num_readers}  ({t.elapsed:.2f}s)")
