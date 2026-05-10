# stats_race.py
"""
A stats accumulator whose two fields must stay in sync.

record() updates count and total on separate lines. A thread switch
between them leaves the object in an inconsistent state: mean() returns
a wrong answer, or crashes with ZeroDivisionError if count lags total.
"""

import sys

import constants as c
from utils import run_and_show


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


def worker() -> None:
    for _ in range(c.ITERATIONS):
        stats.record(1)


def reset() -> None:
    stats.count = 0
    stats.total = 0.0


def status() -> tuple[str, bool]:
    count_ok = stats.count == c.EXPECTED
    total_ok = stats.total == c.EXPECTED
    match (count_ok, total_ok):
        case (True, True):
            s = f"count {stats.count:,}"
        case (False, True):
            s = f"count {stats.count:,}  c.EXPECTED {c.EXPECTED:,}"
        case (True, False):
            s = f"total {stats.total:,.0f}  c.EXPECTED {c.EXPECTED:,}"
        case (False, False):
            s = f"count {stats.count:,}, total {stats.total:,.0f}  c.EXPECTED {c.EXPECTED:,}"
    return s, count_ok and total_ok


if __name__ == "__main__":
    reset()
    run_and_show("threaded", worker, status)

    reset()
    original = sys.getswitchinterval()
    sys.setswitchinterval(c.FAST_SWITCH_INTERVAL)
    try:
        run_and_show("fast switch", worker, status)
    finally:
        sys.setswitchinterval(original)
