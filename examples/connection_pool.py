# connection_pool.py
"""
Lazy initialization looks safe but hides a race.

A common library pattern: create an expensive resource on first use.
With the GIL, the initialization window is rarely interrupted.
Without the GIL, multiple threads pass the None-check simultaneously
and the resource is created more than once.
"""

import sys
import threading

import constants as c
from gil_utils import gil_info, run_threads


class ConnectionPool:
    _pool: object | None = None
    _creations: list[
        int
    ] = []  # list.append is atomic; length = how many times connect() ran
    _barrier: threading.Barrier | None = None

    @classmethod
    def connect(cls) -> object:
        cls._creations.append(1)
        _ = sum(range(100_000))  # CPU work; does not release the GIL
        return object()

    @classmethod
    def get(cls) -> None:
        assert cls._barrier is not None
        cls._barrier.wait()  # all threads start the check simultaneously
        if cls._pool is None:
            cls._pool = cls.connect()

    @classmethod
    def reset(cls) -> None:
        cls._pool = None
        cls._creations.clear()
        cls._barrier = threading.Barrier(c.NUM_THREADS)


def run_threaded() -> None:
    ConnectionPool.reset()
    run_threads(ConnectionPool.get)


def run_threaded_fast_switch() -> None:
    ConnectionPool.reset()
    original = sys.getswitchinterval()
    sys.setswitchinterval(c.FAST_SWITCH_INTERVAL)
    try:
        run_threads(ConnectionPool.get)
    finally:
        sys.setswitchinterval(original)


def report(label: str) -> None:
    n = len(ConnectionPool._creations)
    status = "OK" if n == 1 else f"WRONG  (created {n} times)"
    print(f"  {label:<12} {status}")


if __name__ == "__main__":
    print(gil_info())
    run_threaded()
    report("threaded")
    run_threaded_fast_switch()
    report("fast switch")
