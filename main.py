"""
Hidden race conditions revealed by GIL-free Python.
"""
import os
import threading
import sys
import psutil

print(f"Python: {sys.version.split()[0]}", end=" -- ")
print('No GIL' if "free-threading" in sys.version else 'Standard GIL')

counter = 0  # Shared state


def increment(iterations):
    """Increment a shared counter without synchronization."""
    global counter
    for _ in range(iterations):
        # This looks atomic but isn't without the GIL
        counter += 1


def main():
    global counter

    threads = []
    num_threads = 4
    iterations_per_thread = 100000

    for i in range(num_threads):
        t = threading.Thread(target=increment, args=(iterations_per_thread,))
        threads.append(t)
        t.start()

    print(f"OS Threads: {psutil.Process(os.getpid()).num_threads()}")

    for t in threads:
        t.join()

    expected = num_threads * iterations_per_thread
    print(f"Expected: {expected}")
    print(f"Actual: {counter}")
    print(f"Missing increments: {expected - counter}")


if __name__ == "__main__":
    main()
