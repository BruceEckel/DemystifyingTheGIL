# region setup
# cpu_parallel.py
from concurrent.futures import ThreadPoolExecutor
import constants as c
from utils import timed
N: int = 5_000_000

def work(n: int) -> None:
    total = 0
    for i in range(n):
        total += i * i

# endregion setup

# region comparison

@timed
def sequential():
    for _ in range(c.NUM_THREADS):
        work(N)

@timed
def threaded():
    with ThreadPoolExecutor(max_workers=c.NUM_THREADS) as pool:
        for _ in range(c.NUM_THREADS):
            pool.submit(work, N)

# endregion comparison

# region run_it
seq = sequential()
par = threaded()
print(f"  sequential: {seq:6.2f}s")
print(f"  threaded:   {par:6.2f}s")
print(f"  speedup:    {seq / par:6.2f}x")
# endregion run_it
