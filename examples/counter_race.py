# counter_race.py
"""
Hidden race conditions revealed by GIL-free Python.
"""

import constants as c
from gil_utils import gil_info, report, run_threads

counter: int = 0  # Shared state


def increment(iterations: int) -> None:
    global counter
    for _ in range(iterations):
        counter += 1  # Not atomic: LOAD, BINARY_OP, STORE


if __name__ == "__main__":
    print(gil_info())

    run_threads(increment, (c.ITERATIONS,))
    report("threaded", counter, c.EXPECTED)
