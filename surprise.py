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

import constants as c
from gil_utils import gil_info, run_threads

EXPECTED = c.EXPECTED

counter: int = 0


def increment(x: int) -> int:
    return x + 1


def worker() -> None:
    global counter
    for _ in range(c.ITERATIONS):
        counter = increment(counter)


def run_sequential() -> None:
    global counter
    counter = 0
    for _ in range(EXPECTED):
        counter = increment(counter)


def run_threaded() -> None:
    global counter
    counter = 0
    run_threads(worker)


def run_threaded_fast_switch() -> None:
    global counter
    counter = 0
    original = sys.getswitchinterval()
    sys.setswitchinterval(c.FAST_SWITCH_INTERVAL)
    try:
        run_threads(worker)
    finally:
        sys.setswitchinterval(original)


def report(label: str) -> None:
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
