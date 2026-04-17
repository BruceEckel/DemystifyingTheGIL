# opmap_contents.py
import opcode

print(f"opmap entries: {len(opcode.opmap)}")  # named opcodes
print(f"opname entries: {len(opcode.opname)}")  # includes reserved positions

for num, name in enumerate(opcode.opname):
    print(f"  {num:3d}  {name}")
