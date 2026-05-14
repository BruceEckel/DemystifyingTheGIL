# counter_csp_work.py
"""
CSP model with CPU work per message. Workers do real computation
between `queue.put()` calls, so threads run in parallel and the
queue is just a coordination point rather than a bottleneck.

This is `counter_csp.py` with `WORK_PER_SEND > 0`. The book at
05-HistoryOfTheGIL.md:483 notes that adding real CPU work makes the
speedup real; this file demonstrates that claim.
"""

import queue
import threading
from concurrent.futures import ThreadPoolExecutor

import constants as c
from utils import Timer, report

DONE = object()
WORK_PER_SEND = 200  # LCG iterations between each put()


def counter_process(
    in_channel: queue.Queue[object],
    out_channel: queue.Queue[int],
) -> None:
    count = 0
    while (msg := in_channel.get()) is not DONE:
        if msg == "inc":
            count += 1
    out_channel.put(count)


if __name__ == "__main__":
    in_channel: queue.Queue[object] = queue.Queue()
    out_channel: queue.Queue[int] = queue.Queue()

    counter = threading.Thread(
        target=counter_process, args=(in_channel, out_channel)
    )
    counter.start()

    def worker() -> None:
        v = 1
        for _ in range(c.ITERATIONS):
            for _ in range(WORK_PER_SEND):
                v = (v * 1103515245 + 12345) & 0x7FFFFFFF
            in_channel.put("inc")

    with Timer() as t:
        with ThreadPoolExecutor(max_workers=c.NUM_THREADS) as pool:
            for _ in range(c.NUM_THREADS):
                pool.submit(worker)

        in_channel.put(DONE)
        counter.join()

    report("csp+work", out_channel.get(), c.EXPECTED, t.elapsed)
