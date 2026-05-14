# counter_coarse.py
"""
Coarse-grained locking: each thread does independent CPU work in
batches and only briefly takes the lock to publish the batch total.
The lock protects the shared counter but not the work, so threads
run in parallel between acquisitions.

Compare with:
    the_camels_nose.py  -- one acquisition per increment: lock cost dominates
    counter_sharded.py  -- no lock at all (one merge at the end): fastest
"""

import threading

from utils import run_in_threads

ITERATIONS = 100_000
BATCH = 1_000

counter = 0
lock = threading.Lock()


def worker() -> None:
    global counter
    remaining = ITERATIONS
    while remaining:
        n = min(BATCH, remaining)
        # Independent CPU work outside the lock.
        v = 1
        for _ in range(n):
            v = (v * 1103515245 + 12345) & 0x7FFFFFFF
        # Brief publish under the lock.
        with lock:
            counter += n
        remaining -= n


run_in_threads(worker, lambda: counter)
