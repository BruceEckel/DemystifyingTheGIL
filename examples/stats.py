# stats.py
"""
A stats accumulator whose two fields must stay in sync.

record() updates count and total on separate lines. A thread switch
between them leaves the object in an inconsistent state: mean() returns
a wrong answer, or crashes with ZeroDivisionError if count lags total.
"""

import sys

import constants as c
from gil_utils import gil_info, show_status, run_threads


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
EXPECTED = c.EXPECTED


def worker() -> None:
    for _ in range(c.ITERATIONS):
        stats.record(1)


def reset() -> None:
    stats.count = 0
    stats.total = 0.0


def run_threaded() -> None:
    reset()
    run_threads(worker)


def run_threaded_fast_switch() -> None:
    reset()
    original = sys.getswitchinterval()
    sys.setswitchinterval(c.FAST_SWITCH_INTERVAL)
    try:
        run_threads(worker)
    finally:
        sys.setswitchinterval(original)


def report(label: str) -> None:
    count_ok = stats.count == EXPECTED
    total_ok = stats.total == EXPECTED
    ok = count_ok and total_ok
    if ok:
        status = f"count={stats.count:,}"
    else:
        parts = []
        if not count_ok:
            parts.append(f"count {stats.count:,}")
        if not total_ok:
            parts.append(f"total {stats.total:,.0f}")
        status = f"{',  '.join(parts)}  expected {EXPECTED:,}"
    show_status(label, status, ok)


if __name__ == "__main__":
    print(gil_info())
    run_threaded()
    report("threaded")
    run_threaded_fast_switch()
    report("fast switch")
