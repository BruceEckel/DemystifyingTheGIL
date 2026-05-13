# counter_coarse.py
"""
Coarse-grained locking: amortize lock cost across a batch of operations.
Each thread takes the lock once per CHUNK iterations, not once per
increment. The total number of increments is unchanged, but the number
of lock acquisitions drops by a factor of CHUNK.

Compare with:
    the_camels_nose.py  -- one acquisition per increment: correct but slow
    counter_sharded.py  -- no lock during the loop: faster still
"""

import threading

from utils import run_in_threads

ITERATIONS = 100_000
CHUNK = 1_000

counter = 0
lock = threading.Lock()


def worker() -> None:
    global counter
    remaining = ITERATIONS
    while remaining:
        n = min(CHUNK, remaining)
        with lock:
            for _ in range(n):
                counter += 1
        remaining -= n


run_in_threads(worker, lambda: counter)
