#!/usr/bin/env python3
"""Read and write Magic.exe's card type table, the data ct_all.csv describes.

Replacement for ct2exe.exe, plus its inverse.

Usage:
  ct_all.py decode Magic.exe Manalink.csv BASE_ct_all.csv OUT_ct_all.csv
      Rebuild ct_all.csv from the table in Magic.exe.  BASE supplies the header and,
      for cards it has, the "Sort order" and full "Name" (Magic.exe keeps only 34 chars).
  ct_all.py encode ct_all.csv Manalink.csv Magic.exe OUT.exe [--check]
      Write ct_all.csv's rows into a copy of Magic.exe's table, in file order.  With
      --check, compare the result with Magic.exe instead of writing OUT.exe.

Unlike ct2exe.exe this doesn't sort: rows are written in the order they appear in the
csv, which decode preserves.  The table can't grow past its current size, so new cards
must replace "Dummy" rows (unused slots).

Each 72-byte record is a card_data_t (see defs.h):
  +0 secret  +1 name[35]  +0x24 csvid (uint16, looked up by "Full Card Name in CSV")
  +0x26 reserved  +0x28 type bits  +0x29 family  +0x2a color bits  +0x2b cc[3]
  +0x2e power  +0x30 toughness  +0x32 extra flag bits  +0x33 unused
  +0x34 code address  +0x38 ability bits  +0x3c flag bits  +0x40 rarity
  +0x41 phase bits  +0x42 expansion  +0x43 zero  +0x44 creature rating (int32, -2..3)
Bit fields map one csv column per bit, first column = most significant bit.

Several Manalink.csv rows share a name ("None", "Empty"), so ct_all.csv gets a trailing
"CSV ID" column, filled in only for rows whose name doesn't identify their csvid.
"""

import csv
import struct
import sys

TABLE_OFFSET = 0xFA010	# file offset of the first record in Magic.exe
RECORD_SIZE = 72
NAME_SIZE = 35
DUMMY_ID = 0xFFFF
CSV_ID_COLUMN = "CSV ID"

# (first column, number of columns) for each bit field, by name of the first column.
BIT_FIELDS = {
    "type": ("Type: Effect", 8),
    "color": ("Color Unused", 8),
    "extra": ("Extra Flags (Unused)", 8),
    "abilities": ("Ability: Unknown", 32),
    "flags": ("Flags: Ability Cost", 32),
    "phases": ("Activate after Combat", 8),
}


def num(text):
    text = text.strip()
    if text in ("", "-"):
        return 0
    if text.lower().startswith("0x"):
        return int(text, 16)
    return int(text)


class Columns:
    def __init__(self, header):
        self.header = header
        self.bit_columns = {}
        for field, (first, count) in BIT_FIELDS.items():
            start = header.index(first)
            self.bit_columns[field] = list(range(start, start + count))
        self.index = {name: i for i, name in enumerate(header) if name not in self.index_skip()}

    @staticmethod
    def index_skip():
        return ()

    def col(self, row, name):
        return row[self.header.index(name)]

    def bits(self, row, field):
        value = 0
        for i in self.bit_columns[field]:
            value = (value << 1) | (num(row[i]) & 1)
        return value

    def set_bits(self, row, field, value):
        cols = self.bit_columns[field]
        for k, i in enumerate(cols):
            row[i] = str((value >> (len(cols) - 1 - k)) & 1)


def read_manalink(path):
    by_name, by_id = {}, {}
    with open(path, newline="", encoding="latin-1") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader)
        for row in reader:
            if row and row[0].strip().isdigit():
                by_name.setdefault(row[1], int(row[0]))
                by_id[int(row[0])] = row[1]
    return by_name, by_id


def read_table(exe):
    records = []
    offset = TABLE_OFFSET
    while exe[offset + 1] != 0:
        records.append(exe[offset:offset + RECORD_SIZE])
        offset += RECORD_SIZE
    return records


def encode(cols, row, by_name):
    h = cols.header
    name = cols.col(row, "Name (will be cut down)").encode("latin-1")[:NAME_SIZE - 1]
    full_name = cols.col(row, "Full Card Name in CSV (must be exactly the same)")
    dummy = name == b"Dummy"
    explicit_id = row[h.index(CSV_ID_COLUMN)].strip() if CSV_ID_COLUMN in h else ""
    if dummy:
        csvid = DUMMY_ID
    elif explicit_id:
        csvid = int(explicit_id)
    elif full_name in by_name:
        csvid = by_name[full_name]
    else:
        sys.exit("ct_all.csv: %r isn't in Manalink.csv" % full_name)
    rating = num(cols.col(row, "Creature Rating Mod"))
    if not -2 <= rating <= 3:
        rating = 0
    return struct.pack(
        "<B35sHHBBB3BhhBBIIIBBBBi",
        0xFF if dummy else 0, name, csvid, 0xFFFF if dummy else 0,
        cols.bits(row, "type"), num(cols.col(row, "Family")) & 0xFF, cols.bits(row, "color"),
        num(cols.col(row, "Required COLOR Mana (total)")) & 0xFF,
        num(cols.col(row, "Required Colorless Mana (total)")) & 0xFF,
        num(cols.col(row, "cc[2]")) & 0xFF,
        num(cols.col(row, "Power")), num(cols.col(row, "Toughness")),
        cols.bits(row, "extra"), num(row[h.index("Code Address") - 1]) & 0xFF,
        num(cols.col(row, "Code Address")),
        cols.bits(row, "abilities"), cols.bits(row, "flags"),
        num(cols.col(row, "Rarity (copied)")) & 0xFF, cols.bits(row, "phases"),
        num(cols.col(row, "Expansion (copied)")) & 0xFF, 0, rating)


def decode(cols, record, by_id, by_name, base_row):
    (_secret, name, csvid, _res2, type_bits, family, color_bits, cc0, cc1, cc2, power, toughness,
     extra_bits, unused, code, abilities, flags, rarity, phases, expansion, _zero, rating) = \
        struct.unpack("<B35sHHBBB3BhhBBIIIBBBBi", record)
    h = cols.header
    row = list(base_row) if base_row else ["0"] * len(h)
    name = name.split(b"\0")[0].decode("latin-1")
    if not base_row or not cols.col(row, "Name (will be cut down)").startswith(name):
        row[h.index("Name (will be cut down)")] = name
    if not base_row:
        row[h.index("Sort order")] = "10000"
    full_name = "Dummy" if csvid == DUMMY_ID else by_id[csvid]
    row[h.index("Full Card Name in CSV (must be exactly the same)")] = full_name
    row[h.index(CSV_ID_COLUMN)] = "" if csvid == DUMMY_ID or by_name.get(full_name) == csvid else str(csvid)
    for field, value in (("type", type_bits), ("color", color_bits), ("extra", extra_bits),
                         ("abilities", abilities), ("flags", flags), ("phases", phases)):
        cols.set_bits(row, field, value)
    for column, value in (("Family", family), ("Required COLOR Mana (total)", cc0),
                          ("Required Colorless Mana (total)", cc1), ("cc[2]", cc2),
                          ("Power", power), ("Toughness", toughness), ("Rarity (copied)", rarity),
                          ("Expansion (copied)", expansion)):
        if num(row[h.index(column)]) & (0xFF if column not in ("Power", "Toughness") else 0xFFFF) != \
                value & (0xFF if column not in ("Power", "Toughness") else 0xFFFF):
            row[h.index(column)] = str(value if column in ("Power", "Toughness") or value < 128 or column == "Family"
                                       else value - 256)
    row[h.index("Code Address") - 1] = str(unused)
    if num(cols.col(row, "Code Address")) != code:
        row[h.index("Code Address")] = "0x%x" % code
    old_rating = num(cols.col(row, "Creature Rating Mod"))
    if (old_rating if -2 <= old_rating <= 3 else 0) != rating:
        row[h.index("Creature Rating Mod")] = str(rating)
    return row


def read_ct_all(path):
    with open(path, newline="", encoding="latin-1") as f:
        rows = list(csv.reader(f, delimiter=";"))
    header = rows[0]
    return header, [r + [""] * (len(header) - len(r)) for r in rows[1:] if r]


def main():
    sys.stdout.reconfigure(errors="backslashreplace")
    if len(sys.argv) < 6 or sys.argv[1] not in ("decode", "encode"):
        sys.exit(__doc__)
    if sys.argv[1] == "decode":
        exe_path, manalink, base_path, out_path = sys.argv[2:6]
        with open(exe_path, "rb") as f:
            records = read_table(f.read())
        by_name, by_id = read_manalink(manalink)
        header, base_rows = read_ct_all(base_path)
        if CSV_ID_COLUMN not in header:
            header = header + [CSV_ID_COLUMN]
            base_rows = [r + [""] for r in base_rows]
        cols = Columns(header)
        base = {}
        for row in base_rows:
            base.setdefault(cols.col(row, "Full Card Name in CSV (must be exactly the same)"), row)
        out = []
        for record in records:
            csvid = struct.unpack_from("<H", record, 0x24)[0]
            full_name = "Dummy" if csvid == DUMMY_ID else by_id[csvid]
            out.append(decode(cols, record, by_id, by_name, base.get(full_name) if full_name != "Dummy" else None))
        with open(out_path, "w", newline="", encoding="latin-1") as f:
            writer = csv.writer(f, delimiter=";", lineterminator="\n")
            writer.writerow(header)
            writer.writerows(out)
        print("%s: %d rows" % (out_path, len(out)))
    else:
        ct_path, manalink, exe_path, out_path = sys.argv[2:6]
        header, rows = read_ct_all(ct_path)
        cols = Columns(header)
        by_name, _ = read_manalink(manalink)
        with open(exe_path, "rb") as f:
            exe = bytearray(f.read())
        old_count = len(read_table(exe))
        if len(rows) != old_count:
            sys.exit("%s has %d rows but Magic.exe's table has %d; replace Dummy rows instead of adding"
                     % (ct_path, len(rows), old_count))
        new = bytearray(exe)
        for i, row in enumerate(rows):
            new[TABLE_OFFSET + i * RECORD_SIZE:TABLE_OFFSET + (i + 1) * RECORD_SIZE] = encode(cols, row, by_name)
        if "--check" in sys.argv:
            if new == exe:
                print("%s: table identical (%d records)" % (exe_path, len(rows)))
                return
            diffs = [i for i in range(len(rows)) if new[TABLE_OFFSET + i * RECORD_SIZE:TABLE_OFFSET + (i + 1) * RECORD_SIZE]
                     != exe[TABLE_OFFSET + i * RECORD_SIZE:TABLE_OFFSET + (i + 1) * RECORD_SIZE]]
            for i in diffs[:10]:
                print("record %d (%s) differs" % (i, ascii(rows[i][1])))
            sys.exit("%d records differ" % len(diffs))
        with open(out_path, "wb") as f:
            f.write(new)
        print("%s: wrote %d records" % (out_path, len(rows)))


if __name__ == "__main__":
    main()
