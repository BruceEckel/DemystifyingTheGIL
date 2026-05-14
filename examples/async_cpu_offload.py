# async_cpu_offload.py
"""
Async + CPU offload: an asyncio event loop submits CPU-bound work to
a thread pool via `loop.run_in_executor`. With the GIL, the executor
threads serialize through the GIL and the speedup is none. Without
the GIL, the work runs truly in parallel and the event loop stays
free.

Chapter 4 (04-PythonConcurrencyStrategies.md:63) describes this
benefit: `loop.run_in_executor` becomes useful for CPU-bound calls
under FT, not just I/O-bound ones.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import constants as c
from utils import Timer

N = 5_000_000


def crunch(n: int) -> int:
    total = 0
    for i in range(n):
        total += i * i
    return total


async def main() -> None:
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=c.NUM_THREADS) as pool:
        await asyncio.gather(
            *(
                loop.run_in_executor(pool, crunch, N)
                for _ in range(c.NUM_THREADS)
            )
        )


with Timer() as t:
    asyncio.run(main())

print(f"async + offload  ({t.elapsed:.2f}s)")
