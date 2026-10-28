#!/usr/bin/env python3
"""Start or finish coding a card.

Usage (run from src/; MAGIC_UPDATER defaults to ../magic_updater):
  new_card.py start "Card Name" [cards/some_set.c]
      Give the card a jump-table slot and append a stub function for it to a card file.
      - If Magic.exe already expects the card at an unimplemented slot (see
        "jump_table.py todo"), that slot is used and nothing else changes.
      - Otherwise a slot is appended and the card's "Code Address" in ct_all.csv is
        set to it, as are any other cards with the same name.
      The card file defaults to cards/<newest set the card is in>.c, created if needed.
  new_card.py done "Card Name"
      Set "CODED CARD" to 1 in Manalink.csv, so the card can be put into decks.

Afterwards: make, make verify, make card-data-verify, then install the game data
(make game-data GAME_DIR=...) so Magic.exe and Cards.dat pick up the changes.
"""

import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jump_table  # noqa: E402

UPDATER = os.environ.get("MAGIC_UPDATER", os.path.join("..", "magic_updater"))


def read(path, line_ending):
    with open(path, newline="", encoding="latin-1") as f:
        rows = list(csv.reader(f, delimiter=";"))
    return rows, line_ending


def write(path, rows, line_ending):
    with open(path, "w", newline="", encoding="latin-1") as f:
        csv.writer(f, delimiter=";", lineterminator=line_ending).writerows(rows)


def card_comment(row, header, address):
    col = {name: i for i, name in enumerate(header)}
    name = row[col["Full Name"]]
    rules = row[col["Rules Text"]].replace(name, "~").replace("\\n", "\n")
    type_line = row[col["Type Text"]].replace("\x97", "-")
    if row[col["Power"]] not in ("0", "") or "Creature" in type_line:
        type_line += " %s/%s" % (row[col["Power"]], row[col["Toughness"]])
    lines = ["%s\t%s\t0x%x" % (name, row[col["Cost Text"]], address), type_line] + rules.split("\n")
    return "/* " + "\n * ".join(lines) + " */"


# Set names whose cards/*.c file isn't simply the name in snake_case.
SET_FILES = {
    "Limited Edition Alpha": "unlimited", "Limited Edition Beta": "unlimited", "Unlimited Edition": "unlimited",
    "Revised Edition": "unlimited", "Magic 2010": "m10", "Magic 2011": "m11", "Magic 2012": "m12",
    "Magic 2013": "m13", "Magic 2014": "m14", "Magic 2015": "m15", "Magic Origins": "origins",
    "Odyssey": "odissey", "Judgment": "judgement", "Ravnica: City of Guilds": "ravnica",
    "Urza's Saga": "urza_saga", "Urza's Legacy": "urza_legacy", "Urza's Destiny": "urza_destiny",
    "Portal": "portal_1_2_3k", "Portal Second Age": "portal_1_2_3k", "Portal Three Kingdoms": "portal_1_2_3k",
    "Magic: The Gathering-Conspiracy": "conspiracy", "Magic: The Gathering-Commander": "commander",
    "Unglued": "unglued_unhinged", "Unhinged": "unglued_unhinged",
}


def set_file(row, header):
    """Cards go in their first printing's file, as existing cards do; a new set gets a new file."""
    sets = header[header.index("Promo"):]
    printed = [s for s in sets if row[header.index(s)] not in ("-", "")]
    if not printed:
        sys.exit("%s isn't in any set; pass the card file explicitly" % row[1])
    files = [os.path.join("cards", SET_FILES.get(s, re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")) + ".c")
             for s in printed]
    return next((f for f in files if os.path.exists(f)), files[-1])


def start(name, card_file):
    manalink_path = os.path.join(UPDATER, "Manalink.csv")
    ct_path = os.path.join(UPDATER, "ct_all.csv")
    ml, _ = read(manalink_path, "\r\n")
    header = ml[0]
    row = next((r for r in ml[1:] if r and r[1] == name), None)
    if row is None:
        sys.exit("%r isn't in Manalink.csv" % name)
    ct, _ = read(ct_path, "\n")
    ct_name = ct[0].index("Full Card Name in CSV (must be exactly the same)")
    ct_code = ct[0].index("Code Address")
    ct_rows = [r for r in ct[1:] if r and r[ct_name] == name]
    if not ct_rows:
        sys.exit("%r has no ct_all.csv row; replace a Dummy row with one first" % name)

    asm = jump_table.AsmFile("ManalinkEh.asm")
    slots = {address: (symbol, intended) for address, symbol, intended, _, _ in asm.slots()}
    code = int(ct_rows[0][ct_code], 16) if ct_rows[0][ct_code].startswith("0x") else 0
    function = jump_table.function_name(name)
    if code in slots and slots[code][0] == jump_table.UNIMPLEMENTED:
        function = slots[code][1] or function
        asm.set_slot((code - jump_table.CODE_SECTION_EX) // jump_table.SLOT_SIZE, "_" + function, False)
        address = code
        print("using the slot Magic.exe expects: 0x%x -> %s" % (address, function))
    elif code in slots:
        sys.exit("%r already has code: 0x%x -> %s" % (name, code, slots[code][0]))
    else:
        address = asm.append_slot("_" + function)
        for r in ct_rows:
            r[ct_code] = "0x%x" % address
        write(ct_path, ct, "\n")
        print("appended slot 0x%x -> %s and set it as %s's Code Address in ct_all.csv" % (address, function, name))
    asm.save()

    card_file = card_file or set_file(row, header)
    if not os.path.exists(card_file):
        with open(card_file, "w", encoding="latin-1", newline="\n") as f:
            f.write('// -*- c-basic-offset:2 -*-\n#include "manalink.h"\n\n/***** Functions *****/\n\n/***** Cards *****/\n')
        print("created %s" % card_file)
    with open(card_file, "a", encoding="latin-1", newline="\n") as f:
        f.write("\nint %s(int player, int card, event_t event)\n{\n  %s\n\n  return 0;\n}\n"
                % (function, card_comment(row, header, address).replace("\n", "\n  ")))
    print("appended %s() to %s" % (function, card_file))


def done(name):
    path = os.path.join(UPDATER, "Manalink.csv")
    ml, _ = read(path, "\r\n")
    hits = [r for r in ml[1:] if r and r[1] == name]
    if not hits:
        sys.exit("%r isn't in Manalink.csv" % name)
    for r in hits:
        r[2] = "1"
    write(path, ml, "\r\n")
    print("%s marked CODED CARD" % name)


def main():
    sys.stdout.reconfigure(errors="backslashreplace")
    if len(sys.argv) >= 3 and sys.argv[1] == "start":
        start(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif len(sys.argv) == 3 and sys.argv[1] == "done":
        done(sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
