# refcount_race.py
"""
Demonstrates why CPython's GIL is essential for reference-counted GC.

ob_refcnt manipulation is NOT atomic — it's two operations:
    old = obj.refcount      # LOAD
    obj.refcount = old + 1  # STORE  ← another thread can run between these

With the GIL, the LOAD and STORE are serialized — the refcount is always correct.
Without the GIL, threads interleave freely: negative → premature free (use-after-free);
positive → memory leak.
"""

import threading

import constants as c
from gil_utils import gil_info, show_status


class TrackedObject:
    refcount: int = 0


obj: TrackedObject = TrackedObject()
free_threading = "No GIL" in gil_info()


def inc_refcount() -> None:
    for _ in range(c.ITERATIONS):
        old = obj.refcount
        obj.refcount = old + 1


def dec_refcount() -> None:
    for _ in range(c.ITERATIONS):
        old = obj.refcount
        obj.refcount = old - 1


if __name__ == "__main__":
    print(gil_info())

    t1 = threading.Thread(target=inc_refcount)
    t2 = threading.Thread(target=dec_refcount)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    n = obj.refcount
    match (n, free_threading):
        case (0, False):
            msg = f"{n:+d}  GIL serialized LOAD/STORE"
        case (0, _):
            msg = f"{n:+d}  got lucky — run again"
        case _ if n < 0:
            msg = f"{n:+d}  negative refcount → use-after-free"
        case _:
            msg = f"{n:+d}  positive refcount → memory leak"
    show_status("refcount", msg, n == 0)
