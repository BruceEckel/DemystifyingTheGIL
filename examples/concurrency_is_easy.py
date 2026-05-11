# concurrency_is_easy.py
from utils import run_in_threads

counter = 0

def worker():
    global counter
    for _ in range(100_000):
        counter += 1

run_in_threads(worker, lambda: counter)
