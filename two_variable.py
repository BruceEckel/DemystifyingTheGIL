# two_variable.py
"""
Two variables incremented together -- they should always be equal.
Standard:
    uv run --python 3.14+gil two_variable.py

No GIL:
    uv run --python 3.14t two_variable.py
"""

import constants as c
from gil_utils import gil_info, run_threads

a: int = 0
b: int = 0


def go(iterations: int) -> None:
    global a, b
    for _ in range(iterations):
        a += 1
        b += 1


if __name__ == "__main__":
    print(gil_info())

    run_threads(go, (c.ITERATIONS,))

    print(f"a: {a:,}  b: {b:,}")
