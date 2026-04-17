"""
Forces a context switch between LOAD and STORE to make the race visible.

counter += 1 compiles to three steps:
    temp = counter      # LOAD  ← read current value
    time.sleep(0)       # GIL released → another thread runs here
    counter = temp + 1  # STORE ← write stale value back

time.sleep(0) releases the GIL (all blocking calls do), letting another
thread run between our read and write. This is exactly what happens
naturally in unsafe.py — just made certain instead of rare.

Standard:
    uv run --python 3.14+gil context_switch.py

No GIL:
    uv run --python 3.14t context_switch.py
"""

import threading
import time

import v
from display_gil import gil_info

counter: int = 0


def increment(iterations: int) -> None:
    global counter
    for _ in range(iterations):
        temp = counter  # LOAD
        time.sleep(0)  # force context switch
        counter = temp + 1  # STORE (may overwrite another thread's write)


if __name__ == "__main__":
    print(gil_info())

    threads = [
        threading.Thread(target=increment, args=(50,))
        for _ in range(v.NUM_THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected = v.NUM_THREADS * 50
    print(f"Expected: {expected}")
    print(f"Actual:   {counter}")
    print(f"Lost:     {expected - counter}")
