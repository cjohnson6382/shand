#!/usr/bin/env python3
"""Check that the card data files agree with each other and with the jump table.

Usage: verify_card_data.py MAGIC_UPDATER_DIR GAME_DIR SRC_DIR

  MAGIC_UPDATER_DIR  holds Manalink.csv and ct_all.csv (the sources of truth)
  GAME_DIR           holds the installed Magic.exe, Cards.dat, DBInfo.dat and Rarity.dat
  SRC_DIR            holds card_id.h and ManalinkEh.asm

Errors (exit status 1):
  - card_id.h isn't what gen_card_id.py makes from Manalink.csv
  - Magic.exe points a card at a code address that isn't a jump-table slot
  - a card marked "CODED CARD" in Manalink.csv uses a slot that's still card_unimplemented
Warnings (the installed game is out of date with the csvs; run "make game-data"):
  - Cards.dat / DBInfo.dat / Rarity.dat aren't what csv2dat.py makes from Manalink.csv
  - Magic.exe's card table isn't what ct_all.py makes from ct_all.csv
"""

import io
import os
import struct
import sys
import contextlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import csv2dat  # noqa: E402
import ct_all  # noqa: E402
import gen_card_id  # noqa: E402
import jump_table  # noqa: E402


def main():
    sys.stdout.reconfigure(errors="backslashreplace")
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    updater, game, src = sys.argv[1:]
    manalink_path = os.path.join(updater, "Manalink.csv")
    errors = []
    warnings = []

    # card_id.h
    entries = gen_card_id.read_ids(manalink_path)
    with contextlib.redirect_stdout(io.StringIO()):
        tmp = os.path.join(src, ".card_id.h.verify")
        sys.argv = ["gen_card_id.py", manalink_path, tmp]
        gen_card_id.main()
    with open(tmp, encoding="latin-1") as f:
        generated = f.read()
    os.remove(tmp)
    with open(os.path.join(src, "card_id.h"), encoding="latin-1") as f:
        if f.read() != generated:
            errors.append("card_id.h is out of date with Manalink.csv (run: make card_id.h MANALINK_CSV=...)")

    # .dat files
    rows, rarity_columns = csv2dat.read_csv(manalink_path)
    for name, data in csv2dat.build(rows, rarity_columns).items():
        with open(os.path.join(game, name), "rb") as f:
            if f.read() != data:
                warnings.append("%s is out of date with Manalink.csv" % name)

    # Magic.exe's card table
    with open(os.path.join(game, "Magic.exe"), "rb") as f:
        exe = f.read()
    records = ct_all.read_table(exe)
    header, ct_rows = ct_all.read_ct_all(os.path.join(updater, "ct_all.csv"))
    cols = ct_all.Columns(header)
    by_name, _ = ct_all.read_manalink(manalink_path)
    wanted = [ct_all.encode(cols, row, by_name) for row in ct_rows]
    if wanted != records:
        warnings.append("Magic.exe's card table is out of date with ct_all.csv")

    # Code addresses (as ct_all.csv will set them) against the jump table
    asm = jump_table.AsmFile(os.path.join(src, "ManalinkEh.asm"))
    slots = {address: symbol for address, symbol, _, _, _ in asm.slots()}
    coded = {int(row["ID"]): csv2dat.num(row["CODED CARD"]) for row in rows}
    names = {int(row["ID"]): row["Full Name"] for row in rows}
    unimplemented_coded = []
    for record in wanted:
        csvid, = struct.unpack_from("<H", record, 0x24)
        code, = struct.unpack_from("<I", record, 0x34)
        if csvid == ct_all.DUMMY_ID or not 0x02000000 <= code < 0x03000000:
            continue
        if code not in slots:
            errors.append("%s: code address 0x%x in ct_all.csv isn't a jump-table slot" % (names.get(csvid), code))
        elif slots[code] == jump_table.UNIMPLEMENTED and coded.get(csvid):
            unimplemented_coded.append(names.get(csvid))
    if unimplemented_coded:
        errors.append("%d cards are marked CODED CARD but use card_unimplemented, e.g. %s"
                      % (len(unimplemented_coded), ", ".join(unimplemented_coded[:5])))

    for w in warnings:
        print("warning: " + w)
    for e in errors:
        print("ERROR: " + e)
    print("%d cards, %d ids in card_id.h, %d Magic.exe records, %d jump-table slots (%d unimplemented)"
          % (len(rows), len(entries), len(records), len(slots),
             sum(1 for s in slots.values() if s == jump_table.UNIMPLEMENTED)))
    if errors:
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
