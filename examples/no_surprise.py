# no_surprise.py
"""
Thread-safe version of surprise.py.

The fix: hold a lock across the entire read-modify-write sequence.
The lock must cover all three steps together:
    1. read counter
    2. call increment(counter)
    3. write counter back
Locking only the call to increment() would not help, because increment()
itself is already safe. The race is in steps 1 and 3.

The free-threaded version runs visibly slower. With the GIL, threads don't
run in parallel, so the lock is rarely contested and cheap to acquire. With
free-threading, all 8 threads compete for the same lock on every iteration.
The counter and lock bounce between CPU cache lines as ownership transfers,
and the OS scheduler wakes and sleeps threads constantly. You get the overhead
of true parallelism with none of the benefit, because the lock re-serializes
the threads by design: no two can proceed at the same time.
Free-threading only helps when threads work on independent data and contention is low.
"""

import sys
import threading

import constants as c
from utils import report, run_and_report

counter: int = 0
lock = threading.Lock()


def pure(x: int) -> int:
    return x + 1


def worker() -> None:
    global counter
    for _ in range(c.ITERATIONS):
        with lock:
            counter = pure(counter)


def run_sequential() -> None:
    global counter
    counter = 0
    for _ in range(c.EXPECTED):
        counter = pure(counter)
    report("sequential", counter, c.EXPECTED)


def run_threaded() -> None:
    global counter
    counter = 0
    run_and_report("threaded", worker, lambda: counter)


def run_threaded_fast_switch() -> None:
    global counter
    counter = 0
    original = sys.getswitchinterval()
    sys.setswitchinterval(c.FAST_SWITCH_INTERVAL)
    try:
        run_and_report("fast switch", worker, lambda: counter)
    finally:
        sys.setswitchinterval(original)


if __name__ == "__main__":
    run_sequential()
    run_threaded()
    run_threaded_fast_switch()
