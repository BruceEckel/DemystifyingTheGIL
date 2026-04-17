# refcount_race.py
"""
Demonstrates why CPython's GIL is essential for reference-counted GC.

ob_refcnt manipulation is NOT atomic — it's two operations:
    old = obj.refcount      # LOAD
    obj.refcount = old + 1  # STORE  ← another thread can run between these

With the GIL, the LOAD and STORE are serialized — the refcount is always correct.
Without the GIL, threads interleave freely: negative → premature free (use-after-free);
positive → memory leak.

Standard:
    uv run --python 3.14+gil refcount_race.py

No GIL:
    uv run --python 3.14t refcount_race.py
"""

import threading

import constants as c
from gil_utils import gil_info


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
    t1.start(); t2.start()
    t1.join();  t2.join()

    n = obj.refcount
    print(f"Final refcount: {n:+d}  (expected 0)")
    if n == 0 and not free_threading:
        print("OK — GIL serialized the LOAD/STORE, race prevented")
    elif n == 0:
        print("OK (got lucky — run again)")
    elif n < 0:
        print(f"DANGER — negative refcount → use-after-free")
    else:
        print(f"DANGER — positive refcount → memory leak")
