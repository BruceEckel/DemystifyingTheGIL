# process_pool_executor.py
"""
ProcessPoolExecutor is the concurrent.futures equivalent of
multiprocessing.Pool. Each task runs in a separate process. Same
synthetic crunch workload as mp_pool.py.
"""

from concurrent.futures import ProcessPoolExecutor


def crunch(chunk: list[int]) -> int:
    return sum(x * x for x in chunk)


if __name__ == "__main__":
    data_chunks = [
        list(range(i * 1_000_000, (i + 1) * 1_000_000)) for i in range(4)
    ]

    with ProcessPoolExecutor() as ex:
        results = list(ex.map(crunch, data_chunks))

    print(f"chunk totals: {results}")
    print(f"grand total:  {sum(results)}")
