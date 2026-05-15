# utils.py
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import ParamSpec

import constants as c

_P = ParamSpec("_P")


class Timer:
    elapsed: float

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.elapsed = time.perf_counter() - self._start


def timed(fn: Callable[_P, object]) -> Callable[_P, float]:
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> float:
        with Timer() as t:
            fn(*args, **kwargs)
        return t.elapsed

    return wrapper


_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"


def show(label: str, status: str, ok: bool, elapsed: float | None = None) -> None:
    color = _GREEN if ok else _RED
    timing = f"  ({elapsed:.2f}s)" if elapsed is not None else ""
    print(f"  {label:<12} {color}{status}{_RESET}{timing}")


def value_status(actual: int, expected: int) -> tuple[str, bool]:
    ok = actual == expected
    extra = f"  lost {expected - actual:,}" if not ok else ""
    return f"{actual:>9,}{extra}", ok


def report(
    label: str, actual: int, expected: int, elapsed: float | None = None
) -> None:
    show(label, *value_status(actual, expected), elapsed)


# region run_in_threads
def run_in_threads(
    worker: Callable[[], None],
    value: Callable[[], int],
    threads: int = 10,
) -> None:
    with Timer() as t:
        with ThreadPoolExecutor(
            max_workers=threads
        ) as pool:  # Structured concurrency
            for _ in range(threads):
                pool.submit(worker)
    print(f"{value():,}  ({t.elapsed:.2f}s)")
# endregion run_in_threads


def run_and_show(
    label: str,
    worker: Callable[[], None],
    result: Callable[[], tuple[str, bool]],
) -> None:
    with Timer() as t:
        with ThreadPoolExecutor(max_workers=c.NUM_THREADS) as pool:
            for _ in range(c.NUM_THREADS):
                pool.submit(worker)
    status, ok = result()
    show(label, status, ok, t.elapsed)


def run_and_report(
    label: str,
    worker: Callable[[], None],
    value: Callable[[], int],
    expected: int = c.EXPECTED,
) -> None:
    run_and_show(label, worker, lambda: value_status(value(), expected))
