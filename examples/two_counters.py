# two_counters.py
"""
Two variables incremented together -- they should always be equal.
"""

import constants as c
from utils import run_and_show

a: int = 0
b: int = 0


def two_counters() -> None:
    global a, b
    for _ in range(c.ITERATIONS):
        a += 1
        b += 1


if __name__ == "__main__":
    run_and_show(
        "a == b", two_counters, lambda: (f"a={a:,}  b={b:,}", a == b)
    )
