"""
A stats accumulator whose two fields must stay in sync.

record() updates count and total on separate lines. A thread switch
between them leaves the object in an inconsistent state: mean() returns
a wrong answer, or crashes with ZeroDivisionError if count lags total.

Standard:
    uv run --python 3.14+gil stats.py

No GIL:
    uv run --python 3.14t stats.py
"""

import sys
import threading

import v
from display_gil import gil_info


class Stats:
    def __init__(self) -> None:
        self.count: int = 0
        self.total: float = 0.0

    def record(self, value: float) -> None:
        self.count += 1
        self.total += value

    def mean(self) -> float:
        return self.total / self.count


stats = Stats()
EXPECTED: int = v.NUM_THREADS * v.ITERATIONS


def worker() -> None:
    for _ in range(v.ITERATIONS):
        stats.record(1)


def reset() -> None:
    stats.count = 0
    stats.total = 0.0


def run_threaded() -> None:
    reset()
    threads = [threading.Thread(target=worker) for _ in range(v.NUM_THREADS)]
    for t in threads: t.start()
    for t in threads: t.join()


def run_threaded_fast_switch() -> None:
    reset()
    original = sys.getswitchinterval()
    sys.setswitchinterval(v.FAST_SWITCH_INTERVAL)
    try:
        threads = [threading.Thread(target=worker) for _ in range(v.NUM_THREADS)]
        for t in threads: t.start()
        for t in threads: t.join()
    finally:
        sys.setswitchinterval(original)


def report(label: str) -> None:
    count_ok = stats.count == EXPECTED
    total_ok = stats.total == EXPECTED
    if count_ok and total_ok:
        status = "OK"
    else:
        parts = []
        if not count_ok:
            parts.append(f"count {stats.count:,}")
        if not total_ok:
            parts.append(f"total {stats.total:,.0f}")
        status = f"WRONG  ({',  '.join(parts)}  expected {EXPECTED:,})"
    print(f"  {label:<12} {status}")


if __name__ == "__main__":
    print(gil_info())
    run_threaded()
    report("threaded")
    run_threaded_fast_switch()
    report("fast switch")
