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
from utils import run_and_show


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


def status() -> tuple[str, bool]:
    n = len(ConnectionPool._creations)
    ok = n == 1
    return ("created once" if ok else f"created {n} times", ok)


if __name__ == "__main__":
    ConnectionPool.reset()
    run_and_show("threaded", ConnectionPool.get, status)

    ConnectionPool.reset()
    original = sys.getswitchinterval()
    sys.setswitchinterval(c.FAST_SWITCH_INTERVAL)
    try:
        run_and_show("fast switch", ConnectionPool.get, status)
    finally:
        sys.setswitchinterval(original)
