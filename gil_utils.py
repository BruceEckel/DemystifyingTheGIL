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


def run_threads(target: Callable[..., None], args: tuple[Any, ...] = ()) -> None:
    threads = [threading.Thread(target=target, args=args) for _ in range(c.NUM_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    print(gil_info())
