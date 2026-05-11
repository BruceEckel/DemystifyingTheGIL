# constants.py
import os

NUM_THREADS: int = os.process_cpu_count() or 8
ITERATIONS: int = 100_000
EXPECTED: int = NUM_THREADS * ITERATIONS
FAST_SWITCH_INTERVAL: float = 0.0000001
