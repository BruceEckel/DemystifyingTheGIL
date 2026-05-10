# counter_lock.py
"""
Using a lock to protect non-atomic operation.
"""

import threading

import constants as c
from utils import run_and_report

counter: int = 0  # Shared state

lock = threading.Lock()


def increment() -> None:
    global counter
    for _ in range(c.ITERATIONS):
        with lock:  # Protect non-atomic operation
            counter += 1


if __name__ == "__main__":
    run_and_report("threaded", increment, lambda: counter)
