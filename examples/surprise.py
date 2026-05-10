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
"""

import sys

import constants as c
from utils import report, run_and_report

counter: int = 0


def pure(x: int) -> int:
    return x + 1


def worker() -> None:
    global counter
    for _ in range(c.ITERATIONS):
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
