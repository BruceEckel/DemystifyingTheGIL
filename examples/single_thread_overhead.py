# single_thread_overhead.py
"""
Single-threaded microbenchmarks for comparing GIL and free-threaded builds.

Run under each build and compare the per-task times:
    uv run --python 3.14+gil examples/single_thread_overhead.py
    uv run --python 3.14t   examples/single_thread_overhead.py

Or use compare_overhead.py to run both and print a side-by-side table.

PEP 703 claims single-threaded code stays within a few percent of the GIL
build. These tasks stress the paths free-threading changed, so any
slowdown should show up here.

Tasks (and what each stresses):
    int +=           integer arithmetic with immortal small ints
    obj alloc        object creation and destruction (allocator + refcount)
    tuple new        tuple churn (heap alloc + refcount)
    dict set         dict set/get (per-object lock)
    list append & pop  per-object lock + item refcount
    attr read        attribute reads (type slot and MRO caches)
    func call        function call overhead (frame setup, arg refcounts)
    str join         string list build plus join (alloc + refcount)

Caveats:
    Best-of-5 reduces noise but does not eliminate it. Close the browser,
    kill background syncs, and run on AC power. A 2-3 percent run-to-run
    drift is normal.

    The first run after a Python install pulls and caches the interpreter.
    Run once to warm the uv cache, then run again for the measurement.

    The tasks are tuned so each one takes a noticeable fraction of a
    second on a modern machine. If a task finishes too fast to measure
    cleanly, bump ITER below.
"""

import time
from collections.abc import Callable

ITER: int = 20_000_000
REPEATS: int = 7  # best-of-N to reduce noise


def bench_ints() -> None:
    total = 0
    for i in range(ITER):
        total += i


class Point:
    __slots__ = ("x", "y")

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


def bench_alloc() -> None:
    for i in range(ITER // 5):
        Point(i, i)


def bench_tuple() -> None:
    for i in range(ITER // 3):
        _ = (i, i + 1, i + 2)


def bench_dict() -> None:
    d: dict[int, int] = {}
    for i in range(ITER // 5):
        d[i & 0xFFFF] = i


def bench_list() -> None:
    lst: list[int] = []
    for i in range(ITER // 10):
        lst.append(i)
        lst.pop()


def bench_attr() -> None:
    p = Point(1, 2)
    total = 0
    for _ in range(ITER):
        total += p.x


def _identity(n: int) -> int:
    return n


def bench_call() -> None:
    for i in range(ITER // 2):
        _identity(i)


def bench_string() -> None:
    parts: list[str] = []
    for _ in range(ITER // 50):
        parts.append("x")
    "".join(parts)


TASKS: list[tuple[str, Callable[[], None]]] = [
    ("int +=", bench_ints),
    ("obj alloc", bench_alloc),
    ("tuple new", bench_tuple),
    ("dict set", bench_dict),
    ("list append & pop", bench_list),
    ("attr read", bench_attr),
    ("func call", bench_call),
    ("str join", bench_string),
]


def time_task(fn: Callable[[], None]) -> float:
    best = float("inf")
    for _ in range(REPEATS):
        start = time.perf_counter()
        fn()
        elapsed = time.perf_counter() - start
        if elapsed < best:
            best = elapsed
    return best


if __name__ == "__main__":
    for name, fn in TASKS:
        t = time_task(fn)
        print(f"{name:<20} {t:.4f}")
