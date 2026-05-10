# concurrency_is_easy.py
"""
Simplest demonstration of correct-with-GIL, broken-without-GIL.
"""

from concurrent.futures import ThreadPoolExecutor

counter = 0


def worker():
    global counter
    for _ in range(100_000):
        counter += 1


with ThreadPoolExecutor(max_workers=10) as pool:
    for _ in range(10):
        pool.submit(worker)

print(f"{counter:,}")
