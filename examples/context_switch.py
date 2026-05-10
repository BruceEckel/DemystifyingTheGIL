# context_switch.py
"""
Forces a context switch between LOAD and STORE to make the race visible.

counter += 1 compiles to three steps:
    temp = counter      # LOAD  ← read current value
    time.sleep(0)       # GIL released → another thread runs here
    counter = temp + 1  # STORE ← write stale value back

time.sleep(0) releases the GIL (all blocking calls do), letting another
thread run between our read and write. This is exactly what happens
naturally in counter_race.py, just made certain instead of rare.
"""

import time

import constants as c
from utils import run_and_report

counter: int = 0
ITERS = 50


def increment() -> None:
    global counter
    for _ in range(ITERS):
        temp = counter  # LOAD
        time.sleep(0)  # force context switch
        counter = temp + 1  # STORE (may overwrite another thread's write)


if __name__ == "__main__":
    run_and_report("threaded", increment, lambda: counter, c.NUM_THREADS * ITERS)
