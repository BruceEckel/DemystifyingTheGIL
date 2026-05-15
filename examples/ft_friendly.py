# ft_friendly.py
"""
Run each FT-friendly pattern demo under both the GIL and free-threaded
builds, then print a comparison table.

Usage (from the project root or examples/):
    uv run python examples/ft_friendly.py

Each demo prints its own wall-clock time as `(X.XXs)` or, for
`embarrassingly_parallel.py`, as `threaded:  X.XXs`. The last `X.XXs` token in
each demo's output is taken as the comparable timing.
"""

import re
import subprocess
import sys
from pathlib import Path

DEMOS: list[tuple[str, str]] = [
    ("Embarrassingly parallel", "embarrassingly_parallel.py"),
    ("Async + CPU offload", "async_cpu_offload.py"),
    ("Sharded accumulators", "counter_sharded.py"),
    ("Coarse-grained locking", "counter_coarse.py"),
    ("Read-mostly shared state", "cache_readmostly.py"),
    ("Pipeline parallelism (CSP)", "counter_csp_work.py"),
]

BUILDS: list[tuple[str, str]] = [
    ("GIL", "3.14+gil"),
    ("FT", "3.14t"),
]

EXAMPLES_DIR = Path(__file__).parent
TIME_RE = re.compile(r"([0-9]+\.[0-9]+)s")


def run(script: str, py: str) -> float:
    result = subprocess.run(
        ["uv", "run", "--isolated", "--no-project", "--python", py, script],
        cwd=EXAMPLES_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    matches = TIME_RE.findall(result.stdout)
    if not matches:
        raise RuntimeError(
            f"no timing in {script} output under {py}:\n{result.stdout}"
        )
    return float(matches[-1])


def boxed_table(headers: list[str], rows: list[list[str]]) -> str:
    cols = len(headers)
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(cols)
    ]

    def hline(left: str, mid: str, right: str) -> str:
        return left + mid.join("─" * (w + 2) for w in widths) + right

    def header_row(cells: list[str]) -> str:
        return "│" + "│".join(f" {cells[i]:^{widths[i]}} " for i in range(cols)) + "│"

    def data_row(cells: list[str]) -> str:
        return "│" + "│".join(f" {cells[i]:<{widths[i]}} " for i in range(cols)) + "│"

    lines = [hline("┌", "┬", "┐"), header_row(headers), hline("├", "┼", "┤")]
    for i, row in enumerate(rows):
        lines.append(data_row(row))
        lines.append(hline("├", "┼", "┤") if i < len(rows) - 1 else hline("└", "┴", "┘"))
    return "\n".join(lines)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    cols = len(headers)
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(cols)
    ]

    def row(cells: list[str]) -> str:
        return "| " + " | ".join(cells[i].ljust(widths[i]) for i in range(cols)) + " |"

    separator = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    return "\n".join([row(headers), separator, *(row(r) for r in rows)])


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print("FT-friendly pattern comparison")
    print("Running each demo under both builds (this takes a minute)...")
    print()

    times: dict[str, dict[str, float]] = {label: {} for label, _ in DEMOS}
    for build_label, py in BUILDS:
        print(f"  running {build_label} ({py})...", flush=True)
        for demo_label, script in DEMOS:
            print(f"    {script}", flush=True)
            try:
                times[demo_label][build_label] = run(script, py)
            except subprocess.CalledProcessError as e:
                print(f"    failed: {e.stderr}", file=sys.stderr)
                sys.exit(1)

    headers = ["Pattern", "File", "GIL", "FT", "delta"]
    rows = []
    for label, script in DEMOS:
        gil = times[label]["GIL"]
        ft = times[label]["FT"]
        delta = (ft - gil) / gil * 100 if gil > 0 else float("nan")
        rows.append(
            [label, script, f"{gil:.2f}s", f"{ft:.2f}s", f"{delta:+.1f}%"]
        )
    print()
    print(boxed_table(headers, rows))

    md_path = EXAMPLES_DIR / "ft_friendly.md"
    md_path.write_text(
        "# FT-friendly pattern comparison\n\n"
        + markdown_table(headers, rows)
        + "\n",
        encoding="utf-8",
    )
    print(f"\nMarkdown table written to {md_path}")


if __name__ == "__main__":
    main()
