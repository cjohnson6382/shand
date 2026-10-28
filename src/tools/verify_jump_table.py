#!/usr/bin/env python3
"""Check that ManalinkEh.dll's jump table matches what Magic.exe and ct_all.csv expect.

Usage: verify_jump_table.py ManalinkEh.asm ManalinkEh.dll [ct_all.csv]

Magic.exe and ct_all.csv's "Code Address" column refer to card functions by the
address of their 5-byte "jmp near" slot in ManalinkEh.asm's _CodeSectionEx table,
so every slot must stay at a fixed address.  This checks that:
  1. _CodeSectionEx starts at CODE_SECTION_EX in the linked DLL;
  2. each slot is a jmp to the symbol ManalinkEh.asm says, at the address its
     "; addr" comment says;
  3. (optionally) every ct_all.csv Code Address inside the table lands on a slot.

Set OBJDUMP to override the objdump binary (default i686-w64-mingw32-objdump).
"""

import csv
import os
import re
import subprocess
import sys

CODE_SECTION_EX = 0x02001006
SLOT_SIZE = 5


def read_asm_slots(asm_path):
    slots = []
    in_table = False
    with open(asm_path, encoding="latin-1") as f:
        for line in f:
            if line.startswith("_CodeSectionEx:"):
                in_table = True
                continue
            if not in_table:
                continue
            m = re.match(r"\s*jmp near ([^\s;]+)\s*(?:;\s*([0-9A-Fa-f]+))?", line)
            if m:
                comment = int(m.group(2), 16) if m.group(2) else None
                slots.append((m.group(1), comment))
    return slots


def read_dll_slots(dll_path, count):
    objdump = os.environ.get("OBJDUMP", "i686-w64-mingw32-objdump")
    out = subprocess.run(
        [objdump, "-d", "--no-show-raw-insn",
         "--start-address=0x%x" % CODE_SECTION_EX,
         "--stop-address=0x%x" % (CODE_SECTION_EX + count * SLOT_SIZE),
         dll_path],
        check=True, capture_output=True, text=True).stdout
    slots = {}
    for line in out.splitlines():
        m = re.match(r"\s*([0-9a-f]+):\s+(\S+)\s+([0-9a-f]+)", line)
        if m:
            slots[int(m.group(1), 16)] = (m.group(2), int(m.group(3), 16))
    return slots


def read_symbols(dll_path):
    # Stripped DLLs keep their exports only, so read the .dbg next to it when there is one.
    dbg = os.path.splitext(dll_path)[0] + ".dbg"
    nm = os.environ.get("OBJDUMP", "i686-w64-mingw32-objdump").replace("objdump", "nm")
    out = subprocess.run([nm, dbg if os.path.exists(dbg) else dll_path],
                         check=True, capture_output=True, text=True).stdout
    symbols = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3:
            symbols[parts[2]] = int(parts[0], 16)
    return symbols


def read_linker_script_symbols(lds_path):
    # Symbols the linker script binds to Magic.exe addresses win over same-named C definitions.
    symbols = {}
    with open(lds_path, encoding="latin-1") as f:
        for line in f:
            m = re.match(r"\s*(_\w+)\s*=\s*(0x[0-9A-Fa-f]+)\s*;", line)
            if m:
                symbols[m.group(1)] = int(m.group(2), 16)
    return symbols


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    asm_slots = read_asm_slots(sys.argv[1])
    dll_slots = read_dll_slots(sys.argv[2], len(asm_slots))
    symbols = read_symbols(sys.argv[2])
    exe_symbols = read_linker_script_symbols(os.path.join(os.path.dirname(sys.argv[1]), "manalink.lds"))
    errors = 0

    def error(msg):
        nonlocal errors
        errors += 1
        if errors <= 50:
            print("ERROR: " + msg)

    if symbols.get("_CodeSectionEx") != CODE_SECTION_EX:
        error("_CodeSectionEx is at 0x%x, expected 0x%x"
              % (symbols.get("_CodeSectionEx", -1), CODE_SECTION_EX))

    for i, (symbol, comment) in enumerate(asm_slots):
        addr = CODE_SECTION_EX + i * SLOT_SIZE
        if comment is not None and comment != addr:
            error("slot %d (%s) is at 0x%x but its comment says 0x%x" % (i, symbol, addr, comment))
        if addr not in dll_slots:
            error("no instruction at slot %d (0x%x, %s)" % (i, addr, symbol))
            continue
        insn, target = dll_slots[addr]
        if insn != "jmp":
            error("slot %d (0x%x) is %s, not jmp" % (i, addr, insn))
        elif symbol in exe_symbols:
            if target != exe_symbols[symbol]:
                error("slot %d (0x%x) jumps to 0x%x, but manalink.lds binds %s to 0x%x"
                      % (i, addr, target, symbol, exe_symbols[symbol]))
            else:
                print("note: slot %d (0x%x) %s goes to Magic.exe at 0x%x (bound in manalink.lds)"
                      % (i, addr, symbol, target))
        elif target != symbols.get(symbol):
            error("slot %d (0x%x) jumps to 0x%x, but %s is at 0x%x"
                  % (i, addr, target, symbol, symbols.get(symbol, -1)))

    table_end = CODE_SECTION_EX + len(asm_slots) * SLOT_SIZE
    print("%d slots, 0x%x-0x%x" % (len(asm_slots), CODE_SECTION_EX, table_end - SLOT_SIZE))

    if len(sys.argv) == 4:
        checked = 0
        with open(sys.argv[3], newline="", encoding="latin-1") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader)
            name_col = header.index("Full Card Name in CSV (must be exactly the same)")
            addr_col = header.index("Code Address")
            for row in reader:
                if len(row) <= addr_col or not row[addr_col].startswith("0x"):
                    continue
                addr = int(row[addr_col], 16)
                if CODE_SECTION_EX <= addr < table_end:
                    checked += 1
                    if (addr - CODE_SECTION_EX) % SLOT_SIZE:
                        error("ct_all.csv: %s's Code Address 0x%x is not on a slot boundary"
                              % (row[name_col], addr))
                elif 0x02000000 <= addr < 0x03000000:
                    error("ct_all.csv: %s's Code Address 0x%x is past the end of the table"
                          % (row[name_col], addr))
        print("%d ct_all.csv code addresses point into the table" % checked)

    if errors:
        sys.exit("%d errors" % errors)
    print("OK")


if __name__ == "__main__":
    main()
