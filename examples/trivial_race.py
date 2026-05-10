# trivial_race.py
"""
Simplest demonstration of correct-with-GIL, broken-without-GIL.

Ten threads each add one to a shared counter, 100,000 times.
With GIL:    prints 1000000.
Without GIL: prints something less than 1000000.
"""

import threading

counter = 0


def worker():
    global counter
    for _ in range(100_000):
        counter += 1


threads = [threading.Thread(target=worker) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(counter)
