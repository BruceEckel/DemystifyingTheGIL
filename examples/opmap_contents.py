# opmap_contents.py
"""
Inspect the opcode tables. opmap holds the "public" opcodes visible
in dis output; opname is larger and also includes <N> reserved slots,
INSTRUMENTED_* debugger opcodes, and pseudo-instructions used during
compilation.
"""

import opcode

print(f"opmap entries: {len(opcode.opmap)}")
print(f"opname entries: {len(opcode.opname)}")

for num, name in enumerate(opcode.opname):
    print(f"  {num:3d}  {name}")
