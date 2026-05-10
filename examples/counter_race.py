# counter_race.py
"""
Hidden race conditions revealed by GIL-free Python.
"""

import constants as c
from utils import run_and_report

counter: int = 0  # Shared state


def increment() -> None:
    global counter
    for _ in range(c.ITERATIONS):
        counter += 1  # Not atomic: LOAD, BINARY_OP, STORE


if __name__ == "__main__":
    run_and_report("threaded", increment, lambda: counter)
