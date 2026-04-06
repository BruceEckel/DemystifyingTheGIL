# show_gil.py
import sys


def gil_info():
    major, minor, *_ = sys.version.split()[0].split(".")
    free_threading = "free-threading" in sys.version
    print(f"Python {major}.{minor}{'t' if free_threading else ''}", end=": ")
    print("No GIL" if free_threading else "Standard GIL")


if __name__ == "__main__":
    gil_info()
