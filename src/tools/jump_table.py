#!/usr/bin/env python3
"""Maintain the _CodeSectionEx jump table in ManalinkEh.asm.

Usage:
  jump_table.py extend-from-exe ManalinkEh.asm Magic.exe Manalink.csv
      Append a slot for every code address Magic.exe's card table uses past the end of
      the table, each jumping to card_unimplemented until someone implements it.
  jump_table.py todo ManalinkEh.asm
      List unimplemented slots: address, intended function, and the cards using it.
  jump_table.py assign ManalinkEh.asm ADDRESS|FUNCTION [FUNCTION]
      Point an unimplemented slot at a C function.  The slot can be given by address
      or by the function name recorded in its TODO comment; FUNCTION defaults to that name.
  jump_table.py append ManalinkEh.asm FUNCTION
      Add a new slot at the end of the table; prints its address for ct_all.csv.

Slots are addressed by position (each "jmp near" is 5 bytes from CODE_SECTION_EX), and
Magic.exe and ct_all.csv store those addresses, so slots are only ever appended or
re-pointed, never removed or reordered.  An unimplemented slot looks like
  jmp near _card_unimplemented     ; 200ee68 TODO card_viridian_acolyte: Viridian Acolyte, Helionaut
"""

import csv
import re
import struct
import sys

CODE_SECTION_EX = 0x02001006
SLOT_SIZE = 5
UNIMPLEMENTED = "_card_unimplemented"
SLOT_RE = re.compile(r"^(\s*jmp near )([^\s;]+)(\s*;\s*([0-9A-Fa-f]+))?(.*)$")
TODO_RE = re.compile(r"\s*TODO (\w+)(?::\s*(.*))?$")

EXE_TABLE_OFFSET = 0xFA010
EXE_RECORD_SIZE = 72


def function_name(card_name):
    name = card_name.replace("Æ", "Ae").replace("æ", "ae").replace("'", "").lower()
    return "card_" + re.sub(r"[^a-z0-9]+", "_", name).strip("_")


class AsmFile:
    def __init__(self, path):
        self.path = path
        with open(path, encoding="latin-1", newline="") as f:
            self.lines = f.readlines()
        self.newline = "\r\n" if self.lines and self.lines[0].endswith("\r\n") else "\n"
        start = next(i for i, line in enumerate(self.lines) if line.startswith("_CodeSectionEx:"))
        self.slot_lines = [i for i in range(start + 1, len(self.lines)) if SLOT_RE.match(self.lines[i])
                           and "jmp near" in self.lines[i]]
        self.externs = {line.split()[1] for line in self.lines if line.startswith("extern ")}

    @property
    def end(self):
        return CODE_SECTION_EX + len(self.slot_lines) * SLOT_SIZE

    def slots(self):
        for n, i in enumerate(self.slot_lines):
            m = SLOT_RE.match(self.lines[i].rstrip("\r\n"))
            todo = TODO_RE.match(m.group(5) or "")
            yield (CODE_SECTION_EX + n * SLOT_SIZE, m.group(2), todo.group(1) if todo else None,
                   todo.group(2) if todo else None, i)

    def add_extern(self, symbol):
        if symbol in self.externs:
            return
        last = max(i for i, line in enumerate(self.lines) if line.startswith("extern "))
        self.lines.insert(last + 1, "extern %s%s" % (symbol, self.newline))
        self.slot_lines = [i + 1 if i > last else i for i in self.slot_lines]
        self.externs.add(symbol)

    def append_slot(self, symbol, comment=""):
        address = self.end
        self.add_extern(symbol)
        line = "  jmp near %s     ; %x%s%s" % (symbol, address, comment, self.newline)
        at = self.slot_lines[-1] + 1
        self.lines.insert(at, line)
        self.slot_lines.append(at)
        return address

    def set_slot(self, index, symbol, keep_comment):
        self.add_extern(symbol)
        i = self.slot_lines[index]
        m = SLOT_RE.match(self.lines[i].rstrip("\r\n"))
        address = CODE_SECTION_EX + index * SLOT_SIZE
        tail = m.group(5) if keep_comment else ""
        self.lines[i] = "%s%s     ; %x%s%s" % (m.group(1), symbol, address, tail, self.newline)

    def save(self):
        with open(self.path, "w", encoding="latin-1", newline="") as f:
            f.writelines(self.lines)


def exe_code_users(exe_path, manalink_path):
    names = {}
    with open(manalink_path, newline="", encoding="latin-1") as f:
        for row in csv.reader(f, delimiter=";"):
            if row and row[0].strip().isdigit():
                names[int(row[0])] = row[1]
    with open(exe_path, "rb") as f:
        exe = f.read()
    users = {}
    offset = EXE_TABLE_OFFSET
    while exe[offset + 1]:
        csvid, = struct.unpack_from("<H", exe, offset + 0x24)
        code, = struct.unpack_from("<I", exe, offset + 0x34)
        if csvid != 0xFFFF and 0x02000000 <= code < 0x03000000:
            users.setdefault(code, []).append(names.get(csvid, "csvid %d" % csvid))
        offset += EXE_RECORD_SIZE
    return users


def main():
    sys.stdout.reconfigure(errors="backslashreplace")
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    command, asm_path = sys.argv[1], sys.argv[2]
    asm = AsmFile(asm_path)

    if command == "extend-from-exe":
        users = exe_code_users(sys.argv[3], sys.argv[4])
        last = max(users)
        added = 0
        while asm.end <= last:
            cards = users.get(asm.end, [])
            if cards:
                comment = " TODO %s: %s" % (function_name(cards[0]), ", ".join(cards))
            else:
                comment = " TODO card_unused_%x: (no card in Magic.exe uses this slot)" % asm.end
            asm.append_slot(UNIMPLEMENTED, comment)
            added += 1
        asm.save()
        print("added %d slots; table now ends at 0x%x" % (added, asm.end - SLOT_SIZE))

    elif command == "todo":
        count = 0
        for address, symbol, intended, cards, _ in asm.slots():
            if symbol == UNIMPLEMENTED:
                count += 1
                print("%x  %-40s %s" % (address, intended or "?", cards or ""))
        print("%d unimplemented slots" % count, file=sys.stderr)

    elif command == "assign":
        key = sys.argv[3]
        for index, (address, symbol, intended, _, _) in enumerate(asm.slots()):
            if key.lower() in ("%x" % address, "0x%x" % address) or key == intended:
                if symbol != UNIMPLEMENTED:
                    sys.exit("slot %x already points at %s" % (address, symbol))
                function = sys.argv[4] if len(sys.argv) > 4 else intended
                asm.set_slot(index, "_" + function, keep_comment=False)
                asm.save()
                print("slot %x -> %s" % (address, function))
                return
        sys.exit("no unimplemented slot matches %s" % key)

    elif command == "append":
        function = sys.argv[3]
        if "_" + function in asm.externs:
            sys.exit("%s is already in the table" % function)
        address = asm.append_slot("_" + function)
        asm.save()
        print("0x%x" % address)

    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
