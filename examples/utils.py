# utils.py
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import constants as c


class Timer:
    elapsed: float

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.elapsed = time.perf_counter() - self._start


def run_in_threads(
    worker: Callable[[], None],
    value: Callable[[], int],
    threads: int = 10,
) -> None:
    """Run worker in threads; print value() and elapsed seconds."""
    with Timer() as t, ThreadPoolExecutor(max_workers=threads) as pool:
        for _ in range(threads):
            pool.submit(worker)
    print(f"{value():,}  ({t.elapsed:.2f}s)")


_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"


def show(label: str, status: str, ok: bool, elapsed: float | None = None) -> None:
    color = _GREEN if ok else _RED
    timing = f"  ({elapsed:.2f}s)" if elapsed is not None else ""
    print(f"  {label:<12} {color}{status}{_RESET}{timing}")


def report(
    label: str, actual: int, expected: int, elapsed: float | None = None
) -> None:
    ok = actual == expected
    extra = f"  lost {expected - actual:,}" if not ok else ""
    show(label, f"{actual:>9,}{extra}", ok, elapsed)


def run_threads(worker: Callable[[], None]) -> None:
    # Structured concurrency:
    with ThreadPoolExecutor(max_workers=c.NUM_THREADS) as pool:
        for _ in range(c.NUM_THREADS):
            pool.submit(worker)


def run_and_report(
    label: str,
    worker: Callable[[], None],
    value: Callable[[], int],
    expected: int = c.EXPECTED,
) -> None:
    with Timer() as t:
        run_threads(worker)
    report(label, value(), expected, t.elapsed)


def run_and_show(
    label: str,
    worker: Callable[[], None],
    result: Callable[[], tuple[str, bool]],
) -> None:
    with Timer() as t:
        run_threads(worker)
    status, ok = result()
    show(label, status, ok, t.elapsed)
