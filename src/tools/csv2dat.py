#!/usr/bin/env python3
"""Build Cards.dat, DBInfo.dat and Rarity.dat from Manalink.csv.

Replacement for csv2dat.exe, which is no longer available.

Usage:
  csv2dat.py Manalink.csv OUTDIR          write OUTDIR/{Cards,DBInfo,Rarity}.dat
  csv2dat.py Manalink.csv OUTDIR --check  compare against the files already in OUTDIR instead

File formats (all little-endian; see read_db_guts() in deck/deckdll.cpp):
  Cards.dat   int32 count; int32 text_size; card_ptr_t[count] (152 bytes each, string
              pointers stored as offsets into the text blob); char text[text_size];
              int32 coded_size; coded bitmap (bit id%8 of byte id/8 = "CODED CARD");
              then for each card, int32 offsets of its 5 extra strings (damage text,
              effect title, effect text, legacy title, legacy text).
              The text blob holds 11 NUL-terminated strings per card, in order: full
              name, short name, cost, type, rules, flavor, then the 5 extra strings.
  DBInfo.dat  int32 count; per card: int32 db_card_type_2, int32 num_db_abilities,
              uint8 DBA1..DBA8.
  Rarity.dat  int32 count; int32 num_columns; per card, a little-endian bitfield of
              3 bits per column from "(B) Block" to the last set column, coded
              -=0 C=1 U=2 R=3 M=4 L=5 S=6.
"""

import csv
import os
import struct
import sys

RARITY_CODES = {"-": 0, "": 0, "C": 1, "U": 2, "R": 3, "M": 4, "L": 5, "S": 6}

# 3-bit AI modifier columns: ten per word, the first at bits 27-29, each next one 3 bits lower.
MOD_COLUMNS = ["Mod Direct Fire", "Mod Land Destructor", "Mod Draw Cards", "Mod Discard",
               "Mod Gain Life", "Mod Damage Prevention", "Mod Recycler", "Mod Counter Spell",
               "Mod Control", "Mod Combat Manipulator", "Mod Enchantments", "Mod Artifacts",
               "Mod Creature", "Mod Creature Generator", "Mod Damage Opponent",
               "Mod Library Manipulation", "Mod Dummy 1", "Mod Dummy 2", "Mod Dummy 3", "Mod Dummy 4"]
# 2-bit per-color AI columns, black at bits 10-11 down to white at bits 2-3.
COLOR_ORDER = ["Black", "Blue", "Green", "Red", "White"]
# 3-bit AI ability and dependency columns, the first at the highest bits.
ABILITY_COLUMNS = ["AI Flying", "AI Banding", "AI Trample", "AI First Strike", "AI Wall", "AI Landhome"]
DEPENDENCY_COLUMNS = ["Dependent Artifact", "Dependent Creature", "Dependent Wall"]

EXTRA_TEXT_COLUMNS = ["Damage Text", "Effect Title Text", "Effect Text", "Legacy Title Text", "Legacy Text"]


def num(text):
    text = text.strip()
    if text in ("", "-"):
        return 0
    if text[-1] in "hH":
        return int(text[:-1], 16)
    return int(text)


def text(value):
    return value.replace("\\n", "\n").encode("latin-1")


def pack_columns(row, columns, top_bit, width):
    value = 0
    for i, col in enumerate(columns):
        value |= (num(row[col]) & ((1 << width) - 1)) << (top_bit - width * i)
    return value


def read_csv(csv_path):
    with open(csv_path, newline="", encoding="latin-1") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader)
        rows = []
        for raw in reader:
            if raw and raw[0].strip().isdigit():
                raw += [""] * (len(header) - len(raw))
                rows.append(dict(zip(header, raw)))
    for i, row in enumerate(rows):
        if int(row["ID"]) != i:
            sys.exit("Manalink.csv: row %d has ID %s; IDs must be consecutive from 0" % (i, row["ID"]))
    rarity_columns = header[header.index("(B) Block"):]
    return rows, rarity_columns


def build(rows, rarity_columns):
    blob = bytearray()
    records = bytearray()
    extras = bytearray()

    def add_string(s):
        offset = len(blob)
        blob.extend(text(s) + b"\0")
        return offset

    for row in rows:
        full_name = add_string(row["Full Name"])
        name = add_string(row["Short Name"])
        cost = add_string(row["Cost Text"])
        type_text = add_string(row["Type Text"])
        rules = add_string(row["Rules Text"])
        flavor = add_string(row["Flavor Text"])
        for col in EXTRA_TEXT_COLUMNS:
            extras += struct.pack("<I", add_string(row[col]))

        color_fields = []
        for prefix in ("VS %s", "For %s", "Count as %s", "VS %s Land", "For %s Land", "Count as %s Land"):
            color_fields.append(pack_columns(row, [prefix % c for c in COLOR_ORDER], 10, 2))
        mods = pack_columns(row, MOD_COLUMNS[:10], 27, 3), pack_columns(row, MOD_COLUMNS[10:], 27, 3)
        types = [num(row["New Types %d" % i]) & 0xFFFF for i in range(1, 8)]

        records += struct.pack(
            "<IIIIIIHHIIIBBBBBBBBBBHIIIIIIIIBBBBhhihhhhhhiiIIii7HbbBBBB",
            int(row["ID"]), full_name, name, num(row["Expansion"]), num(row["Color"]),
            num(row["Card Type"]), num(row["Subtype"]) & 0xFFFF, num(row["Subtype 2"]) & 0xFFFF,
            type_text, 0, num(row["Rarity"]),
            num(row["Req Colorless"]), num(row["Req Black"]), num(row["Req Blue"]), 0, 0,
            num(row["Req Green"]), 0, num(row["Req Red"]), num(row["Req White"]), 0, 0,
            0, 0, 0,                                    # flags, unused0x38, unused0x3c
            0, num(row["Num Pics"]), cost,              # artist, num_pics, mana_cost_text
            mods[0], mods[1],
            num(row["AI Inc Power"]), num(row["AI Inc Toughness"]), num(row["AI Power"]),
            num(row["AI Toughness"]), num(row["AI Base Value"]),
            pack_columns(row, DEPENDENCY_COLUMNS, 6, 3),
            0,                                          # sleight_color
            *color_fields,
            pack_columns(row, ABILITY_COLUMNS, 15, 3),
            num(row["Expansions Rarity"]), rules, flavor,
            num(row["Power"]), num(row["Toughness"]), *types,
            num(row["Mana Source Colors"]), num(row["Inflatable"]), num(row["Hack Color"]), 0,
            num(row["Enchant Type OWN"]) | (num(row["Enchant Type OPP"]) << 4), num(row["Hack Mode"]))

    count = len(rows)
    coded = bytearray((count + 7) >> 3)
    for i, row in enumerate(rows):
        if num(row["CODED CARD"]):
            coded[i >> 3] |= 1 << (i & 7)

    cards = (struct.pack("<ii", count, len(blob)) + records + blob
             + struct.pack("<i", len(coded)) + coded + extras)

    dbinfo = bytearray(struct.pack("<i", count))
    for row in rows:
        dbinfo += struct.pack("<ii8B", num(row["DB Card Type 2"]), num(row["Num of DB Abilities"]),
                              *[num(row["DBA%d" % i]) for i in range(1, 9)])

    bytes_per_card = (3 * len(rarity_columns) + 7) >> 3
    rarity = bytearray(struct.pack("<ii", count, len(rarity_columns)))
    for row in rows:
        bits = 0
        for i, col in enumerate(rarity_columns):
            code = row[col].strip()
            if code not in RARITY_CODES:
                sys.exit("%s: unknown rarity %r in column %r" % (row["Full Name"], code, col))
            bits |= RARITY_CODES[code] << (3 * i)
        rarity += bits.to_bytes(bytes_per_card, "little")

    return {"Cards.dat": bytes(cards), "DBInfo.dat": bytes(dbinfo), "Rarity.dat": bytes(rarity)}


def check(outputs, outdir):
    ok = True
    for name, data in outputs.items():
        path = os.path.join(outdir, name)
        with open(path, "rb") as f:
            existing = f.read()
        if existing == data:
            print("%s: identical (%d bytes)" % (path, len(data)))
            continue
        ok = False
        first = next((i for i in range(min(len(data), len(existing))) if data[i] != existing[i]),
                     min(len(data), len(existing)))
        print("%s: DIFFERS (generated %d bytes, existing %d bytes, first difference at offset %d)"
              % (path, len(data), len(existing), first))
    return ok


def main():
    sys.stdout.reconfigure(errors="backslashreplace")
    args = [a for a in sys.argv[1:] if a != "--check"]
    if len(args) != 2:
        sys.exit(__doc__)
    rows, rarity_columns = read_csv(args[0])
    outputs = build(rows, rarity_columns)
    if "--check" in sys.argv:
        sys.exit(0 if check(outputs, args[1]) else 1)
    for name, data in outputs.items():
        with open(os.path.join(args[1], name), "wb") as f:
            f.write(data)
        print("%s: %d bytes" % (os.path.join(args[1], name), len(data)))
    print("%d cards" % len(rows))


if __name__ == "__main__":
    main()
