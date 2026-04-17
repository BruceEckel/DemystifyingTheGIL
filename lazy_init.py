"""
Lazy initialization looks safe but hides a race.

A common library pattern: create an expensive resource on first use.
With the GIL, the initialization window is rarely interrupted.
Without the GIL, multiple threads pass the None-check simultaneously
and the resource is created more than once.

Standard:
    uv run --python 3.14+gil lazy_init.py

No GIL:
    uv run --python 3.14t lazy_init.py
"""

import sys
import threading

import v
from display_gil import gil_info

_pool: object | None = None
_creations: list[int] = []  # list.append is atomic; length = how many times connect() ran
_barrier: threading.Barrier | None = None


def connect() -> object:
    _creations.append(1)
    _ = sum(range(100_000))  # CPU work; does not release the GIL
    return object()


def get_pool() -> None:
    assert _barrier is not None
    _barrier.wait()  # all threads start the check simultaneously
    global _pool
    if _pool is None:
        _pool = connect()


def reset() -> None:
    global _pool, _barrier
    _pool = None
    _creations.clear()
    _barrier = threading.Barrier(v.NUM_THREADS)


def run_threaded() -> None:
    reset()
    threads = [threading.Thread(target=get_pool) for _ in range(v.NUM_THREADS)]
    for t in threads: t.start()
    for t in threads: t.join()


def run_threaded_fast_switch() -> None:
    reset()
    original = sys.getswitchinterval()
    sys.setswitchinterval(v.FAST_SWITCH_INTERVAL)
    try:
        threads = [threading.Thread(target=get_pool) for _ in range(v.NUM_THREADS)]
        for t in threads: t.start()
        for t in threads: t.join()
    finally:
        sys.setswitchinterval(original)


def report(label: str) -> None:
    n = len(_creations)
    status = "OK" if n == 1 else f"WRONG  (created {n} times)"
    print(f"  {label:<12} {status}")


if __name__ == "__main__":
    print(gil_info())
    run_threaded()
    report("threaded")
    run_threaded_fast_switch()
    report("fast switch")
