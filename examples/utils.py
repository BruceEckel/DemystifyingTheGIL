# utils.py
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import constants as c


_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"


def show(label: str, status: str, ok: bool) -> None:
    color = _GREEN if ok else _RED
    print(f"  {label:<12} {color}{status}{_RESET}")


def report(label: str, actual: int, expected: int) -> None:
    ok = actual == expected
    extra = f"  lost {expected - actual:,}" if not ok else ""
    show(label, f"{actual:>9,}{extra}", ok)


def run_threads(target: Callable[..., None], args: tuple[Any, ...] = ()) -> None:
    # Structured concurrency:
    with ThreadPoolExecutor(max_workers=c.NUM_THREADS) as pool:
        for _ in range(c.NUM_THREADS):
            pool.submit(target, *args)
