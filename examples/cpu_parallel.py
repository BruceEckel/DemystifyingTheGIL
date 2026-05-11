# cpu_parallel.py
"""
CPU-bound, embarrassingly parallel work with no shared state.
With the GIL: threads serialize, time ~= sequential.
Without the GIL: threads run on separate cores, near-linear speedup.
"""

import time
from concurrent.futures import ThreadPoolExecutor

import constants as c

N: int = 5_000_000


def work(n: int) -> None:
    total = 0
    for i in range(n):
        total += i * i


def time_sequential() -> float:
    start = time.perf_counter()
    for _ in range(c.NUM_THREADS):
        work(N)
    return time.perf_counter() - start


def time_threaded() -> float:
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=c.NUM_THREADS) as pool:
        for _ in range(c.NUM_THREADS):
            pool.submit(work, N)
    return time.perf_counter() - start


if __name__ == "__main__":
    seq = time_sequential()
    par = time_threaded()
    print(f"  sequential: {seq:6.2f}s")
    print(f"  threaded:   {par:6.2f}s")
    print(f"  speedup:    {seq / par:6.2f}x")
