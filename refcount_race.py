"""
Demonstrates why CPython's GIL is essential for reference-counted GC.

ob_refcnt manipulation is NOT atomic — it's three machine instructions:
    LOAD  ob_refcnt
    ADD   1          ← thread switch can happen here
    STORE ob_refcnt

Without the GIL, two threads racing on the same object's refcount
produce incorrect counts: negative → premature free (use-after-free);
positive → memory leak.

We simulate this by forcing a GIL-release (time.sleep(0)) between
the LOAD and STORE to expose the race that the GIL normally prevents.
"""

import threading
import time


class TrackedObject:
    """Simulates an object whose ob_refcnt is manipulated by two threads."""
    refcount: int = 0


obj = TrackedObject()
ITERATIONS = 200


def inc_refcount() -> None:
    for _ in range(ITERATIONS):
        old = obj.refcount      # LOAD
        time.sleep(0)           # yield GIL → force context switch
        obj.refcount = old + 1  # STORE (may clobber concurrent write)


def dec_refcount() -> None:
    for _ in range(ITERATIONS):
        old = obj.refcount
        time.sleep(0)
        obj.refcount = old - 1


t1 = threading.Thread(target=inc_refcount)
t2 = threading.Thread(target=dec_refcount)

t1.start(); t2.start()
t1.join();  t2.join()

print(f"Final refcount : {obj.refcount:+d}  (expected 0)")
match obj.refcount:
    case n if n < 0:
        print("DANGER: negative refcount → object freed while still referenced (use-after-free)")
    case n if n > 0:
        print("DANGER: positive refcount → object never freed (memory leak)")
    case _:
        print("OK (got lucky — run again)")