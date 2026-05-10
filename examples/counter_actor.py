# counter_actor.py
"""
Actor model: the counter is private to one thread (the actor), which
processes messages from a mailbox one at a time. Workers send "inc"
messages but never touch the counter. No locks are needed, even
without the GIL, because the counter is never shared.
"""

import queue
import threading

import constants as c
from utils import report, run_threads

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


def worker(mailbox: queue.Queue[object], iterations: int) -> None:
    for _ in range(iterations):
        mailbox.put("inc")


if __name__ == "__main__":
    actor = CounterActor()
    actor.start()
    run_threads(worker, (actor.mailbox, c.ITERATIONS))
    actor.stop()

    report("actor", actor.count, c.EXPECTED)
