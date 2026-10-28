# -*- makefile -*-

include Makefile-common

# Flags
LFLAGS := $(LFLAGS) -Wl,-Tmanalink.lds --entry _DllEntry

# Input files
SUBDIRS = cards functions
# Legacy color-sorted card files, written against an older API.  Every card they
# define is either reimplemented in a per-set file or not in the jump table.
LEGACY_CFILES = $(patsubst %,cards/%.c,artifacts artifact_creatures		\
	black_creatures black_enchantments black_oneshot			\
	blue_creatures blue_enchantments blue_oneshot				\
	green_creatures green_enchantments green_oneshot			\
	red_creatures red_enchantments red_oneshot				\
	white_creatures white_enchantments white_oneshot			\
	jatill lands recoded_cards)
# Superseded by the static inline affect_me() in manalink.h.
LEGACY_CFILES += functions/affect_me.c
# Superseded by windows.c; get_ability_image() has no jump-table slot.
LEGACY_CFILES += functions/ability_icons.c
CFILES := $(filter-out $(LEGACY_CFILES),$(CFILES))
# Superseded by the C versions in functions/deck.c and functions/display_error_message.asm.
LEGACY_AFILES = functions/get_card_instance.asm functions/in_play.asm
AFILES := $(filter-out $(LEGACY_AFILES),$(AFILES)) ManalinkEh.asm
LIBS = gdi32 msimg32
LOCAL_LIBS = capturestackbacktrace Drawcardlib

# Output files
OUTPUT = ManalinkEh.dll

include Makefile-targets

$(OUTPUT): manalink.lds

PYTHON ?= python3

# card_id.h is committed, since Manalink.csv isn't.  Regenerate it after adding cards with
#   make card_id.h MANALINK_CSV=../magic_updater/Manalink.csv
ifdef MANALINK_CSV
card_id.h: $(MANALINK_CSV) tools/gen_card_id.py
	$(PYTHON) tools/gen_card_id.py $< $@
endif

# Checks that every jump-table slot is where Magic.exe and ct_all.csv expect it.
CT_ALL_CSV ?= $(wildcard ../magic_updater/ct_all.csv)
verify: $(OUTPUT)
	OBJDUMP=$(OBJCOPY:objcopy=objdump) $(PYTHON) tools/verify_jump_table.py ManalinkEh.asm $(OUTPUT) $(CT_ALL_CSV)

.PHONY: verify

# The card data pipeline (see tools/*.py).  Manalink.csv and ct_all.csv are the sources of truth;
# Cards.dat, DBInfo.dat, Rarity.dat and Magic.exe's card table are generated from them.
MAGIC_UPDATER ?= ../magic_updater

# Checks the csvs, card_id.h and the jump table agree, and whether GAME_DIR's files are up to date.
card-data-verify:
	$(PYTHON) tools/verify_card_data.py $(MAGIC_UPDATER) $(or $(GAME_DIR),..) .

# Writes the generated files into an install, e.g.  make game-data GAME_DIR=..
game-data:
	$(if $(GAME_DIR),,$(error set GAME_DIR to the game folder to update))
	$(PYTHON) tools/csv2dat.py $(MAGIC_UPDATER)/Manalink.csv $(GAME_DIR)
	$(PYTHON) tools/ct_all.py encode $(MAGIC_UPDATER)/ct_all.csv $(MAGIC_UPDATER)/Manalink.csv \
		$(GAME_DIR)/Magic.exe $(GAME_DIR)/Magic.exe

# Writes Playdeck/test-*.dck from tests/decks/*.txt for play-testing (see tests/README.md).
test-decks:
	$(if $(GAME_DIR),,$(error set GAME_DIR to the game folder))
	$(PYTHON) tools/make_test_decks.py $(MAGIC_UPDATER)/Manalink.csv tests/decks $(GAME_DIR)/Playdeck

.PHONY: card-data-verify game-data test-decks

clean::
	-$(RM) ManalinkEh.ao