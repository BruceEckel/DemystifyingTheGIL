# compare_overhead.py
"""
Run single_thread_overhead.py under both Python builds, parse the per-task
times, and print a side-by-side comparison with percent deltas.

Usage (from the project root or examples/):
    uv run python examples/compare_overhead.py

Positive delta means free-threaded is slower than the GIL build for that
task. PEP 703's claim is that the totals stay within a few percent.
"""

import subprocess
import sys
from pathlib import Path

from single_thread_overhead import REPEATS

SCRIPT = Path(__file__).parent / "single_thread_overhead.py"

BUILDS: list[tuple[str, str]] = [
    ("GIL", "3.14+gil"),
    ("FT", "3.14t"),
]


def run(py: str) -> dict[str, float]:
    result = subprocess.run(
        ["uv", "run", "--isolated", "--no-project", "--python", py, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=True,
    )
    times: dict[str, float] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        *name_parts, value = parts
        try:
            times[" ".join(name_parts)] = float(value)
        except ValueError:
            continue
    return times


def main() -> None:
    print("Cost of using FT build without using threads")
    print(f"Running both builds (best-of-{REPEATS} per task; ~half a minute)...")
    print()
    results: dict[str, dict[str, float]] = {}
    for label, py in BUILDS:
        print(f"  running {label} ({py})...", flush=True)
        try:
            results[label] = run(py)
        except subprocess.CalledProcessError as e:
            print(f"  failed: {e.stderr}", file=sys.stderr)
            sys.exit(1)

    gil = results["GIL"]
    ft = results["FT"]
    tasks = list(gil.keys())

    print()
    print(f"{'task':<20} {'GIL (s)':>10} {'FT (s)':>10} {'delta':>10}")
    print("-" * 54)
    gil_total = 0.0
    ft_total = 0.0
    for task in tasks:
        g = gil[task]
        f = ft.get(task, float("nan"))
        gil_total += g
        ft_total += f
        delta_pct = (f - g) / g * 100 if g > 0 else 0.0
        print(f"{task:<20} {g:>10.4f} {f:>10.4f} {delta_pct:>+9.1f}%")
    print("-" * 54)
    total_delta = (ft_total - gil_total) / gil_total * 100
    print(f"{'total':<20} {gil_total:>10.4f} {ft_total:>10.4f} {total_delta:>+9.1f}%")


if __name__ == "__main__":
    main()
