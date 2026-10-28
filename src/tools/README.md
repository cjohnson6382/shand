# Card data tools

These replace the old `csv2dat.exe` and `ct2exe.exe`, which aren't available any more, and add the checks that keep the five places a card lives in agreement.

## Where a card lives

| Source of truth | Generated | Tool |
|---|---|---|
| `magic_updater/Manalink.csv` | `Cards.dat`, `DBInfo.dat`, `Rarity.dat` | `csv2dat.py` (inverse: `dat2csv.py`) |
| `magic_updater/Manalink.csv` | `src/card_id.h` | `gen_card_id.py` |
| `magic_updater/ct_all.csv` | the card table inside `Magic.exe` | `ct_all.py encode` (inverse: `ct_all.py decode`) |
| `src/cards/*.c` | `ManalinkEh.dll` | `make` |
| `src/ManalinkEh.asm` jump table | the addresses in `ct_all.csv` "Code Address" | `jump_table.py` |

Every generator reproduces the shipped files byte for byte from the CSVs, which is how each was validated. The CSVs in `magic_updater/` were themselves recovered from the installed `Cards.dat` and `Magic.exe` with `dat2csv.py` and `ct_all.py decode`. The older CSVs had fallen behind the installed game, so they're kept as `*.before-*-recovery`.

**IDs are positions.** A card's ID is its row in `Manalink.csv`, and decks and saves store IDs. So only ever append rows, and regenerate `card_id.h` whenever rows change. The same goes for jump-table slots: `Magic.exe` stores their addresses, so slots are only appended or re-pointed.

## Coding a card

From `src/`:

```sh
python3 tools/new_card.py start "Card Name"   # gives it a slot, appends a stub to its set's file
# ... write the card function ...
make && make verify
python3 tools/new_card.py done "Card Name"    # sets CODED CARD so it can go in decks
make card-data-verify
make game-data GAME_DIR=..                    # writes Cards.dat etc. and Magic.exe's card table into the install
```

`start` reuses the slot `Magic.exe` already expects when there is one. `jump_table.py todo ManalinkEh.asm` lists those. Otherwise it appends a slot and points the card's `ct_all.csv` row at it.

To make a card share another card's function, use `jump_table.py assign ManalinkEh.asm ADDRESS card_other_function`. Only do this when the rules text is identical, and only after checking that the function doesn't test its own card ID.

## Checks

- `make verify`: every jump-table slot is where `ManalinkEh.asm`'s comments and `ct_all.csv` say.
- `make card-data-verify`: `card_id.h` matches `Manalink.csv`; every code address in `ct_all.csv` is a slot; no card marked `CODED CARD` uses `card_unimplemented`. It also warns when the installed game files are older than the CSVs.
- `make test-decks GAME_DIR=..`: writes `Playdeck/test-*.dck` from `tests/decks/*.txt` for play-testing. See `tests/README.md`.

## Known limits

- **New cards need room in `Magic.exe`'s card table.** It has 16 unused "Dummy" rows and can't grow without patching the exe, so a whole new set can't be added yet.
- **Many cards are uncoded but already point at a real function.** About 300 non-token rows have `CODED CARD` 0 while their code address is a real function. Many are helper pseudo-cards, like "Faerie Conclave Animated", that are uncoded on purpose. Review them case by case rather than flipping the flag.
