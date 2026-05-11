# counter_sharded.py
"""
Each thread accumulates its own local count and returns it. The main
thread sums the per-thread results. No shared mutable state during
the loop, so FT scales.

Compare with:
    concurrency_is_easy.py  -- one shared counter, no lock: wrong under FT
    the_camels_nose.py      -- one shared counter + lock: correct but slow
"""

from concurrent.futures import ThreadPoolExecutor

from utils import Timer


def worker() -> int:
    count = 0
    for _ in range(100_000):
        count += 1
    return count


with Timer() as t, ThreadPoolExecutor(max_workers=10) as pool:
    futures = [pool.submit(worker) for _ in range(10)]
    total = sum(f.result() for f in futures)

print(f"{total:,}  ({t.elapsed:.2f}s)")
