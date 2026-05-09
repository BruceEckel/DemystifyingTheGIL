# dis_increment.py
"""
Disassemble `counter += 1` to show the LOAD / BINARY_OP / STORE
bytecode sequence that makes the increment non-atomic.
"""

import dis


def increment():
    counter += 1  # pyright: ignore[reportUnboundVariable]


dis.dis(increment)

