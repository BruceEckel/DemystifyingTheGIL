# list_opcodes.py
"""
Explore the Python opcodes executed by the VM
"""

import opcode

print(f"named opcodes: {len(opcode.opmap)}")
print(f"opname entries (includes reserved positions): {len(opcode.opname)}")

for num, name in enumerate(opcode.opname):
    print(f"  {num:3d}  {name}")
