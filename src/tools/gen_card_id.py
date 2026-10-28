#!/usr/bin/env python3
"""Generate card_id.h from Manalink.csv.

Replacement for the card_id.h half of csv2dat.exe, which is no longer available.

Usage: gen_card_id.py path/to/Manalink.csv path/to/card_id.h

Naming rule (matches the historical csv2dat output):
  - "Full Name" column, Latin-1 encoded, ';'-separated
  - AE ligature becomes E, accents are stripped, apostrophes are dropped
  - everything else that isn't [A-Z0-9] collapses to '_'
  - duplicate names keep their first (lowest) id
  - placeholder rows (empty "Short Name" column) are skipped
"""

import csv
import re
import sys
import unicodedata


def identifier(name):
    name = name.replace("Æ", "E").replace("æ", "e")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.replace("'", "").upper()
    name = re.sub(r"[^A-Z0-9]+", "_", name).strip("_")
    return "CARD_ID_" + name


def read_ids(csv_path):
    with open(csv_path, newline="", encoding="latin-1") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader)
        id_col = header.index("ID")
        name_col = header.index("Full Name")
        short_name_col = header.index("Short Name")
        seen = set()
        entries = []
        for row in reader:
            if len(row) <= short_name_col or not row[id_col].strip().isdigit():
                continue
            if not row[short_name_col].strip():
                continue  # placeholder rows such as "Empty" and "None"
            ident = identifier(row[name_col])
            if ident in seen:
                continue
            seen.add(ident)
            entries.append((ident, int(row[id_col])))
        return entries


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    entries = read_ids(sys.argv[1])
    lines = ["#ifndef CARD_ID_H", "#define CARD_ID_H", "", "typedef enum", "{"]
    for i, (ident, num) in enumerate(entries):
        sep = "," if i < len(entries) - 1 else ""
        lines.append("  %-38s=%5d%s" % (ident, num, sep))
    lines += ["} card_id_t;", "", "#endif", ""]
    with open(sys.argv[2], "w", newline="\n") as f:
        f.write("\n".join(lines))
    print("%s: %d ids" % (sys.argv[2], len(entries)))


if __name__ == "__main__":
    main()
