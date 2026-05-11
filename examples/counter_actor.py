# counter_actor.py
"""
Actor model: the counter is private to one thread (the actor), which
processes messages from a mailbox one at a time. Workers send "inc"
messages but never touch the counter. No locks are needed, even
without the GIL, because the counter is never shared.
"""

import queue
import threading
from concurrent.futures import ThreadPoolExecutor

import constants as c
from utils import report

STOP = object()  # Sentinel that tells the actor to shut down.


class CounterActor:
    def __init__(self) -> None:
        self.mailbox: queue.Queue[object] = queue.Queue()
        self.count = 0
        self._thread = threading.Thread(target=self._run)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self.mailbox.put(STOP)
        self._thread.join()

    def _run(self) -> None:
        while (msg := self.mailbox.get()) is not STOP:
            if msg == "inc":
                self.count += 1


if __name__ == "__main__":
    actor = CounterActor()
    actor.start()

    def worker() -> None:
        for _ in range(c.ITERATIONS):
            actor.mailbox.put("inc")

    with ThreadPoolExecutor(max_workers=c.NUM_THREADS) as pool:
        for _ in range(c.NUM_THREADS):
            pool.submit(worker)
    actor.stop()

    report("actor", actor.count, c.EXPECTED)
