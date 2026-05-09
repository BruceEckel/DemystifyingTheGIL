# mp_pool.py
"""
multiprocessing.Pool fans CPU-bound work out to separate processes,
each with its own Python interpreter and GIL. Synthetic workload:
sum of squares over four million-int chunks.
"""

from multiprocessing import Pool


def crunch(chunk: list[int]) -> int:
    return sum(x * x for x in chunk)


if __name__ == "__main__":
    data_chunks = [
        list(range(i * 1_000_000, (i + 1) * 1_000_000)) for i in range(4)
    ]

    with Pool() as pool:
        results = pool.map(crunch, data_chunks)

    print(f"chunk totals: {results}")
    print(f"grand total:  {sum(results)}")
