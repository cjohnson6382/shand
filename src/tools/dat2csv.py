#!/usr/bin/env python3
"""Rebuild Manalink.csv from Cards.dat, DBInfo.dat and Rarity.dat (the inverse of csv2dat.py).

Usage: dat2csv.py DATDIR BASE.csv OUT.csv

BASE.csv supplies the header, and for every card whose name appears in it, the whole
row (with ID updated to the card's position in Cards.dat) - which keeps the CSV-only
"Sleighted Color" column and formatting such as "800h" vs "2048".  Cards not in BASE.csv
are decoded from the .dat files alone, with "Sleighted Color" derived from the cost.
Rows taken from BASE.csv are then checked against the .dat data, so any drift between
the two is reported rather than silently kept.

Run csv2dat.py OUT.csv DATDIR --check afterwards to confirm the round trip is exact.
"""

import csv
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import csv2dat  # noqa: E402

RARITY_LETTERS = {v: k for k, v in csv2dat.RARITY_CODES.items() if k}
COST_SLEIGHT_BITS = {"B": 2, "U": 4, "G": 8, "R": 16, "W": 32}


def read_dats(datdir):
    with open(os.path.join(datdir, "Cards.dat"), "rb") as f:
        cards = f.read()
    count, text_size = struct.unpack_from("<ii", cards, 0)
    blob_start = 8 + 152 * count
    blob = cards[blob_start:blob_start + text_size]
    pos = blob_start + text_size
    coded_size = struct.unpack_from("<i", cards, pos)[0]
    coded = cards[pos + 4:pos + 4 + coded_size]
    extras_start = pos + 4 + coded_size

    def string(offset):
        return blob[offset:blob.index(b"\0", offset)].decode("latin-1").replace("\n", "\\n")

    with open(os.path.join(datdir, "DBInfo.dat"), "rb") as f:
        dbinfo = f.read()
    with open(os.path.join(datdir, "Rarity.dat"), "rb") as f:
        rarity = f.read()
    num_rarity_columns = struct.unpack_from("<i", rarity, 4)[0]
    bytes_per_card = (3 * num_rarity_columns + 7) >> 3

    for i in range(count):
        f = struct.unpack_from("<IIIIIIHHIIIBBBBBBBBBBHIIIIIIIIBBBBhhihhhhhhiiIIii7HbbBBBB", cards, 8 + 152 * i)
        (cid, full_name, name, expansion, color, card_type, subtype1, subtype2, type_text, _db2, rar,
         req_c, req_b, req_u, _u2b, _u2c, req_g, _u2e, req_r, req_w, _u31, _u32, _flags, _u38, _u3c,
         _artist, num_pics, cost, mod1, mod2, ai_inc_p, ai_inc_t, ai_p, ai_t, ai_base, deps, _sleight,
         vs, for_, cnt, vsl, forl, cntl, abilities, exp_rarity, rules, flavor, power, toughness) = f[:49]
        types = f[49:56]
        mana_src, inflatable, hack_color, _zero, enchant, hack_mode = f[56:62]
        extras = struct.unpack_from("<5I", cards, extras_start + 20 * i)
        db2, num_dba = struct.unpack_from("<ii", dbinfo, 4 + 16 * i)
        dba = struct.unpack_from("<8B", dbinfo, 12 + 16 * i)
        bits = int.from_bytes(rarity[8 + bytes_per_card * i:8 + bytes_per_card * (i + 1)], "little")

        row = {
            "ID": str(cid), "Full Name": string(full_name), "CODED CARD": str((coded[i >> 3] >> (i & 7)) & 1),
            "Short Name": string(name), "Cost Text": string(cost), "Expansion": "%Xh" % expansion,
            "Color": str(color), "Card Type": str(card_type), "Rarity": str(rar),
            "Req Colorless": str(req_c), "Req Black": str(req_b), "Req Blue": str(req_u),
            "Req Green": str(req_g), "Req Red": str(req_r), "Req White": str(req_w),
            "Num Pics": str(num_pics), "Expansions Rarity": "%Xh" % exp_rarity,
            "Power": str(power), "Toughness": str(toughness),
            "Hack Color": str(hack_color), "Hack Mode": str(hack_mode),
            "Enchant Type OWN": str(enchant & 0xF), "Enchant Type OPP": str(enchant >> 4),
            "Subtype": str(subtype1), "Subtype 2": str(subtype2), "Mana Source Colors": str(mana_src),
            "Type Text": string(type_text), "Rules Text": string(rules), "Flavor Text": string(flavor),
            "AI Inc Power": str(ai_inc_p), "AI Inc Toughness": str(ai_inc_t), "AI Power": str(ai_p),
            "AI Toughness": str(ai_t), "AI Base Value": str(ai_base), "Inflatable": str(inflatable),
            "DB Card Type 2": str(db2), "Num of DB Abilities": str(num_dba),
        }
        for n, t in enumerate(types, 1):
            row["New Types %d" % n] = "-1" if t == 0xFFFF else "%Xh" % t
        for col, offset in zip(csv2dat.EXTRA_TEXT_COLUMNS, extras):
            row[col] = string(offset)
        for n, v in enumerate(dba, 1):
            row["DBA%d" % n] = str(v)
        unpack(row, csv2dat.MOD_COLUMNS[:10], mod1, 27, 3)
        unpack(row, csv2dat.MOD_COLUMNS[10:], mod2, 27, 3)
        unpack(row, csv2dat.DEPENDENCY_COLUMNS, deps, 6, 3)
        unpack(row, csv2dat.ABILITY_COLUMNS, abilities, 15, 3)
        for prefix, value in zip(("VS %s", "For %s", "Count as %s", "VS %s Land", "For %s Land", "Count as %s Land"),
                                 (vs, for_, cnt, vsl, forl, cntl)):
            unpack(row, [prefix % c for c in csv2dat.COLOR_ORDER], value, 10, 2)
        rarity_codes = [RARITY_LETTERS.get((bits >> (3 * k)) & 7, "-") for k in range(num_rarity_columns)]
        yield row, rarity_codes


def unpack(row, columns, value, top_bit, width):
    for i, col in enumerate(columns):
        row[col] = str((value >> (top_bit - width * i)) & ((1 << width) - 1))


def main():
    sys.stdout.reconfigure(errors="backslashreplace")
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    datdir, base_path, out_path = sys.argv[1:]
    with open(base_path, newline="", encoding="latin-1") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader)
        base = {}
        for raw in reader:
            if raw and raw[0].strip().isdigit():
                raw += [""] * (len(header) - len(raw))
                base.setdefault(raw[1], dict(zip(header, raw)))
    rarity_columns = header[header.index("(B) Block"):]

    out_rows = []
    reused = decoded = drifted = 0
    for row, rarity_codes in read_dats(datdir):
        if len(rarity_codes) != len(rarity_columns):
            sys.exit("Rarity.dat has %d columns, %s has %d" % (len(rarity_codes), base_path, len(rarity_columns)))
        row.update(zip(rarity_columns, rarity_codes))
        old = base.get(row["Full Name"])
        if old is not None:
            reused += 1
            merged = dict(old, ID=row["ID"])
            diffs = [c for c in row if c != "ID" and normalize(c, row[c]) != normalize(c, merged[c])]
            if diffs:
                drifted += 1
                if drifted <= 10:
                    print("%s: .dat differs from %s in %s; using .dat values" % (row["Full Name"], base_path, diffs[:6]))
                merged.update({c: row[c] for c in diffs})
            out_rows.append(merged)
        else:
            decoded += 1
            row["Sleighted Color"] = str(sum(bit for letter, bit in COST_SLEIGHT_BITS.items()
                                             if "|" + letter in row["Cost Text"]))
            out_rows.append({c: row.get(c, "0") for c in header})

    with open(out_path, "w", newline="", encoding="latin-1") as f:
        writer = csv.writer(f, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(header)
        for row in out_rows:
            writer.writerow([row[c] for c in header])
    print("%s: %d cards (%d from %s, %d of those corrected from .dat; %d decoded from .dat only)"
          % (out_path, len(out_rows), reused, base_path, drifted, decoded))


def normalize(column, value):
    """The value as csv2dat.py would encode it, so "-1" equals "FFFFh" for a 16-bit field."""
    if column in csv2dat.RARITY_CODES or value.strip() in csv2dat.RARITY_CODES:
        return csv2dat.RARITY_CODES.get(value.strip(), value)
    try:
        number = csv2dat.num(value)
    except ValueError:
        return value
    if column.startswith("New Types") or column.startswith("Subtype"):
        return number & 0xFFFF
    return number


if __name__ == "__main__":
    main()
