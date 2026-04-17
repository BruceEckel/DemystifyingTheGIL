"""
Two variables incremented together -- they should always be equal.
Standard:
    uv run --python 3.14+gil two_variable.py

No GIL:
    uv run --python 3.14t two_variable.py
"""

import threading

import v
from display_gil import gil_info

a = 0
b = 0


def go(iterations):
    global a, b
    for _ in range(iterations):
        a += 1
        b += 1


if __name__ == "__main__":
    print(gil_info())

    threads = [
        threading.Thread(target=go, args=(v.ITERATIONS,))
        for _ in range(v.NUM_THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"a: {a:,}  b: {b:,}")
