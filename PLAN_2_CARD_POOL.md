# Plan 2 — Expanding the card pool and supporting newer rules

> **Status (2026-10-27): Phase A done; Phases B and C started; Phase D not started.** Details are in `src/tools/README.md` and `src/tests/README.md`.
>
> **What changed from the plan below:**
> - **The repo's CSVs were older than the installed game.** `Cards.dat` and `Magic.exe` contain 388 more cards (Conspiracy: Take the Crown and Kaladesh), and both shipped `ManalinkEh.dll` and the earlier rebuild used out-of-date IDs for every token and special card. Both CSVs were rebuilt from the installed files, and the rebuilds re-encode to them byte for byte. `card_id.h` is now generated from the rebuilt CSV.
> - **`Magic.exe` already referenced 341 jump-table slots that this source didn't have** (lost upstream work, mostly Kaladesh and Eldritch Moon). Those slots now exist and default to `card_unimplemented`, which behaves like an uncoded card instead of jumping into padding. Phase B fills them in place, with no change to `Magic.exe`.
> - **Revolt and improvise belong to Aether Revolt,** which isn't in the data, so they move to Phase D. The monarch (Conspiracy: Take the Crown) was done instead.
>
> **Phase A:**
> - `csv2dat.py` / `dat2csv.py` and `ct_all.py` (replaces `ct2exe`), all validated byte for byte against the installed files.
> - `gen_card_id.py`, `jump_table.py`, `new_card.py`, `verify_card_data.py`, `make_test_decks.py`.
> - make targets: `card-data-verify`, `game-data`, `test-decks`.
> - Not done: the MTGJSON/Scryfall importer. It's only useful for Phase D, which is also blocked by `Magic.exe`'s card table having just 16 free rows.
>
> **Phase B:** 41 cards in 33 slots: 33 Kaladesh, 7 Conspiracy: Take the Crown, and Stun. 5 more cards got back their earlier implementations; 288 unimplemented cards are now marked uncoded. 310 slots remain.
>
> **Phase C:**
> - Energy: storage, display and saving.
> - Fabricate.
> - Vehicles and crew.
> - The monarch.

**Prerequisite:** Plan 1. You need a reproducible `ManalinkEh.dll` build and the `make verify` jump-table check before adding anything. Every step below changes ID-bearing or address-bearing data, so do it under git.

## Where things stand

- **Card database** (`magic_updater/Manalink.csv`): 16,430 cards, **12,869 coded**. The other **3,561** have a database row but no implementation.
- **Latest supported set:** Eldritch Moon (July 2016). It's the last entry in `src/Expansions.h` (`= 145`).
- **CSV columns for later sets:** columns for *Kaladesh*, *Commander 2016* and *Aether Revolt* exist, but every value in them is `-`.
- **Mechanics:** Kaladesh-era mechanics (vehicles/crew, energy, fabricate, improvise) are essentially absent from the engine. Older mechanics such as morph, transform/double-faced cards, flashback, devotion, bestow, awaken and emblems are well supported.

### How a card exists

A card exists in **5 places**, and they must agree:

| # | Where | What | Tool |
|---|---|---|---|
| 1 | `magic_updater/Manalink.csv` | ID (row index), name, cost, type line, rules text, AI "Mod" ratings, rarity and set columns | `csv2dat.exe` turns it into `Cards.dat`, `DBInfo.dat`, `Rarity.dat` and `src/card_id.h` (**the tool is missing**) |
| 2 | `magic_updater/ct_all.csv` | Engine record: type flags, colors, P/T, a fixed 32-bit keyword bitfield, behavior flags, **Code Address** | `ct2exe.exe` writes it into Magic.exe's card-type table |
| 3 | `src/cards/<set>.c` | `int card_foo(int player, int card, event_t event)`, an event-driven handler | gcc |
| 4 | `src/ManalinkEh.asm` | `extern _card_foo` plus an **appended** `jmp near _card_foo ; <addr>`. That address becomes column 3's Code Address. | `src/build.pl <name>` appends both lines |
| 5 | Assets and config | Art in `Cardart/` or `CardArtNew/`, set enum in `Expansions.h`, `Rarity.csv`, `prices.csv`, `DraftSets`, and the `[Sets]` / `[Enable]` / `[Nosale]` / `[Cards]` sections of `Shandalar.ini` for shops, dungeons and enemy decks | hand edit |

### Rules you can never break

- **IDs are append-only.** A new card always goes at the end of `Manalink.csv`. Inserting or reordering rows renumbers every later card, which breaks `Cards.dat`, saved games and every `.dck` file (decks store IDs).
- **The jump table is append-only.** Each `jmp near` is a fixed 5-byte slot whose address is stored in `ct_all.csv`. Never reorder, delete or insert in the middle. If a card is retired, keep its slot pointing at a stub.
- **New engine state needs a home in Magic.exe's memory.** There is no general persistence, so anything that has to survive a save goes through the existing save/load hook (`patches/patch_save_or_load_supplement.pl`).

## Phase A — Rebuild the pipeline tooling (do this first)

Every later phase depends on it, and the main tool is missing.

1. **Replace `csv2dat.exe`.** Search upstream (the GitHub project history, or the Slightly Magic forum threads linked in `README (2).txt`) for the binary or its source. If you can't find it, reverse-engineer the formats of `Cards.dat`, `DBInfo.dat` and `Rarity.dat`:
   - Run the old csv2dat output against `Program/magic_updater/Manalink.csv` (15,718 rows) to get known-good input/output pairs.
   - Write `tools/csv2dat.py`.
   - The `card_id.h` half is already solved; see Plan 1, Step 2.
2. **Make `ct2exe.exe` reproducible.** It's a 4.6 KB exe with no source. Either find its source, or document and wrap it so it runs headless from the Makefile.
3. **Import card data automatically.** `magic_updater/xml-to-csv.pl` (with `Manalink/CSV.pm`) already merges card data into both CSVs: rules text, types, costs and set columns. It reads an old Gatherer-style XML. Point it at a current source instead:
   - Add an adapter from **MTGJSON** (`AllPrintings.json`) or **Scryfall bulk data** into that XML shape, or port the script.
   - The script already has `--update`, `--abils` and `--tokens` modes. Keep them.
   - It must append new rows only, never reorder (see the rules above).
4. **Script the "add a card" flow.** Write `tools/new_card.py <set> "<Card Name>"`, which:
   - creates a `card_*` stub in `src/cards/<set>.c` with the card's text as the header comment, following the existing comment convention (`/* Name |cost 0xADDR * type * text */`)
   - appends the asm `extern` and `jmp` lines (logic lifted from `build.pl`, minus the `c:\magic2k` copy)
   - writes the resulting address into the `ct_all.csv` Code Address column
   - sets `CODED CARD=1` in `Manalink.csv`
5. **Add consistency checks** under `make verify` from Plan 1:
   - every `CODED CARD=1` row has a `ct_all.csv` row with a non-zero Code Address
   - every `0x0200xxxx` Code Address maps to a jump slot that exists
   - every jump slot's symbol is defined in C
   - every `CARD_ID_*` the code uses is generated from the CSV

   `magic_updater/test.pl` already does part of this (for example, legendary cards must have C code, and planeswalker flag sanity). Fold it in.
6. **Build a regression harness.** There are no automated tests, so make a minimal one:
   - Keep a folder of fixed test decks (`Playdeck/test-*.dck`), one per mechanic family.
   - Write a short manual script: cast each card, check its triggers.
   - Start a known-bugs list.
   - Later, look at whether Magic.exe's AI-vs-AI mode can run headlessly for crash testing.

## Phase B — Code the 3,561 cards that already have database rows

This is the cheapest way to grow the pool and the best way to prove Phase A works end to end:
- No new IDs, no CSV row insertion, and no engine changes for most cards.
- Art and rules text are usually already present.

The uncoded cards are spread across sets: about 120 each in Invasion, Onslaught and Mercadian Masques, about 100 in Odyssey, 91 in Eldritch Moon, and around 50–90 each in the Kamigawa, Lorwyn/Shadowmoor and Time Spiral blocks. 338 belong to no set (tokens, schemes and special cards).

1. Rank the backlog: cards already in `Shandalar.ini` card pools or enemy decks first, then cards that only use existing helpers (`generic_spell`, `generic_aura`, `count_for_gfp_ability`, `generate_token_by_id`, …), then the rest.
2. For each card: run `tools/new_card.py`, implement it, play-test it, commit.
3. Batch commits by set. Fill `src/cards/eldritch_moon.c` first, since it's the freshest code and the most familiar patterns.
4. Rewrite the coding conventions as `CONTRIBUTING.md`: event-handler structure, `target_definition_t` and `test_definition_t`, how the AI reads `EVENT_CHECK_PUMP`, and the `IS_GS_EVENT` / `generic_spell` pattern. Use `galvanic_bombardment` and `ulvenwald_observer` in `cards/eldritch_moon.c` as worked examples.

## Phase C — Engine support for newer rules

Group mechanics by the **kind** of engine change they need, because cost depends on the kind, not on the set. Do the cheap kinds first.

### C1. Keyword-style abilities: helper function only

These fit the existing event model and only need a reusable helper in `src/functions/`, like `prowess` and `menace` today.

> **Note:** *Explore, mentor, riot, adapt, afterlife, surveil, amass, proliferate, enrage, ascend, raid, revolt, exert, embalm, eternalize, afflict, improvise, fabricate, jump-start, spectacle, escape, foretell, boast, ward, toxic, …*

Pattern:
- Add a helper, for example `int explore(int player, int card)` or `void afterlife(int player, int card, event_t event, int n)`.
- Add a `SP_KEYWORD_*` bit if it needs to be displayed, but check what's free first: the `SP_KEYWORD` enum in `defs.h` is a bitmask and some bits are already reused.
- Add an ability icon if wanted (`functions/ability_icons.c`, `patches/patch_icons.pl`).
- Teach the AI through the `Mod …` ratings in the CSV and `EVENT_CHECK_PUMP`-style hooks.

Some of these depend on later items: *ward* needs reliable "becomes the target" events, and *ascend* needs the per-player flag from C2.

### C2. New per-player or global game state

These need storage that survives save and load.
- **Energy** (Kaladesh): `PlayerCounters` in `defs.h` already has `poison_` and `experience_` plus **two unused bytes (`unused1`, `unused2`)** at `0x4EF530`. Put energy in `unused1` and copy the experience-counter accessors, display and save handling (`patches/patch_experience_counters.pl`).
- **City's blessing** (ascend), **the monarch**, **the initiative**, **day/night**, **dungeon progress / venture**, **speed**: per-player or global state. Put small flags in `unused2` as bits. Anything larger goes in a new supplement block through `patch_save_or_load_supplement.pl`.
- Every new state needs: storage, UI (status panel and tooltip), save/load, and AI awareness.

### C3. New permanent subtypes and behaviors built on existing machinery

| Mechanic | What to build on | Work needed |
|---|---|---|
| **Vehicles / crew** | Man-lands (Mishra's Factory, `CARD_ID_ASSEMBLY_WORKER` animation) | "Becomes an artifact creature until end of turn" already exists. Add a `crew N` activated-cost helper (tap creatures with total power ≥ N) and the AI's choice of crew. |
| **Sagas** | Counters and upkeep/main-phase triggers (`functions/counters.c`, `upkeep.c`) | Lore-counter trigger after the draw step, then sacrifice. Needs a rendering tweak in `drawcardlib` for the chapter frame. |
| **Treasure / Food / Clue / Blood / Map tokens** | `cards/tokens.c` (Clue already exists for Shadows over Innistrad) | Add a token row to the CSV plus a small token function each. Easy. |
| **Classes, Cases, Rooms, Role tokens** | Aura and counter machinery | Level/state tracked on the card instance. |
| **New creature/artifact types** (Dinosaur, Vehicle, Saga, …) | `src/subtypes.h` (625 entries; hard-coded ones end at 234) | Add to subtypes and to the type-line parser. Check how subtypes are indexed in Cards.dat before assuming there's room. |

### C4. Card-layout changes: expensive, involve Magic.exe and the renderer

- **Adventure, modal double-faced cards, split cards with aftermath, prototype, disguise/cloak**: the engine has `double_faced_card()` (Innistrad transform) and morph face-down support (`CARD_ID_FACE_DOWN_CREATURE`). Extend these patterns: one CSV row per face, linked as the transform cards are, plus cast-from-alternate-face logic and `drawcardlib` frame support.
- **Battles** are a new *card type*. Card types are a fixed bitmask (`TYPE_*`) in Magic.exe's card-type table and in `ct_all.csv` ("Type: …" columns). Adding one probably means an exe patch. Defer it.
- **Mutate** and **companion** need cross-card merging and outside-the-game zones. Defer these too, or skip them.

### C5. Rules changes that alter how existing cards behave

Review these separately because they can break already-coded cards. Decide case by case whether Shandalar should follow modern rules.
- **Planeswalker uniqueness → legend rule** (2017): check `patches/patch_legend_rule.c` and `gain_control_and_legend_rule.c`.
- **Mulligan** (London mulligan, 2019) in the duel start (`patches/patch_duel_start.pl`).
- **Damage assignment order removed** (2024): check `multiblock.c` and the blocker-ordering UI.
- Wording and Oracle updates can be pulled in by the Phase A importer's `--update` mode. They change text only, so they're safe.

## Phase D — Add new sets, one at a time, in dependency order

For each set:
1. Add `EXPANSION_<SET>` to the end of `src/Expansions.h` (146, 147, …). Fill its column in `Manalink.csv`, or add the column if it doesn't exist.
2. Import the set's cards with the Phase A importer. This appends rows, regenerates `card_id.h` and the `.dat` files, and adds `ct_all.csv` stubs.
3. Create `src/cards/<set>.c` and implement the cards. Ship the set even if it's only partly coded: uncoded cards stay `CODED CARD=0` and won't appear in play.
4. Add art, `Rarity.csv`/`prices.csv` entries, the set icon and watermark (`watermarks.csv`, `drawcardlib/config.c`) and `DraftSets`.
5. Shandalar integration: `[Sets]` / `[Enable]` / `[Nosale]` in `Shandalar.ini`, optional new enemy decks in `Decks*/`, and dungeon treasure.
6. Run `make verify`, the regression decks and a Shandalar playthrough smoke test, then commit.

Suggested order, from least to most new engine work:

| Order | Set(s) | Why it's here |
|---|---|---|
| 1 | **A core set with mostly evergreen keywords** (Core Set 2019 or 2020) | Pilot for the whole Phase A/D pipeline with almost no engine work |
| 2 | **Kaladesh, Aether Revolt** | The CSV columns already exist. Energy, vehicles, fabricate, improvise and revolt cover C1, C2 and C3 in one block. |
| 3 | **Amonkhet, Hour of Devastation** | Embalm/eternalize (graveyard token copies), exert, afflict, aftermath (needs the C4 split-card work, so do it last within the block) |
| 4 | **Ixalan, Rivals of Ixalan** | Explore, enrage, treasure, ascend (the C2 flag), transforming legendary artifacts (existing DFC support) |
| 5 | **Dominaria** | Sagas, historic, the legend rule for planeswalkers (C5) |
| 6 | **Guilds of Ravnica, Ravnica Allegiance, War of the Spark** | Many C1 keywords. Amass and static planeswalker abilities. |
| 7 | **Throne of Eldraine, Theros Beyond Death, later sets** | Adventures (C4), food, escape. Later sets bring MDFCs, dungeons, day/night and battles, each blocked on its C2/C4 work. |

## Risks

- **The missing `csv2dat.exe` is the critical path.** Until Phase A step 1 is done, you can't add new IDs safely. You can still do Phase B, which needs no new IDs.
- **Magic.exe-side limits are unknown.** Card count, subtype count and type-bitfield width are set by a closed binary. Probe each one with a throwaway build before committing to a set. Watch for 16-bit fields: some structures and IIDs may cap at 16,384 (see `patch_iid16384.pl`).
- **AI quality.** Most AI behavior for a card comes from the CSV "Mod/AI" ratings plus `EVENT_CHECK_PUMP`-style hints. New mechanics need explicit AI decisions (crew, energy spending, explore choices), or the AI will hold cards it can't use.
- **Save compatibility.** New per-player state and new IDs can invalidate old `.SVE` files. Bump a version marker and handle it in the save/load supplement.
