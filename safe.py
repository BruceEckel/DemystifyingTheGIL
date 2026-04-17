"""
Using a lock to protect non-atomic operation.
Standard:
    uv run --python 3.14+gil safe.py

No GIL:
    uv run --python 3.14t safe.py
"""

import threading

import v
from display_gil import gil_info

counter: int = 0  # Shared state

lock = threading.Lock()


def increment(iterations: int) -> None:
    global counter
    for _ in range(iterations):
        with lock:  # Protect non-atomic operation
            counter += 1


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
