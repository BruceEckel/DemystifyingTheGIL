# region show
# the_camels_nose.py
import threading
from utils import run_in_threads
counter = 0
lock = threading.Lock()  # aka mutex

def worker():
    global counter
    for _ in range(100_000):
        with lock:
            counter += 1
# endregion show

run_in_threads(worker, lambda: counter)
