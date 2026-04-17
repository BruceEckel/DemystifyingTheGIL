# two_variable.py
"""
Two variables incremented together -- they should always be equal.
"""

import constants as c
from gil_utils import gil_info, run_threads, show_status

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

    ok = a == b
    show_status("a == b", f"a={a:,}  b={b:,}", ok)
