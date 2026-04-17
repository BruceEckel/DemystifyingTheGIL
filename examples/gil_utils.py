# gil_utils.py
import sys
import threading
from collections.abc import Callable
from typing import Any

import constants as c


def gil_info() -> str:
    major, minor, *_ = sys.version.split()[0].split(".")
    free_threading = "free-threading" in sys.version
    tag = f"Python {major}.{minor}{'t' if free_threading else ''}"
    status = "No GIL" if free_threading else "Standard GIL"
    return f"{tag}: {status}"


_GREEN = "\033[32m"
_RED   = "\033[31m"
_RESET = "\033[0m"


def show_status(label: str, status: str, ok: bool) -> None:
    color = _GREEN if ok else _RED
    print(f"  {label:<12} {color}{status}{_RESET}")


def report(label: str, actual: int, expected: int) -> None:
    ok = actual == expected
    extra = f"  lost {expected - actual:,}" if not ok else ""
    show_status(label, f"{actual:>9,}{extra}", ok)


def run_threads(target: Callable[..., None], args: tuple[Any, ...] = ()) -> None:
    threads = [threading.Thread(target=target, args=args) for _ in range(c.NUM_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    print(gil_info())
