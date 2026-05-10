# counter_csp.py
"""
CSP model: workers and a counter process communicate through channels.
A channel is a first-class object, owned by neither side. Workers write
increments to the in-channel; the counter reads them and publishes the
total on the out-channel. No locks are needed: the count is private
to the counter thread.

Contrast with counter_actor.py: in the actor model, messages are addressed
to a specific actor (its mailbox). Here messages flow through a shared
channel and the counter just happens to be the reader.
"""

import queue
import threading

import constants as c
from utils import report, run_threads

DONE = object()  # Sentinel: no more increments will arrive.


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
        for _ in range(c.ITERATIONS):
            in_channel.put("inc")

    run_threads(worker)

    in_channel.put(DONE)
    counter.join()

    report("csp", out_channel.get(), c.EXPECTED)
