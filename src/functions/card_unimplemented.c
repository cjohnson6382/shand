#include "manalink.h"

/* Target of jump-table slots that Magic.exe's card table already references but whose card function hasn't been written
 * (yet) - see "jump_table.py todo".  Behaves like Magic.exe's own rfalse_1() at 0x401000, which vanilla cards use, so these
 * cards act as if they had no rules text instead of jumping into whatever follows the table.  Their "CODED CARD" column in
 * Manalink.csv should be 0 so they aren't put into decks. */
int card_unimplemented(int player, int card, event_t event)
{
  return 0;
}
