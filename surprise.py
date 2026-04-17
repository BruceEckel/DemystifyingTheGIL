# surprise.py
"""
A pure function used to update shared state becomes unsafe under free-threading.

increment(x) is pure: no shared state, no side effects.
But counter = increment(counter) reads counter, calls the function,
then writes back. In Python 3.11+, CALL is a GIL check point, so the
GIL can release between the read and the write.

With the GIL, the race can still occur, but the 5ms switch interval makes it
uncommon. Forcing a much shorter interval (0.0000001s) makes it reliable.
Without the GIL, the race is continuous and the result is wrong.

With GIL:
    uv run --python 3.14+gil surprise.py

Without GIL:
    uv run --python 3.14t surprise.py
"""

import sys
import threading

import v
from display_gil import gil_info

EXPECTED = v.NUM_THREADS * v.ITERATIONS

counter = 0


def increment(x):
    return x + 1


def worker():
    global counter
    for _ in range(v.ITERATIONS):
        counter = increment(counter)


def run_sequential():
    global counter
    counter = 0
    for _ in range(EXPECTED):
        counter = increment(counter)


def run_threaded():
    global counter
    counter = 0
    threads = [threading.Thread(target=worker) for _ in range(v.NUM_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def run_threaded_fast_switch():
    global counter
    counter = 0
    original = sys.getswitchinterval()
    sys.setswitchinterval(v.FAST_SWITCH_INTERVAL)
    try:
        threads = [threading.Thread(target=worker) for _ in range(v.NUM_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(original)


def report(label):
    status = "OK" if counter == EXPECTED else f"WRONG  (lost {EXPECTED - counter:,})"
    print(f"  {label:<12} {counter:>9,}   {status}")


if __name__ == "__main__":
    print(gil_info())
    run_sequential()
    report("sequential")
    run_threaded()
    report("threaded")
    run_threaded_fast_switch()
    report("fast switch")
