# show_gil.py
import sys


def gil_info() -> str:
    major, minor, *_ = sys.version.split()[0].split(".")
    free_threading = "free-threading" in sys.version
    tag = f"Python {major}.{minor}{'t' if free_threading else ''}"
    status = "No GIL" if free_threading else "Standard GIL"
    return f"{tag}: {status}"


if __name__ == "__main__":
    print(gil_info())
