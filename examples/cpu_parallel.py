# region setup
# cpu_parallel.py
import time
from concurrent.futures import ThreadPoolExecutor
import constants as c
N: int = 5_000_000

def work(n: int) -> None:
    total = 0
    for i in range(n):
        total += i * i

# endregion setup

# region seq_comparison

def time_sequential() -> float:
    start = time.perf_counter()
    for _ in range(c.NUM_THREADS):
        work(N)
    return time.perf_counter() - start

# endregion seq_comparison
# region par_comparison

def time_threaded() -> float:
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=c.NUM_THREADS) as pool:
        for _ in range(c.NUM_THREADS):
            pool.submit(work, N)
    return time.perf_counter() - start

# endregion par_comparison

# region run_it
seq = time_sequential()
par = time_threaded()
print(f"  sequential: {seq:6.2f}s")
print(f"  threaded:   {par:6.2f}s")
print(f"  speedup:    {seq / par:6.2f}x")
# endregion run_it
