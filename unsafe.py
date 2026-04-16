"""
Hidden race conditions revealed by GIL-free Python.
Standard:
    uv run --python 3.14+gil unsafe.py

No GIL:
    uv run --python 3.14t unsafe.py
"""

import threading

from display_gil import gil_info

counter = 0  # Shared state


def increment(iterations):
    global counter
    for _ in range(iterations):
        # Non-atomic operation protected by GIL:
        counter += 1


def main():
    global counter
    print(gil_info())

    threads = []
    num_threads = 8
    iterations_per_thread = 100000

    for i in range(num_threads):
        t = threading.Thread(target=increment, args=(iterations_per_thread,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    expected = num_threads * iterations_per_thread
    print(f"Expected: {expected:,}")
    print(f"Actual: {counter:,}")


if __name__ == "__main__":
    main()
