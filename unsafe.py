"""
Hidden race conditions revealed by GIL-free Python.
Standard:
    uv run --python 3.14+gil unsafe.py

No GIL:
    uv run --python 3.14t unsafe.py
"""

import threading

import v
from display_gil import gil_info

counter: int = 0  # Shared state


def increment(iterations: int) -> None:
    global counter
    for _ in range(iterations):
        counter += 1  # Not atomic: LOAD, BINARY_OP, STORE


if __name__ == "__main__":
    print(gil_info())

    threads = [
        threading.Thread(target=increment, args=(v.ITERATIONS,))
        for _ in range(v.NUM_THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected = v.NUM_THREADS * v.ITERATIONS
    print(f"Expected: {expected:,}")
    print(f"Actual: {counter:,}")
