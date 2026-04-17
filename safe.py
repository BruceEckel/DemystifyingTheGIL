# safe.py
"""
Using a lock to protect non-atomic operation.
Standard:
    uv run --python 3.14+gil safe.py

No GIL:
    uv run --python 3.14t safe.py
"""

import threading

import constants as c
from gil_utils import gil_info, run_threads

counter: int = 0  # Shared state

lock = threading.Lock()


def increment(iterations: int) -> None:
    global counter
    for _ in range(iterations):
        with lock:  # Protect non-atomic operation
            counter += 1


if __name__ == "__main__":
    print(gil_info())

    run_threads(increment, (c.ITERATIONS,))

    expected = c.EXPECTED
    print(f"Expected: {expected:,}")
    print(f"Actual: {counter:,}")
